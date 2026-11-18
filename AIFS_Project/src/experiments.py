"""
experiments.py — Experiment orchestration for Reliability-Aware EV Charging.

Orchestrates all required experiment groups (A through G), saves raw and
processed results, and logs execution details.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data import load_dataset, create_splits
from src.preprocessing import clean_data, generate_quality_report
from src.forecasting import fit_forecaster, evaluate_forecast
from src.uncertainty import (
    ConformalPredictor,
    compute_horizon_reliability,
    evaluate_intervals,
)
from src.scheduler import solve_schedule
from src.simulation import simulate_day
from src.metrics import calculate_metrics, aggregate_metrics
from src.statistics import compare_controllers, paired_t_test, bootstrap_ci, cohens_d
from src.reporting import (
    save_json_results,
    save_csv_table,
    results_to_dataframe,
    aggregate_summary_table,
    generate_latex_table,
)
from src.plotting import (
    plot_pv_forecast_example,
    plot_forecast_error_distribution,
    plot_interval_coverage,
    plot_controller_comparison_cost,
    plot_solar_contribution,
    plot_peak_and_deadline,
    plot_stress_test,
    plot_threshold_sensitivity,
    plot_system_architecture,
    plot_bidirectional_scenarios,
    plot_real_vs_synthetic,
)

logger = logging.getLogger(__name__)


def setup_logging(results_dir: str):
    """Setup file and console logging."""
    log_dir = Path(results_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "experiment.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def extract_day_data(
    dataset: dict,
    date_val: Any,
    config: dict,
) -> dict:
    """Extract 24-hour slices for PV, load, and tariff for a specific calendar date.
    Builds the EV availability mask and returns a complete day payload.
    """
    dt = config.get("data", {}).get("time_resolution_hours", 1.0)
    ev_cfg = config.get("ev", {})

    pv_df = dataset["pv"]
    load_df = dataset["load"]
    tariff_df = dataset["tariff"]

    day_mask_pv = pv_df.index.date == date_val
    day_pv = pv_df.loc[day_mask_pv, "pv_generation_kw"].values

    day_mask_load = load_df.index.date == date_val
    day_load = load_df.loc[day_mask_load, "load_kw"].values

    day_mask_tariff = tariff_df.index.date == date_val
    day_tariff = tariff_df.loc[day_mask_tariff, "price_per_kwh"].values

    n_intervals = len(day_pv)
    if n_intervals != 24:
        raise ValueError(f"Expected 24 intervals for {date_val}, got {n_intervals}")

    # Availability mask
    # Arrival at arrival_hour (e.g. 17:00), departure at departure_hour (e.g. 07:00 next day)
    arr = ev_cfg.get("arrival_hour", 17)
    dep = ev_cfg.get("departure_hour", 7)

    availability = np.zeros(n_intervals, dtype=float)
    if arr > dep:
        # Overnight window in single day: e.g. 17-23 and 0-6
        availability[arr:] = 1.0
        availability[:dep] = 1.0
    else:
        availability[arr:dep] = 1.0

    ev_params = {
        "battery_capacity_kwh": ev_cfg.get("battery_capacity_kwh", 40.0),
        "initial_soc_kwh": ev_cfg.get("initial_soc_kwh", 10.0),
        "required_energy_kwh": ev_cfg.get("required_energy_kwh", 20.0),
        "max_charger_power_kw": ev_cfg.get("max_charger_power_kw", 7.0),
        "charging_efficiency": ev_cfg.get("charging_efficiency", 0.90),
        "availability": availability,
    }

    return {
        "date": str(date_val),
        "pv_actual": day_pv,
        "load": day_load,
        "tariff": day_tariff,
        "ev_params": ev_params,
    }


def add_synthetic_error(
    pv_forecast: np.ndarray,
    scenario_name: str,
    scenario_cfg: dict,
    pv_capacity: float,
    seed: int,
) -> np.ndarray:
    """Create controlled perturbation of PV forecast.
    Applies zero nighttime and physical capacity clipping.
    """
    rng = np.random.RandomState(seed)
    noise_frac = scenario_cfg.get("noise_std_fraction", 0.15)
    temporal_corr = scenario_cfg.get("temporal_correlation", 0.0)
    regime_bias = scenario_cfg.get("regime_bias_kw", 0.0)
    regime_prob = scenario_cfg.get("regime_prob", 0.0)

    n = len(pv_forecast)
    sigma = noise_frac * pv_capacity

    # Base noise
    white_noise = rng.normal(0, sigma, size=n)
    if temporal_corr > 0.0:
        noise = np.zeros(n)
        noise[0] = white_noise[0]
        for t in range(1, n):
            noise[t] = temporal_corr * noise[t - 1] + np.sqrt(1 - temporal_corr**2) * white_noise[t]
    else:
        noise = white_noise

    # Regime bias (e.g. unexpected overcast cloud bank)
    if regime_bias > 0.0 and rng.rand() < regime_prob:
        noise -= regime_bias

    perturbed = pv_forecast + noise
    # Maintain physical constraints:
    # 1. Zero at night when baseline forecast is zero
    perturbed = np.where(pv_forecast <= 1e-4, 0.0, perturbed)
    # 2. Non-negative
    perturbed = np.clip(perturbed, 0.0, pv_capacity)
    return perturbed


def run_experiments(config: dict) -> dict:
    """Run all experimental evaluations."""
    results_dir = config.get("output", {}).get("results_dir", "results")
    setup_logging(results_dir)
    logger.info("Starting complete reproducible experiment suite...")

    raw_dir = Path(results_dir) / "raw"
    proc_dir = Path(results_dir) / "processed"
    tables_dir = Path(results_dir) / "tables"
    fig_dir = Path(results_dir) / "figures"

    for d in [raw_dir, proc_dir, tables_dir, fig_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Load Data and Splits
    dataset = load_dataset(config)
    splits = create_splits(dataset, config)
    logger.info(f"Loaded dataset: {dataset['metadata']['n_hours']} hours.")
    logger.info(f"Splits: Train {splits['train']}, Cal {splits['calibration']}, Val {splits['validation']}, Test {splits['test']}")

    pv_df = dataset["pv"]
    pv_capacity = config.get("data", {}).get("pv_capacity_kw", 5.0)

    # Date partitions
    train_dates = sorted(set(pv_df.loc[splits["train"]["start"] : splits["train"]["end"]].index.date))
    cal_dates = sorted(set(pv_df.loc[splits["calibration"]["start"] : splits["calibration"]["end"]].index.date))
    val_dates = sorted(set(pv_df.loc[splits["validation"]["start"] : splits["validation"]["end"]].index.date))
    test_dates = sorted(set(pv_df.loc[splits["test"]["start"] : splits["test"]["end"]].index.date))

    train_df = pv_df.loc[splits["train"]["start"] : splits["train"]["end"]]
    cal_df = pv_df.loc[splits["calibration"]["start"] : splits["calibration"]["end"]]
    val_df = pv_df.loc[splits["validation"]["start"] : splits["validation"]["end"]]
    test_df = pv_df.loc[splits["test"]["start"] : splits["test"]["end"]]

    # 2. Experiment A: Train Forecasters & Calibrate Conformal Predictor
    logger.info("Experiment A: Fitting persistence and ML forecasters...")
    f_persistence = fit_forecaster(train_df, {"type": "persistence", "persistence_lag_days": 1})
    f_ml = fit_forecaster(train_df, {"type": "ml", **config.get("forecasting", {})})

    # Evaluate on Validation
    val_pred_persist = f_persistence.predict(val_df.index, pv_df)
    val_pred_ml = f_ml.predict(val_df.index, pv_df)
    val_actual = val_df["pv_generation_kw"].values

    metrics_persist = evaluate_forecast(val_actual, val_pred_persist)
    metrics_ml = evaluate_forecast(val_actual, val_pred_ml)

    logger.info(f"Persistence Validation MAE: {metrics_persist['mae']:.4f}, RMSE: {metrics_persist['rmse']:.4f}")
    logger.info(f"ML Forecaster Validation MAE: {metrics_ml['mae']:.4f}, RMSE: {metrics_ml['rmse']:.4f}")

    # Calibrate Conformal Predictor on Calibration Set using chosen ML model
    logger.info("Calibrating split conformal prediction on calibration split...")
    cal_pred_ml = f_ml.predict(cal_df.index, pv_df)
    cal_actual = cal_df["pv_generation_kw"].values

    conformal = ConformalPredictor(nominal_coverage=config.get("uncertainty", {}).get("nominal_coverage", 0.90))
    conformal.calibrate(cal_actual, cal_pred_ml)
    q_alpha = conformal.q_alpha_
    logger.info(f"Conformal calibration completed: q_alpha = {q_alpha:.4f} kW")

    # Evaluate intervals on validation split
    val_low, val_high = conformal.predict_interval(val_pred_ml, pv_capacity=pv_capacity)
    val_interval_metrics = evaluate_intervals(val_actual, val_low, val_high)
    logger.info(f"Validation Interval Coverage: {val_interval_metrics['coverage']:.4f}, Mean Width: {val_interval_metrics['mean_width']:.4f} kW")

    exp_a_results = {
        "persistence": metrics_persist,
        "ml": metrics_ml,
        "q_alpha": q_alpha,
        "validation_intervals": val_interval_metrics,
    }
    save_json_results(exp_a_results, str(proc_dir / "exp_a_forecasting.json"))

    # 3. Validation Threshold Selection
    logger.info("Selecting reliability threshold tau on validation split...")
    candidate_quantiles = config.get("threshold_selection", {}).get("candidate_quantiles", [0.1, 0.3, 0.5, 0.7, 0.9])

    # Compute validation daily reliabilities
    val_day_reliabilities = []
    val_days_data = []
    for d in val_dates:
        d_data = extract_day_data(dataset, d, config)
        d_idx = pv_df.loc[pv_df.index.date == d].index
        d_forecast = f_ml.predict(d_idx, pv_df)
        d_low, d_high = conformal.predict_interval(d_forecast, pv_capacity=pv_capacity)
        d_widths = d_high - d_low
        rel = compute_horizon_reliability(d_widths, scale=pv_capacity)
        d_data["pv_forecast"] = d_forecast
        d_data["reliability"] = rel
        val_day_reliabilities.append(rel)
        val_days_data.append(d_data)

    val_day_reliabilities = np.array(val_day_reliabilities)
    candidate_thresholds = [float(np.quantile(val_day_reliabilities, q)) for q in candidate_quantiles]

    best_tau = None
    best_val_cost = float("inf")
    tau_search_results = []

    for tau in candidate_thresholds:
        tau_costs = []
        tau_deadlines = []
        tau_fallbacks = []

        for d_data in val_days_data:
            sched_inputs = {
                "pv_forecast": d_data["pv_forecast"],
                "load": d_data["load"],
                "tariff": d_data["tariff"],
                "ev_params": d_data["ev_params"],
                "actual_pv": d_data["pv_actual"],
                "config": {"dt": 1.0, "export_rate": config.get("tariff", {}).get("export_rate", 0.04)},
            }
            sched = solve_schedule(
                sched_inputs,
                method="reliability_aware",
                config={"dt": 1.0},
                reliability_score=d_data["reliability"],
                threshold=tau,
            )
            sim = simulate_day(
                schedule=sched,
                actual_data={"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": d_data["tariff"]},
                ev_params=d_data["ev_params"],
                config={"dt": 1.0, "export_rate": config.get("tariff", {}).get("export_rate", 0.04)},
            )
            tau_costs.append(sim["total_cost"])
            tau_deadlines.append(sim["deadline_met"])
            tau_fallbacks.append(sched.get("used_fallback", False))

        mean_cost = float(np.mean(tau_costs))
        deadline_rate = float(np.mean(tau_deadlines))
        fallback_rate = float(np.mean(tau_fallbacks))

        tau_search_results.append({
            "threshold": tau,
            "mean_cost": mean_cost,
            "deadline_success_rate": deadline_rate,
            "fallback_rate": fallback_rate,
        })

        # Selection rule: zero deadline miss tolerance, then lowest cost
        if deadline_rate >= 1.0 and mean_cost < best_val_cost:
            best_val_cost = mean_cost
            best_tau = tau

    if best_tau is None:
        best_tau = float(np.median(candidate_thresholds))
        logger.warning(f"No threshold met 100% deadline rate on validation. Defaulting to median: {best_tau:.4f}")
    else:
        logger.info(f"Selected optimal threshold tau = {best_tau:.4f} (Validation Mean Cost: ${best_val_cost:.4f})")

    save_json_results({
        "selected_tau": best_tau,
        "grid_search": tau_search_results,
    }, str(proc_dir / "threshold_selection.json"))

    # 4. Prepare Test Days Data
    logger.info("Preparing frozen test split days...")
    test_days_data = []
    for d in test_dates:
        d_data = extract_day_data(dataset, d, config)
        d_idx = pv_df.loc[pv_df.index.date == d].index
        d_forecast = f_ml.predict(d_idx, pv_df)
        d_low, d_high = conformal.predict_interval(d_forecast, pv_capacity=pv_capacity)
        d_widths = d_high - d_low
        rel = compute_horizon_reliability(d_widths, scale=pv_capacity)
        d_data["pv_forecast"] = d_forecast
        d_data["pv_forecast_low"] = d_low
        d_data["pv_forecast_high"] = d_high
        d_data["reliability"] = rel
        test_days_data.append(d_data)

    # 5. Experiment B: Main Controller Comparison on Test Split
    logger.info("Experiment B: Evaluating Controllers B1 through B6 on test days...")
    controllers = [
        "fixed",
        "cheapest_hours",
        "forecast_driven",
        "reliability_aware",
        "conservative_fallback",
        "oracle",
    ]

    exp_b_results = {ctrl: [] for ctrl in controllers}

    for d_data in test_days_data:
        sched_inputs = {
            "pv_forecast": d_data["pv_forecast"],
            "load": d_data["load"],
            "tariff": d_data["tariff"],
            "ev_params": d_data["ev_params"],
            "actual_pv": d_data["pv_actual"],
            "config": {"dt": 1.0, "export_rate": config.get("tariff", {}).get("export_rate", 0.04)},
        }
        actual_sim_data = {
            "pv_actual": d_data["pv_actual"],
            "load": d_data["load"],
            "tariff": d_data["tariff"],
        }
        sim_cfg = {"dt": 1.0, "export_rate": config.get("tariff", {}).get("export_rate", 0.04)}

        for ctrl in controllers:
            kwargs = {}
            if ctrl == "reliability_aware":
                kwargs = {
                    "reliability_score": d_data["reliability"],
                    "threshold": best_tau,
                }
            sched = solve_schedule(sched_inputs, method=ctrl, config={"dt": 1.0}, **kwargs)
            sim = simulate_day(sched, actual_sim_data, d_data["ev_params"], sim_cfg)
            sim["date"] = d_data["date"]
            sim["method"] = ctrl
            if "used_fallback" in sched:
                sim["used_fallback"] = sched["used_fallback"]
            exp_b_results[ctrl].append(sim)

    # Save raw outputs
    save_json_results(exp_b_results, str(raw_dir / "exp_b_main_controllers.json"))

    # Convert to DataFrames and aggregate
    exp_b_df = results_to_dataframe(exp_b_results, config)
    save_csv_table(exp_b_df, str(proc_dir / "exp_b_daily_results.csv"), index=False)

    summary_b = aggregate_summary_table(exp_b_df)
    save_csv_table(summary_b, str(tables_dir / "table5_main_controller_comparison.csv"))
    logger.info("Experiment B completed. Summary:\n" + str(summary_b))

    # Statistical Comparison against B3 (forecast_driven) and B2 (cheapest_hours)
    logger.info("Computing paired statistical tests...")
    cost_series = {ctrl: [r["total_cost"] for r in exp_b_results[ctrl]] for ctrl in controllers}
    stat_vs_b3 = compare_controllers(cost_series, baseline_name="forecast_driven", config=config)
    save_csv_table(stat_vs_b3, str(tables_dir / "table6_statistical_vs_forecast_driven.csv"), index=False)

    stat_vs_b2 = compare_controllers(cost_series, baseline_name="cheapest_hours", config=config)
    save_csv_table(stat_vs_b2, str(tables_dir / "table6b_statistical_vs_cheapest_hours.csv"), index=False)

    # 6. Experiment C: Forecast-Error Stress Testing
    logger.info("Experiment C: Stress testing across synthetic forecast error scenarios...")
    error_scenarios = config.get("synthetic_errors", {}).get("scenarios", {})
    exp_c_results = {}

    for sc_name, sc_cfg in error_scenarios.items():
        exp_c_results[sc_name] = {}
        for ctrl in ["cheapest_hours", "forecast_driven", "reliability_aware", "conservative_fallback"]:
            sc_ctrl_costs = []
            for seed in config.get("synthetic_errors", {}).get("random_seeds", [42]):
                for d_data in test_days_data:
                    perturbed_pv = add_synthetic_error(
                        d_data["pv_forecast"], sc_name, sc_cfg, pv_capacity, seed
                    )
                    sched_inputs = {
                        "pv_forecast": perturbed_pv,
                        "load": d_data["load"],
                        "tariff": d_data["tariff"],
                        "ev_params": d_data["ev_params"],
                        "actual_pv": d_data["pv_actual"],
                        "config": {"dt": 1.0, "export_rate": 0.04},
                    }
                    kwargs = {}
                    if ctrl == "reliability_aware":
                        kwargs = {
                            "reliability_score": d_data["reliability"],
                            "threshold": best_tau,
                        }
                    sched = solve_schedule(sched_inputs, method=ctrl, config={"dt": 1.0}, **kwargs)
                    sim = simulate_day(
                        sched,
                        {"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": d_data["tariff"]},
                        d_data["ev_params"],
                        {"dt": 1.0, "export_rate": 0.04},
                    )
                    sc_ctrl_costs.append(sim["total_cost"])
            exp_c_results[sc_name][ctrl] = float(np.mean(sc_ctrl_costs))

    save_json_results(exp_c_results, str(proc_dir / "exp_c_stress_test.json"))
    exp_c_df = pd.DataFrame(exp_c_results).T
    save_csv_table(exp_c_df, str(tables_dir / "table8_stress_test_comparison.csv"))
    logger.info("Experiment C completed.")

    # 7. Experiment D: Confidence-Threshold Sensitivity on Test Split
    logger.info("Experiment D: Evaluating threshold sensitivity on test split...")
    exp_d_results = []
    test_thresholds = np.linspace(
        float(np.min(val_day_reliabilities)), float(np.max(val_day_reliabilities)), 9
    )

    for tau_val in test_thresholds:
        t_costs = []
        t_deadlines = []
        t_fallbacks = []
        for d_data in test_days_data:
            sched_inputs = {
                "pv_forecast": d_data["pv_forecast"],
                "load": d_data["load"],
                "tariff": d_data["tariff"],
                "ev_params": d_data["ev_params"],
                "actual_pv": d_data["pv_actual"],
                "config": {"dt": 1.0, "export_rate": 0.04},
            }
            sched = solve_schedule(
                sched_inputs,
                method="reliability_aware",
                config={"dt": 1.0},
                reliability_score=d_data["reliability"],
                threshold=tau_val,
            )
            sim = simulate_day(
                sched,
                {"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": d_data["tariff"]},
                d_data["ev_params"],
                {"dt": 1.0, "export_rate": 0.04},
            )
            t_costs.append(sim["total_cost"])
            t_deadlines.append(sim["deadline_met"])
            t_fallbacks.append(sched.get("used_fallback", False))

        exp_d_results.append({
            "threshold": float(tau_val),
            "mean_cost": float(np.mean(t_costs)),
            "deadline_success_rate": float(np.mean(t_deadlines)),
            "fallback_rate": float(np.mean(t_fallbacks)),
        })

    save_json_results(exp_d_results, str(proc_dir / "exp_d_threshold_sensitivity.json"))
    exp_d_df = pd.DataFrame(exp_d_results)
    save_csv_table(exp_d_df, str(tables_dir / "table8b_threshold_sensitivity.csv"), index=False)
    logger.info("Experiment D completed.")

    # 8. Experiment E: EV Demand and Deadline Sensitivity
    logger.info("Experiment E: EV demand and charging window sensitivity...")
    e_energies = config.get("experiments", {}).get("sensitivity_ev_energy_kwh", [10.0, 15.0, 20.0, 25.0, 30.0])
    exp_e_results = []

    for req_e in e_energies:
        for ctrl in ["cheapest_hours", "forecast_driven", "reliability_aware", "conservative_fallback"]:
            e_costs = []
            e_deadlines = []
            for d_data in test_days_data:
                ev_p = dict(d_data["ev_params"])
                ev_p["required_energy_kwh"] = req_e

                sched_inputs = {
                    "pv_forecast": d_data["pv_forecast"],
                    "load": d_data["load"],
                    "tariff": d_data["tariff"],
                    "ev_params": ev_p,
                    "actual_pv": d_data["pv_actual"],
                    "config": {"dt": 1.0, "export_rate": 0.04},
                }
                kwargs = {}
                if ctrl == "reliability_aware":
                    kwargs = {
                        "reliability_score": d_data["reliability"],
                        "threshold": best_tau,
                    }
                sched = solve_schedule(sched_inputs, method=ctrl, config={"dt": 1.0}, **kwargs)
                sim = simulate_day(
                    sched,
                    {"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": d_data["tariff"]},
                    ev_p,
                    {"dt": 1.0, "export_rate": 0.04},
                )
                e_costs.append(sim["total_cost"])
                e_deadlines.append(sim["deadline_met"])

            exp_e_results.append({
                "required_energy_kwh": req_e,
                "controller": ctrl,
                "mean_cost": float(np.mean(e_costs)),
                "deadline_success_rate": float(np.mean(e_deadlines)),
            })

    save_json_results(exp_e_results, str(proc_dir / "exp_e_ev_demand_sensitivity.json"))
    exp_e_df = pd.DataFrame(exp_e_results)
    save_csv_table(exp_e_df, str(tables_dir / "table8c_ev_demand_sensitivity.csv"), index=False)
    logger.info("Experiment E completed.")

    # 9. Experiment F: Tariff Sensitivity (TOU vs Flat)
    logger.info("Experiment F: Evaluating tariff structure sensitivity (TOU vs Flat)...")
    exp_f_results = []
    flat_rate = config.get("tariff", {}).get("flat_rate", 0.15)

    for ctrl in ["cheapest_hours", "forecast_driven", "reliability_aware", "conservative_fallback"]:
        flat_costs = []
        for d_data in test_days_data:
            flat_tariff = np.full(len(d_data["tariff"]), flat_rate)
            sched_inputs = {
                "pv_forecast": d_data["pv_forecast"],
                "load": d_data["load"],
                "tariff": flat_tariff,
                "ev_params": d_data["ev_params"],
                "actual_pv": d_data["pv_actual"],
                "config": {"dt": 1.0, "export_rate": 0.04},
            }
            kwargs = {}
            if ctrl == "reliability_aware":
                kwargs = {
                    "reliability_score": d_data["reliability"],
                    "threshold": best_tau,
                }
            sched = solve_schedule(sched_inputs, method=ctrl, config={"dt": 1.0}, **kwargs)
            sim = simulate_day(
                sched,
                {"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": flat_tariff},
                d_data["ev_params"],
                {"dt": 1.0, "export_rate": 0.04},
            )
            flat_costs.append(sim["total_cost"])

        exp_f_results.append({
            "tariff": "flat",
            "controller": ctrl,
            "mean_cost": float(np.mean(flat_costs)),
        })
        # Add TOU baseline
        tou_costs = [r["total_cost"] for r in exp_b_results[ctrl]]
        exp_f_results.append({
            "tariff": "time_of_use",
            "controller": ctrl,
            "mean_cost": float(np.mean(tou_costs)),
        })

    save_json_results(exp_f_results, str(proc_dir / "exp_f_tariff_sensitivity.json"))
    exp_f_df = pd.DataFrame(exp_f_results)
    save_csv_table(exp_f_df, str(tables_dir / "table8d_tariff_sensitivity.csv"), index=False)
    logger.info("Experiment F completed.")

    # 10. Experiment G: Ablation Study
    logger.info("Experiment G: Running Ablation Study...")
    ablation_summary = [
        {"configuration": "Forecast-driven (no confidence awareness, B3)", "mean_cost": float(summary_b.loc["forecast_driven", "mean_cost"]), "deadline_success_rate": float(summary_b.loc["forecast_driven", "deadline_success_rate"])},
        {"configuration": "Proposed Reliability-aware switching (tau*= " + f"{best_tau:.3f})", "mean_cost": float(summary_b.loc["reliability_aware", "mean_cost"]), "deadline_success_rate": float(summary_b.loc["reliability_aware", "deadline_success_rate"])},
        {"configuration": "Conservative Fallback always active (B5)", "mean_cost": float(summary_b.loc["conservative_fallback", "mean_cost"]), "deadline_success_rate": float(summary_b.loc["conservative_fallback", "deadline_success_rate"])},
        {"configuration": "Fixed schedule (B1)", "mean_cost": float(summary_b.loc["fixed", "mean_cost"]), "deadline_success_rate": float(summary_b.loc["fixed", "deadline_success_rate"])},
    ]
    save_json_results(ablation_summary, str(proc_dir / "exp_g_ablation.json"))
    ablation_df = pd.DataFrame(ablation_summary)
    save_csv_table(ablation_df, str(tables_dir / "table7_ablation_results.csv"), index=False)
    logger.info("Experiment G completed.")

    # 10b. Experiment H: Bidirectional E2H and E2G Scenarios (S1 through S4)
    logger.info("Experiment H: Evaluating Bidirectional Scenarios S1 (Baseline), S2 (E2H), S3 (E2G), and S4 (Combined)...")
    bidi_scenarios = {
        "S1": {"name": "Unidirectional (Baseline)", "enable_e2h": False, "enable_e2g": False},
        "S2": {"name": "E2H-Only (Vehicle-to-Home)", "enable_e2h": True, "enable_e2g": False},
        "S3": {"name": "E2G-Only (Vehicle-to-Grid)", "enable_e2h": False, "enable_e2g": True},
        "S4": {"name": "Combined (E2H + E2G)", "enable_e2h": True, "enable_e2g": True},
    }

    bidi_summary_rows = []
    bidi_plot_metrics = {}
    s1_net_costs = []
    scenario_cost_series = {}

    for sc_id, sc_params in bidi_scenarios.items():
        sc_net_costs = []
        sc_grid_imports = []
        sc_grid_exports = []
        sc_discharged = []
        sc_e2h = []
        sc_e2g = []
        sc_peak_imports = []
        sc_deadlines = []

        for d_data in test_days_data:
            sc_cfg = {
                "dt": 1.0,
                "export_rate": config.get("tariff", {}).get("export_rate", 0.04),
                "enable_e2h": sc_params["enable_e2h"],
                "enable_e2g": sc_params["enable_e2g"],
                "degradation_cost_per_kwh": config.get("bidirectional", {}).get("degradation_cost_per_kwh", 0.015),
            }

            sched_inputs = {
                "pv_forecast": d_data["pv_forecast"],
                "load": d_data["load"],
                "tariff": d_data["tariff"],
                "ev_params": d_data["ev_params"],
                "actual_pv": d_data["pv_actual"],
                "config": sc_cfg,
            }

            sched = solve_schedule(
                sched_inputs,
                method="reliability_aware",
                config=sc_cfg,
                reliability_score=d_data["reliability"],
                threshold=best_tau,
            )

            sim = simulate_day(
                sched,
                {"pv_actual": d_data["pv_actual"], "load": d_data["load"], "tariff": d_data["tariff"]},
                d_data["ev_params"],
                sc_cfg,
            )

            sc_net_costs.append(sim["net_cost"])
            sc_grid_imports.append(np.sum(sim["grid_import"]))
            sc_grid_exports.append(np.sum(sim["export"]))
            sc_discharged.append(sim["battery_throughput_kwh"])
            sc_e2h.append(np.sum(sim["p_e2h"]))
            sc_e2g.append(np.sum(sim["p_e2g"]))
            sc_peak_imports.append(sim["peak_grid_import_kw"])
            sc_deadlines.append(sim["deadline_met"])

        scenario_cost_series[sc_id] = sc_net_costs
        if sc_id == "S1":
            s1_net_costs = sc_net_costs

        bidi_summary_rows.append({
            "scenario": sc_id,
            "description": sc_params["name"],
            "e2h_enabled": sc_params["enable_e2h"],
            "e2g_enabled": sc_params["enable_e2g"],
            "mean_net_cost": float(np.mean(sc_net_costs)),
            "std_net_cost": float(np.std(sc_net_costs)),
            "mean_grid_import_kwh": float(np.mean(sc_grid_imports)),
            "mean_grid_export_kwh": float(np.mean(sc_grid_exports)),
            "mean_discharged_kwh": float(np.mean(sc_discharged)),
            "mean_e2h_kwh": float(np.mean(sc_e2h)),
            "mean_e2g_kwh": float(np.mean(sc_e2g)),
            "peak_grid_import_kw": float(np.mean(sc_peak_imports)),
            "deadline_success_rate": float(np.mean(sc_deadlines)),
        })

        bidi_plot_metrics[sc_id] = {
            "net_cost": float(np.mean(sc_net_costs)),
            "grid_import": float(np.mean(sc_grid_imports)),
            "grid_export": float(np.mean(sc_grid_exports)),
            "e2h_energy": float(np.mean(sc_e2h)),
            "e2g_energy": float(np.mean(sc_e2g)),
            "peak_import": float(np.mean(sc_peak_imports)),
        }

    bidi_df = pd.DataFrame(bidi_summary_rows)
    save_csv_table(bidi_df, str(tables_dir / "table9_bidirectional_s1_s4_comparison.csv"), index=False)
    save_json_results(bidi_summary_rows, str(proc_dir / "exp_h_bidirectional.json"))
    logger.info("Experiment H completed. Summary:\n" + str(bidi_df))

    # Statistical significance of S2, S3, S4 against S1 baseline
    logger.info("Computing paired statistical tests for bidirectional scenarios...")
    bidi_stats_df = compare_controllers(scenario_cost_series, baseline_name="S1", config={"metric_name": "net_cost", "confidence": 0.95})
    save_csv_table(bidi_stats_df, str(tables_dir / "table10_bidirectional_statistical_tests.csv"), index=False)

    # 11. Generate Publication Figures
    logger.info("Generating publication figures from verified test results...")
    try:
        plot_system_architecture(str(fig_dir / "fig1_system_architecture.png"))
        
        # Example day plot
        ex_day = test_days_data[0]
        plot_pv_forecast_example(
            timestamps=np.arange(24),
            actual=ex_day["pv_actual"],
            forecast=ex_day["pv_forecast"],
            lower=ex_day["pv_forecast_low"],
            upper=ex_day["pv_forecast_high"],
            save_path=str(fig_dir / "fig2_pv_forecast_interval.png"),
        )

        # Forecast error distribution
        all_test_actual = np.concatenate([d["pv_actual"] for d in test_days_data])
        all_test_forecast = np.concatenate([d["pv_forecast"] for d in test_days_data])
        plot_forecast_error_distribution(
            errors=all_test_actual - all_test_forecast,
            save_path=str(fig_dir / "fig3_forecast_error_dist.png"),
        )

        # Interval coverage
        plot_interval_coverage(
            coverages={"Validation": val_interval_metrics["coverage"], "Test": evaluate_intervals(all_test_actual, np.concatenate([d['pv_forecast_low'] for d in test_days_data]), np.concatenate([d['pv_forecast_high'] for d in test_days_data]))["coverage"]},
            widths={"Validation": val_interval_metrics["mean_width"], "Test": float(np.mean(np.concatenate([d['pv_forecast_high'] - d['pv_forecast_low'] for d in test_days_data])))},
            nominal=0.90,
            save_path=str(fig_dir / "fig4_interval_calibration.png"),
        )

        # Controller cost comparison
        plot_controller_comparison_cost(
            results=cost_series,
            save_path=str(fig_dir / "fig5_daily_cost_by_controller.png"),
        )

        # Solar contribution
        solar_series = {ctrl: [np.sum(r["pv_to_ev"]) for r in exp_b_results[ctrl]] for ctrl in controllers}
        plot_solar_contribution(
            results=solar_series,
            save_path=str(fig_dir / "fig6_solar_contribution.png"),
        )

        # Peak and deadline
        peak_series = {ctrl: [r["peak_grid_import_kw"] for r in exp_b_results[ctrl]] for ctrl in controllers}
        deadline_series = {ctrl: float(summary_b.loc[ctrl, "deadline_success_rate"]) for ctrl in controllers}
        plot_peak_and_deadline(
            peak_results=peak_series,
            deadline_results=deadline_series,
            save_path=str(fig_dir / "fig7_peak_and_deadline.png"),
        )

        # Stress test
        plot_stress_test(
            scenario_results=exp_c_results,
            metric="Mean Daily Electricity Cost ($)",
            save_path=str(fig_dir / "fig8_stress_test_comparison.png"),
        )

        # Threshold sensitivity
        plot_threshold_sensitivity(
            thresholds=exp_d_df["threshold"].values,
            costs=exp_d_df["mean_cost"].values,
            deadline_rates=exp_d_df["deadline_success_rate"].values,
            fallback_rates=exp_d_df["fallback_rate"].values,
            selected_threshold=best_tau,
            save_path=str(fig_dir / "fig9_threshold_sensitivity.png"),
        )

        # Fig 10: Bidirectional Scenarios
        plot_bidirectional_scenarios(
            scenario_metrics=bidi_plot_metrics,
            save_path=str(fig_dir / "fig10_bidirectional_flows_s1_s4.png"),
        )

        # Fig 11: Real vs Synthetic profiles comparison
        from src.data import generate_synthetic_pv, generate_synthetic_load
        syn_pv_df = generate_synthetic_pv(config)
        syn_load_df = generate_synthetic_load(config)
        ex_real_pv = test_days_data[0]["pv_actual"]
        ex_syn_pv = syn_pv_df.iloc[:24]["pv_generation_kw"].values
        ex_real_load = test_days_data[0]["load"]
        ex_syn_load = syn_load_df.iloc[:24]["load_kw"].values
        plot_real_vs_synthetic(
            real_pv=ex_real_pv,
            syn_pv=ex_syn_pv,
            real_load=ex_real_load,
            syn_load=ex_syn_load,
            save_path=str(fig_dir / "fig11_real_vs_synthetic_profiles.png"),
        )

        logger.info("All publication figures successfully generated.")
    except Exception as e:
        logger.error(f"Error generating figures: {e}", exc_info=True)

    # 12. Copy Figures and Tables to Paper Directory
    logger.info("Synchronizing figures and tables to paper/ directory...")
    paper_fig_dir = Path(config.get("output", {}).get("paper_dir", "paper")) / "figures"
    paper_tbl_dir = Path(config.get("output", {}).get("paper_dir", "paper")) / "tables"
    paper_fig_dir.mkdir(parents=True, exist_ok=True)
    paper_tbl_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    for f in fig_dir.glob("*.*"):
        if f.suffix in [".png", ".pdf"]:
            shutil.copy2(f, paper_fig_dir / f.name)
    for f in tables_dir.glob("*.csv"):
        shutil.copy2(f, paper_tbl_dir / f.name)

    logger.info("Entire experimental pipeline executed successfully and completely!")
    return {
        "status": "success",
        "selected_tau": best_tau,
        "n_test_days": len(test_days_data),
        "results_dir": results_dir,
    }

