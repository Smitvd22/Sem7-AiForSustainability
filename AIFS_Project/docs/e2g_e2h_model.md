# Technical Specification: E2G and E2H Bidirectional Energy Models

## 1. Critical Terminology and Energy Flow Clarifications

In residential energy management and smart charging literature, terminology varies across engineering disciplines. To avoid ambiguity, this project strictly defines and enforces the following technical taxonomy:

| Label in Request | Standard Academic Term | Physical Meaning | Energy Source | Energy Destination |
|---|---|---|---|---|
| **E2H** | **V2H (Vehicle-to-Home)** | Electric Vehicle discharging power to supply residential behind-the-meter domestic load. | EV Battery | Household Electrical Bus |
| **E2G** | **V2G (Vehicle-to-Grid)** | Electric Vehicle discharging power through the inverter to export energy across the utility meter to the distribution grid for feed-in compensation. | EV Battery | Distribution Electric Grid |
| **G2V** | **Standard EV Charging** | Grid electricity imported across the meter to charge the EV battery. | Electric Grid | EV Battery |
| **PV2EV** | **Solar Self-Consumption** | On-site rooftop photovoltaic surplus directly diverted to charge the EV battery. | Rooftop Solar Inverter | EV Battery |
| **PV2H** | **Direct Solar Consumption** | On-site rooftop photovoltaic generation directly supplying household demand. | Rooftop Solar Inverter | Household Electrical Bus |
| **PV2G** | **Solar Export** | On-site rooftop photovoltaic surplus exported to the distribution grid. | Rooftop Solar Inverter | Distribution Electric Grid |

> **Notation Convention**: In the Python codebase and configuration files, the configurable feature flags are named `enable_e2h` and `enable_e2g` (matching the project specification), while in the IEEE research paper (`paper/main.tex`), standard terms **V2H** and **V2G** are formally used alongside an explicit note that they implement the E2H and E2G capabilities.

---

## 2. Physical System Architecture and Energy Balance

```
                      +-----------------------------+
                      |   Distribution Power Grid   |
                      +-----------------------------+
                           ^                   |
            P_export(t)    |                   |  P_import(t)
            (PV2G + E2G)   |                   |  (G2H + G2V)
                           v                   v
                =======================================
                            UTILITY REVENUE METER
                =======================================
                                   |
                                   v  Home AC Bus
                 +-----------------+-----------------+
                 |                                   |
                 v                                   v
        +------------------+                +------------------+
        |  Household Load  |                | Bidirectional EV |
        |      L(t)        |                |  Charger (EVSE)  |
        +------------------+                +------------------+
                 ^                                   ^
                 | (PV2H + E2H)                      | (PV2EV + G2V) [Charge]
                 |                                   | (E2H + E2G)   [Discharge]
        +------------------+                +------------------+
        | Rooftop Solar PV |                |    EV Battery    |
        |      G(t)        |                |      E_EV(t)     |
        +------------------+                +------------------+
```

### 2.1 Interval Energy Balance Equations
For every discrete time interval $t \in \{0, 1, \dots, T-1\}$ with duration $\Delta t = 1.0\text{ h}$:

1. **EV Battery Dynamics**:
   $$E_{\text{EV}}(t+1) = E_{\text{EV}}(t) + \left( \eta_c \cdot p_c(t) - \frac{p_d(t)}{\eta_d} \right) \Delta t$$
   where:
   - $E_{\text{EV}}(t)$ is stored energy at start of interval $t$ [kWh].
   - $p_c(t) \ge 0$ is EV charging power drawn from the home bus [kW].
   - $p_d(t) \ge 0$ is EV discharging power supplied to the home bus [kW].
   - $\eta_c \in (0, 1]$ is charging efficiency ($\eta_c = 0.90$).
   - $\eta_d \in (0, 1]$ is discharging efficiency ($\eta_d = 0.90$).

2. **Discharge Flow Decomposition**:
   $$p_d(t) = p_{\text{e2h}}(t) + p_{\text{e2g}}(t)$$
   where:
   - $p_{\text{e2h}}(t) \ge 0$: Power dedicated to offsetting domestic demand ($p_{\text{e2h}}(t) \le \max(0, L_t - G_t)$).
   - $p_{\text{e2g}}(t) \ge 0$: Power dedicated to grid export.

3. **Home Electrical Bus Net Power**:
   $$P_{\text{net}}(t) = L(t) + p_c(t) - G(t) - p_d(t)$$
   - When $P_{\text{net}}(t) \ge 0$, the deficit is imported from the grid:
     $$P_{\text{import}}(t) = P_{\text{net}}(t)$$
     $$P_{\text{export}}(t) = 0$$
   - When $P_{\text{net}}(t) < 0$, the surplus is exported to the grid:
     $$P_{\text{import}}(t) = 0$$
     $$P_{\text{export}}(t) = -P_{\text{net}}(t)$$

---

## 3. Operational and Physical Constraints

1. **Power Rating Bounds**:
   $$0 \le p_c(t) \le a(t) \cdot P_{c, \max}$$
   $$0 \le p_d(t) \le a(t) \cdot P_{d, \max}$$
   where $a(t) \in \{0, 1\}$ is EV physical plug-in availability indicator ($a(t) = 0$ outside connection window).

2. **Operating Mode Enablers**:
   $$p_{\text{e2h}}(t) \le \mathbb{I}_{\text{E2H}} \cdot a(t) \cdot P_{d, \max}$$
   $$p_{\text{e2g}}(t) \le \mathbb{I}_{\text{E2G}} \cdot a(t) \cdot P_{d, \max}$$
   where $\mathbb{I}_{\text{E2H}}, \mathbb{I}_{\text{E2G}} \in \{0, 1\}$ represent configuration flags.

3. **Non-Simultaneous Charging and Discharging**:
   $$p_c(t) \cdot p_d(t) = 0, \quad \forall t$$
   In our linear programming formulation, since round-trip efficiency $\eta_c \cdot \eta_d = 0.90 \times 0.90 = 0.81 < 1.0$, any simultaneous non-zero charging and discharging strictly wastes energy and strictly increases the cost objective function under non-negative tariffs; thus, the LP optimizer inherently selects non-simultaneous schedules without requiring artificial integer variables. In simulation, non-simultaneity is explicitly validated.

4. **Battery Energy and Minimum Reserve**:
   $$E_{\text{reserve}} \le E_{\text{EV}}(t) \le E_{\text{battery, max}}, \quad \forall t$$
   where $E_{\text{reserve}} = 0.20 \times E_{\text{battery, max}} = 8.0\text{ kWh}$ guarantees that emergency transportation reserve is never depleted.

5. **Departure Energy Requirement**:
   $$E_{\text{EV}}(T) \ge E_{\text{target}} = E_0 + E_{\text{req}}$$
   This is enforced as a strict hard constraint. Under no circumstances may E2H or E2G discharging cause a departure deadline violation when the initial required energy was feasible.

---

## 4. Economic Optimization Objective

The generalized operating cost objective across the scheduling horizon $T$ is:
$$\min \sum_{t=0}^{T-1} \left( c_{\text{import}}(t) \cdot P_{\text{import}}(t) - c_{\text{export}}(t) \cdot P_{\text{export}}(t) + c_{\text{deg}} \cdot p_d(t) \right) \Delta t$$
where:
- $c_{\text{import}}(t)$ is the TOU retail rate (\$/kWh).
- $c_{\text{export}}(t)$ is the export feed-in tariff (\$/kWh, typically \$0.04/kWh or NEM rate).
- $c_{\text{deg}}$ is the battery cycling throughput degradation factor (\$/kWh throughput, default \$0.015/kWh).

---

## 5. Experimental Scenarios (S1 through S4)

| Scenario | Mode Label | EV Charging | EV-to-Home (E2H) | EV-to-Grid (E2G) |
|---|---|---|---|---|
| **S1** | Baseline (Unidirectional) | Enabled | Disabled ($\mathbb{I}_{\text{E2H}}=0$) | Disabled ($\mathbb{I}_{\text{E2G}}=0$) |
| **S2** | E2H-Only (Peak Shaving) | Enabled | Enabled ($\mathbb{I}_{\text{E2H}}=1$) | Disabled ($\mathbb{I}_{\text{E2G}}=0$) |
| **S3** | E2G-Only (Grid Export) | Enabled | Disabled ($\mathbb{I}_{\text{E2H}}=0$) | Enabled ($\mathbb{I}_{\text{E2G}}=1$) |
| **S4** | Combined Bidirectional | Enabled | Enabled ($\mathbb{I}_{\text{E2H}}=1$) | Enabled ($\mathbb{I}_{\text{E2G}}=1$) |

All four scenarios are tested under identical weather, solar forecast, household load, initial SOC, and departure deadline conditions.
