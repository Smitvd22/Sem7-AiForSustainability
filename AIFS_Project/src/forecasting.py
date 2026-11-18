"""
PV Forecasting Models for Reliability-Aware EV Charging Scheduling.

This module implements persistence-based and ML-based solar PV generation
forecasters, along with evaluation utilities.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class PersistenceForecaster:
    """Naive persistence forecaster that predicts PV output based on the same
    hour from ``lag_days`` days ago.

    If the lagged day is unavailable, the most recent available day at the
    same hour is used instead.
    """

    def __init__(self, lag_days: int = 1) -> None:
        """Initialise the persistence forecaster.

        Parameters
        ----------
        lag_days : int
            Number of days to look back (default 1 = yesterday).
        """
        self.lag_days = lag_days
        self.train_data_: pd.DataFrame | None = None

    def fit(self, train_data: pd.DataFrame) -> "PersistenceForecaster":
        """Store the training history used for look-ups during prediction.

        Parameters
        ----------
        train_data : pd.DataFrame
            Must contain a ``pv_generation_kw`` column with a
            :class:`~pandas.DatetimeIndex`.

        Returns
        -------
        PersistenceForecaster
            The fitted forecaster (self).
        """
        self.train_data_ = train_data[["pv_generation_kw"]].copy()
        return self

    def predict(
        self, timestamps: pd.DatetimeIndex, history: pd.DataFrame
    ) -> np.ndarray:
        """Predict PV generation for each timestamp.

        For each requested timestamp the method returns the PV value from
        ``lag_days`` days ago at the same hour.  If that specific day is not
        present in *history*, the most recent earlier day with data at the
        same hour is used.

        Parameters
        ----------
        timestamps : pd.DatetimeIndex
            Target timestamps to forecast.
        history : pd.DataFrame
            Historical PV data with ``pv_generation_kw`` and a
            :class:`~pandas.DatetimeIndex`.

        Returns
        -------
        np.ndarray
            Predicted PV generation (kW), clipped to >= 0.
        """
        pv_series = history["pv_generation_kw"]
        predictions = np.zeros(len(timestamps), dtype=np.float64)

        for i, ts in enumerate(timestamps):
            target_hour = ts.hour
            # Primary: exact lag
            lagged_ts = ts - pd.Timedelta(days=self.lag_days)
            if lagged_ts in pv_series.index:
                predictions[i] = pv_series.loc[lagged_ts]
            else:
                # Fallback: most recent available day with the same hour
                candidates = pv_series[
                    (pv_series.index.hour == target_hour)
                    & (pv_series.index < ts)
                ]
                if len(candidates) > 0:
                    predictions[i] = candidates.iloc[-1]
                else:
                    predictions[i] = 0.0

        return np.clip(predictions, 0.0, None)


class MLForecaster:
    """Gradient-boosted regression forecaster for PV generation.

    Uses :class:`~sklearn.ensemble.HistGradientBoostingRegressor` with
    time-based and lag features engineered from historical PV data.
    """

    def __init__(self, config: dict) -> None:
        """Initialise the ML forecaster.

        Parameters
        ----------
        config : dict
            Parameters forwarded to
            :class:`~sklearn.ensemble.HistGradientBoostingRegressor`.
            Recognised keys include ``max_iter``, ``max_depth``,
            ``learning_rate``, ``min_samples_leaf``, etc.
        """
        model_params = {
            k: v
            for k, v in config.items()
            if k
            in {
                "max_iter",
                "max_depth",
                "learning_rate",
                "min_samples_leaf",
                "l2_regularization",
                "max_leaf_nodes",
                "random_state",
            }
        }
        self.model = HistGradientBoostingRegressor(**model_params)
        self.feature_columns_: list[str] | None = None

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    @staticmethod
    def _create_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create time-based and lag features from historical PV data.

        All features are computed from **past data only** to prevent data
        leakage.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain ``pv_generation_kw`` with a
            :class:`~pandas.DatetimeIndex`.

        Returns
        -------
        pd.DataFrame
            Feature matrix with columns:
            ``hour``, ``day_of_year``, ``pv_lag_1d``, ``pv_lag_2d``,
            ``pv_lag_7d``, ``pv_rolling_3d_mean``, ``pv_rolling_7d_mean``,
            ``is_weekend``.
        """
        features = pd.DataFrame(index=df.index)

        # Time-based features
        features["hour"] = df.index.hour
        features["day_of_year"] = df.index.dayofyear
        features["is_weekend"] = df.index.dayofweek.isin([5, 6]).astype(int)

        # Lag features (shift by number of periods corresponding to days,
        # assuming hourly data → 24 periods per day)
        pv = df["pv_generation_kw"]
        features["pv_lag_1d"] = pv.shift(24)
        features["pv_lag_2d"] = pv.shift(48)
        features["pv_lag_7d"] = pv.shift(168)

        # Rolling mean of daily PV over last N days.
        # We first compute a daily total, then roll, then map back.
        daily_pv = pv.resample("D").mean()
        rolling_3d = daily_pv.shift(1).rolling(window=3, min_periods=1).mean()
        rolling_7d = daily_pv.shift(1).rolling(window=7, min_periods=1).mean()

        # Map daily rolling values back to hourly index
        date_index = pd.Series(df.index.date, index=df.index)
        features["pv_rolling_3d_mean"] = date_index.map(
            pd.Series(rolling_3d.values, index=rolling_3d.index.date)
        ).values
        features["pv_rolling_7d_mean"] = date_index.map(
            pd.Series(rolling_7d.values, index=rolling_7d.index.date)
        ).values

        return features

    # ------------------------------------------------------------------
    # Training & inference
    # ------------------------------------------------------------------

    def fit(self, train_data: pd.DataFrame) -> "MLForecaster":
        """Fit the model on training data.

        Rows with NaN features (produced by lag computation at the start of
        the series) are dropped before fitting.

        Parameters
        ----------
        train_data : pd.DataFrame
            Training data with ``pv_generation_kw`` and a
            :class:`~pandas.DatetimeIndex`.

        Returns
        -------
        MLForecaster
            The fitted forecaster (self).
        """
        features = self._create_features(train_data)
        target = train_data["pv_generation_kw"]

        # Align & drop NaNs
        combined = features.join(target)
        combined = combined.dropna()

        self.feature_columns_ = [c for c in features.columns]
        X = combined[self.feature_columns_].values
        y = combined["pv_generation_kw"].values

        self.model.fit(X, y)
        return self

    def predict(
        self, timestamps: pd.DatetimeIndex, history: pd.DataFrame
    ) -> np.ndarray:
        """Predict PV generation for the requested timestamps.

        Parameters
        ----------
        timestamps : pd.DatetimeIndex
            Target timestamps.
        history : pd.DataFrame
            Historical data used to compute lag/rolling features.

        Returns
        -------
        np.ndarray
            Predicted PV generation (kW), clipped to >= 0.
        """
        # Build a combined frame covering history + target timestamps so
        # that lag features can be computed for the target rows.
        hist = history[["pv_generation_kw"]].copy()

        # Add placeholder rows for target timestamps not already in history
        new_idx = timestamps.difference(hist.index)
        if len(new_idx) > 0:
            placeholder = pd.DataFrame(
                {"pv_generation_kw": np.nan}, index=new_idx
            )
            hist = pd.concat([hist, placeholder]).sort_index()
            # Remove any duplicate index entries, keeping the first (real data)
            hist = hist[~hist.index.duplicated(keep="first")]

        features = self._create_features(hist)
        X = features.loc[timestamps, self.feature_columns_].values

        predictions = self.model.predict(X)
        return np.clip(predictions, 0.0, None)


# ======================================================================
# Evaluation
# ======================================================================


def evaluate_forecast(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Compute standard forecast evaluation metrics.

    Parameters
    ----------
    actual : np.ndarray
        Ground-truth PV generation values.
    predicted : np.ndarray
        Forecasted PV generation values.

    Returns
    -------
    dict
        Dictionary with keys ``mae``, ``rmse``, ``mbe``, ``r2``.
    """
    actual = np.asarray(actual, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)

    mae = mean_absolute_error(actual, predicted)
    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
    mbe = float(np.mean(predicted - actual))
    r2 = r2_score(actual, predicted)

    return {"mae": mae, "rmse": rmse, "mbe": mbe, "r2": r2}


# ======================================================================
# Factory / wrapper helpers
# ======================================================================


def fit_forecaster(train_data: pd.DataFrame, config: dict) -> object:
    """Factory function that creates and fits the appropriate forecaster.

    Parameters
    ----------
    train_data : pd.DataFrame
        Training data with ``pv_generation_kw`` and a
        :class:`~pandas.DatetimeIndex`.
    config : dict
        Must contain a ``model_type`` key (``"persistence"`` or ``"ml"``).
        Remaining keys are forwarded to the chosen forecaster.

    Returns
    -------
    object
        A fitted forecaster instance.
    """
    model_type = config.get("model_type", "persistence")

    if model_type == "persistence":
        lag_days = config.get("lag_days", 1)
        forecaster = PersistenceForecaster(lag_days=lag_days)
    elif model_type == "ml":
        forecaster = MLForecaster(config)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    return forecaster.fit(train_data)


def predict_pv(
    model: object,
    history: pd.DataFrame,
    timestamps: pd.DatetimeIndex,
    config: dict,
) -> np.ndarray:
    """Wrapper that calls the model's predict method.

    Parameters
    ----------
    model : object
        A fitted forecaster with a ``predict`` method.
    history : pd.DataFrame
        Historical PV data.
    timestamps : pd.DatetimeIndex
        Timestamps to forecast.
    config : dict
        Additional configuration (reserved for future use).

    Returns
    -------
    np.ndarray
        Predicted PV generation (kW).
    """
    return model.predict(timestamps, history)
