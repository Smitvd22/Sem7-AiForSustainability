"""
cli.py — Command-Line Interface for the Reliability-Aware EV Charging research suite.

Usage:
    python -m src.cli validate-data --config configs/default.json
    python -m src.cli train --config configs/default.json
    python -m src.cli run-experiments --config configs/default.json
    python -m src.cli analyze --config configs/default.json
    python -m src.cli build-paper --config configs/default.json
    python -m src.cli run-all --config configs/default.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.data import load_dataset, create_splits
from src.preprocessing import generate_quality_report
from src.forecasting import fit_forecaster, evaluate_forecast
from src.uncertainty import ConformalPredictor, evaluate_intervals
from src.experiments import run_experiments
from src.statistics import analyze_results
from src.reporting import (
    build_paper,
    generate_experiment_manifest,
    generate_completion_checklist,
    save_json_results,
)

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_validate_data(config: dict):
    print(">>> [Stage 1] Validating dataset and provenance...")
    dataset = load_dataset(config)
    splits = create_splits(dataset, config)
    report = generate_quality_report(dataset)
    print("Quality Report:")
    for series, stats in report.items():
        print(f"  - {series}: count={stats['count']}, min={stats['min']:.3f}, max={stats['max']:.3f}, mean={stats['mean']:.3f}")
    print(f"Splits generated: {list(splits.keys())}")
    print("Validation successful!")


def cmd_train(config: dict):
    print(">>> [Stage 2] Training forecasters and calibrating prediction intervals...")
    dataset = load_dataset(config)
    splits = create_splits(dataset, config)
    pv_df = dataset["pv"]

    train_df = pv_df.loc[splits["train"]["start"] : splits["train"]["end"]]
    cal_df = pv_df.loc[splits["calibration"]["start"] : splits["calibration"]["end"]]

    # Persistence
    f_p = fit_forecaster(train_df, {"type": "persistence", "persistence_lag_days": 1})
    # ML
    f_ml = fit_forecaster(train_df, {"type": "ml", **config.get("forecasting", {})})

    # Calibrate
    cal_preds = f_ml.predict(cal_df.index, pv_df)
    cal_actuals = cal_df["pv_generation_kw"].values

    conformal = ConformalPredictor(nominal_coverage=config.get("uncertainty", {}).get("nominal_coverage", 0.90))
    conformal.calibrate(cal_actuals, cal_preds)

    print(f"Model trained and calibrated successfully! Conformal q_alpha = {conformal.q_alpha_:.4f} kW")


def cmd_run_experiments(config: dict):
    print(">>> [Stage 3] Running full experimental protocol...")
    res = run_experiments(config)
    print(f"Experiments completed! Result status: {res['status']}")
    print(f"Optimal threshold tau: {res['selected_tau']:.4f}")
    print(f"Evaluated on {res['n_test_days']} test days.")


def cmd_analyze(config: dict):
    print(">>> [Stage 4] Analyzing experiment outputs and computing statistical tests...")
    results_dir = config.get("output", {}).get("results_dir", "results")
    analysis = analyze_results(results_dir, config)
    print("Analysis complete! Generated statistical tests and summary DataFrames.")


def cmd_build_paper(config: dict):
    print(">>> [Stage 5] Assembling paper components and manifest...")
    results_dir = config.get("output", {}).get("results_dir", "results")
    paper_res = build_paper(results_dir, config)
    manifest = generate_experiment_manifest(config, results_dir)
    save_json_results(manifest, f"{results_dir}/logs/manifest.json")
    checklist = generate_completion_checklist(results_dir, config)
    save_json_results(checklist, f"{results_dir}/logs/completion_checklist.json")
    print(f"Paper synchronized: {len(paper_res['figures'])} figures, {len(paper_res['tables'])} tables.")
    print("Manifest and completion checklist saved.")


def cmd_run_all(config: dict):
    print("=================================================================")
    print("EXECUTING END-TO-END RESEARCH WORKFLOW")
    print("=================================================================")
    cmd_validate_data(config)
    cmd_train(config)
    cmd_run_experiments(config)
    cmd_analyze(config)
    cmd_build_paper(config)
    print("=================================================================")
    print("END-TO-END WORKFLOW COMPLETED SUCCESSFULLY!")
    print("=================================================================")


def main():
    parser = argparse.ArgumentParser(description="Reliability-Aware EV Charging Research CLI")
    parser.add_argument(
        "command",
        choices=["validate-data", "train", "run-experiments", "analyze", "build-paper", "run-all"],
        help="Command to execute",
    )
    parser.add_argument(
        "--config",
        default="configs/default.json",
        help="Path to configuration JSON file (default: configs/default.json)",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "validate-data":
        cmd_validate_data(config)
    elif args.command == "train":
        cmd_train(config)
    elif args.command == "run-experiments":
        cmd_run_experiments(config)
    elif args.command == "analyze":
        cmd_analyze(config)
    elif args.command == "build-paper":
        cmd_build_paper(config)
    elif args.command == "run-all":
        cmd_run_all(config)


if __name__ == "__main__":
    main()

