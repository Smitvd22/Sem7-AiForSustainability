"""
Unit tests for data generation, loading, splits, and quality verification.
"""

import json
import numpy as np
import pandas as pd
import pytest

from src.data import (
    generate_synthetic_pv,
    generate_synthetic_load,
    generate_tariff,
    load_dataset,
    create_splits,
)
from src.preprocessing import validate_data, clean_data, generate_quality_report


@pytest.fixture
def test_config():
    return {
        "pv_capacity_kw": 5.0,
        "latitude": 35.0,
        "year": 2023,
        "seed": 42,
        "tariff_type": "tou",
        "data": {
            "source": "synthetic",
            "time_resolution_hours": 1.0,
            "raw_dir": "data/raw",
            "processed_dir": "data/processed",
        },
        "split_ratios": {"train": 0.60, "calibration": 0.15, "validation": 0.10, "test": 0.15},
    }


def test_pv_generation_non_negative_and_nighttime_zero(test_config):
    df = generate_synthetic_pv(test_config)
    assert isinstance(df, pd.DataFrame)
    assert "pv_generation_kw" in df.columns
    # Check no negative values
    assert (df["pv_generation_kw"] >= 0.0).all()
    # Check night hours (e.g. midnight to 4am) are zero
    midnight_pv = df.loc[df.index.hour == 1, "pv_generation_kw"]
    assert (midnight_pv == 0.0).all()
    # Max within capacity
    assert df["pv_generation_kw"].max() <= test_config["pv_capacity_kw"] + 1e-4


def test_load_generation_positive(test_config):
    df = generate_synthetic_load(test_config)
    assert isinstance(df, pd.DataFrame)
    assert "load_kw" in df.columns
    # Household load is strictly positive
    assert (df["load_kw"] > 0.0).all()


def test_tariff_generation(test_config):
    df = generate_tariff(test_config)
    assert "price_per_kwh" in df.columns
    assert (df["price_per_kwh"] > 0.0).all()


def test_data_splits_chronological_and_no_leakage(test_config):
    dataset = load_dataset(test_config)
    splits = create_splits(dataset, test_config)

    # Check keys
    assert set(splits.keys()) == {"train", "calibration", "validation", "test"}

    # Verify chronological ordering
    train_end = pd.Timestamp(splits["train"]["end"])
    cal_start = pd.Timestamp(splits["calibration"]["start"])
    cal_end = pd.Timestamp(splits["calibration"]["end"])
    val_start = pd.Timestamp(splits["validation"]["start"])
    val_end = pd.Timestamp(splits["validation"]["end"])
    test_start = pd.Timestamp(splits["test"]["start"])

    assert train_end < cal_start
    assert cal_end < val_start
    assert val_end < test_start


def test_quality_report(test_config):
    dataset = load_dataset(test_config)
    report = generate_quality_report(dataset)
    assert "pv" in report
    assert "load" in report
    assert "tariff" in report
    assert report["pv"]["missing_pct"] == 0.0

