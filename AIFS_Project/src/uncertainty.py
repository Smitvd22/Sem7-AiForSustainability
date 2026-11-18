"""
Uncertainty Quantification via Split Conformal Prediction.

This module implements conformal prediction intervals and reliability
scoring for the Reliability-Aware EV Charging Scheduling project.
"""

import numpy as np
from scipy import stats


class ConformalPredictor:
    """Split conformal predictor that wraps a point forecaster with
    distribution-free prediction intervals.

    Uses the finite-sample-valid quantile of calibration residuals to
    construct marginal coverage guarantees.
    """

    def __init__(self, nominal_coverage: float = 0.90) -> None:
        """Initialise the conformal predictor.

        Parameters
        ----------
        nominal_coverage : float
            Target coverage probability, e.g. 0.90 for 90 % intervals.
        """
        self.nominal_coverage = nominal_coverage
        self.q_alpha_: float | None = None
        self.calibration_residuals_: np.ndarray | None = None

    def calibrate(
        self, actual: np.ndarray, predicted: np.ndarray
    ) -> "ConformalPredictor":
        """Calibrate the predictor on a held-out calibration set.

        Computes absolute residuals and determines the conformal quantile
        using the finite-sample correction:

        .. math::

            q_{\\alpha} = \\text{Quantile}\\bigl(
                r_1, \\ldots, r_n;\\;
                \\lceil (n+1)(1-\\alpha) \\rceil / n
            \\bigr)

        Parameters
        ----------
        actual : np.ndarray
            Ground-truth values on the calibration set.
        predicted : np.ndarray
            Point-forecast values on the calibration set.

        Returns
        -------
        ConformalPredictor
            The calibrated predictor (self).
        """
        actual = np.asarray(actual, dtype=np.float64)
        predicted = np.asarray(predicted, dtype=np.float64)

        residuals = np.abs(actual - predicted)
        self.calibration_residuals_ = residuals

        n = len(residuals)
        alpha = 1.0 - self.nominal_coverage

        # Finite-sample correction for the quantile level
        quantile_level = np.ceil((n + 1) * (1.0 - alpha)) / n
        # Clip to [0, 1] in case of tiny calibration sets
        quantile_level = float(np.clip(quantile_level, 0.0, 1.0))

        self.q_alpha_ = float(np.quantile(residuals, quantile_level))

        return self

    def predict_interval(
        self,
        point_forecast: np.ndarray,
        pv_capacity: float | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Construct prediction intervals around point forecasts.

        Parameters
        ----------
        point_forecast : np.ndarray
            Point-forecast values.
        pv_capacity : float, optional
            Maximum PV capacity (kW).  If given, the upper bound is
            clipped to this value.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            ``(lower, upper)`` prediction interval bounds.

        Raises
        ------
        RuntimeError
            If :meth:`calibrate` has not been called.
        """
        if self.q_alpha_ is None:
            raise RuntimeError(
                "ConformalPredictor has not been calibrated. "
                "Call calibrate() first."
            )

        point_forecast = np.asarray(point_forecast, dtype=np.float64)
        lower = np.clip(point_forecast - self.q_alpha_, 0.0, None)
        upper = point_forecast + self.q_alpha_

        if pv_capacity is not None:
            upper = np.clip(upper, None, pv_capacity)

        return lower, upper

    def get_interval_width(
        self,
        point_forecast: np.ndarray,
        pv_capacity: float | None = None,
    ) -> np.ndarray:
        """Return the width of the prediction interval for each forecast.

        Parameters
        ----------
        point_forecast : np.ndarray
            Point-forecast values.
        pv_capacity : float, optional
            Maximum PV capacity (kW).

        Returns
        -------
        np.ndarray
            Interval widths (upper − lower).
        """
        lower, upper = self.predict_interval(point_forecast, pv_capacity)
        return upper - lower


# ======================================================================
# Reliability scoring
# ======================================================================


def compute_reliability(
    interval_width: np.ndarray, scale: float
) -> np.ndarray:
    """Compute per-timestep reliability scores.

    .. math::

        r_t = 1 - \\text{clip}\\bigl(w_t \\,/\\, s,\\; 0,\\; 1\\bigr)

    A narrower interval (relative to *scale*) yields a higher reliability
    score (closer to 1).

    Parameters
    ----------
    interval_width : np.ndarray
        Prediction-interval widths for each timestep.
    scale : float
        Normalisation constant (e.g. PV system capacity in kW).

    Returns
    -------
    np.ndarray
        Reliability scores in [0, 1].
    """
    interval_width = np.asarray(interval_width, dtype=np.float64)
    normalised = np.clip(interval_width / scale, 0.0, 1.0)
    return 1.0 - normalised


def compute_horizon_reliability(
    interval_widths: np.ndarray, scale: float
) -> float:
    """Compute the mean reliability across a scheduling horizon.

    Parameters
    ----------
    interval_widths : np.ndarray
        Prediction-interval widths for each timestep in the horizon.
    scale : float
        Normalisation constant.

    Returns
    -------
    float
        Mean reliability score over the horizon.
    """
    return float(np.mean(compute_reliability(interval_widths, scale)))


# ======================================================================
# Interval evaluation
# ======================================================================


def evaluate_intervals(
    actual: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> dict:
    """Evaluate the quality of prediction intervals.

    Parameters
    ----------
    actual : np.ndarray
        Ground-truth values.
    lower : np.ndarray
        Lower bounds of the prediction intervals.
    upper : np.ndarray
        Upper bounds of the prediction intervals.

    Returns
    -------
    dict
        Dictionary with keys:
        - ``coverage``: fraction of actuals within [lower, upper].
        - ``mean_width``: mean interval width.
        - ``median_width``: median interval width.
        - ``coverage_by_quantile``: dict mapping quantile labels to
          coverage within each quartile of the point-forecast
          distribution (only if >= 8 samples).
    """
    actual = np.asarray(actual, dtype=np.float64)
    lower = np.asarray(lower, dtype=np.float64)
    upper = np.asarray(upper, dtype=np.float64)

    covered = (actual >= lower) & (actual <= upper)
    widths = upper - lower

    result: dict = {
        "coverage": float(np.mean(covered)),
        "mean_width": float(np.mean(widths)),
        "median_width": float(np.median(widths)),
    }

    # Coverage broken down by quartiles of the midpoint forecast
    if len(actual) >= 8:
        midpoints = (lower + upper) / 2.0
        quartile_edges = np.percentile(midpoints, [25, 50, 75])
        labels = ["Q1 (0-25%)", "Q2 (25-50%)", "Q3 (50-75%)", "Q4 (75-100%)"]
        masks = [
            midpoints <= quartile_edges[0],
            (midpoints > quartile_edges[0]) & (midpoints <= quartile_edges[1]),
            (midpoints > quartile_edges[1]) & (midpoints <= quartile_edges[2]),
            midpoints > quartile_edges[2],
        ]
        coverage_by_q: dict[str, float] = {}
        for label, mask in zip(labels, masks):
            if mask.sum() > 0:
                coverage_by_q[label] = float(np.mean(covered[mask]))
        result["coverage_by_quantile"] = coverage_by_q

    return result


# ======================================================================
# Factory / wrapper helpers
# ======================================================================


def calibrate_intervals(
    model: object,
    calibration_data: "pd.DataFrame",  # noqa: F821 – forward ref to pandas
    config: dict,
) -> ConformalPredictor:
    """Factory that calibrates a :class:`ConformalPredictor` using a
    fitted forecaster and a calibration dataset.

    Parameters
    ----------
    model : object
        A fitted forecaster with a ``predict`` method.
    calibration_data : pd.DataFrame
        Calibration split with ``pv_generation_kw`` and a
        :class:`~pandas.DatetimeIndex`.
    config : dict
        Must contain ``nominal_coverage`` (float).  May also contain
        ``pv_capacity`` (float).

    Returns
    -------
    ConformalPredictor
        A calibrated conformal predictor.
    """
    import pandas as pd  # deferred to keep top-level imports lightweight

    actual = calibration_data["pv_generation_kw"].values
    timestamps = calibration_data.index
    if not isinstance(timestamps, pd.DatetimeIndex):
        timestamps = pd.DatetimeIndex(timestamps)

    predicted = model.predict(timestamps, calibration_data)

    coverage = config.get("nominal_coverage", 0.90)
    cp = ConformalPredictor(nominal_coverage=coverage)
    cp.calibrate(actual, predicted)

    return cp


def predict_interval(
    model: object,
    uncertainty_model: ConformalPredictor,
    inputs: "pd.DataFrame",  # noqa: F821
    config: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Wrapper that produces point forecasts and prediction intervals.

    Parameters
    ----------
    model : object
        A fitted forecaster with a ``predict`` method.
    uncertainty_model : ConformalPredictor
        A calibrated :class:`ConformalPredictor`.
    inputs : pd.DataFrame
        Historical data used for feature computation.
    config : dict
        Must contain ``timestamps`` (:class:`~pandas.DatetimeIndex`).
        May contain ``pv_capacity`` (float).

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        ``(point_forecast, lower, upper)``.
    """
    import pandas as pd  # deferred import

    timestamps = config["timestamps"]
    if not isinstance(timestamps, pd.DatetimeIndex):
        timestamps = pd.DatetimeIndex(timestamps)

    point_forecast = model.predict(timestamps, inputs)
    pv_capacity = config.get("pv_capacity", None)
    lower, upper = uncertainty_model.predict_interval(
        point_forecast, pv_capacity=pv_capacity
    )

    return point_forecast, lower, upper
