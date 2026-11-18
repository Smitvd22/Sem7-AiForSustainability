"""
Unit tests for numerical reproducibility and seed stability.
"""

import numpy as np
import pytest

from src.data import generate_synthetic_pv, generate_synthetic_load
from src.forecasting import MLForecaster


def test_data_generation_reproducible_with_seed():
    cfg1 = {"seed": 1234, "pv_capacity_kw": 5.0, "latitude": 35.0, "year": 2023}
    cfg2 = {"seed": 1234, "pv_capacity_kw": 5.0, "latitude": 35.0, "year": 2023}

    df1 = generate_synthetic_pv(cfg1)
    df2 = generate_synthetic_pv(cfg2)

    assert np.allclose(df1["pv_generation_kw"].values, df2["pv_generation_kw"].values)

    load1 = generate_synthetic_load(cfg1)
    load2 = generate_synthetic_load(cfg2)

    assert np.allclose(load1["load_kw"].values, load2["load_kw"].values)


def test_ml_forecaster_reproducible():
    rng = np.random.RandomState(42)
    X = rng.normal(size=(100, 5))
    y = X[:, 0] * 2 + rng.normal(size=100) * 0.1

    cfg1 = {"random_state": 42, "max_iter": 50}
    cfg2 = {"random_state": 42, "max_iter": 50}

    from sklearn.ensemble import HistGradientBoostingRegressor
    m1 = HistGradientBoostingRegressor(**cfg1).fit(X, y)
    m2 = HistGradientBoostingRegressor(**cfg2).fit(X, y)

    preds1 = m1.predict(X)
    preds2 = m2.predict(X)

    assert np.allclose(preds1, preds2)

