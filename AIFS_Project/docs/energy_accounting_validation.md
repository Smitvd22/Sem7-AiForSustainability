# Energy Accounting Validation and Conservation Audit

## 1. Sign Conventions and System Boundaries

All energy fluxes are evaluated behind the utility revenue meter at the main household distribution panel.

| Variable | Symbol | Direction / Meaning | Valid Range |
|---|---|---|---|
| Solar PV Generation | $G(t)$ | Injection from PV inverter onto AC bus | $[0, P_{\text{pv, cap}}]$ kW |
| Household Demand | $L(t)$ | Inflexible load extraction from AC bus | $[L_{\min}, L_{\max}]$ kW ($>0$) |
| EV Charging Power | $p_c(t)$ | Power drawn by charger from AC bus into battery | $[0, P_{c, \max}]$ kW |
| EV Discharging Power | $p_d(t)$ | Power injected by inverter from battery into AC bus | $[0, P_{d, \max}]$ kW |
| Grid Import Power | $P_{\text{import}}(t)$ | Power drawn across utility meter into AC bus | $\ge 0$ kW |
| Grid Export Power | $P_{\text{export}}(t)$ | Power injected across utility meter into grid | $\ge 0$ kW |
| Battery Stored Energy | $E_{\text{EV}}(t)$ | Electrochemical energy stored in EV battery pack | $[E_{\text{reserve}}, E_{\text{cap}}]$ kWh |

---

## 2. Interval Energy Conservation Balance
For every interval $t \in \{0, \dots, T-1\}$ and duration $\Delta t$:

### A. Bus Electrical Conservation
The net electrical flux at the domestic AC bus must sum to zero:
$$\text{Residual}_{\text{bus}}(t) = G(t) + P_{\text{import}}(t) + p_d(t) - L(t) - p_c(t) - P_{\text{export}}(t) = 0$$

Numerical verification tolerance: $|\text{Residual}_{\text{bus}}(t)| \le 10^{-6}\text{ kW}$.

### B. EV Battery Energy Conservation
For interval $t$:
$$E_{\text{EV}}(t+1) - E_{\text{EV}}(t) = \left( \eta_c \cdot p_c(t) - \frac{p_d(t)}{\eta_d} \right) \Delta t$$
Summing across the 24-hour horizon:
$$E_{\text{EV}}(T) - E_{\text{EV}}(0) = \sum_{t=0}^{T-1} \left( \eta_c \cdot p_c(t) \cdot \Delta t \right) - \sum_{t=0}^{T-1} \left( \frac{p_d(t)}{\eta_d} \cdot \Delta t \right)$$
Numerical verification tolerance: $|\Delta E_{\text{calc}} - \Delta E_{\text{actual}}| \le 10^{-6}\text{ kWh}$.

---

## 3. Physical Mutually Exclusive Operation (Non-Simultaneity)

1. **Grid Import vs. Grid Export**:
   $$P_{\text{import}}(t) \cdot P_{\text{export}}(t) = 0$$
   An energy management system cannot simultaneously draw wholesale retail power while pushing power back into the same point of common coupling.
2. **EV Charging vs. EV Discharging**:
   $$p_c(t) \cdot p_d(t) = 0$$
   A single physical bidirectional inverter/charger operates in either buck (rectifier) or boost (inverter) mode at any given instantaneous switching state.

---

## 4. Detailed Component Energy Routing

At each interval, the flows are partitioned without double-counting:

1. **Solar to Home ($PV_{\text{H}}$)**:
   $$PV_{\text{H}}(t) = \min(G(t), L(t))$$
2. **Solar Surplus after Home ($PV_{\text{surplus}}$)**:
   $$PV_{\text{surplus}}(t) = \max(0, G(t) - L(t))$$
3. **Solar to EV ($PV_{\text{EV}}$)**:
   $$PV_{\text{EV}}(t) = \min(p_c(t), PV_{\text{surplus}}(t))$$
4. **Solar to Grid ($PV_{\text{G}}$)**:
   $$PV_{\text{G}}(t) = \max(0, PV_{\text{surplus}}(t) - p_c(t))$$
5. **EV to Home ($E2H$)**:
   $$p_{\text{e2h}}(t) = \min(p_d(t), \max(0, L(t) - G(t)))$$
6. **EV to Grid ($E2G$)**:
   $$p_{\text{e2g}}(t) = \max(0, p_d(t) - p_{\text{e2h}}(t))$$
7. **Grid to Home ($G2H$)**:
   $$G2H(t) = \max(0, L(t) - G(t) - p_{\text{e2h}}(t))$$
8. **Grid to EV ($G2V$)**:
   $$G2V(t) = \max(0, p_c(t) - PV_{\text{EV}}(t))$$

Notice that:
- $L(t) = PV_{\text{H}}(t) + p_{\text{e2h}}(t) + G2H(t)$ (exact home demand coverage).
- $p_c(t) = PV_{\text{EV}}(t) + G2V(t)$ (exact charging power breakdown).
- $P_{\text{import}}(t) = G2H(t) + G2V(t)$ (exact grid import breakdown).
- $P_{\text{export}}(t) = PV_{\text{G}}(t) + p_{\text{e2g}}(t)$ (exact grid export breakdown).

Every kilowatt-hour is mathematically accounted for with strict physical provenance.
