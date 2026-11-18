# Existing Project Audit: Reliability-Aware EV Charging Research

## 1. Actual Repository Structure
The project repository is structured as a modular Python package adhering to clean research software engineering standards:
```
AIFS_Project/
├── configs/
│   └── default.json             # Central configuration (data, splits, EV, tariffs, forecasting, uncertainty, errors, etc.)
├── data/
│   ├── raw/                     # Directory for unprocessed source files
│   └── processed/               # Processed hourly datasets (pv.csv, load.csv, tariff.csv, splits.json, metadata.json)
├── docs/                        # Research design, protocol, mathematical model, and review documents
├── notebooks/
│   └── 01_exploration_and_demo.ipynb
├── paper/
│   ├── figures/                 # fig1 through fig9 (PNG format)
│   ├── tables/                  # table5, table6, table6b, table7, table8, table8b, table8c, table8d (CSV format)
│   ├── main.tex                 # IEEE conference template research paper
│   ├── references.bib           # BibTeX references
│   └── DraftedPaper.pdf         # Compiled baseline IEEE paper PDF
├── presentation/                # Slides and defense questions
├── references/                  # Literature audit matrix and BibTeX
├── results/
│   ├── figures/                 # Generated publication figures
│   ├── logs/                    # experiment.log, manifest.json, completion_checklist.json
│   ├── processed/               # Aggregated experiment JSONs & daily results CSV
│   ├── raw/                     # Raw daily simulation dictionaries
│   └── tables/                  # Generated CSV tables
├── src/
│   ├── __init__.py
│   ├── cli.py                   # Command-line entry points
│   ├── data.py                  # Data loading and synthetic generation
│   ├── experiments.py           # Experiment orchestration (Exp A through G)
│   ├── forecasting.py           # Persistence and HistGradientBoosting forecasters
│   ├── metrics.py               # Energy, economic, and forecast accuracy metrics
│   ├── plotting.py              # Publication-quality matplotlib/seaborn plots
│   ├── preprocessing.py         # Data validation, cleaning, and quality reporting
│   ├── reporting.py             # Manifest, checklist, and LaTeX table generators
│   ├── scheduler.py             # LP and rule-based EV charging controllers (B1–B6)
│   ├── simulation.py            # Hourly physical energy simulation engine
│   ├── statistics.py            # Paired t-tests, bootstrap CIs, Cohen's d, Wilcoxon
│   └── uncertainty.py           # Split conformal prediction and reliability index
├── tests/                       # 7 test files, 23 passing unit tests
├── baseline_backup/             # Safe snapshot of pre-modification repository state
├── requirements.txt             # Minimal dependencies specification
└── README.md                    # Project overview and CLI reproduction guide
```

---

## 2. Existing System Architecture
The existing architecture connects behind-the-meter rooftop solar PV, residential domestic load, an electric vehicle battery (Level 2 charger), and the electric grid under a Time-of-Use (TOU) tariff.
- The pipeline executes sequentially:
  1. Historical data ingestion & feature engineering.
  2. Four-way chronological split (Train, Calibration, Validation, Test).
  3. Point forecasting using Histogram Gradient Boosting.
  4. Distribution-free uncertainty calibration via Split Conformal Prediction.
  5. Horizon-level reliability score computation based on interval width normalized by system capacity.
  6. Out-of-sample threshold ($\tau^*$) grid search on the validation set.
  7. Day-ahead dispatch scheduling (Switching between Forecast-Driven LP and Conservative Zero-Solar Fallback).
  8. Physical simulation with ground-truth data, evaluating energy balances, grid imports, peak power, solar self-consumption, and departure deadlines.
  9. Statistical verification against baselines (Fixed, Cheapest Hours, Forecast-Driven, Fallback, Oracle).

---

## 3. Description of Each Important Module
- `src/data.py`: Generates synthetic 8,760-hour profiles for PV generation (clear-sky model with beta cloud attenuation), household load (dual-peak Gaussian model), and TOU tariff. Implements `load_dataset` and `create_splits`.
- `src/preprocessing.py`: Implements validation checks (NaNs, negative values, duplicates, range violations) and data cleaning with short-gap linear interpolation (≤ 3 hours).
- `src/forecasting.py`: Implements `PersistenceForecaster` and `MLForecaster` (`HistGradientBoostingRegressor`) with time and lag features (`hour`, `day_of_year`, `pv_lag_1d`, `pv_lag_2d`, `pv_lag_7d`, `pv_rolling_3d_mean`, `pv_rolling_7d_mean`, `is_weekend`).
- `src/uncertainty.py`: Implements `ConformalPredictor` computing the finite-sample adjusted non-conformity quantile $q_\alpha$ and horizon reliability $\bar{r} = 1 - \frac{1}{T}\sum \text{clip}(w_t / P_{\text{cap}}, 0, 1)$.
- `src/scheduler.py`: Contains linear programming models (`scipy.optimize.linprog` with HiGHS solver) for controllers B1 (Fixed), B2 (Cheapest Hours), B3 (Forecast-Driven), B4 (Reliability-Aware Switching), B5 (Conservative Fallback), and B6 (Oracle).
- `src/simulation.py`: Simulates physical interval dynamics for each day, enforcing battery charging efficiency ($\eta = 0.90$), energy conservation, grid import calculation, export tracking, and departure deadline verification.
- `src/metrics.py`: Computes MAE, RMSE, MBE for forecasting, and daily cost, grid import, peak grid demand, PV-to-EV energy, solar self-consumption ratio, EV solar fraction, and deadline satisfaction for simulation.
- `src/statistics.py`: Implements paired two-sided t-tests, Wilcoxon signed-rank tests, bootstrap confidence intervals (1,000 resamples), Cohen's $d$, and Bonferroni corrections.
- `src/experiments.py`: Orchestrates the complete evaluation suite across experiments A through G.
- `src/plotting.py`: Generates publication figures fig1 through fig9.
- `src/reporting.py`: Generates LaTeX tables, summary CSVs, manifest, and completion checklist.
- `src/cli.py`: CLI dispatcher supporting `validate-data`, `train`, `run-experiments`, `analyze`, `build-paper`, and `run-all`.

---

## 4. Current Dataset Sources
Currently, the system generates synthetic hourly data:
- PV: Clear-sky sine envelope with latitude-dependent daylength and Beta(6, 2) cloud attenuation.
- Household Load: 0.5 kW base load + 1.5 kW morning peak + 2.5 kW evening peak + seasonal variation + Gaussian noise.
- Tariff: 3-tier Time-Of-Use ($0.08 off-peak, $0.12 mid-peak, $0.25 on-peak; export compensation $0.04/kWh).
- EV: 40 kWh battery, 10 kWh initial SOC, 20 kWh session demand (target 30 kWh), 7 kW Level 2 EVSE, arrival at 17:00, departure at 07:00.

---

## 5. Existing Synthetic Data Generation
All inputs are generated mathematically in `src/data.py` across 365 days (8,760 hours for calendar year 2023). While physically plausible and continuous, they do not reflect actual measured microclimatic intermittency, authentic residential smart-meter appliance spikes, or empirical EV charging session behavior.

---

## 6. Existing Forecasting and Uncertainty Methods
- Forecasting: Histogram-based Gradient Boosting regression (`HistGradientBoostingRegressor`, `max_iter=200`, `max_depth=5`, `learning_rate=0.1`).
- Uncertainty Quantification: Split Conformal Prediction with marginal coverage $1-\alpha = 0.90$. Calibration residuals are computed on the held-out calibration split (54 days).
- Reliability Index: Mean normalized interval width across the 24-hour horizon.
- Threshold Tuning: Grid search evaluated strictly on the validation split (36 days), selecting $\tau^* = 0.7049$ to minimize cost subject to zero deadline violations.

---

## 7. Existing Controller Implementations
- **B1 (Fixed)**: Uniform charging power across available connection hours.
- **B2 (Cheapest Hours)**: Greedy sort of available hours by tariff ascending; charges at $P_{\max}$ during the lowest price slots.
- **B3 (Forecast-Driven LP)**: Cost-minimizing linear program using point solar forecast $\hat{G}_t$.
- **B4 (Reliability-Aware Switching)**: If $\bar{r} \ge \tau^*$, dispatches B3; else dispatches B5.
- **B5 (Conservative Fallback)**: Cost-minimizing LP assuming zero future solar generation ($\hat{G}_t \equiv 0$).
- **B6 (Oracle)**: Cost-minimizing LP using actual realized solar generation $G_t$.

---

## 8. Existing Energy Accounting
- Interval Net Demand: $P_{\text{net}, t} = L_t + p_t - G_t$.
- Grid Import: $P_{\text{grid}, t} = \max(0, P_{\text{net}, t})$.
- Grid Export: $P_{\text{export}, t} = \max(0, -P_{\text{net}, t})$.
- Solar to EV: $PV_{\text{EV}, t} = \min(p_t, \max(0, G_t - L_t))$.
- Battery State: $E_{t+1} = \min(E_{\text{cap}}, E_t + \eta \cdot p_t \cdot \Delta t)$.
- Unidirectional flow only: The EV can only draw power ($p_t \ge 0$). Discharging to home (E2H/V2H) or grid (E2G/V2G) is not modeled.

---

## 9. Existing Experimental Protocol
Chronological splits across 365 days:
- Training: 2023-01-01 to 2023-08-07 (219 days, 60%).
- Calibration: 2023-08-08 to 2023-09-30 (54 days, 15%).
- Validation: 2023-10-01 to 2023-11-05 (36 days, 10%).
- Test: 2023-11-06 to 2023-12-31 (56 days, 15%).
Zero data leakage is preserved between splits. Threshold is frozen before test set evaluation.

---

## 10. Current Metrics
- Forecasting: MAE, RMSE, MBE, $R^2$.
- Intervals: Empirical Coverage, Mean Width, Median Width, Quartile-stratified coverage.
- Daily Simulation: Total Electricity Cost ($), Grid Import (kWh), Peak Grid Import (kW), Solar PV-to-EV (kWh), Solar Self-Consumption Ratio, EV Solar Ratio, Deadline Satisfaction Rate (%), Unmet Energy (kWh).
- Statistical: Paired mean differences, 95% bootstrap CIs, paired t-statistic and p-value, Cohen's $d$.

---

## 11. Existing Paper Structure
- IEEE Conference format (`IEEEtran.cls`), 2-column layout.
- Sections:
  I. Introduction (Problem context, research question, hypotheses H1–H3, contributions).
  II. Related Work.
  III. System Model and Problem Formulation.
  IV. Proposed Methodology.
  V. Experimental Setup.
  VI. Results (Forecasting, controller comparison, statistical tests, stress testing, sensitivity).
  VII. Discussion (Hypothesis verdicts, negative finding analysis).
  VIII. Limitations and Future Work.
  IX. Conclusion.
  References (11 cited papers).

---

## 12. Existing Figures and Tables
- Figures:
  - `fig1_system_architecture.png`
  - `fig2_pv_forecast_interval.png`
  - `fig3_forecast_error_dist.png`
  - `fig4_interval_calibration.png`
  - `fig5_daily_cost_by_controller.png`
  - `fig6_solar_contribution.png`
  - `fig7_peak_and_deadline.png`
  - `fig8_stress_test_comparison.png`
  - `fig9_threshold_sensitivity.png`
- Tables:
  - `table5_main_controller_comparison.csv`
  - `table6_statistical_vs_forecast_driven.csv`
  - `table6b_statistical_vs_cheapest_hours.csv`
  - `table7_ablation_results.csv`
  - `table8_stress_test_comparison.csv`
  - `table8b_threshold_sensitivity.csv`
  - `table8c_ev_demand_sensitivity.csv`
  - `table8d_tariff_sensitivity.csv`

---

## 13. Baseline Execution Status
- Test Suite: All 23 unit tests in `tests/` pass with zero failures (pytest 9.2.0, Python 3.12.10).
- CLI commands: `validate-data`, `train`, `run-experiments`, `analyze`, `build-paper` execute cleanly.
- Baseline Backup: Created in `baseline_backup/`.
- LaTeX Environment: No local `pdflatex` or `latexmk` binary is installed on Windows PATH. Existing compiled PDF `paper/DraftedPaper.pdf` exists.

---

## 14. Problems and Gaps Identified
1. **Synthetic Data Reliance**: PV generation and household load are entirely synthetic, limiting real-world microclimatic validity.
2. **Unidirectional Restriction**: EV model only allows G2V charging; no support for bidirectional EV-to-Home (E2H/V2H) peak shaving or EV-to-Grid (E2G/V2G) export arbitrage.
3. **Paper Completeness**: Several figures in `main.tex` lack comprehensive textual introductions prior to appearance. The paper does not yet reflect real-world dataset provenance or bidirectional energy flows.
4. **Visual Quality**: Figures are saved at standard PNG rasterization without publication-grade vector PDF options or high-contrast styling.

---

## 15. Recommended Minimal Modifications
1. Implement real-world dataset ingestion loaders in `src/data.py` (e.g., authentic measured solar PV from NREL/PVDAQ/OPSD/Pecan Street and real residential load from UK-DALE/Pecan Street/REFIT).
2. Formulate bidirectional EV energy flows (E2H and E2G) in `src/scheduler.py` (LP with non-simultaneous charging/discharging constraints, battery reserve, discharge efficiency, export limits).
3. Update `src/simulation.py` to account for bidirectional energy balances (PV to Home, PV to EV, Grid to Home, Grid to EV, EV to Home, EV to Grid).
4. Extend `src/experiments.py` to evaluate Scenarios S1 (unidirectional), S2 (E2H), S3 (E2G), and S4 (E2H+E2G) across controllers.
5. Enhance plotting scripts in `src/plotting.py` for professional publication standards (both high-resolution PNG and vector PDF).
6. Update `paper/main.tex` and `references.bib` with rigorous technical descriptions of real data, E2G/E2H models, new results, and mandatory pre-figure introductions.

---

## 16. Files That Must Remain Unchanged or Preserved
- `baseline_backup/`: Complete untouched snapshot.
- Core reliability-aware switching algorithm logic: Preserved and extended gracefully to bidirectional operation without corrupting the original scientific research question.
