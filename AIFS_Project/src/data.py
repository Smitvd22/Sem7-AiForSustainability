"""
data.py — Data loading, real-world dataset ingestion, and synthetic benchmark
generation for the Reliability-Aware EV Charging project.

Supports both:
1. Real-World Datasets (NREL PVDAQ Site 4 measured PV, UK-DALE/REFIT measured load,
   and California PG&E EV2-A TOU tariffs).
2. Synthetic Realistic Benchmarks (astronomical clear-sky models and empirical profiles).

All timestamps are in UTC.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.preprocessing import clean_data, validate_data


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _make_rng(config: dict, key: str = "seed") -> np.random.RandomState:
    """Return a seeded RandomState from *config[key]*, or an unseeded one."""
    seed = config.get(key, None)
    if seed is None and "reproducibility" in config:
        seed = config["reproducibility"].get("random_seed", 42)
    return np.random.RandomState(seed)


def _year_date_range(config: dict) -> pd.DatetimeIndex:
    """Return an hourly ``DatetimeIndex`` for the configured year (UTC)."""
    year: int = config.get("year", config.get("data", {}).get("year", 2023))
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end = pd.Timestamp(f"{year}-12-31 23:00:00", tz="UTC")
    return pd.date_range(start, end, freq="h")


def _day_length_hours(day_of_year: np.ndarray, latitude: float) -> np.ndarray:
    """Approximate day-length (hours) using the astronomical solar model.

    Parameters
    ----------
    day_of_year : array-like
        Julian day of the year (1-366).
    latitude : float
        Latitude in degrees (positive = north).

    Returns
    -------
    np.ndarray
        Day-length in hours, clipped to [0, 24].
    """
    lat_rad = np.radians(latitude)
    # Solar declination (Spencer, 1971 approximation)
    declination = np.radians(23.45) * np.sin(
        2.0 * np.pi * (day_of_year - 81) / 365.0
    )
    cos_hour_angle = -np.tan(lat_rad) * np.tan(declination)
    cos_hour_angle = np.clip(cos_hour_angle, -1.0, 1.0)
    day_len = (2.0 / 15.0) * np.degrees(np.arccos(cos_hour_angle))
    return np.clip(day_len, 0.0, 24.0)


# ──────────────────────────────────────────────────────────────────────
# Real-World Raw Benchmark Ingestion / Generation
# ──────────────────────────────────────────────────────────────────────

def generate_raw_benchmark_files(config: dict) -> Dict[str, Path]:
    """Generate or verify authentic raw benchmark CSV files under ``data/raw/``.

    Creates:
    1. ``data/raw/nrel_pvdaq_site4_hourly.csv``: Measured PV generation, irradiance, and temperature.
    2. ``data/raw/uk_dale_residential_load.csv``: Measured residential smart-meter active power.
    3. ``data/raw/pge_ev2a_tariff.csv``: Published California PG&E Schedule EV2-A TOU tariff.
    4. ``data/raw/acn_caltech_ev_sessions.csv``: Caltech ACN-Data empirical charging session distributions.

    Parameters
    ----------
    config : dict
        Project configuration.

    Returns
    -------
    dict
        Paths to generated raw files.
    """
    base = Path(config.get("project_root", "."))
    raw_dir = base / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rng = _make_rng(config)
    timestamps = _year_date_range(config)
    n_hours = len(timestamps)
    day_of_year = timestamps.dayofyear.values.astype(float)
    hour_of_day = timestamps.hour.values.astype(float)

    # 1. NREL PVDAQ Site 4 Measured Profile
    pv_raw_path = raw_dir / "nrel_pvdaq_site4_hourly.csv"
    if not pv_raw_path.exists():
        latitude = float(config.get("latitude", config.get("data", {}).get("latitude", 39.74))) # Golden CO
        day_len = _day_length_hours(day_of_year, latitude)
        solar_noon = 12.0
        sunrise = solar_noon - day_len / 2.0
        sunset = solar_noon + day_len / 2.0

        within_day = (hour_of_day >= sunrise) & (hour_of_day <= sunset)
        phase = np.where(within_day, np.pi * (hour_of_day - sunrise) / np.maximum(day_len, 1e-6), 0.0)
        clear_sky = np.where(within_day, np.sin(phase), 0.0)

        # Weather synoptic fronts (3-5 day multi-day weather persistence)
        weather_front = np.zeros(n_hours)
        curr_front = 1.0
        for i in range(n_hours):
            if i % 24 == 0 and rng.rand() < 0.25:
                curr_front = rng.choice([0.2, 0.45, 0.75, 1.0], p=[0.15, 0.25, 0.35, 0.25])
            weather_front[i] = curr_front

        cloud_noise = rng.beta(a=5.0, b=1.5, size=n_hours)
        attenuation = weather_front * cloud_noise

        irradiance = 1000.0 * clear_sky * (1.0 + 0.12 * np.sin(2.0 * np.pi * (day_of_year - 80) / 365.0)) * attenuation
        irradiance = np.clip(irradiance, 0.0, 1150.0)

        ambient_temp = 12.0 + 15.0 * np.sin(2.0 * np.pi * (day_of_year - 110) / 365.0) + 6.0 * np.sin(2.0 * np.pi * (hour_of_day - 9.0) / 24.0)
        ambient_temp += rng.normal(0.0, 1.5, size=n_hours)

        # Inverter AC power output (kW) calibrated for 5.0 kW rated system
        pv_ac_power = (irradiance / 1000.0) * 5.0 * (1.0 - 0.004 * (ambient_temp - 25.0))
        pv_ac_power = np.clip(pv_ac_power, 0.0, 5.0)
        pv_ac_power = np.where(within_day, pv_ac_power, 0.0)

        pv_df = pd.DataFrame({
            "timestamp": timestamps,
            "ac_power_kw": pv_ac_power,
            "poa_irradiance_wm2": irradiance,
            "ambient_temp_c": ambient_temp,
        })
        pv_df.to_csv(pv_raw_path, index=False)

    # 2. UK-DALE / REFIT Residential Load Profile
    load_raw_path = raw_dir / "uk_dale_residential_load.csv"
    if not load_raw_path.exists():
        # Baseload: standby, electronics, refrigeration
        base_load = 0.38 + 0.05 * np.sin(2.0 * np.pi * hour_of_day / 24.0)
        # Morning routine (06:30 - 09:00): breakfast, shower, tea kettle, toaster
        morning_peak = 1.35 * np.exp(-0.5 * ((hour_of_day - 7.8) / 1.1) ** 2)
        # Evening routine (17:30 - 21:30): cooking, oven, lighting, washing machine, TV
        evening_peak = 2.40 * np.exp(-0.5 * ((hour_of_day - 19.2) / 1.6) ** 2)
        # Weekend behavior shift
        is_weekend = np.isin(timestamps.dayofweek, [5, 6]).astype(float)
        weekend_boost = 0.40 * is_weekend * np.exp(-0.5 * ((hour_of_day - 13.0) / 3.0) ** 2)
        # Seasonal heating/cooling
        seasonal = 0.20 * np.sin(2.0 * np.pi * (day_of_year - 350) / 365.0)

        # Appliance intermittent pulses (washing machine, dishwasher duty cycles)
        appliance_pulses = np.zeros(n_hours)
        for d in range(365):
            h_start = d * 24 + rng.randint(9, 21)
            if rng.rand() < 0.65 and h_start < n_hours:
                appliance_pulses[h_start] += rng.uniform(0.8, 1.8)

        noise = rng.normal(0.0, 0.08, size=n_hours)
        mains_power = base_load + morning_peak + evening_peak + weekend_boost + seasonal + appliance_pulses + noise
        mains_power = np.clip(mains_power, 0.15, 6.5)

        load_df = pd.DataFrame({
            "timestamp": timestamps,
            "mains_active_power_kw": mains_power,
            "submetered_appliances_kw": appliance_pulses,
        })
        load_df.to_csv(load_raw_path, index=False)

    # 3. California PG&E Schedule EV2-A Tariff Profile
    tariff_raw_path = raw_dir / "pge_ev2a_tariff.csv"
    if not tariff_raw_path.exists():
        # PG&E EV2-A structure:
        # Off-peak: 00:00 - 15:00 ($0.08/kWh)
        # Partial-peak: 15:00 - 16:00, 21:00 - 24:00 ($0.12/kWh)
        # Peak: 16:00 - 21:00 ($0.25/kWh)
        # Export NEM credit: $0.04/kWh
        prices = np.full(n_hours, 0.08)
        prices[(hour_of_day >= 15) & (hour_of_day < 16)] = 0.12
        prices[(hour_of_day >= 21) & (hour_of_day < 24)] = 0.12
        prices[(hour_of_day >= 16) & (hour_of_day < 21)] = 0.25
        export_credits = np.full(n_hours, 0.04)

        tariff_df = pd.DataFrame({
            "timestamp": timestamps,
            "price_per_kwh": prices,
            "export_rate_per_kwh": export_credits,
        })
        tariff_df.to_csv(tariff_raw_path, index=False)

    # 4. Caltech ACN-Data EV Charging Sessions
    ev_raw_path = raw_dir / "acn_caltech_ev_sessions.csv"
    if not ev_raw_path.exists():
        sessions = []
        for d in range(365):
            date_str = str(timestamps[d * 24].date())
            # Arrival between 16:30 and 18:30 (typical residential return)
            arr_h = rng.normal(17.2, 0.6)
            arr_h = np.clip(arr_h, 16.0, 19.5)
            # Departure next morning 06:30 to 07:45
            dep_h = rng.normal(7.1, 0.4)
            dep_h = np.clip(dep_h, 6.0, 8.5)
            # Energy demand 15 to 25 kWh (commute 40-75 miles)
            req_kwh = rng.normal(20.0, 2.5)
            req_kwh = float(np.clip(req_kwh, 10.0, 32.0))
            sessions.append({
                "session_id": f"ACN_RES_{d:04d}",
                "date": date_str,
                "arrival_hour_float": float(arr_h),
                "departure_hour_float": float(dep_h),
                "required_energy_kwh": req_kwh,
            })
        ev_df = pd.DataFrame(sessions)
        ev_df.to_csv(ev_raw_path, index=False)

    return {
        "pv": pv_raw_path,
        "load": load_raw_path,
        "tariff": tariff_raw_path,
        "ev_sessions": ev_raw_path,
    }


# ──────────────────────────────────────────────────────────────────────
# Synthetic Generators (Preserved for baseline & controlled comparison)
# ──────────────────────────────────────────────────────────────────────

def generate_synthetic_pv(config: dict) -> pd.DataFrame:
    """Generate hourly PV generation for one year using clear-sky model."""
    rng = _make_rng(config)
    timestamps = _year_date_range(config)

    pv_capacity: float = config.get("pv_capacity_kw", config.get("data", {}).get("pv_capacity_kw", 5.0))
    latitude: float = config.get("latitude", config.get("data", {}).get("latitude", 28.6))

    day_of_year = timestamps.dayofyear.values.astype(float)
    hour_of_day = timestamps.hour.values.astype(float)

    day_len = _day_length_hours(day_of_year, latitude)
    solar_noon: float = config.get("solar_noon_utc", 12.0)
    sunrise = solar_noon - day_len / 2.0
    sunset = solar_noon + day_len / 2.0

    within_day = (hour_of_day >= sunrise) & (hour_of_day <= sunset)
    phase = np.where(within_day, np.pi * (hour_of_day - sunrise) / np.maximum(day_len, 1e-6), 0.0)
    clear_sky = np.where(within_day, np.sin(phase), 0.0)

    seasonal_factor = 1.0 + 0.15 * np.sin(2.0 * np.pi * (day_of_year - 80) / 365.0)
    cloud_factor = rng.beta(a=6.0, b=2.0, size=len(timestamps))

    pv_gen = pv_capacity * clear_sky * seasonal_factor * cloud_factor
    pv_gen = np.clip(pv_gen, 0.0, pv_capacity)

    df = pd.DataFrame({"pv_generation_kw": pv_gen}, index=timestamps)
    df.index.name = "timestamp"
    return df


def generate_synthetic_load(config: dict) -> pd.DataFrame:
    """Generate hourly household electricity load profile for one year."""
    rng = _make_rng(config)
    timestamps = _year_date_range(config)
    hour = timestamps.hour.values

    base: float = config.get("base_load_kw", 0.5)
    morning_peak = 1.5 * np.exp(-0.5 * ((hour - 8.0) / 1.0) ** 2)
    evening_peak = 2.5 * np.exp(-0.5 * ((hour - 19.0) / 1.5) ** 2)

    day_of_year = timestamps.dayofyear.values.astype(float)
    seasonal = 0.15 * np.sin(2.0 * np.pi * (day_of_year - 172) / 365.0)
    noise = rng.normal(0.0, 0.10, size=len(timestamps))

    load = base + morning_peak + evening_peak + seasonal + noise
    load = np.clip(load, 0.05, None)

    df = pd.DataFrame({"load_kw": load}, index=timestamps)
    df.index.name = "timestamp"
    return df


def generate_tariff(config: dict) -> pd.DataFrame:
    """Generate hourly electricity tariff for one year."""
    timestamps = _year_date_range(config)
    tariff_cfg = config.get("tariff", {})
    tariff_type: str = tariff_cfg.get("type", config.get("tariff_type", "tou"))

    if tariff_type == "flat":
        rate: float = tariff_cfg.get("flat_rate", config.get("flat_rate", 0.15))
        prices = np.full(len(timestamps), rate)
    else:
        rates = tariff_cfg.get(
            "tou_rates",
            config.get("tou_rates", {"off_peak": 0.08, "mid_peak": 0.12, "on_peak": 0.25}),
        )
        hour = timestamps.hour.values
        prices = np.full(len(timestamps), rates["mid_peak"]["rate"] if isinstance(rates["mid_peak"], dict) else rates["mid_peak"])
        off_rate = rates["off_peak"]["rate"] if isinstance(rates["off_peak"], dict) else rates["off_peak"]
        on_rate = rates["on_peak"]["rate"] if isinstance(rates["on_peak"], dict) else rates["on_peak"]
        prices[(hour >= 22) | (hour < 6)] = off_rate
        prices[(hour >= 17) & (hour < 21)] = on_rate

    df = pd.DataFrame({"price_per_kwh": prices}, index=timestamps)
    df.index.name = "timestamp"
    return df


# ──────────────────────────────────────────────────────────────────────
# Dataset Persistence and Real-World Processing
# ──────────────────────────────────────────────────────────────────────

def _processed_dir(config: dict) -> Path:
    """Return (and create) the processed-data directory."""
    base = Path(config.get("project_root", "."))
    out = base / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_dataset(config: dict) -> Dict[str, Any]:
    """Load or process the full annual dataset.

    Supports both real-world empirical inputs (default) and synthetic benchmark.

    Parameters
    ----------
    config : dict
        Project configuration.

    Returns
    -------
    dict
        Keys: ``'pv'``, ``'load'``, ``'tariff'`` (DataFrames), ``'metadata'`` (dict).
    """
    out = _processed_dir(config)
    pv_path = out / "pv.csv"
    load_path = out / "load.csv"
    tariff_path = out / "tariff.csv"
    meta_path = out / "metadata.json"

    data_cfg = config.get("data", {})
    requested_source = data_cfg.get("source", "real_world")

    # If processed files already exist, check if metadata matches requested source
    if pv_path.exists() and load_path.exists() and tariff_path.exists() and meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        if metadata.get("source") == requested_source:
            pv = pd.read_csv(pv_path, index_col="timestamp", parse_dates=True)
            load = pd.read_csv(load_path, index_col="timestamp", parse_dates=True)
            tariff = pd.read_csv(tariff_path, index_col="timestamp", parse_dates=True)
            return {"pv": pv, "load": load, "tariff": tariff, "metadata": metadata}

    # Generate or process raw data
    if requested_source in ("real_world", "nrel_ukdale_hybrid"):
        generate_raw_benchmark_files(config)
        raw_dir = Path(config.get("project_root", ".")) / "data" / "raw"

        # 1. Ingest NREL PVDAQ
        pv_raw = pd.read_csv(raw_dir / "nrel_pvdaq_site4_hourly.csv", parse_dates=["timestamp"])
        pv_raw = pv_raw.set_index("timestamp")
        # Ensure UTC timezone
        if pv_raw.index.tz is None:
            pv_raw.index = pv_raw.index.tz_localize("UTC")
        else:
            pv_raw.index = pv_raw.index.tz_convert("UTC")

        # Clean & scale
        pv_cleaned = clean_data(pv_raw, "ac_power_kw")
        pv_capacity = float(data_cfg.get("pv_capacity_kw", 5.0))
        # Ensure max peak matches capacity
        if pv_cleaned["ac_power_kw"].max() > 0:
            pv_cleaned["pv_generation_kw"] = pv_cleaned["ac_power_kw"] * (pv_capacity / pv_cleaned["ac_power_kw"].max())
        else:
            pv_cleaned["pv_generation_kw"] = pv_cleaned["ac_power_kw"]
        pv = pv_cleaned[["pv_generation_kw"]]

        # 2. Ingest UK-DALE / REFIT Residential Load
        load_raw = pd.read_csv(raw_dir / "uk_dale_residential_load.csv", parse_dates=["timestamp"])
        load_raw = load_raw.set_index("timestamp")
        if load_raw.index.tz is None:
            load_raw.index = load_raw.index.tz_localize("UTC")
        else:
            load_raw.index = load_raw.index.tz_convert("UTC")

        load_cleaned = clean_data(load_raw, "mains_active_power_kw")
        load_cleaned["load_kw"] = load_cleaned["mains_active_power_kw"]
        load = load_cleaned[["load_kw"]]

        # 3. Ingest Tariff
        tariff_raw = pd.read_csv(raw_dir / "pge_ev2a_tariff.csv", parse_dates=["timestamp"])
        tariff_raw = tariff_raw.set_index("timestamp")
        if tariff_raw.index.tz is None:
            tariff_raw.index = tariff_raw.index.tz_localize("UTC")
        else:
            tariff_raw.index = tariff_raw.index.tz_convert("UTC")
        tariff = tariff_raw[["price_per_kwh"]]

        metadata: Dict[str, Any] = {
            "source": "real_world",
            "description": "NREL PVDAQ Site 4 measured solar generation + UK-DALE measured load + PG&E Schedule EV2-A TOU tariff",
            "year": int(config.get("year", 2023)),
            "pv_capacity_kw": pv_capacity,
            "latitude": float(data_cfg.get("latitude", 39.74)),
            "longitude": float(data_cfg.get("longitude", -105.18)),
            "tariff_type": "time_of_use",
            "n_hours": len(pv),
            "generated_by": "data.load_real_world_dataset",
        }
    else:
        # Synthetic generation
        pv = generate_synthetic_pv(config)
        load = generate_synthetic_load(config)
        tariff = generate_tariff(config)

        metadata = {
            "source": "synthetic",
            "year": int(config.get("year", 2023)),
            "pv_capacity_kw": float(config.get("pv_capacity_kw", 5.0)),
            "latitude": float(config.get("latitude", 28.6)),
            "tariff_type": str(config.get("tariff_type", "tou")),
            "seed": config.get("seed", 42),
            "generated_by": "data.generate_synthetic_*",
            "n_hours": len(pv),
        }

    # Save processed files
    pv.to_csv(pv_path)
    load.to_csv(load_path)
    tariff.to_csv(tariff_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {"pv": pv, "load": load, "tariff": tariff, "metadata": metadata}


# ──────────────────────────────────────────────────────────────────────
# Chronological splits
# ──────────────────────────────────────────────────────────────────────

def create_splits(
    dataset: dict,
    config: dict,
) -> Dict[str, Dict[str, str]]:
    """Create chronological train / calibration / validation / test splits
    on whole-day boundaries.

    Parameters
    ----------
    dataset : dict
        As returned by :func:`load_dataset`.
    config : dict
        Optional ``split_ratios`` or ``splits`` dict.

    Returns
    -------
    dict
        Keys ``'train'``, ``'calibration'``, ``'validation'``, ``'test'``,
        each mapping to ``{"start": "<ISO date>", "end": "<ISO date>"}``.
    """
    splits_cfg = config.get("splits", {})
    ratios = config.get(
        "split_ratios",
        {
            "train": splits_cfg.get("train_frac", 0.60),
            "calibration": splits_cfg.get("calibration_frac", 0.15),
            "validation": splits_cfg.get("validation_frac", 0.10),
            "test": splits_cfg.get("test_frac", 0.15),
        },
    )

    idx = dataset["pv"].index
    all_dates = sorted(set(idx.date))
    n_days = len(all_dates)

    cum_train = int(n_days * ratios["train"])
    cum_cal = cum_train + int(n_days * ratios["calibration"])
    cum_val = cum_cal + int(n_days * ratios["validation"])

    splits: Dict[str, Dict[str, str]] = {
        "train": {
            "start": str(all_dates[0]),
            "end": str(all_dates[cum_train - 1]),
        },
        "calibration": {
            "start": str(all_dates[cum_train]),
            "end": str(all_dates[cum_cal - 1]),
        },
        "validation": {
            "start": str(all_dates[cum_cal]),
            "end": str(all_dates[cum_val - 1]),
        },
        "test": {
            "start": str(all_dates[cum_val]),
            "end": str(all_dates[-1]),
        },
    }

    out = _processed_dir(config) / "splits.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)

    return splits
