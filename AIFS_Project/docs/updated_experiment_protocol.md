# Updated Experiment Protocol

## 1. Overview and Chronological Structure
The experiment protocol evaluates residential electric vehicle charging under solar photovoltaic forecast uncertainty, real-world meteorological and demand telemetry, and bidirectional energy flows (E2G/E2H).

The 8,760 hourly intervals of the calendar year are strictly partitioned into four non-overlapping chronological blocks to eliminate future information leakage:
1. **Training Split**: Days 1–219 (2023-01-01 to 2023-08-07, 60% of data).
   - Used exclusively to train point forecasting models (`PersistenceForecaster` and `HistGradientBoostingRegressor`).
2. **Calibration Split**: Days 220–273 (2023-08-08 to 2023-09-30, 15% of data).
   - Used exclusively to compute absolute residuals and calibrate the finite-sample distribution-free Conformal Prediction quantile $\hat{q}_\alpha$ at nominal $1-\alpha = 0.90$.
3. **Validation Split**: Days 274–309 (2023-10-01 to 2023-11-05, 10% of data).
   - Used exclusively to select the optimal reliability switching threshold $\tau^* = 0.8283$ via grid search over empirical reliability quantiles, optimizing cost subject to zero deadline violations.
4. **Test Split**: Days 310–365 (2023-11-06 to 2023-12-31, 56 continuous days, 15% of data).
   - Frozen test set on which all benchmark controllers, stress tests, sensitivity sweeps, and bidirectional scenarios are evaluated.

---

## 2. Benchmark Controllers Evaluated
- **B1 (Fixed Schedule)**: Uniform power draw across all available connection hours.
- **B2 (Cheapest Hours)**: Greedy sort of connection hours by tariff ascending; charges at $P_{\max}$ during the lowest price intervals.
- **B3 (Forecast-Driven LP)**: Cost-minimizing linear program using day-ahead point solar forecast $\hat{G}_t$.
- **B4 (Proposed Reliability-Aware Controller)**: Switches between B3 (if horizon reliability index $\bar{r} \ge \tau^*$) and B5 (if $\bar{r} < \tau^*$).
- **B5 (Conservative Fallback)**: Cost-minimizing LP assuming zero future solar generation ($\hat{G}_t \equiv 0$).
- **B6 (Perfect Oracle)**: Benchmark linear program using ground-truth realized solar generation $G_t$.

---

## 3. Bidirectional Operating Scenarios (S1 through S4)
- **Scenario S1 (Baseline Unidirectional)**: Ordinary EV charging (G2V / PV2EV); discharging disabled ($\mathbb{I}_{\text{E2H}}=0, \mathbb{I}_{\text{E2G}}=0$).
- **Scenario S2 (E2H-Only Peak Shaving)**: EV discharges to offset domestic demand during peak tariff periods ($p_{\text{e2h}} \le \max(0, L_t - G_t)$); grid export disabled ($\mathbb{I}_{\text{E2H}}=1, \mathbb{I}_{\text{E2G}}=0$).
- **Scenario S3 (E2G-Only Grid Export)**: EV discharges surplus energy across the utility revenue meter for export compensation ($p_{\text{e2g}} \le P_{d, \max}$); domestic load offset disabled ($\mathbb{I}_{\text{E2H}}=0, \mathbb{I}_{\text{E2G}}=1$).
- **Scenario S4 (Combined Bidirectional)**: Both E2H and E2G simultaneously enabled under combined inverter rating limits ($p_{\text{e2h}} + p_{\text{e2g}} \le a_t \cdot P_{d, \max}$).

---

## 4. Controlled Sensitivity Sweeps
- **Stress Testing (Experiment C)**: Controlled perturbations (low, moderate, high, correlated noise, and sudden cloud regime shifts) across 5 random seeds.
- **Threshold Sensitivity (Experiment D)**: Sweeping $\tau \in [0.50, 0.95]$ across test days.
- **EV Demand Sensitivity (Experiment E)**: Sweeping session demand $E_{\text{req}} \in [10, 15, 20, 25, 30]\text{ kWh}$.
- **Tariff Structure Sensitivity (Experiment F)**: Comparing TOU rate against uniform flat retail tariff (\$0.15/kWh).
- **Ablation Study (Experiment G)**: Evaluating rule contributions with confidence awareness toggled on/off.
