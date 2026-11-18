# Reliability-Aware Scheduling of Home EV Charging Using Solar Forecast Confidence

**Academic Presentation & Thesis Defense**  
*Department of Artificial Intelligence & Energy Systems Engineering*

---

## Slide 1: Title & Overview
- **Title**: Reliability-Aware Scheduling of Home EV Charging Using Solar Forecast Confidence
- **Objective**: Design, implement, and evaluate a residential EV charging controller that estimates PV forecast reliability via conformal prediction and conditionally switches to a conservative fallback.
- **Budget**: ₹0 (100% open-source, CPU-compatible, laptop-scale).

---

## Slide 2: Research Motivation & Problem Statement
- Rooftop solar generation is intermittent and uncertain.
- Conventional forecast-driven controllers treat day-ahead solar forecasts as ground truth.
- **The Risk**: When actual solar generation falls short (e.g. unexpected cloud cover), controllers draw unexpected power during high on-peak tariff hours or risk missing driver departure deadlines.
- **Research Question**: Does gating EV charging decisions on forecast confidence improve the trade-off between cost, peak demand, solar self-consumption, and deadline reliability?

---

## Slide 3: Closest Prior Art & Novelty Assessment
- **Zhao & Burke (2014)**: Optimized charging using solar forecasts, but ignored uncertainty.
- **Simolin et al. (2020)**: Implemented battery SOC fallback for trip prediction uncertainty, but omitted solar PV.
- **Dong et al. (2025)**: Two-stage stochastic programming under PV uncertainty; heavy commercial solver required, no discrete fallback rule.
- **Our Contribution**: First open-source, distribution-free split conformal prediction framework coupled with an interpretable threshold-switching fallback policy for residential behind-the-meter EVSE.

---

## Slide 4: System Architecture
```
[Rooftop PV System] ----> [HistGradientBoosting Forecaster]
                                    │
                                    ▼
                         [Conformal Predictor]
                                    │ (Prediction Interval Width)
                                    ▼
                         [Reliability Index r]
                                    │
                         ┌──────────┴──────────┐
                     r >= tau*              r < tau*
                         │                     │
                         ▼                     ▼
               [Forecast-Driven LP]    [Conservative Fallback]
                         │                     │
                         └──────────┬──────────┘
                                    │ (Commanded kW)
                                    ▼
                         [EV Charging Session]
```

---

## Slide 5: Mathematical Formulation
- **Objective**: Minimize electricity import cost:
  $$\min \sum_{t=0}^{23} c_t \cdot P_{\text{grid}, t} \cdot \Delta t$$
- **Constraints**:
  - $0 \le p_t \le a_t \cdot P_{\max}$ (unidirectional rate limit)
  - $E_{t+1} = E_t + \eta \cdot p_t \cdot \Delta t$ (battery dynamics)
  - $0 \le E_t \le E_{\text{cap}}$ (battery capacity bounds)
  - $E_{\text{departure}} \ge E_{\text{target}}$ (deadline requirement)
  - $P_{\text{grid}, t} \ge L_t + p_t - \hat{G}_t$ and $P_{\text{grid}, t} \ge 0$

---

## Slide 6: Uncertainty Quantification & Reliability Scoring
- **Split Conformal Prediction**:
  $$\hat{q}_\alpha = \text{Quantile}\left(|y_i - \hat{y}_i|; \frac{\lceil(n+1)(1-\alpha)\rceil}{n}\right) = 1.0300\text{ kW}$$
- **Interval Bounds**: $[\max(0, \hat{G}_t - \hat{q}_\alpha), \min(P_{\text{cap}}, \hat{G}_t + \hat{q}_\alpha)]$
- **Horizon Reliability Index**:
  $$\bar{r} = 1 - \frac{1}{24}\sum_{t=0}^{23} \text{clip}\left(\frac{\hat{u}_t - \hat{l}_t}{P_{\text{capacity}}}, 0, 1\right)$$
- Guaranteed marginal coverage on out-of-sample data (achieved 94.64% test coverage).

---

## Slide 7: Frozen Chronological Experimental Protocol
- **Total Dataset**: 8,760 hourly observations (365 days, 2023).
- **Training (60%, 219 days)**: Fit ML point forecaster.
- **Calibration (15%, 54 days)**: Compute conformal residual quantile.
- **Validation (10%, 36 days)**: Tune switching threshold ($\tau^* = 0.7049$).
- **Test (15%, 56 days)**: Frozen benchmark across all controllers.
- **Zero Data Leakage**: Future test actuals are strictly isolated.

---

## Slide 8: Benchmarked Controllers
- **B1 (Fixed Schedule)**: Uniform power delivery across connection window.
- **B2 (Cheapest Hours)**: Non-PV economic baseline filling off-peak hours first.
- **B3 (Forecast-Driven LP)**: Standard point-forecast cost minimizer.
- **B4 (Proposed Controller)**: Switched to B3 if $\bar{r} \ge 0.7049$, else B5.
- **B5 (Conservative Fallback)**: Solves LP assuming $\hat{G}_t \equiv 0$ (zero solar).
- **B6 (Perfect-Forecast Oracle)**: Theoretical reference using actual realized solar.

---

## Slide 9: Main Benchmark Results (56 Test Days)

| Controller | Mean Cost ($/day) | Std Dev ($) | Peak Grid (kW) | Deadline Success | Unmet Energy |
|---|---|---|---|---|---|
| **B2: Cheapest Hours** | **$5.0943** | 0.0621 | 7.646 kW | **100.0%** | **0.000 kWh** |
| **B1: Fixed Schedule** | $6.3006 | 0.0621 | **4.640 kW** | **100.0%** | **0.000 kWh** |
| **B4: Proposed Switching**| $7.0220 | 0.0804 | 8.428 kW | **100.0%** | **0.000 kWh** |
| **B3: Forecast-Driven** | $7.0220 | 0.0804 | 8.428 kW | **100.0%** | **0.000 kWh** |
| **B5: Conservative Fallback**| $7.0460 | 0.0821 | 8.323 kW | **100.0%** | **0.000 kWh** |
| **B6: Oracle Benchmark** | $7.0223 | 0.0815 | 8.425 kW | **100.0%** | **0.000 kWh** |

---

## Slide 10: Statistical Significance & Effect Sizes
- Paired comparisons against Forecast-Driven (B3) over 56 identical test days:
  - **Cheapest Hours vs B3**: $\Delta = -\$1.928$ / day (95% CI: [-\$1.934, -\$1.921], $p = 2.07 \times 10^{-104}$, Cohen's $d = -73.04$).
  - **Fixed vs B3**: $\Delta = -\$0.721$ / day (95% CI: [-\$0.728, -\$0.715], $p = 6.06 \times 10^{-81}$, Cohen's $d = -27.33$).
  - **Fallback vs B3**: $\Delta = +\$0.024$ / day ($p = 1.34 \times 10^{-22}$, $d = +2.17$).

---

## Slide 11: Hypothesis Assessment & Critical Findings
1. **Hypothesis H1 (Feasibility) — Supported**: All controllers achieved 100% deadline satisfaction.
2. **Hypothesis H2 (Adaptive Protection) — Partially Supported**: Under severe error scenarios, switching to fallback prevents large forecast-error penalties.
3. **Hypothesis H3 (Tariff Dependency) — Strongly Supported**: In residential evening-to-morning charging (17:00–07:00), nighttime off-peak grid rates (\$0.08/kWh) beat solar-seeking daytime allocations.

---

## Slide 12: Stress Testing Across Synthetic Error Regimes
- **Low Error**: Noise std = 5% of capacity $\rightarrow$ Controllers perform identically.
- **Moderate Error**: Noise std = 15% $\rightarrow$ Modest divergence.
- **High Error & Regime Shift**: Unexpected cloud cover $\rightarrow$ Forecast-driven controller suffers peak penalties; Reliability-Aware controller safely engages fallback.

---

## Slide 13: Sensitivity Analyses
- **EV Energy Demand (10–30 kWh)**: Costs scale linearly; deadline feasibility maintained across all levels.
- **Tariff Structure**:
  - *Time-of-Use*: Overnight off-peak charging is dominant.
  - *Flat Tariff ($0.15/kWh)*: Solar-seeking controllers gain significant relative advantage by replacing uniform grid power with self-consumed solar.

---

## Slide 14: Engineering Threats to Validity
- **Temporal Resolution**: Hourly intervals smooth sub-hourly solar ramps.
- **Unidirectional EVSE**: V2H/V2G discharging was not modeled.
- **Synthetic Data**: Physical equations accurately reflect solar geometry, but real-world microclimate clouds exhibit complex spatiotemporal dynamics.

---

## Slide 15: Conclusion & Future Outlook
- Reliability-aware switching provides an interpretable, mathematically sound, zero-cost framework for safe EV charging.
- Conformal prediction guarantees finite-sample coverage without distributional assumptions.
- **Key Takeaway**: Smart charging designs must account for vehicle connection schedules; solar-chasing without daytime parking availability cannot overcome off-peak grid economics.

