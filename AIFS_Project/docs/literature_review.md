# Literature Review and Comparative Audit

## 1. Scope and Taxonomy of Prior Art

Residential electric vehicle (EV) charging under behind-the-meter rooftop photovoltaic (PV) generation spans three major engineering literature domains:
1. **Solar Generation Forecasting and Uncertainty Quantification**: Deterministic persistence and machine learning forecasters versus probabilistic methods (quantile regression, Gaussian processes, conformal prediction).
2. **EV Smart Charging Optimization**: Linear programming, quadratic programming, and receding-horizon model predictive control (MPC) under time-varying electricity tariffs.
3. **Uncertainty-Aware Decision Systems**: Stochastic programming, robust optimization (RO), distributionally robust optimization (DRO), and heuristic fallback policies.

---

## 2. Deep Audit of Closest Studies

### 2.1 Zhao and Burke (2014) — *IEVC*
- **Citation**: Z. Zhao and A. F. Burke, "An Intelligent Solar Powered Battery Buffered EV Charging Station with Solar and Load Forecasting," *2014 IEEE International Electric Vehicle Conference (IEVC)*, doi: `10.1109/IEVC.2014.7056081`.
- **System**: Public/workplace charging station equipped with PV generation and a stationary battery buffer.
- **Uncertainty Handling**: Incorporates cloud-cover and weather-based PV forecasts into day-ahead optimization, but treats forecasts as deterministic point estimates.
- **Limitation**: Ignores forecast errors during execution. When actual solar falls short, the controller must draw unbudgeted power from the grid during high-tariff periods.
- **Relation to Our Work**: Represents the baseline deterministic forecast-driven formulation (Controller B3 in our benchmark).

### 2.2 Simolin, Rautiainen, and Järventausta (2020) — *IREE*
- **Citation**: T. Simolin, A. Rautiainen, and P. Järventausta, "Assessment of Prediction Uncertainties in EV Charging Management," *International Review of Electrical Engineering (IREE)*, vol. 15, no. 2, pp. 139–146, 2020, doi: `10.15866/iree.v15i2.17937`.
- **System**: Residential EV charging management under uncertain driver behavior (unpredictable departure times and session energy demands).
- **Uncertainty Handling**: Compares forecast-based schedules against state-of-charge (SOC) feedback rules. When trip predictions exhibit high variance, the system reverts to an SOC-prioritized fallback rule to ensure mobility requirements are satisfied.
- **Limitation**: Focuses strictly on trip/driver uncertainty; does not incorporate rooftop solar PV generation or time-varying generation uncertainty.
- **Relation to Our Work**: Directly motivates the fallback paradigm, but our work translates this concept to solar generation uncertainty calibrated via conformal prediction.

### 2.3 Dong, Zhang, Liu, and Chen (2025) — *Energy*
- **Citation**: X. Dong, Y. Zhang, M. Liu, and H. Chen, "Stochastic optimization of integrated EV charging stations under photovoltaic uncertainty and battery constraints," *Energy*, vol. 290, p. 130250, 2025, doi: `10.1016/j.energy.2024.130250`.
- **System**: Multi-charger EV hub integrated with stationary storage and PV.
- **Uncertainty Handling**: Implements two-stage stochastic programming using scenario generation and reduction.
- **Limitation**: High computational overhead requiring commercial MILP/MINLP solvers. The optimization policy is continuous and monolithic; it lacks an interpretable, transparent threshold check and requires stationary scenario distributions.
- **Relation to Our Work**: Demonstrates the performance bounds of stochastic planning, whereas our work investigates whether a lightweight, zero-cost threshold-switching rule can offer practical robustness without heavy scenario modeling.

### 2.4 Yu, Chandra Mouli, Damianakis, and Bauer (2024) — *IEEE PEMC*
- **Citation**: Z. Yu, G. R. Chandra Mouli, M. Damianakis, and P. Bauer, "Impact of Uncertainties and Price of Robustness in receding-horizon EV Smart-Charging," *2024 IEEE 21st International Power Electronics and Motion Control Conference (PEMC)*, doi: `10.1109/PEMC61721.2024.10726368`.
- **System**: Receding-horizon smart-charging under uncertainty in dynamic tariffs and vehicle availability.
- **Findings**: Quantifies the "price of robustness" — conservative robust schedules sacrifice economic efficiency to guarantee constraint satisfaction.
- **Relation to Our Work**: Confirms that over-conservatism increases total charging cost, underscoring the necessity of gating conservative fallback policies only during intervals with low forecast confidence.

### 2.5 Angelopoulos and Bates (2021) & Vovk et al. (2005) — *Conformal Prediction Foundations*
- **Citation**: A. N. Angelopoulos and S. Bates, "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification," *arXiv:2107.07511*, 2021.
- **Relevance**: Supplies the mathematical machinery for finite-sample, distribution-free prediction intervals:
  $$\hat{q}_\alpha = \text{Quantile}\left(|y_i - \hat{y}_i|; \frac{\lceil(n+1)(1-\alpha)\rceil}{n}\right)$$
  This guarantees marginal calibration on out-of-sample test data without parametric assumptions regarding solar irradiance distributions.

---

## 3. Literature Matrix Summary

| Method Category | Representative Papers | PV Modeled | Uncertainty Quantified | Switching Policy | Fallback Included |
|---|---|---|---|---|---|
| Deterministic PV-EV | Zhao & Burke (2014) | Yes | No | No | No |
| Trip-Uncertainty Fallback | Simolin et al. (2020) | No | Yes (Trip) | Partial | Yes (SOC) |
| Stochastic Programming | Dong et al. (2025) | Yes | Yes (Scenarios) | No | No |
| Receding Robust MPC | Yu et al. (2024), Cabrera-Tobar (2024) | Partial | Yes (Bounds) | No | No |
| Weather-Adaptive Stations | Son et al. (2026) | Yes | Yes (Clustering) | Partial | No |
| **Proposed Controller** | **This Research** | **Yes** | **Yes (Conformal)** | **Yes ($\tau$-Gated)** | **Yes (Zero-PV)** |

