"""
Evaluation metrics for Reliability-Aware Scheduling of Home EV Charging.

This module computes forecast accuracy metrics, energy/cost metrics for
daily simulation results, prediction interval metrics, and aggregate
statistics across multiple simulation days.
"""

import numpy as np
from typing import Any


# ---------------------------------------------------------------------------
# Forecast accuracy metrics
# ---------------------------------------------------------------------------

def forecast_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Mean Absolute Error between actual and predicted arrays.

    Parameters
    ----------
    actual : np.ndarray
        Ground-truth values.
    predicted : np.ndarray
        Predicted / forecast values.

    Returns
    -------
    float
        Mean absolute error.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return float(np.mean(np.abs(actual - predicted)))


def forecast_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Root Mean Squared Error between actual and predicted arrays.

    Parameters
    ----------
    actual : np.ndarray
        Ground-truth values.
    predicted : np.ndarray
        Predicted / forecast values.

    Returns
    -------
    float
        Root mean squared error.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def forecast_mbe(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Compute Mean Bias Error (predicted − actual).

    A positive MBE indicates the forecast tends to over-predict.

    Parameters
    ----------
    actual : np.ndarray
        Ground-truth values.
    predicted : np.ndarray
        Predicted / forecast values.

    Returns
    -------
    float
        Mean bias error.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return float(np.mean(predicted - actual))


# ---------------------------------------------------------------------------
# Energy / cost metrics  (operate on a daily simulation result dict)
# ---------------------------------------------------------------------------

def daily_cost(result: dict) -> float:
    """Return the total electricity cost for one simulated day.

    Parameters
    ----------
    result : dict
        Daily simulation result dictionary containing key ``'total_cost'``.

    Returns
    -------
    float
        Total cost in currency units.
    """
    return float(result["total_cost"])


def daily_grid_import_kwh(result: dict, dt: float = 1.0) -> float:
    """Compute total grid energy imported over a simulated day.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'grid_import'`` array (kW).
    dt : float, optional
        Time-step duration in hours (default 1.0 h).

    Returns
    -------
    float
        Total grid import in kWh.
    """
    grid_import = np.asarray(result["grid_import"], dtype=float)
    return float(np.sum(grid_import * dt))


def daily_peak_grid_kw(result: dict) -> float:
    """Return the peak grid import power during a simulated day.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'grid_import'`` array (kW).

    Returns
    -------
    float
        Peak grid import in kW.
    """
    grid_import = np.asarray(result["grid_import"], dtype=float)
    return float(np.max(grid_import))


def daily_pv_to_ev_kwh(result: dict, dt: float = 1.0) -> float:
    """Compute total solar energy routed directly to EV charging.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'pv_to_ev'`` array (kW).
    dt : float, optional
        Time-step duration in hours (default 1.0 h).

    Returns
    -------
    float
        PV-to-EV energy in kWh.
    """
    pv_to_ev = np.asarray(result["pv_to_ev"], dtype=float)
    return float(np.sum(pv_to_ev * dt))


def daily_solar_self_consumption(
    result: dict,
    actual_pv: np.ndarray,
    dt: float = 1.0,
) -> float:
    """Compute the solar self-consumption ratio for one day.

    Self-consumption = energy consumed on-site from PV / total PV generation.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'pv_self_consumed'`` array (kW).
    actual_pv : np.ndarray
        Actual PV generation profile (kW) for the day.
    dt : float, optional
        Time-step duration in hours (default 1.0 h).

    Returns
    -------
    float
        Self-consumption ratio in [0, 1].  Returns 0.0 when total PV is zero.
    """
    pv_self_consumed = np.asarray(result["pv_self_consumed"], dtype=float)
    actual_pv = np.asarray(actual_pv, dtype=float)

    total_pv = np.sum(actual_pv * dt)
    if total_pv == 0.0:
        return 0.0
    return float(np.sum(pv_self_consumed * dt) / total_pv)


def daily_ev_solar_ratio(result: dict, dt: float = 1.0) -> float:
    """Fraction of EV charging energy supplied by solar PV.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'pv_to_ev'`` and
        ``'charging_power'`` arrays (kW).
    dt : float, optional
        Time-step duration in hours (default 1.0 h).

    Returns
    -------
    float
        Ratio in [0, 1].  Returns 0.0 when total charging energy is zero.
    """
    pv_to_ev = np.asarray(result["pv_to_ev"], dtype=float)
    charging_power = np.asarray(result["charging_power"], dtype=float)

    total_charging = np.sum(charging_power * dt)
    if total_charging == 0.0:
        return 0.0
    return float(np.sum(pv_to_ev * dt) / total_charging)


def deadline_met(result: dict) -> bool:
    """Check whether the EV charging deadline was met.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'deadline_met'`` boolean.

    Returns
    -------
    bool
        True if the deadline was satisfied.
    """
    return bool(result["deadline_met"])


def unmet_energy_kwh(result: dict) -> float:
    """Return the amount of unmet EV energy demand.

    Parameters
    ----------
    result : dict
        Daily simulation result containing ``'unmet_energy_kwh'``.

    Returns
    -------
    float
        Unmet energy in kWh (0.0 if deadline was met).
    """
    return float(result["unmet_energy_kwh"])


# ---------------------------------------------------------------------------
# Prediction-interval metrics
# ---------------------------------------------------------------------------

def interval_coverage(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """Compute empirical coverage of a prediction interval.

    Parameters
    ----------
    actual : np.ndarray
        Observed / ground-truth values.
    lower : np.ndarray
        Lower bound of the prediction interval.
    upper : np.ndarray
        Upper bound of the prediction interval.

    Returns
    -------
    float
        Fraction of observations falling within [lower, upper].
    """
    actual = np.asarray(actual, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    within = (actual >= lower) & (actual <= upper)
    return float(np.mean(within))


def interval_mean_width(lower: np.ndarray, upper: np.ndarray) -> float:
    """Compute the mean width of a prediction interval.

    Parameters
    ----------
    lower : np.ndarray
        Lower bound of the prediction interval.
    upper : np.ndarray
        Upper bound of the prediction interval.

    Returns
    -------
    float
        Average interval width.
    """
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    return float(np.mean(upper - lower))


# ---------------------------------------------------------------------------
# Aggregate / summary functions
# ---------------------------------------------------------------------------

def aggregate_metrics(
    daily_results: list[dict],
    actual_pv_series: list[np.ndarray],
    config: dict,
) -> dict:
    """Aggregate per-day metrics across an entire evaluation period.

    Parameters
    ----------
    daily_results : list[dict]
        List of daily simulation result dicts (one per day).
    actual_pv_series : list[np.ndarray]
        Corresponding actual PV generation profiles, one array per day.
    config : dict
        Configuration dictionary (may contain ``'dt'`` time-step).

    Returns
    -------
    dict
        Aggregated metrics with the following keys:

        - ``mean_cost`` – average daily cost
        - ``total_cost`` – cumulative cost
        - ``mean_grid_import`` – average daily grid import (kWh)
        - ``mean_peak_grid`` – average daily peak grid (kW)
        - ``mean_pv_to_ev`` – average daily PV-to-EV energy (kWh)
        - ``mean_solar_self_consumption`` – average self-consumption ratio
        - ``mean_ev_solar_ratio`` – average EV solar ratio
        - ``deadline_miss_rate`` – fraction of days the deadline was missed
        - ``mean_unmet_energy`` – average unmet energy (kWh)
        - ``total_days`` – number of simulated days
        - ``infeasible_count`` – number of days with unmet energy > 0
    """
    dt: float = config.get("dt", 1.0)
    n_days: int = len(daily_results)

    costs: list[float] = []
    grid_imports: list[float] = []
    peak_grids: list[float] = []
    pv_to_evs: list[float] = []
    self_consumptions: list[float] = []
    ev_solar_ratios: list[float] = []
    deadlines_met: list[bool] = []
    unmet_energies: list[float] = []

    for i, result in enumerate(daily_results):
        costs.append(daily_cost(result))
        grid_imports.append(daily_grid_import_kwh(result, dt=dt))
        peak_grids.append(daily_peak_grid_kw(result))
        pv_to_evs.append(daily_pv_to_ev_kwh(result, dt=dt))
        self_consumptions.append(
            daily_solar_self_consumption(result, actual_pv_series[i], dt=dt)
        )
        ev_solar_ratios.append(daily_ev_solar_ratio(result, dt=dt))
        deadlines_met.append(deadline_met(result))
        unmet_energies.append(unmet_energy_kwh(result))

    infeasible_count = sum(1 for u in unmet_energies if u > 0.0)

    return {
        "mean_cost": float(np.mean(costs)) if n_days > 0 else 0.0,
        "total_cost": float(np.sum(costs)),
        "mean_grid_import": float(np.mean(grid_imports)) if n_days > 0 else 0.0,
        "mean_peak_grid": float(np.mean(peak_grids)) if n_days > 0 else 0.0,
        "mean_pv_to_ev": float(np.mean(pv_to_evs)) if n_days > 0 else 0.0,
        "mean_solar_self_consumption": (
            float(np.mean(self_consumptions)) if n_days > 0 else 0.0
        ),
        "mean_ev_solar_ratio": (
            float(np.mean(ev_solar_ratios)) if n_days > 0 else 0.0
        ),
        "deadline_miss_rate": (
            float(1.0 - np.mean(deadlines_met)) if n_days > 0 else 0.0
        ),
        "mean_unmet_energy": (
            float(np.mean(unmet_energies)) if n_days > 0 else 0.0
        ),
        "total_days": n_days,
        "infeasible_count": infeasible_count,
    }


def calculate_metrics(simulation_result: dict, config: dict) -> dict:
    """Calculate all relevant metrics for a single simulated day.

    This is a convenience wrapper that collects per-day energy, cost, and
    reliability metrics into a single dictionary.

    Parameters
    ----------
    simulation_result : dict
        Daily simulation result dictionary.
    config : dict
        Configuration dictionary (may contain ``'dt'`` and
        ``'actual_pv'`` for self-consumption calculation).

    Returns
    -------
    dict
        Dictionary of computed metric values for the day.
    """
    dt: float = config.get("dt", 1.0)
    actual_pv: np.ndarray = np.asarray(
        config.get("actual_pv", simulation_result.get("actual_pv", [])),
        dtype=float,
    )

    metrics: dict[str, Any] = {
        "cost": daily_cost(simulation_result),
        "total_cost": daily_cost(simulation_result),
        "net_cost": float(simulation_result.get("net_cost", daily_cost(simulation_result))),
        "export_revenue": float(simulation_result.get("export_revenue", 0.0)),
        "degradation_cost": float(simulation_result.get("degradation_cost", 0.0)),
        "grid_import_kwh": daily_grid_import_kwh(simulation_result, dt=dt),
        "export_kwh": float(np.sum(simulation_result.get("export", [])) * dt) if "export" in simulation_result else 0.0,
        "peak_grid_kw": daily_peak_grid_kw(simulation_result),
        "peak_export_kw": float(simulation_result.get("peak_grid_export_kw", 0.0)),
        "pv_to_ev_kwh": daily_pv_to_ev_kwh(simulation_result, dt=dt),
        "discharging_kwh": float(np.sum(simulation_result.get("discharging_power", [])) * dt) if "discharging_power" in simulation_result else 0.0,
        "e2h_kwh": float(np.sum(simulation_result.get("p_e2h", [])) * dt) if "p_e2h" in simulation_result else 0.0,
        "e2g_kwh": float(np.sum(simulation_result.get("p_e2g", [])) * dt) if "p_e2g" in simulation_result else 0.0,
        "solar_self_consumption": daily_solar_self_consumption(
            simulation_result, actual_pv, dt=dt
        ),
        "ev_solar_ratio": daily_ev_solar_ratio(simulation_result, dt=dt),
        "deadline_met": deadline_met(simulation_result),
        "unmet_energy_kwh": unmet_energy_kwh(simulation_result),
    }

    return metrics
