"""
Statistical analysis utilities for paired controller comparisons.

This module provides parametric and non-parametric hypothesis tests,
bootstrap confidence intervals, effect-size measures, and multiple-testing
corrections used to compare EV charging scheduling strategies.
"""

import os
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ttest_rel, wilcoxon as scipy_wilcoxon


# ---------------------------------------------------------------------------
# Paired hypothesis tests
# ---------------------------------------------------------------------------

def paired_t_test(
    x: np.ndarray,
    y: np.ndarray,
    confidence: float = 0.95,
) -> dict:
    """Perform a paired two-sided t-test on the differences *d = x − y*.

    Parameters
    ----------
    x : np.ndarray
        Metric values from the first (treatment) controller, one per day.
    y : np.ndarray
        Metric values from the baseline controller, one per day.
    confidence : float, optional
        Confidence level for the interval (default 0.95).

    Returns
    -------
    dict
        Keys: ``mean_diff``, ``std_diff``, ``t_statistic``, ``p_value``,
        ``ci_lower``, ``ci_upper``, ``n``, ``significant``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    n = len(d)

    mean_diff = float(np.mean(d))
    std_diff = float(np.std(d, ddof=1))

    t_stat, p_value = ttest_rel(x, y)

    alpha = 1.0 - confidence
    from scipy.stats import t as t_dist
    t_crit = t_dist.ppf(1.0 - alpha / 2.0, df=n - 1)
    se = std_diff / np.sqrt(n)
    ci_lower = mean_diff - t_crit * se
    ci_upper = mean_diff + t_crit * se

    return {
        "mean_diff": mean_diff,
        "std_diff": std_diff,
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "n": n,
        "significant": bool(p_value < alpha),
    }


def wilcoxon_test(
    x: np.ndarray,
    y: np.ndarray,
    confidence: float = 0.95,
) -> dict:
    """Perform a Wilcoxon signed-rank test on paired differences.

    Parameters
    ----------
    x : np.ndarray
        Metric values from the treatment controller.
    y : np.ndarray
        Metric values from the baseline controller.
    confidence : float, optional
        Confidence level (default 0.95).

    Returns
    -------
    dict
        Keys: ``median_diff``, ``statistic``, ``p_value``, ``n``,
        ``significant``.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    n = len(d)
    alpha = 1.0 - confidence

    median_diff = float(np.median(d))

    # Wilcoxon requires at least one non-zero difference
    if np.all(d == 0):
        return {
            "median_diff": median_diff,
            "statistic": 0.0,
            "p_value": 1.0,
            "n": n,
            "significant": False,
        }

    stat, p_value = scipy_wilcoxon(d, alternative="two-sided")

    return {
        "median_diff": median_diff,
        "statistic": float(stat),
        "p_value": float(p_value),
        "n": n,
        "significant": bool(p_value < alpha),
    }


# ---------------------------------------------------------------------------
# Bootstrap confidence interval
# ---------------------------------------------------------------------------

def bootstrap_ci(
    x: np.ndarray,
    y: np.ndarray,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict:
    """Bootstrap confidence interval for the mean paired difference.

    Day-level pairs are resampled with replacement to construct the
    sampling distribution of the mean difference.

    Parameters
    ----------
    x : np.ndarray
        Treatment metric values (one per day).
    y : np.ndarray
        Baseline metric values (one per day).
    n_bootstrap : int, optional
        Number of bootstrap resamples (default 1000).
    confidence : float, optional
        Confidence level (default 0.95).
    seed : int, optional
        Random seed for reproducibility (default 42).

    Returns
    -------
    dict
        Keys: ``mean_diff``, ``ci_lower``, ``ci_upper``,
        ``bootstrap_means`` (list of resampled means).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    n = len(d)

    rng = np.random.default_rng(seed)
    bootstrap_means: list[float] = []

    for _ in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)
        bootstrap_means.append(float(np.mean(d[indices])))

    bootstrap_means_arr = np.array(bootstrap_means)
    alpha = 1.0 - confidence
    ci_lower = float(np.percentile(bootstrap_means_arr, 100 * alpha / 2.0))
    ci_upper = float(np.percentile(bootstrap_means_arr, 100 * (1.0 - alpha / 2.0)))

    return {
        "mean_diff": float(np.mean(d)),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "bootstrap_means": bootstrap_means,
    }


# ---------------------------------------------------------------------------
# Effect size
# ---------------------------------------------------------------------------

def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cohen's d effect size for paired differences.

    Effect size is defined as ``mean(x − y) / std(x − y)``.

    Parameters
    ----------
    x : np.ndarray
        Treatment metric values.
    y : np.ndarray
        Baseline metric values.

    Returns
    -------
    float
        Cohen's d.  Returns 0.0 if the standard deviation is zero.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    std = float(np.std(d, ddof=1))
    if std == 0.0:
        return 0.0
    return float(np.mean(d) / std)


# ---------------------------------------------------------------------------
# Multiple-testing correction
# ---------------------------------------------------------------------------

def bonferroni_correction(
    p_values: list[float],
    alpha: float = 0.05,
) -> list[dict]:
    """Apply Bonferroni correction to a list of p-values.

    Parameters
    ----------
    p_values : list[float]
        Raw p-values from multiple hypothesis tests.
    alpha : float, optional
        Family-wise error rate (default 0.05).

    Returns
    -------
    list[dict]
        Each element is a dict with keys ``original_p``, ``corrected_p``,
        and ``significant``.
    """
    m = len(p_values)
    results: list[dict] = []
    for p in p_values:
        corrected = min(p * m, 1.0)
        results.append({
            "original_p": float(p),
            "corrected_p": float(corrected),
            "significant": bool(corrected < alpha),
        })
    return results


# ---------------------------------------------------------------------------
# Controller comparison
# ---------------------------------------------------------------------------

def compare_controllers(
    results: dict,
    baseline_name: str,
    config: dict,
) -> pd.DataFrame:
    """Compare every controller against a baseline using statistical tests.

    For each non-baseline controller the function runs:
    1. Paired t-test
    2. Bootstrap confidence interval
    3. Cohen's d effect size

    Parameters
    ----------
    results : dict
        Mapping of ``controller_name`` → list of daily metric values
        (one float per simulated day).
    baseline_name : str
        Key in *results* that identifies the baseline controller.
    config : dict
        Configuration dictionary.  Recognised keys:

        - ``'metric_name'`` (str) – label for the metric being compared
          (default ``'metric'``).
        - ``'confidence'`` (float) – confidence level (default 0.95).
        - ``'n_bootstrap'`` (int) – bootstrap resamples (default 1000).

    Returns
    -------
    pd.DataFrame
        One row per (controller, baseline) comparison with columns:
        ``controller``, ``baseline``, ``metric``, ``n``, ``mean_diff``,
        ``ci_lower``, ``ci_upper``, ``p_value``, ``cohens_d``,
        ``significant``.
    """
    metric_name: str = config.get("metric_name", "metric")
    confidence: float = config.get("confidence", 0.95)
    n_bootstrap: int = config.get("n_bootstrap", 1000)

    baseline_values = np.asarray(results[baseline_name], dtype=float)

    rows: list[dict[str, Any]] = []
    for ctrl_name, ctrl_values_raw in results.items():
        if ctrl_name == baseline_name:
            continue

        ctrl_values = np.asarray(ctrl_values_raw, dtype=float)

        # Paired t-test
        tt = paired_t_test(ctrl_values, baseline_values, confidence=confidence)

        # Bootstrap CI
        bs = bootstrap_ci(
            ctrl_values,
            baseline_values,
            n_bootstrap=n_bootstrap,
            confidence=confidence,
        )

        # Effect size
        cd = cohens_d(ctrl_values, baseline_values)

        rows.append({
            "controller": ctrl_name,
            "baseline": baseline_name,
            "metric": metric_name,
            "n": tt["n"],
            "mean_diff": tt["mean_diff"],
            "ci_lower": bs["ci_lower"],
            "ci_upper": bs["ci_upper"],
            "p_value": tt["p_value"],
            "cohens_d": cd,
            "significant": tt["significant"],
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# End-to-end results analysis
# ---------------------------------------------------------------------------

def analyze_results(results_directory: str, config: dict) -> dict:
    """Load saved results, run all pairwise comparisons, and persist output.

    The function expects JSON files in *results_directory* with the naming
    convention ``<controller_name>_results.json``.  Each JSON file should
    contain a list of daily metric dictionaries.

    Processed outputs are saved to ``<results_directory>/processed/``.

    Parameters
    ----------
    results_directory : str
        Path to the directory containing per-controller result files.
    config : dict
        Configuration dictionary.  Recognised keys:

        - ``'baseline_name'`` (str) – name of the baseline controller
          (default ``'greedy'``).
        - ``'metrics_to_compare'`` (list[str]) – metric keys to compare
          (default ``['cost']``).
        - ``'confidence'`` (float) – confidence level (default 0.95).
        - ``'n_bootstrap'`` (int) – number of bootstrap resamples
          (default 1000).

    Returns
    -------
    dict
        Summary dictionary with keys ``'comparisons'`` (dict of DataFrames
        keyed by metric name) and ``'output_directory'`` (str).
    """
    results_dir = Path(results_directory)
    baseline_name: str = config.get("baseline_name", "greedy")
    metrics_to_compare: list[str] = config.get("metrics_to_compare", ["cost"])
    confidence: float = config.get("confidence", 0.95)
    n_bootstrap: int = config.get("n_bootstrap", 1000)

    # ------------------------------------------------------------------
    # 1. Load per-controller results
    # ------------------------------------------------------------------
    controller_data: dict[str, list[dict]] = {}
    for fpath in results_dir.glob("*_results.json"):
        ctrl_name = fpath.stem.replace("_results", "")
        with open(fpath, "r", encoding="utf-8") as fh:
            controller_data[ctrl_name] = json.load(fh)

    # ------------------------------------------------------------------
    # 2. Run comparisons for each metric
    # ------------------------------------------------------------------
    comparisons: dict[str, pd.DataFrame] = {}
    for metric_key in metrics_to_compare:
        # Build dict: controller_name -> list[float] of the metric
        metric_results: dict[str, list[float]] = {}
        for ctrl_name, daily_dicts in controller_data.items():
            metric_results[ctrl_name] = [
                float(d.get(metric_key, 0.0)) for d in daily_dicts
            ]

        if baseline_name not in metric_results:
            continue

        comp_config = {
            "metric_name": metric_key,
            "confidence": confidence,
            "n_bootstrap": n_bootstrap,
        }
        df = compare_controllers(metric_results, baseline_name, comp_config)
        comparisons[metric_key] = df

    # ------------------------------------------------------------------
    # 3. Save processed outputs
    # ------------------------------------------------------------------
    output_dir = results_dir / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    for metric_key, df in comparisons.items():
        csv_path = output_dir / f"comparison_{metric_key}.csv"
        df.to_csv(str(csv_path), index=False)

    # Summary JSON
    summary: dict[str, Any] = {
        "comparisons": {
            k: df.to_dict(orient="records") for k, df in comparisons.items()
        },
        "output_directory": str(output_dir),
    }
    summary_path = output_dir / "analysis_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    return summary
