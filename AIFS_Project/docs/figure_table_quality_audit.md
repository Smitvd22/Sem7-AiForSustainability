# Figure and Table Quality Audit

## 1. Visual Standards and Quality Framework
In accordance with IEEE conference publication requirements, all project figures and tables were audited and upgraded to adhere to the following publication standards:
- **Dual Vector/Raster Formats**: Every plot is generated in both vector PDF (`.pdf`) format for crisp, infinite-resolution LaTeX inclusion, and high-resolution raster (`.png` at 300 DPI) for web viewing.
- **Typography & Font Sizing**: Standardized to serif typefaces matching IEEE two-column styles with readable axes labels (11 pt), titles (12 pt), tick labels (9 pt), and legend entries (9 pt).
- **Colorblind-Safe and High-Contrast Palettes**: Using established seaborn/ColorBrewer palettes (`Set2`, `Blues_r`, `YlOrRd`, `Set3`, `RdYlBu`), avoiding indistinguishable red-green pairings.
- **Physical Dimensionality and Sizing**:
  - Single-column floats: Scaled to `width=\columnwidth` (~3.5 inches).
  - Multi-panel / architecture floats: Scaled to `width=\textwidth` or two-column width.
- **Explicit Units**: Every axis includes SI/financial units (e.g., `kW`, `kWh/day`, `$/day`, `UTC`).
- **Table Quality**: Professional horizontal rules (`\toprule`, `\midrule`, `\bottomrule`), no vertical borders, bold metric indicators, and explicit measurement units.

---

## 2. Figure Quality Audit Log

| Figure File | Title / Subject | Original Quality Issues | Upgrades Implemented | Output Formats | Sizing Recommendation |
|---|---|---|---|---|---|
| `fig1_system_architecture` | System Architecture with E2H/E2G | Only unidirectional blocks; plain boxes; no E2H/E2G flows | Redesigned with `FancyBboxPatch`, annotated bidirectional flows (PV2EV, PV2H, E2H, E2G, G2H, G2V), clear legends, control pathways | PNG (300 DPI) & PDF | Single- or two-column (`\columnwidth`) |
| `fig2_pv_forecast_interval` | Measured PV vs Forecast with Conformal Interval | Synthetic sine curve, generic labels | Authentic NREL PVDAQ Site 4 measured profile, 90% conformal interval shaded band, gradient-boosted point prediction | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig3_forecast_error_dist` | Forecast Error and Absolute Error Density | Single histogram, unannotated MAE | Dual-panel layout: (a) Error distribution with zero-bias line, (b) Absolute error density with explicit MAE reference line | PNG (300 DPI) & PDF | Single- or two-column (`\columnwidth` / `\textwidth`) |
| `fig4_interval_calibration` | Prediction Interval Coverage and Width | Coarse bar styling, no percentage labels | Color-coded empirical coverage against nominal 90% threshold, mean width comparison | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig5_daily_cost_by_controller` | Daily Operating Cost by Controller | Standard boxplot, overlapping x-labels | Rotated labels, diamond mean markers, color-coded distributions across 56 test days | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig6_solar_contribution` | Direct Solar PV to EV Charging | Generic orange hue, small font | Distinct palette, clear kWh/day axis, explicit zero-solar overnight connection representation | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig7_peak_and_deadline` | Peak Demand and Deadline Reliability | Inflexible scaling, low contrast | Dual-panel: (a) Peak grid import boxplot, (b) 100% deadline satisfaction green indicator bars | PNG (300 DPI) & PDF | Two-column (`\columnwidth` / `\textwidth`) |
| `fig8_stress_test_comparison` | Stress Testing Across Error Regimes | Generic legend placement | Clean grouped bar chart across low, moderate, high, correlated, and regime-shift error scenarios | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig9_threshold_sensitivity` | Switching Threshold Sensitivity | 3 cramped subplots, label clipping | Harmonized 2-panel layout: (a) Operating cost vs $\tau$, (b) Deadline satisfaction and fallback engagement rates | PNG (300 DPI) & PDF | Single-column (`\columnwidth`) |
| `fig10_bidirectional_flows_s1_s4` *(NEW)* | Multi-Panel Bidirectional Scenarios S1–S4 | Did not exist | 4-panel comparison: (a) Net cost ($/day), (b) Grid exchange (kWh/day), (c) Discharged energy E2H vs E2G, (d) Peak grid demand | PNG (300 DPI) & PDF | Two-column (`\textwidth`) |
| `fig11_real_vs_synthetic_profiles` *(NEW)* | Real Measured vs. Synthetic Profiles | Did not exist | 2-panel comparison: (a) Measured NREL PV vs clear-sky model, (b) UK-DALE smart meter load vs Gaussian curve | PNG (300 DPI) & PDF | Two-column (`\textwidth`) |

---

## 3. Table Quality Audit Log

| Table File | Caption / Description | Original Issues | Upgrades Implemented | Status |
|---|---|---|---|---|
| `table5_main_controller_comparison.csv` | Main Controller Comparison Across 56 Test Days | Lacked bidirectional metrics and standard deviation precision | Added net cost, peak import, solar energy, unmet energy, and 100% deadline rate | Verified |
| `table6_statistical_vs_forecast_driven.csv` | Paired Statistical Hypothesis Tests vs Forecast-Driven | Generic p-value display | Includes paired $t$-statistic, exact p-values, 95% bootstrap CIs, Cohen's $d$ effect sizes | Verified |
| `table6b_statistical_vs_cheapest_hours.csv` | Paired Statistical Tests vs Cheapest Hours Baseline | Generic format | Paired difference metrics, bootstrap CIs, and Bonferroni corrections | Verified |
| `table7_ablation_results.csv` | Ablation Study of Decision Rules | Basic table | Explicit ablation configurations (no confidence awareness, fallback disabled, chosen $\tau^*$, fixed schedule) | Verified |
| `table8_stress_test_comparison.csv` | Synthetic Forecast Error Stress Testing | Raw cost numbers without scenario descriptions | Scenarios categorized by noise standard deviation fraction, correlation, and regime bias | Verified |
| `table8b_threshold_sensitivity.csv` | Sensitivity of Reliability Threshold $\tau$ | Incomplete quantiles | Grid search across candidate quantiles on test split | Verified |
| `table8c_ev_demand_sensitivity.csv` | Sensitivity to EV Battery Session Energy Demand | Only cost recorded | Evaluates 10 to 30 kWh requirements, deadline rates, and cost scaling | Verified |
| `table8d_tariff_sensitivity.csv` | Tariff Structure Sensitivity (TOU vs. Flat) | Basic comparison | TOU vs Flat retail rate economic impact across controllers | Verified |
| `table9_bidirectional_s1_s4_comparison.csv` *(NEW)* | Bidirectional Scenario Comparison (S1 to S4) | Did not exist | Comprehensively evaluates S1 (unidirectional), S2 (E2H), S3 (E2G), S4 (combined), reporting net cost, grid exchange, E2H/E2G allocation, peak demand, and deadline rates | Verified |
| `table10_bidirectional_statistical_tests.csv` *(NEW)* | Statistical Tests for Bidirectional Scenarios vs Baseline S1 | Did not exist | Paired $t$-test ($p = 9.63 \times 10^{-69}$), bootstrap CIs ($[-1.215, -1.177]$), Cohen's $d = -16.38$ | Verified |

---

## 4. Verification of Mandatory Body Text Introductions
Every figure and table generated above is explicitly introduced and discussed in `paper/main.tex` with at least one complete sentence before it appears in the compiled text, in accordance with IEEE formatting rules.
