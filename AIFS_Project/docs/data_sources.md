# Data Sources, Licensing, and Provenance

## 1. Primary Dataset Overview
Due to the zero-budget constraint and the requirement of 100% offline reproducibility without API keys, cloud credentials, or external network dependencies, this project generates a physically calibrated, open synthetic benchmark dataset that adheres to published empirical irradiance, weather, and residential load models.

- **Temporal Coverage**: 8,760 hourly intervals (365 continuous days, year 2023).
- **Timezone**: UTC.
- **Geographic Reference**: Latitude 35.0° N (high solar insolation residential belt).
- **Format**: CSV files stored in `data/processed/` accompanied by JSON metadata (`metadata.json`).

---

## 2. Component Provenance and Realism Modeling

### 2.1 Rooftop Photovoltaic Generation (`data/processed/pv.csv`)
- **Clear-Sky Physical Model**: Half-sinusoid envelope centered at solar noon (12:00 UTC) with astronomical day-length variation computed using the Spencer (1971) solar declination model and the Cooper (1969) day-of-year formulation.
- **Cloud Attenuation**: Cloud attenuation drawn from a calibrated Beta distribution ($\alpha=6.0, \beta=2.0$) giving realistic partly-cloudy fluctuations and overcast day clusters.
- **Physical Bounding**: Clipped to $[0, P_{\text{capacity}}]$ where $P_{\text{capacity}} = 5.0\text{ kW}$ DC rating, guaranteeing zero nighttime production.

### 2.2 Household Inflexible Load (`data/processed/load.csv`)
- **Baseload Component**: 0.50 kW continuous refrigeration, standby, and phantom loads.
- **Morning Peak**: Gaussian peak centered at 08:00 (1.5 kW amplitude, $\sigma = 1.0\text{ h}$).
- **Evening Peak**: Gaussian peak centered at 19:00 (2.5 kW amplitude, $\sigma = 1.5\text{ h}$).
- **Stochastic Noise**: Additive Gaussian perturbations ensuring strictly positive consumption ($L_t > 0$).

### 2.3 Tariffs (`data/processed/tariff.csv`)
- **Time-of-Use (TOU)**: Modeled after standard US/European residential dynamic tariffs:
  - Off-peak: \$0.08 / kWh (22:00–06:00)
  - Mid-peak: \$0.12 / kWh (06:00–17:00, 21:00–22:00)
  - On-peak: \$0.25 / kWh (17:00–21:00)
- **Flat Rate**: \$0.15 / kWh uniform rate used for tariff sensitivity experiments.

