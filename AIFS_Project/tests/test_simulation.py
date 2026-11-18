"""
Unit tests for simulation and physical energy accounting.
"""

import numpy as np
import pytest

from src.simulation import simulate_day


@pytest.fixture
def base_sim_setup():
    T = 24
    dt = 1.0
    ev_params = {
        "battery_capacity_kwh": 40.0,
        "initial_soc_kwh": 10.0,
        "required_energy_kwh": 20.0,
        "max_charger_power_kw": 7.0,
        "charging_efficiency": 0.90,
    }
    config = {"dt": dt, "export_rate": 0.04}
    return ev_params, config


def test_no_negative_grid_imports(base_sim_setup):
    ev_params, config = base_sim_setup
    T = 24
    # High PV, low load
    actual_data = {
        "pv_actual": np.full(T, 10.0),
        "load": np.full(T, 1.0),
        "tariff": np.full(T, 0.15),
    }
    schedule = {"charging_power": np.zeros(T)}

    res = simulate_day(schedule, actual_data, ev_params, config)
    # Grid import must be non-negative
    assert (res["grid_import"] >= 0.0).all()
    # When PV (10) > load (1), grid import should be 0, export should be 9
    assert np.allclose(res["grid_import"], 0.0)
    assert np.allclose(res["export"], 9.0)


def test_battery_energy_conservation_and_capacity_cap(base_sim_setup):
    ev_params, config = base_sim_setup
    T = 24
    p_charge = np.zeros(T)
    # Charge 5 kW for 5 hours = 25 kWh gross * 0.9 = 22.5 kWh net
    p_charge[0:5] = 5.0
    schedule = {"charging_power": p_charge}
    actual_data = {
        "pv_actual": np.zeros(T),
        "load": np.full(T, 1.0),
        "tariff": np.full(T, 0.15),
    }

    res = simulate_day(schedule, actual_data, ev_params, config)
    # Battery initial = 10.0
    # Final should be 10.0 + 22.5 = 32.5 <= 40.0
    assert np.isclose(res["final_soc_kwh"], 32.5)
    # Battery capacity never exceeded
    assert (res["ev_energy_trace"] <= ev_params["battery_capacity_kwh"]).all()
    # Required was 20.0 (target 30.0), so 32.5 >= 30.0 -> deadline met
    assert res["deadline_met"] is True
    assert res["unmet_energy_kwh"] == 0.0


def test_pv_exceeding_and_insufficient_for_load(base_sim_setup):
    ev_params, config = base_sim_setup
    T = 2
    # Interval 0: PV (5) > load (2) + charge (1) -> import = 0, export = 2, pv_to_ev = 1
    # Interval 1: PV (1) < load (2) + charge (1) -> import = 2, export = 0, pv_to_ev = 0
    actual_data = {
        "pv_actual": np.array([5.0, 1.0]),
        "load": np.array([2.0, 2.0]),
        "tariff": np.array([0.10, 0.10]),
    }
    schedule = {"charging_power": np.array([1.0, 1.0])}

    res = simulate_day(schedule, actual_data, ev_params, config)

    assert np.isclose(res["grid_import"][0], 0.0)
    assert np.isclose(res["export"][0], 2.0)
    assert np.isclose(res["pv_to_ev"][0], 1.0)

    assert np.isclose(res["grid_import"][1], 2.0)
    assert np.isclose(res["export"][1], 0.0)
    assert np.isclose(res["pv_to_ev"][1], 0.0)

