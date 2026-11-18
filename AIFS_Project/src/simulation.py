"""
Reliability-Aware Scheduling of Home EV Charging Using Solar Forecast Confidence.

This module executes physical interval simulation evaluating pre-computed
charging and bidirectional discharging schedules against realized real-world data.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Single-day physical simulation
# ---------------------------------------------------------------------------

def simulate_day(
    schedule: dict,
    actual_data: dict,
    ev_params: dict,
    config: dict,
) -> dict:
    """Simulate one day of EV charging and bidirectional energy flows.

    Parameters
    ----------
    schedule : dict
        Output of a scheduler, containing ``charging_power`` (kW array) and
        optionally ``discharging_power``, ``p_e2h``, ``p_e2g`` (kW arrays).
    actual_data : dict
        Must contain ``pv_actual`` (kW), ``load`` (kW), ``tariff`` ($/kWh).
    ev_params : dict
        EV battery parameters: capacity, initial SOC, efficiency, ratings.
    config : dict
        Simulation configuration:
        - ``dt`` (float): interval duration in hours (default 1.0).
        - ``export_rate`` (float): $/kWh paid for exported electricity.
        - ``degradation_cost_per_kwh`` (float): battery degradation factor.

    Returns
    -------
    dict
        Detailed physical and economic simulation results for the day.
    """
    dt: float = float(config.get("dt", 1.0))
    export_rate: float = float(config.get("export_rate", config.get("tariff", {}).get("export_rate", 0.04)))
    c_deg: float = float(config.get("degradation_cost_per_kwh", config.get("bidirectional", {}).get("degradation_cost_per_kwh", 0.0)))

    p_charge = np.asarray(schedule.get("charging_power", []), dtype=float)
    T = len(p_charge)

    if "discharging_power" in schedule:
        p_discharge = np.asarray(schedule["discharging_power"], dtype=float)
    else:
        p_discharge = np.zeros(T)

    pv_actual = np.asarray(actual_data["pv_actual"], dtype=float)
    load = np.asarray(actual_data["load"], dtype=float)
    tariff = np.asarray(actual_data["tariff"], dtype=float)

    eta_c: float = float(ev_params["charging_efficiency"])
    eta_d: float = float(ev_params.get("discharge_efficiency", config.get("bidirectional", {}).get("discharge_efficiency", eta_c)))
    battery_cap: float = float(ev_params["battery_capacity_kwh"])
    e_init: float = float(ev_params["initial_soc_kwh"])
    required_energy: float = float(ev_params["required_energy_kwh"])
    e_target: float = e_init + required_energy

    # Interval-by-interval energy accounting
    grid_import = np.zeros(T)
    export = np.zeros(T)
    pv_to_load = np.zeros(T)
    pv_to_ev = np.zeros(T)
    pv_to_grid = np.zeros(T)
    pv_self_consumed = np.zeros(T)
    e2h_power = np.zeros(T)
    e2g_power = np.zeros(T)
    grid_to_load = np.zeros(T)
    grid_to_ev = np.zeros(T)
    bus_residuals = np.zeros(T)

    ev_energy_trace = np.zeros(T + 1)
    ev_energy_trace[0] = e_init

    for t in range(T):
        pc = p_charge[t]
        pd = p_discharge[t]
        pv = pv_actual[t]
        ld = load[t]

        # 1. EV Discharging decomposition: E2H serves domestic load first
        p_e2h = min(pd, max(0.0, ld - pv))
        p_e2g = max(0.0, pd - p_e2h)
        e2h_power[t] = p_e2h
        e2g_power[t] = p_e2g

        # 2. Solar PV routing
        # Solar to home
        pv_h = min(pv, ld)
        pv_to_load[t] = pv_h
        pv_surplus = max(0.0, pv - ld)

        # Solar to EV
        pv_ev = min(pc, pv_surplus)
        pv_to_ev[t] = pv_ev

        # Solar to Grid
        pv_g = max(0.0, pv_surplus - pv_ev)
        pv_to_grid[t] = pv_g

        # Total on-site solar self-consumed
        pv_self_consumed[t] = pv_h + pv_ev

        # 3. Grid interactions
        # Grid to Home
        g_h = max(0.0, ld - pv_h - p_e2h)
        grid_to_load[t] = g_h

        # Grid to EV
        g_ev = max(0.0, pc - pv_ev)
        grid_to_ev[t] = g_ev

        # Aggregated meter exchange
        grid_import[t] = g_h + g_ev
        export[t] = pv_g + p_e2g

        # Numerical conservation audit
        bus_residuals[t] = (pv + grid_import[t] + pd) - (ld + pc + export[t])

        # 4. Battery energy evolution
        net_energy_change = (eta_c * pc - (pd / eta_d)) * dt
        ev_energy_trace[t + 1] = np.clip(
            ev_energy_trace[t] + net_energy_change, 0.0, battery_cap
        )

    # Economic accounting
    import_cost = float(np.sum(tariff * grid_import * dt))
    export_revenue = float(np.sum(export_rate * export * dt))
    degradation_cost = float(np.sum(c_deg * p_discharge * dt))
    net_cost = import_cost - export_revenue + degradation_cost
    total_cost = import_cost  # Preserved standard retail import expenditure

    final_soc_kwh = float(ev_energy_trace[-1])
    deadline_met = final_soc_kwh >= e_target - 1e-5
    unmet_energy_kwh = 0.0 if deadline_met else float(max(0.0, e_target - final_soc_kwh))
    peak_grid_import_kw = float(np.max(grid_import)) if T > 0 else 0.0
    peak_grid_export_kw = float(np.max(export)) if T > 0 else 0.0

    return {
        "charging_power": p_charge,
        "discharging_power": p_discharge,
        "p_e2h": e2h_power,
        "p_e2g": e2g_power,
        "grid_import": grid_import,
        "export": export,
        "grid_to_load": grid_to_load,
        "grid_to_ev": grid_to_ev,
        "pv_to_load": pv_to_load,
        "pv_to_ev": pv_to_ev,
        "pv_to_grid": pv_to_grid,
        "pv_self_consumed": pv_self_consumed,
        "ev_energy_trace": ev_energy_trace,
        "import_cost": import_cost,
        "total_cost": total_cost,
        "export_revenue": export_revenue,
        "degradation_cost": degradation_cost,
        "net_cost": net_cost,
        "deadline_met": deadline_met,
        "final_soc_kwh": final_soc_kwh,
        "unmet_energy_kwh": unmet_energy_kwh,
        "peak_grid_import_kw": peak_grid_import_kw,
        "peak_grid_export_kw": peak_grid_export_kw,
        "battery_throughput_kwh": float(np.sum(p_discharge * dt)),
        "max_bus_residual": float(np.max(np.abs(bus_residuals))),
    }


# ---------------------------------------------------------------------------
# Multi-day simulation
# ---------------------------------------------------------------------------

def simulate_period(
    days_data: list[dict],
    controller_fn: Callable[..., dict],
    config: dict,
) -> list[dict]:
    """Run ``simulate_day`` for each day in a multi-day dataset."""
    results: list[dict] = []

    for day in days_data:
        scheduler_inputs: dict = {
            "pv_forecast": np.asarray(day["pv_forecast"], dtype=float),
            "load": np.asarray(day["load"], dtype=float),
            "tariff": np.asarray(day["tariff"], dtype=float),
            "ev_params": day["ev_params"],
            "config": config,
        }

        if "pv_actual" in day:
            scheduler_inputs["actual_pv"] = np.asarray(day["pv_actual"], dtype=float)

        schedule = controller_fn(scheduler_inputs)

        actual_data = {
            "pv_actual": np.asarray(day["pv_actual"], dtype=float),
            "load": np.asarray(day["load"], dtype=float),
            "tariff": np.asarray(day["tariff"], dtype=float),
        }

        day_result = simulate_day(
            schedule=schedule,
            actual_data=actual_data,
            ev_params=day["ev_params"],
            config=config,
        )

        day_result["date"] = day.get("date")
        day_result["schedule_status"] = schedule.get("status", "unknown")
        day_result["method"] = schedule.get("method", "unknown")
        day_result["solver_time"] = schedule.get("solver_time", 0.0)

        results.append(day_result)

    return results


# ---------------------------------------------------------------------------
# Data preparation helper
# ---------------------------------------------------------------------------

def prepare_daily_inputs(
    dataset: dict,
    date: Any,
    config: dict,
) -> dict:
    """Extract one day's data from the full dataset and build scheduler inputs."""
    n_intervals: int = config.get("n_intervals", 24)
    dt: float = config.get("dt", 1.0)

    arrival_hour: int = config.get("arrival_hour", 17)
    departure_hour: int = config.get("departure_hour", 7)

    availability = _build_availability_mask(
        arrival_hour=arrival_hour,
        departure_hour=departure_hour,
        n_intervals=n_intervals,
        dt=dt,
    )

    pv_forecast = np.asarray(dataset["pv_forecast"][date], dtype=float)
    pv_actual = np.asarray(dataset["pv_actual"][date], dtype=float)
    load = np.asarray(dataset["load"][date], dtype=float)
    tariff = np.asarray(dataset["tariff"][date], dtype=float)

    ev_params: dict = {
        "battery_capacity_kwh": config["battery_capacity_kwh"],
        "initial_soc_kwh": config["initial_soc_kwh"],
        "required_energy_kwh": config["required_energy_kwh"],
        "max_charger_power_kw": config["max_charger_power_kw"],
        "charging_efficiency": config["charging_efficiency"],
        "availability": availability,
    }

    if "max_discharge_power_kw" in config:
        ev_params["max_discharge_power_kw"] = config["max_discharge_power_kw"]
    if "discharge_efficiency" in config:
        ev_params["discharge_efficiency"] = config["discharge_efficiency"]
    if "min_soc_reserve_kwh" in config:
        ev_params["min_soc_reserve_kwh"] = config["min_soc_reserve_kwh"]

    return {
        "pv_forecast": pv_forecast,
        "load": load,
        "tariff": tariff,
        "actual_pv": pv_actual,
        "ev_params": ev_params,
        "config": config,
    }


def _build_availability_mask(
    arrival_hour: int,
    departure_hour: int,
    n_intervals: int = 24,
    dt: float = 1.0,
) -> np.ndarray:
    """Create binary availability mask for a potentially overnight EV window."""
    mask = np.zeros(n_intervals, dtype=float)
    intervals_per_hour = 1.0 / dt

    if arrival_hour < departure_hour:
        start_idx = int(arrival_hour * intervals_per_hour)
        end_idx = int(departure_hour * intervals_per_hour)
        mask[start_idx:end_idx] = 1.0
    else:
        start_idx = int(arrival_hour * intervals_per_hour)
        end_idx = int(departure_hour * intervals_per_hour)
        mask[start_idx:] = 1.0
        mask[:end_idx] = 1.0

    return mask
