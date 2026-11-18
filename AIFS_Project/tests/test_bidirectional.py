"""
Unit tests for Bidirectional EV operations (E2H and E2G), energy conservation,
battery reserve protection, and non-simultaneity guarantees.
"""

import numpy as np
import pytest

from src.scheduler import solve_forecast_driven, solve_schedule
from src.simulation import simulate_day


@pytest.fixture
def bidi_inputs():
    T = 24
    dt = 1.0
    # EV connected from 17:00 to 07:00 (14-hour overnight window)
    avail = np.zeros(T)
    avail[17:] = 1.0
    avail[:7] = 1.0

    pv = np.zeros(T)
    pv[8:17] = [0.5, 1.5, 3.0, 4.5, 4.8, 4.2, 2.5, 1.0, 0.2]

    load = np.full(T, 1.0)
    load[17:21] = 2.5  # Evening domestic peak

    # TOU: $0.08 off-peak, $0.12 mid-peak, $0.25 on-peak (17:00 - 21:00)
    tariff = np.full(T, 0.12)
    tariff[:6] = 0.08
    tariff[22:] = 0.08
    tariff[17:21] = 0.25

    ev_params = {
        "battery_capacity_kwh": 40.0,
        "initial_soc_kwh": 20.0,  # Starts with ample energy to test discharging
        "required_energy_kwh": 5.0,  # Target: 25.0 kWh
        "max_charger_power_kw": 7.0,
        "max_discharge_power_kw": 7.0,
        "charging_efficiency": 0.90,
        "discharge_efficiency": 0.90,
        "min_soc_reserve_kwh": 8.0,
        "availability": avail,
    }

    config = {
        "dt": dt,
        "export_rate": 0.04,
        "degradation_cost_per_kwh": 0.01,
        "bidirectional": {
            "enable_e2h": True,
            "enable_e2g": True,
            "max_discharge_power_kw": 7.0,
            "discharge_efficiency": 0.90,
            "min_soc_reserve_kwh": 8.0,
            "degradation_cost_per_kwh": 0.01,
        },
    }

    return {
        "pv_forecast": pv,
        "actual_pv": pv,
        "load": load,
        "tariff": tariff,
        "ev_params": ev_params,
        "config": config,
    }


def test_e2h_only_peak_shaving(bidi_inputs):
    inputs = dict(bidi_inputs)
    cfg = dict(inputs["config"])
    cfg["enable_e2h"] = True
    cfg["enable_e2g"] = False
    inputs["config"] = cfg

    sched = solve_forecast_driven(inputs)
    assert sched["status"] == "optimal"

    # E2H should be active during evening peak, E2G must be strictly zero
    assert np.sum(sched["p_e2h"]) > 0.0
    assert np.allclose(sched["p_e2g"], 0.0)

    # Discharging should not exceed household load
    for t in range(24):
        assert sched["p_e2h"][t] <= inputs["load"][t] + 1e-5


def test_e2g_grid_export(bidi_inputs):
    inputs = dict(bidi_inputs)
    cfg = dict(inputs["config"])
    cfg["enable_e2h"] = False
    cfg["enable_e2g"] = True
    cfg["export_rate"] = 0.20  # High export tariff to incentivize V2G export
    inputs["config"] = cfg

    sched = solve_forecast_driven(inputs)
    assert sched["status"] == "optimal"

    # E2G active, E2H zero
    assert np.allclose(sched["p_e2h"], 0.0)
    assert np.sum(sched["p_e2g"]) > 0.0


def test_battery_reserve_protection(bidi_inputs):
    # Initial SOC close to reserve
    inputs = dict(bidi_inputs)
    ev_p = dict(inputs["ev_params"])
    ev_p["initial_soc_kwh"] = 9.0  # Only 1.0 kWh above reserve
    ev_p["min_soc_reserve_kwh"] = 8.0
    inputs["ev_params"] = ev_p

    sched = solve_forecast_driven(inputs)
    actual_data = {
        "pv_actual": inputs["actual_pv"],
        "load": inputs["load"],
        "tariff": inputs["tariff"],
    }
    sim = simulate_day(sched, actual_data, ev_p, inputs["config"])

    # Verify battery energy never drops below reserve
    assert (sim["ev_energy_trace"] >= ev_p["min_soc_reserve_kwh"] - 1e-5).all()


def test_departure_deadline_enforced(bidi_inputs):
    inputs = dict(bidi_inputs)
    sched = solve_forecast_driven(inputs)
    actual_data = {
        "pv_actual": inputs["actual_pv"],
        "load": inputs["load"],
        "tariff": inputs["tariff"],
    }
    sim = simulate_day(sched, actual_data, inputs["ev_params"], inputs["config"])

    target = inputs["ev_params"]["initial_soc_kwh"] + inputs["ev_params"]["required_energy_kwh"]
    assert sim["deadline_met"] is True
    assert sim["final_soc_kwh"] >= target - 1e-5
    assert sim["unmet_energy_kwh"] == 0.0


def test_no_simultaneous_charging_and_discharging(bidi_inputs):
    sched = solve_forecast_driven(bidi_inputs)
    pc = sched["charging_power"]
    pd = sched["discharging_power"]

    # At no interval should both pc and pd be simultaneously positive
    simul = (pc > 1e-4) & (pd > 1e-4)
    assert not np.any(simul)


def test_strict_energy_balance_conservation(bidi_inputs):
    sched = solve_forecast_driven(bidi_inputs)
    actual_data = {
        "pv_actual": bidi_inputs["actual_pv"],
        "load": bidi_inputs["load"],
        "tariff": bidi_inputs["tariff"],
    }
    sim = simulate_day(sched, actual_data, bidi_inputs["ev_params"], bidi_inputs["config"])

    # Max bus residual must be below numerical precision threshold
    assert sim["max_bus_residual"] < 1e-5
