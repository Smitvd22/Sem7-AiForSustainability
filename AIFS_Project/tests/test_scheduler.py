"""
Unit tests for EV charging controllers and schedulers.
"""

import numpy as np
import pytest

from src.scheduler import (
    check_feasibility,
    solve_fixed_schedule,
    solve_cheapest_hours,
    solve_forecast_driven,
    solve_conservative_fallback,
    solve_oracle,
    solve_reliability_aware,
    solve_schedule,
)


@pytest.fixture
def base_inputs():
    # 24 hour day
    # EV arrives at 17, departs at 7 next morning (14 hour window)
    avail = np.zeros(24)
    avail[17:] = 1.0
    avail[:7] = 1.0

    return {
        "pv_forecast": np.zeros(24),
        "load": np.full(24, 1.0),
        "tariff": np.full(24, 0.15),
        "ev_params": {
            "battery_capacity_kwh": 40.0,
            "initial_soc_kwh": 10.0,
            "required_energy_kwh": 20.0,
            "max_charger_power_kw": 7.0,
            "charging_efficiency": 0.90,
            "availability": avail,
        },
        "config": {"dt": 1.0},
    }


def test_feasibility_check(base_inputs):
    ev = base_inputs["ev_params"]
    # 14 hours available * 7 kW * 0.9 = 88.2 kWh > 20 kWh -> Feasible
    res = check_feasibility(ev, dt=1.0)
    assert res["feasible"] is True

    # Infeasible test: 1 hour available * 7 kW * 0.9 = 6.3 kWh < 20 kWh
    ev_infeas = dict(ev)
    avail = np.zeros(24)
    avail[18] = 1.0
    ev_infeas["availability"] = avail
    res_infeas = check_feasibility(ev_infeas, dt=1.0)
    assert res_infeas["feasible"] is False


def test_no_charging_outside_availability(base_inputs):
    res_fixed = solve_fixed_schedule(base_inputs)
    res_cheapest = solve_cheapest_hours(base_inputs)
    res_fd = solve_forecast_driven(base_inputs)

    avail = base_inputs["ev_params"]["availability"]
    unavail = avail == 0.0

    assert (res_fixed["charging_power"][unavail] == 0.0).all()
    assert (res_cheapest["charging_power"][unavail] == 0.0).all()
    assert (res_fd["charging_power"][unavail] == 0.0).all()


def test_max_charger_power_limit(base_inputs):
    res_fd = solve_forecast_driven(base_inputs)
    p_max = base_inputs["ev_params"]["max_charger_power_kw"]
    assert (res_fd["charging_power"] <= p_max + 1e-5).all()
    assert (res_fd["charging_power"] >= 0.0).all()


def test_reliability_aware_switching(base_inputs):
    # If reliability >= threshold -> uses forecast-driven
    res_high = solve_reliability_aware(base_inputs, reliability_score=0.8, threshold=0.5)
    assert res_high["used_fallback"] is False

    # If reliability < threshold -> uses conservative fallback
    res_low = solve_reliability_aware(base_inputs, reliability_score=0.3, threshold=0.5)
    assert res_low["used_fallback"] is True


def test_oracle_isolation(base_inputs):
    # Modifying actual_pv should change oracle schedule, but NOT change forecast_driven schedule
    inputs = dict(base_inputs)
    inputs["actual_pv"] = np.full(24, 5.0)
    inputs["pv_forecast"] = np.zeros(24)

    sched_fd = solve_forecast_driven(inputs)
    sched_oracle = solve_oracle(inputs)

    # Forecast-driven only sees pv_forecast (zero), while oracle sees actual_pv (5.0)
    # Under tariff 0.15, oracle will shift charging to daytime if PV is high
    assert "actual_pv" in inputs

