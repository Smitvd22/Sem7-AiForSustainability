"""
preprocessing.py — Data cleaning, validation, and quality reporting for the
Reliability-Aware EV Charging project.

All helpers operate on pandas DataFrames with a ``DatetimeIndex`` named
``'timestamp'``.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────

def validate_data(
    df: pd.DataFrame,
    column: str,
    data_type: str,
) -> Dict[str, Any]:
    """Run quality checks on a single data column.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with a ``DatetimeIndex`` and at least *column*.
    column : str
        Name of the column to validate.
    data_type : str
        One of ``"pv"``, ``"load"``, or ``"tariff"``.  Determines which
        domain-specific checks are applied.

    Returns
    -------
    dict
        Quality report with the following keys:

        - ``column`` (str): Column name.
        - ``data_type`` (str): Data type label.
        - ``n_rows`` (int): Total rows.
        - ``n_nan`` (int): Count of NaN values.
        - ``n_negative`` (int): Count of negative values (for PV/load).
        - ``n_duplicate_timestamps`` (int): Duplicate index entries.
        - ``n_missing_timestamps`` (int): Gaps in the expected hourly sequence.
        - ``range_violations`` (int): Values outside plausible range.
        - ``issues`` (list[str]): Human-readable list of issues found.
    """
    issues: List[str] = []
    series = df[column]

    n_nan = int(series.isna().sum())
    if n_nan > 0:
        issues.append(f"{n_nan} NaN value(s) found.")

    # Negative values
    n_negative = 0
    if data_type in ("pv", "load"):
        n_negative = int((series < 0).sum())
        if n_negative > 0:
            issues.append(f"{n_negative} negative value(s) in '{column}'.")

    # Duplicate timestamps
    n_dup = int(df.index.duplicated().sum())
    if n_dup > 0:
        issues.append(f"{n_dup} duplicate timestamp(s).")

    # Missing timestamps (expected hourly)
    n_missing = 0
    if len(df) > 1:
        expected = pd.date_range(df.index.min(), df.index.max(), freq="h")
        n_missing = len(expected) - len(df.index.intersection(expected))
        if n_missing > 0:
            issues.append(f"{n_missing} missing hourly timestamp(s).")

    # Range violations
    range_violations = 0
    if data_type == "pv":
        # PV should not exceed ~20 kW for a residential system
        upper = 20.0
        range_violations = int((series > upper).sum())
        if range_violations > 0:
            issues.append(
                f"{range_violations} PV value(s) exceed {upper} kW."
            )
    elif data_type == "load":
        upper = 15.0
        range_violations = int((series > upper).sum())
        if range_violations > 0:
            issues.append(
                f"{range_violations} load value(s) exceed {upper} kW."
            )
    elif data_type == "tariff":
        upper = 5.0
        range_violations = int((series > upper).sum())
        if range_violations > 0:
            issues.append(
                f"{range_violations} tariff value(s) exceed {upper} $/kWh."
            )

    return {
        "column": column,
        "data_type": data_type,
        "n_rows": len(df),
        "n_nan": n_nan,
        "n_negative": n_negative,
        "n_duplicate_timestamps": n_dup,
        "n_missing_timestamps": n_missing,
        "range_violations": range_violations,
        "issues": issues,
    }


# ──────────────────────────────────────────────────────────────────────
# Cleaning
# ──────────────────────────────────────────────────────────────────────

def clean_data(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Clean a time-series DataFrame.

    Steps performed (in order):
    1. Sort by timestamp index.
    2. Remove duplicate timestamps (keep first).
    3. Reindex to a complete hourly range to expose gaps.
    4. Interpolate small gaps (≤ 3 consecutive hours) linearly.
    5. Clip negative PV values to 0.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with ``DatetimeIndex``.
    column : str
        Column to clean.

    Returns
    -------
    pd.DataFrame
        Cleaned copy of the input.
    """
    df = df.copy()

    # 1. Sort
    df = df.sort_index()

    # 2. Remove duplicates
    df = df[~df.index.duplicated(keep="first")]

    # 3. Reindex to full hourly range
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq="h")
    df = df.reindex(full_idx)
    df.index.name = "timestamp"

    # 4. Interpolate small gaps (≤ 3 hours)
    mask = df[column].isna()
    if mask.any():
        # Identify gap lengths
        gap_id = (~mask).cumsum()
        gap_sizes = mask.groupby(gap_id).transform("sum")
        fillable = mask & (gap_sizes <= 3)

        interpolated = df[column].interpolate(method="time")
        df.loc[fillable, column] = interpolated.loc[fillable]

    # 5. Clip negatives for PV-like columns
    if "pv" in column.lower() or "generation" in column.lower():
        df[column] = df[column].clip(lower=0.0)

    return df


# ──────────────────────────────────────────────────────────────────────
# Quality report
# ──────────────────────────────────────────────────────────────────────

def generate_quality_report(dataset: dict) -> Dict[str, Dict[str, Any]]:
    """Create a comprehensive quality report for every series in the dataset.

    Parameters
    ----------
    dataset : dict
        As returned by ``data.load_dataset``, with keys ``'pv'``, ``'load'``,
        ``'tariff'``.

    Returns
    -------
    dict
        Mapping of series name to a statistics dict containing:
        ``count``, ``missing_pct``, ``min``, ``max``, ``mean``, ``std``,
        ``date_range`` (``[start, end]`` ISO strings).
    """
    series_map = {
        "pv": ("pv_generation_kw", "pv"),
        "load": ("load_kw", "load"),
        "tariff": ("price_per_kwh", "tariff"),
    }

    report: Dict[str, Dict[str, Any]] = {}

    for key, (col, dtype) in series_map.items():
        if key not in dataset:
            continue
        df = dataset[key]
        s = df[col]

        n_total = len(s)
        n_nan = int(s.isna().sum())
        missing_pct = round(100.0 * n_nan / max(n_total, 1), 4)

        report[key] = {
            "column": col,
            "count": n_total,
            "missing_pct": missing_pct,
            "min": float(s.min()) if not s.empty else None,
            "max": float(s.max()) if not s.empty else None,
            "mean": float(s.mean()) if not s.empty else None,
            "std": float(s.std()) if not s.empty else None,
            "date_range": [
                str(df.index.min()),
                str(df.index.max()),
            ],
            "validation": validate_data(df, col, dtype),
        }

    return report


# ──────────────────────────────────────────────────────────────────────
# Timestamp alignment
# ──────────────────────────────────────────────────────────────────────

def align_timestamps(dfs: List[pd.DataFrame]) -> List[pd.DataFrame]:
    """Align multiple DataFrames to their common timestamps (inner join).

    Parameters
    ----------
    dfs : list[pd.DataFrame]
        DataFrames, each with a ``DatetimeIndex``.

    Returns
    -------
    list[pd.DataFrame]
        Copies of the input DataFrames restricted to the shared index.
    """
    if not dfs:
        return []

    common_idx = dfs[0].index
    for df in dfs[1:]:
        common_idx = common_idx.intersection(df.index)

    return [df.loc[common_idx].copy() for df in dfs]
