# Research Design and System Formulation

## 1. Primary Research Question
Does a residential EV charging controller that estimates solar photovoltaic (PV) forecast reliability and switches to a conservative fallback scheduling policy improve the trade-off between electricity cost, local solar utilization, peak demand, and charging deadline reliability compared with non-adaptive charging controllers?

## 2. Central Hypotheses
- **H1 (Feasibility & Deadline Reliability)**: Under forecast uncertainty and model errors, an aggressive forecast-driven controller risks undercharging or charging during expensive penalty intervals. A reliability-triggered switch to a conservative fallback maintains 100% deadline satisfaction.
- **H2 (Economic Trade-Off)**: When solar forecasts have high confidence, forecast-driven charging captures daytime solar energy. When confidence is low, switching to fallback prevents forecast-error-induced grid penalties.
- **H3 (Tariff-Sensitivity Dependency)**: Non-adaptive economic baselines (such as off-peak cheapest-hours charging) can outperform solar-chasing controllers if the EV is predominantly connected during night hours when solar generation is zero and off-peak grid tariffs are low.

## 3. System Boundary
- **Residence**: Single-family home with behind-the-meter 5.0 kW rooftop PV installation and non-shiftable domestic baseload (~1.05 kW average).
- **EV & Charger**: 40.0 kWh battery capacity, 10.0 kWh initial state-of-charge, 20.0 kWh required energy delivery before morning departure (target SOC = 30.0 kWh). Unidirectional Level 2 EVSE with 7.0 kW peak power and 90% round-trip conversion efficiency.
- **Grid & Tariffs**: Unidirectional/net-metered grid connection with Time-of-Use (TOU) import pricing:
  - Off-peak: $0.08 / kWh (22:00–06:00)
  - Mid-peak: $0.12 / kWh (06:00–17:00, 21:00–22:00)
  - On-peak: $0.25 / kWh (17:00–21:00)
  - Solar export compensation: $0.04 / kWh

