# Faculty Defense Questions and Evidence-Based Answers

### Q1: What is genuinely novel about this work compared to existing EV charging literature?
**Answer**: While solar-powered EV charging (Zhao & Burke 2014) and robust scheduling (Dong et al. 2025, Yu et al. 2024) are established, prior research relies on continuous stochastic or robust optimization frameworks that solve heavy mathematical programs across all periods. Our contribution is the integration of distribution-free split conformal prediction intervals with a discrete confidence-gated fallback rule ($\bar{r} \ge \tau^*$). This provides an interpretable, zero-cost, CPU-solvable controller that maintains 100% deadline satisfaction while avoiding the computational overhead of commercial MILP/MINLP solvers.

### Q2: How does the proposed controller differ fundamentally from robust optimization?
**Answer**: Robust optimization (RO) enforces worst-case bounds continuously at every timestep, which causes persistent over-conservatism (the "price of robustness" documented by Yu et al., 2024). In contrast, our controller behaves aggressively like a standard deterministic cost-minimizer during high-confidence periods, and only retreats to the conservative (zero-solar) fallback when empirical forecast reliability drops below the validation-calibrated threshold $\tau^*$.

### Q3: Why use a confidence threshold switching rule instead of continuous weighting?
**Answer**: Discrete threshold switching provides operational transparency, predictable fail-safe behavior, and zero solver complexity. For residential energy management systems (HEMS), embedded microcontrollers require deterministic runtime guarantees. Evaluating an if-else check against $\tau^*$ takes microseconds, whereas continuously re-solving non-linear chance-constrained problems is prone to solver failure on low-power hardware.

### Q4: How was forecast uncertainty calibrated mathematically?
**Answer**: We implement split conformal prediction (Vovk et al., 2005; Angelopoulos & Bates, 2021). Out-of-sample absolute residuals $r_i = |y_i - \hat{y}_i|$ are computed on a dedicated 54-day calibration set. For nominal miscoverage $\alpha = 0.10$ (90% target coverage), the conformal quantile is computed with the finite-sample correction $q_\alpha = \text{Quantile}(r; \lceil(n+1)(1-\alpha)\rceil / n) = 1.0300\text{ kW}$. Empirical coverage on the validation and test sets reached 95.49% and 94.64%, confirming valid calibration.

### Q5: What exact measures were implemented to prevent data leakage?
**Answer**: A strict four-way chronological partition was enforced on whole-day boundaries: Training (earliest 60%, 219 days), Calibration (next 15%, 54 days), Validation (next 10%, 36 days), and Test (final 15%, 56 days). Forecasters were fit exclusively on training data; conformal intervals were calibrated exclusively on calibration residuals; the threshold $\tau^* = 0.7049$ was selected solely on validation days; and test days were frozen until final benchmarking. No future observations or test metrics were ever seen by model fitting or threshold tuning.

### Q6: Why is the fallback considered conservative?
**Answer**: The fallback policy assumes zero future solar generation ($\hat{G}_t \equiv 0$). By assuming a complete solar blackout, the linear program allocates charging entirely from the grid during the cheapest available connection intervals, guaranteeing that the target energy ($E_{\text{req}} = 20.0\text{ kWh}$) is fully delivered to the battery regardless of real-time solar shortfalls.

### Q7: How are solar energy allocation and grid imports accounted for physically?
**Answer**: Behind-the-meter physical energy balance is enforced interval-by-interval. Net demand is $D_t = L_t + p_t - G_t$. Grid import is $\max(0, D_t)$ and export is $\max(0, -D_t)$. Household load has priority over solar; solar delivered to the EV is calculated strictly as $\min(p_t, \max(0, G_t - L_t))$. Simultaneous artificial import and export is strictly prevented.

### Q8: Is the perfect-forecast oracle a fair baseline?
**Answer**: The oracle is explicitly labeled as a theoretical benchmark (an unattainable upper bound), not a deployable controller. It solves the exact same LP formulation as the forecast-driven controller but replaces the day-ahead forecast with actual future generation $G_t$. It illustrates the theoretical maximum benefit achievable if forecast errors were zero.

### Q9: How do you know the observed differences are statistically meaningful?
**Answer**: We conducted paired test-day comparisons over 56 identical test days. For each comparison, we report paired mean differences, 95% bootstrap confidence intervals, paired t-tests, Wilcoxon signed-rank tests, and Cohen's $d$ effect sizes. For example, comparing Cheapest-Hours to Forecast-Driven yields a mean difference of -\$1.928 / day (95% CI: [-\$1.934, -\$1.921], $p = 2.07 \times 10^{-104}, d = -73.04$).

### Q10: What if the proposed method performs worse than a simple baseline?
**Answer**: We report this openly as a primary scientific finding. In our empirical results, Controller B2 (Cheapest-Hours without solar awareness) achieved the lowest daily cost (\$5.0943 vs \$7.0220). This occurs because the vehicle is plugged in overnight (17:00 to 07:00), when solar irradiance is zero and grid power is at its cheapest off-peak rate (\$0.08/kWh). This confirms Hypothesis H3: solar-chasing controllers are economically disadvantageous if the vehicle is absent during daylight hours and off-peak grid tariffs are low.

### Q11: How generalizable are these results to other climates or tariffs?
**Answer**: In our Tariff Sensitivity Experiment (Experiment F), under a flat tariff (\$0.15/kWh), daytime solar utilization becomes economically paramount because off-peak grid electricity no longer provides a cost discount. Under daytime connection profiles (e.g. workplace charging or weekends), solar self-consumption increases substantially. The modular architecture allows instant re-running under any regional weather or tariff configuration.

### Q12: What components were implemented independently versus imported?
**Answer**: Every controller algorithm (B1–B6), conformal prediction routine, horizon reliability scoring, physical simulation engine, chronological data pipeline, and metric calculation was designed, implemented, and tested from scratch in Python. Only standard open-source numeric primitives (`numpy`, `pandas`, `scipy.optimize.linprog`, `scikit-learn`) were imported.

### Q13: Did any controller miss a charging deadline during the test?
**Answer**: No. All controllers achieved a 100% deadline success rate (mean unmet energy = 0.000 kWh across all 56 test days). This confirms that with a 14-hour overnight window and a 7 kW charger, the required 20 kWh delivery is physically feasible even under complete solar absence.

### Q14: How does the system handle days where total energy demand is physically infeasible?
**Answer**: Module `src/scheduler.py` includes an explicit physical feasibility check (`check_feasibility`). If the connection duration multiplied by $P_{\max} \cdot \eta$ is less than $E_{\text{req}}$, the scheduler returns `status='infeasible'` and logs the exact shortfall, rather than silently outputting an impossible schedule.

### Q15: What is the primary takeaway for an energy-systems engineer?
**Answer**: Do not assume that adding solar forecasting to EV charging always saves money. In residential settings with overnight parking and time-of-use rates, simple off-peak grid charging is often economically superior. Solar-aware controllers should only be deployed when daytime connection windows exist, and when used, must be paired with conformal reliability gating to prevent expensive peak-hour grid draws during overcast forecast failures.

