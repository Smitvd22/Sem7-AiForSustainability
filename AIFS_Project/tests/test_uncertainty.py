"""
Unit tests for split conformal prediction and reliability score.
"""

import numpy as np
import pytest

from src.uncertainty import (
    ConformalPredictor,
    compute_reliability,
    compute_horizon_reliability,
    evaluate_intervals,
)


def test_conformal_calibration_and_coverage():
    rng = np.random.RandomState(42)
    n_cal = 500
    actual_cal = rng.uniform(0, 5, size=n_cal)
    # Add noise to simulate forecast
    noise = rng.normal(0, 0.5, size=n_cal)
    pred_cal = np.maximum(0, actual_cal + noise)

    cp = ConformalPredictor(nominal_coverage=0.90)
    cp.calibrate(actual_cal, pred_cal)
    assert cp.q_alpha_ is not None
    assert cp.q_alpha_ > 0.0

    # Test on new out-of-sample data
    n_test = 500
    actual_test = rng.uniform(0, 5, size=n_test)
    pred_test = np.maximum(0, actual_test + rng.normal(0, 0.5, size=n_test))

    lower, upper = cp.predict_interval(pred_test, pv_capacity=5.0)
    assert len(lower) == n_test
    assert (lower >= 0.0).all()
    assert (upper <= 5.0).all()
    assert (upper >= lower).all()

    eval_res = evaluate_intervals(actual_test, lower, upper)
    # Empirical coverage should be close to 90% (e.g. between 85% and 95%)
    assert 0.85 <= eval_res["coverage"] <= 0.95


def test_reliability_scoring():
    widths = np.array([0.0, 1.0, 2.5, 5.0, 10.0])
    scale = 5.0
    rel = compute_reliability(widths, scale=scale)

    assert rel[0] == 1.0  # Zero width -> highest reliability
    assert rel[1] == 1.0 - (1.0 / 5.0)
    assert rel[3] == 0.0  # Width equals scale -> zero reliability
    assert rel[4] == 0.0  # Clipped to 0

    horizon_rel = compute_horizon_reliability(widths, scale=scale)
    assert 0.0 <= horizon_rel <= 1.0

