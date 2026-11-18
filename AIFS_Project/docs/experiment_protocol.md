# Experimental Protocol and Chronological Partitions

## 1. Frozen Chronological Splitting Protocol
To strictly prevent data leakage and lookahead bias, the 365 days of chronological data are partitioned on whole-day boundaries as follows:

| Split Role | Date Range | Duration (Days) | Fraction | Purpose |
|---|---|---|---|---|
| **Training** | 2023-01-01 to 2023-08-07 | 219 days | 60.0% | Fit ML forecaster & persistence models |
| **Calibration** | 2023-08-08 to 2023-09-30 | 54 days | 15.0% | Calibrate conformal prediction quantile $\hat{q}_\alpha$ on out-of-sample residuals |
| **Validation** | 2023-10-01 to 2023-11-05 | 36 days | 10.0% | Tune reliability threshold $\tau^*$ via grid search |
| **Test** | 2023-11-06 to 2023-12-31 | 56 days | 15.0% | Final out-of-sample benchmark of controllers B1–B6 |

**Strict Isolation Rule**: Test observations never enter feature extraction, model fitting, interval calibration, or threshold selection.

---

## 2. Controller Benchmarking Suite
All six controllers are evaluated over the identical 56 test days with identical physical inputs ($G_t$, $L_t$, $c_t$, $a_t$, EV initial state):

1. **Controller B1 (Fixed Schedule)**: Distributes required energy evenly across available connection intervals.
2. **Controller B2 (Cheapest Hours)**: Allocates charging to the lowest-priced available intervals without PV awareness.
3. **Controller B3 (Forecast-Driven Optimization)**: Minimizes cost using point PV forecasts without error checking.
4. **Controller B4 (Proposed Reliability-Aware Switching)**: Evaluates horizon reliability $\bar{r}$; switches to B3 if $\bar{r} \ge \tau^*$, else switches to B5 fallback.
5. **Controller B5 (Conservative Fallback)**: Solves cost-minimization assuming zero future solar generation.
6. **Controller B6 (Perfect-Forecast Oracle)**: Solves cost-minimization using future actual solar generation (ideal reference).

---

## 3. Experiment Groups
- **Exp A**: Forecast and uncertainty calibration (persistence vs ML, conformal coverage).
- **Exp B**: Main controller comparison (cost, deadline misses, peak load, solar utilization).
- **Exp C**: Synthetic error stress testing (low, moderate, high, correlated, regime shift).
- **Exp D**: Threshold sensitivity on test split ($\tau \in [0.55, 0.95]$).
- **Exp E**: EV demand sensitivity ($E_{\text{req}} \in [10, 30]\text{ kWh}$).
- **Exp F**: Tariff sensitivity (Time-of-Use vs Flat rate).
- **Exp G**: Ablation study (evaluating individual mechanism contributions).

