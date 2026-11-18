# Mathematical Model and Energy Accounting

## 1. Notation and Discrete Time Framework
The scheduling horizon spans $T = 24$ discrete intervals of duration $\Delta t = 1.0$ hour, indexed by $t \in \{0, 1, \dots, T-1\}$.

### Variables and Parameters
- $G_t \ge 0$: Actual measured PV generation at hour $t$ (kW).
- $\hat{G}_t \ge 0$: Day-ahead forecast PV generation (kW).
- $L_t > 0$: Inflexible household electricity load (kW).
- $p_t \ge 0$: EV charging power commanded by the scheduler (kW).
- $c_t > 0$: Electricity import price at hour $t$ ($/kWh).
- $c_{\text{export}} \ge 0$: Compensation tariff for exported solar surplus ($/kWh).
- $a_t \in \{0, 1\}$: Connection indicator ($a_t = 1$ when EV is plugged in, 0 otherwise).
- $P_{\max}$: Charger rated capacity (7.0 kW).
- $\eta$: Charger and battery charging efficiency ($\eta = 0.90$).
- $E_t$: EV battery state-of-charge (energy) at interval $t$ (kWh).
- $E_{\text{cap}}$: Maximum usable battery capacity (40.0 kWh).
- $E_0$: Initial energy at session start (10.0 kWh).
- $E_{\text{req}}$: Required net energy delivered to battery (20.0 kWh).
- $E_{\text{target}} = E_0 + E_{\text{req}}$: Target departure energy (30.0 kWh).

---

## 2. Constraints

### 2.1 Charger Availability and Rate Bounds
$$0 \le p_t \le a_t \cdot P_{\max}, \quad \forall t \in \{0, \dots, T-1\}$$
Charging is strictly prohibited when the vehicle is disconnected ($a_t = 0$).

### 2.2 Battery Dynamics and Capacity Limits
$$E_{t+1} = E_t + \eta \cdot p_t \cdot \Delta t, \quad \forall t \in \{0, \dots, T-1\}$$
$$0 \le E_t \le E_{\text{cap}}, \quad \forall t \in \{0, \dots, T\}$$

### 2.3 Departure Deadline Requirement
$$E_T \ge E_{\text{target}}$$

---

## 3. Realized Behind-the-Meter Energy Balance
In actual execution, the home simulator calculates physical energy flows:
- **Net Demand**: $D_t = L_t + p_t - G_t$
- **Grid Import Power**: $P_{\text{grid}, t} = \max(0, D_t)$
- **Grid Export Power**: $P_{\text{export}, t} = \max(0, -D_t)$
- **PV Delivered to EV**: $PV_{\text{EV}, t} = \min\left(p_t, \max(0, G_t - L_t)\right)$
- **PV Self-Consumed by Household & EV**: $PV_{\text{self}, t} = \min\left(G_t, L_t + p_t\right)$

Simultaneous import and export cannot occur under this net-metered formulation ($P_{\text{grid}, t} \cdot P_{\text{export}, t} = 0$).

---

## 4. Optimization Formulations (Linear Programs)

### 4.1 Forecast-Driven Optimization (B3)
Minimizes anticipated electricity import costs subject to forecast solar $\hat{G}_t$:
$$\min_{\{p_t, g_t\}} \sum_{t=0}^{T-1} c_t \cdot g_t \cdot \Delta t$$
Subject to:
$$g_t \ge L_t + p_t - \hat{G}_t, \quad \forall t$$
$$g_t \ge 0, \quad \forall t$$
$$0 \le p_t \le a_t \cdot P_{\max}, \quad \forall t$$
$$E_0 + \sum_{\tau=0}^{t-1} \eta \cdot p_\tau \cdot \Delta t \le E_{\text{cap}}, \quad \forall t$$
$$E_0 + \sum_{t=0}^{T-1} \eta \cdot p_t \cdot \Delta t \ge E_{\text{target}}$$

### 4.2 Conservative Fallback (B5)
Identical to the forecast-driven linear program, but with $\hat{G}_t \equiv 0$ for all $t$. This guarantees that the charging schedule is fully feasible and optimal under a worst-case complete blackout of rooftop solar generation.

### 4.3 Proposed Reliability-Aware Switching Controller (B4)
Given calibrated horizon reliability score $\bar{r} \in [0, 1]$ and validation-selected threshold $\tau^*$:
$$\text{Schedule} = \begin{cases} \text{solve\_forecast\_driven}(\dots), & \text{if } \bar{r} \ge \tau^* \\ \text{solve\_conservative\_fallback}(\dots), & \text{if } \bar{r} < \tau^* \end{cases}$$

