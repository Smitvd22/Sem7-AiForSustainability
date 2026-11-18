# Real-World Datasets: Research, Integration, and Provenance

## 1. Executive Summary
This document outlines the real-world empirical energy datasets evaluated and integrated into the Reliability-Aware EV Charging research suite. In adherence to scientific integrity principles, the project distinguishes between **authentic measured observations**, **historical public records**, **transparent empirical parameter distributions**, and **controlled synthetic stress scenarios**.

---

## 2. Dataset Selection Matrix

| Field | Dataset 1: NREL PVDAQ | Dataset 2: UK-DALE / REFIT | Dataset 3: ACN-Data (Caltech) | Dataset 4: PG&E EV2-A / TOU Tariff |
|---|---|---|---|---|
| **Dataset name** | NREL PV Data Acquisition (Site 4) | UK Domestic Appliance-Level Electricity (UK-DALE) / REFIT | Adaptive Charging Network (ACN-Data) | PG&E Schedule EV2-A Residential TOU |
| **Official Source** | https://data.openei.org/datasets/5502 | https://jack-kelly.com/data/ | https://ev.caltech.edu/dataset | https://www.pge.com/tariffs/ |
| **License** | Public Domain / Apache 2.0 (OEDI) | CC BY 4.0 | CC BY-NC-SA 4.0 | Public Utility Tariff Schedule |
| **Data type** | Measured Rooftop Solar PV Output | Measured Whole-Home Inflexible Demand | Empirical EV Charging Sessions | Published Retail Time-of-Use Electricity Rate |
| **Geographic location** | Golden / Denver, CO, USA | London / Berkshire / Loughborough, UK | Pasadena, CA, USA | Northern / Central California, USA |
| **Time period** | 2020 (8,760 continuous hours) | 2013–2014 (full annual profiles) | 2018–2021 (thousands of sessions) | Annual TOU schedule (Summer / Winter blocks) |
| **Time resolution** | 15-minute raw, resampled to 1 hour | 6-second / 8-second, resampled to 1 hour | Session-level timestamps (arrival/departure) | Hourly price tiers |
| **Variables** | `ac_power`, `dc_power`, `poa_irradiance` | `mains_active_power`, `aggregate_power` | `connectionTime`, `disconnectTime`, `kWhDelivered` | `price_per_kwh`, `export_rate` |
| **Units** | kW, W/m², °C | Watts (converted to kW) | Timestamp, kWh, hours | USD / kWh |
| **Access** | Direct open HTTP / AWS S3 data lake | Direct HTTP open download | Open API / CSV export | Direct public PDF / CSV tariff schedules |
| **Compatibility** | Aligned to UTC hourly index | Aligned to UTC hourly index | Informs residential arrival/departure windows | Directly mapped to hourly simulation horizon |
| **Limitations** | Single fixed tilt; minor inverter clipping | Climate differs from high-insolation US sites | Workplace/depot charging; filtered for residential | Policy-dependent; export compensation differs from retail |

---

## 3. Provenance and Multi-Dataset Harmonization
Because no single publicly accessible, non-gated repository simultaneously captures matched rooftop PV, household demand, bidirectional EV battery telemetry, and dynamic tariff data for an identical physical home over a full calendar year without restrictive NDAs:
1. **Cross-Dataset Framework**: We model a residential prosumer system where:
   - Solar PV generation is driven by **measured empirical PV production** (NREL PVDAQ Site 4, scaled to 5.0 kW peak capacity).
   - Household load is driven by **measured residential smart-meter load** (UK-DALE / REFIT hourly consumption, capturing genuine appliance cycling, baseline standby, and evening peaks).
   - EV connection parameters are parameterized using **ACN-Data empirical session distributions** (overnight connection window, typically 17:00 arrival to 07:00 departure, 20 kWh session demand).
   - Tariffs reflect the **commercial residential EV Time-of-Use structure** (off-peak, mid-peak, on-peak rates, and export feed-in credits).
2. **Attribution & Transparency**: The integrated dataset is explicitly identified as a *cross-dataset empirical co-simulation*, not a single physical house.

---

## 4. Preprocessing and Quality Assurance Pipeline
All raw time series undergo a deterministic preprocessing pipeline implemented in `src/preprocessing.py`:
1. **Timestamp Normalization**: Convert all timestamps to UTC `DatetimeIndex`.
2. **Duplicate Elimination**: Drop duplicate timestamps, preserving the first recorded observation.
3. **Resampling**: Uniform 1-hour interval integration ($\Delta t = 1.0\text{ h}$).
4. **Physical Range Bounds**:
   - PV generation: Clipped strictly to $[0, P_{\text{capacity}}]$ ($5.0\text{ kW}$). Nighttime generation (solar zenith $> 90^\circ$ or astronomical sunset) is strictly enforced to $0.0\text{ kW}$.
   - Household load: Strictly positive ($L_t \ge 0.05\text{ kW}$ baseload), filtered for transmission anomalies ($L_t \le 15.0\text{ kW}$).
5. **Short-Gap Interpolation**: Missing gaps $\le 3\text{ consecutive hours}$ are linearly interpolated; gaps $> 3\text{ hours}$ invalidate the daily record to prevent artificial data fabrication.
6. **Chronological Partitioning**: Strictly preserves temporal ordering (Train $\rightarrow$ Calibration $\rightarrow$ Validation $\rightarrow$ Test) across full day boundaries to prevent future information leakage into historical forecasters.

---

## 5. Download and Reproduction Instructions
For offline or air-gapped environments, the repository includes pre-processed, fully validated historical benchmark datasets in `data/processed/`.

To inspect or reload the raw real-world datasets:
1. **NREL PVDAQ**:
   - Visit: https://data.openei.org/datasets/5502
   - Download Site 4 1-year PV generation CSV.
   - Place in `data/raw/nrel_pvdaq_site4.csv`.
2. **UK-DALE / REFIT**:
   - Visit: https://jack-kelly.com/data/ or https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements
   - Extract House 1 or House 2 aggregate load CSV.
   - Place in `data/raw/residential_load_raw.csv`.
3. **Execute Ingestion CLI**:
   ```bash
   python -m src.cli validate-data --config configs/default.json
   ```
   The loader will automatically detect raw files in `data/raw/`, run quality checks, execute resampling and calibration, and update `data/processed/` and `docs/dataset_provenance.csv`.
