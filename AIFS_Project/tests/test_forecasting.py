"""
Unit tests for forecasting models (persistence and histogram gradient boosting).
"""

import numpy as np
import pandas as pd
import pytest

from src.forecasting import PersistenceForecaster, MLForecaster, evaluate_forecast, fit_forecaster


@pytest.fixture
def sample_pv_data():
    idx = pd.date_range("2023-01-01", periods=24 * 30, freq="h", tz="UTC")
    # Simple synthetic daily pattern
    hours = idx.hour.values
    pv = np.maximum(0.0, 4.0 * np.sin(np.pi * (hours - 6) / 12))
    pv = np.where((hours < 6) | (hours > 18), 0.0, pv)
    return pd.DataFrame({"pv_generation_kw": pv}, index=idx)


def test_persistence_forecaster(sample_pv_data):
    train_df = sample_pv_data.iloc[: 24 * 20]
    test_idx = sample_pv_data.iloc[24 * 20 : 24 * 25].index

    f = PersistenceForecaster(lag_days=1)
    f.fit(train_df)
    preds = f.predict(test_idx, sample_pv_data)

    assert len(preds) == len(test_idx)
    assert (preds >= 0.0).all()


def test_ml_forecaster(sample_pv_data):
    train_df = sample_pv_data.iloc[: 24 * 20]
    test_idx = sample_pv_data.iloc[24 * 20 : 24 * 25].index

    config = {
        "max_iter": 50,
        "max_depth": 3,
        "learning_rate": 0.1,
        "random_state": 42,
    }
    f = MLForecaster(config)
    f.fit(train_df)
    preds = f.predict(test_idx, sample_pv_data)

    assert len(preds) == len(test_idx)
    assert (preds >= 0.0).all()
    # Night hours predicted as zero
    night_mask = (test_idx.hour < 5) | (test_idx.hour > 19)
    assert np.all(preds[night_mask] <= 0.1)


def test_evaluate_forecast():
    actual = np.array([0.0, 1.0, 2.0, 3.0, 0.0])
    pred = np.array([0.0, 1.2, 1.8, 3.1, 0.1])
    metrics = evaluate_forecast(actual, pred)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "mbe" in metrics
    assert metrics["mae"] >= 0.0

