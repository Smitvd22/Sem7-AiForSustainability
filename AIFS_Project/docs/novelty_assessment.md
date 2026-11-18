# Novelty Assessment and Calibrated Scientific Claims

## 1. Core Novelty Questions

### 1.1 Is uncertainty-aware EV charging already established?
**Yes.** As documented in the literature review, extensive prior research exists using stochastic programming (Dong et al., 2025), robust model predictive control (Yu et al., 2024; Cabrera-Tobar et al., 2024), and distributionally robust optimization (Wang et al., 2025). Uncertainty awareness per se is not a novel topic.

### 1.2 Have previous controllers changed decisions according to forecast reliability?
**Partially in other domains, but rarely via explicit confidence gating for residential PV-EV.**
- Simolin et al. (2020) demonstrated switching to battery SOC feedback when travel predictions were unreliable, but did not consider solar generation or dynamic tariffs.
- Son et al. (2026) adapted station parameters to weather clusters, but did not implement real-time or horizon-level prediction interval gating.

### 1.3 Have similar controllers used fallback schedules?
**Rarely in residential energy management.** Most existing uncertainty controllers operate in a continuous robust formulation where conservative margins (e.g. budget of uncertainty) are enforced continuously across all timesteps. A discrete switching policy that operates conditionally between an aggressive forecast-driven optimizer and a conservative zero-solar fallback has not been systematically investigated on residential datasets.

### 1.4 Does an existing method substantially reproduce the proposed switching logic?
**No single identified publication implements this exact pipeline**:
1. Fitting an empirical point forecaster (persistence / gradient boosting);
2. Calibrating finite-sample prediction intervals via split conformal prediction;
3. Computing an interpretable horizon reliability index:
   $$\bar{r} = 1 - \frac{1}{T}\sum_{t=1}^T \text{clip}\left(\frac{\hat{u}_t - \hat{l}_t}{P_{\text{capacity}}}, 0, 1\right);$$
4. Tuning the decision threshold $\tau^*$ exclusively on a held-out chronological validation split under a strict zero-deadline-miss constraint;
5. Evaluating against both economic (cheapest-hours) and physical (oracle, fallback, fixed) baselines across controlled stress scenarios.

---

## 2. Calibrated Contribution Conclusion

**Category: Defensible Incremental Novelty and Empirical Protocol Contribution.**

The contribution is not the invention of an entirely new optimization class. Rather, it is:
1. **Architectural & Algorithmic Integration**: Combining distribution-free conformal calibration with a discrete fallback switching policy in residential behind-the-meter EV charging.
2. **Interpretability & Deployability**: Providing an open-source, CPU-solvable alternative to heavy stochastic or robust optimization that requires ₹0 in commercial software.
3. **Falsifiable Empirical Benchmarking**: Proving through rigorous paired statistical testing that while the proposed method achieves 100% deadline satisfaction and protects against severe forecast errors, tariff structure (off-peak grid rates) heavily dictates whether solar-chasing is economically superior to simple off-peak charging.

We explicitly disclose that if off-peak grid electricity is significantly cheaper than solar opportunity costs or when daytime solar cannot be captured due to nighttime vehicle connection windows, non-PV economic baselines (cheapest-hours) will naturally achieve lower costs. This honest disclosure prevents misleading claims of universal superiority.

