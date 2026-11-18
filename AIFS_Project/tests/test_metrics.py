"""
Unit tests for evaluation metrics.
"""

import numpy as np
import pytest

from src.metrics import (
    forecast_mae,
    forecast_rmse,
    forecast_mbe,
    daily_cost,
    daily_grid_import_kwh,
    daily_peak_grid_kw,
    daily_solar_self_consumption,
    daily_ev_solar_ratio,
    interval_coverage,
    interval_mean_width,
)


def test_forecast_metrics():
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.5, 2.0, 2.5])
    assert np.isclose(forecast_mae(y_true, y_pred), (0.5 + 0.0 + 0.5) / 3)
    assert np.isclose(forecast_rmse(y_true, y_pred), np.sqrt((0.25 + 0.0 + 0.25) / 3))
    assert np.isclose(forecast_mbe(y_true, y_pred), (0.5 + 0.0 - 0.5) / 3)


def test_interval_metrics():
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    low = np.array([0.5, 1.5, 2.5, 4.5])  # 4th observation misses
    high = np.array([1.5, 2.5, 3.5, 5.5])

    cov = interval_coverage(y_true, low, high)
    assert np.isclose(cov, 0.75)
    width = interval_mean_width(low, high)
    assert np.isclose(width, 1.0)


def test_solar_metrics():
    res = {
        "charging_power": np.array([2.0, 2.0]),
        "pv_to_ev": np.array([1.0, 2.0]),
        "pv_self_consumed": np.array([3.0, 3.0]),
    }
    actual_pv = np.array([5.0, 5.0])

    scr = daily_solar_self_consumption(res, actual_pv, dt=1.0)
    assert np.isclose(scr, 6.0 / 10.0)

    esr = daily_ev_solar_ratio(res, dt=1.0)
    assert np.isclose(esr, 3.0 / 4.0)

