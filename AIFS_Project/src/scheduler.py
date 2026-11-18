"""
Reliability-Aware Scheduling of Home EV Charging Using Solar Forecast Confidence.

This module implements all EV charging and bidirectional (E2G/E2H) controllers.
Each scheduler shares a common interface:
    Input:  dict with keys pv_forecast, load, tariff, ev_params, config, (actual_pv for oracle)
    Output: dict with keys charging_power, discharging_power, p_e2h, p_e2g, status, method, solver_time
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.optimize import linprog, OptimizeResult


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def check_feasibility(ev_params: dict, dt: float) -> dict:
    """Check whether the required energy can be delivered within the connection window.

    Parameters
    ----------
    ev_params : dict
        Must contain *battery_capacity_kwh*, *initial_soc_kwh*,
        *required_energy_kwh*, *max_charger_power_kw*, *charging_efficiency*,
        and *availability* (binary array, one entry per interval).
    dt : float
        Duration of each time interval in hours (e.g. 1.0 for hourly).

    Returns
    -------
    dict
        ``feasible`` (bool), ``max_deliverable_kwh``, ``required_kwh``,
        ``available_hours``.
    """
    availability: np.ndarray = np.asarray(ev_params["availability"], dtype=float)
    available_intervals = float(np.sum(availability))
    available_hours = available_intervals * dt

    p_max: float = ev_params["max_charger_power_kw"]
    eta: float = ev_params["charging_efficiency"]
    required_kwh: float = ev_params["required_energy_kwh"]

    # Maximum energy that can be delivered to the battery
    max_deliverable_kwh = p_max * eta * available_hours

    return {
        "feasible": max_deliverable_kwh >= required_kwh - 1e-6,
        "max_deliverable_kwh": max_deliverable_kwh,
        "required_kwh": required_kwh,
        "available_hours": available_hours,
    }


# ---------------------------------------------------------------------------
# B1 – Fixed (uniform) schedule
# ---------------------------------------------------------------------------

def solve_fixed_schedule(inputs: dict) -> dict:
    """Distribute required energy evenly across available intervals.

    Parameters
    ----------
    inputs : dict
        Standard scheduler input dict.

    Returns
    -------
    dict
        Standard scheduler output dict with ``method='fixed'``.
    """
    t_start = time.perf_counter()

    ev = inputs["ev_params"]
    config = inputs.get("config", {})
    dt: float = config.get("dt", 1.0)

    availability = np.asarray(ev["availability"], dtype=float)
    n_intervals = len(availability)
    p_max: float = ev["max_charger_power_kw"]
    eta: float = ev["charging_efficiency"]
    required_energy: float = ev["required_energy_kwh"]

    feas = check_feasibility(ev, dt)
    if not feas["feasible"]:
        return {
            "charging_power": np.zeros(n_intervals),
            "discharging_power": np.zeros(n_intervals),
            "p_e2h": np.zeros(n_intervals),
            "p_e2g": np.zeros(n_intervals),
            "status": "infeasible",
            "method": "fixed",
            "solver_time": time.perf_counter() - t_start,
        }

    energy_to_draw = required_energy / eta
    avail_idx = np.where(availability > 0.5)[0]
    n_avail = len(avail_idx)

    charging_power = np.zeros(n_intervals)
    uniform_power = energy_to_draw / (n_avail * dt)

    if uniform_power <= p_max:
        charging_power[avail_idx] = uniform_power
    else:
        remaining_energy = energy_to_draw
        remaining_idx = list(avail_idx)
        while remaining_energy > 1e-9 and remaining_idx:
            per_slot = remaining_energy / (len(remaining_idx) * dt)
            if per_slot <= p_max:
                for idx in remaining_idx:
                    charging_power[idx] = per_slot
                remaining_energy = 0.0
            else:
                for idx in remaining_idx:
                    charging_power[idx] = p_max
                remaining_energy -= len(remaining_idx) * p_max * dt
                remaining_idx = []

    solver_time = time.perf_counter() - t_start
    return {
        "charging_power": charging_power,
        "discharging_power": np.zeros(n_intervals),
        "p_e2h": np.zeros(n_intervals),
        "p_e2g": np.zeros(n_intervals),
        "status": "optimal",
        "method": "fixed",
        "solver_time": solver_time,
    }


# ---------------------------------------------------------------------------
# B2 – Cheapest-hours (greedy tariff-based)
# ---------------------------------------------------------------------------

def solve_cheapest_hours(inputs: dict) -> dict:
    """Sort available intervals by tariff ascending; fill cheapest first at P_max.

    Parameters
    ----------
    inputs : dict
        Standard scheduler input dict.

    Returns
    -------
    dict
        Standard scheduler output dict with ``method='cheapest_hours'``.
    """
    t_start = time.perf_counter()

    ev = inputs["ev_params"]
    config = inputs.get("config", {})
    dt: float = config.get("dt", 1.0)
    tariff = np.asarray(inputs["tariff"], dtype=float)

    availability = np.asarray(ev["availability"], dtype=float)
    n_intervals = len(availability)
    p_max: float = ev["max_charger_power_kw"]
    eta: float = ev["charging_efficiency"]
    required_energy: float = ev["required_energy_kwh"]

    feas = check_feasibility(ev, dt)
    if not feas["feasible"]:
        return {
            "charging_power": np.zeros(n_intervals),
            "discharging_power": np.zeros(n_intervals),
            "p_e2h": np.zeros(n_intervals),
            "p_e2g": np.zeros(n_intervals),
            "status": "infeasible",
            "method": "cheapest_hours",
            "solver_time": time.perf_counter() - t_start,
        }

    energy_to_draw = required_energy / eta
    avail_idx = np.where(availability > 0.5)[0]
    sorted_idx = avail_idx[np.argsort(tariff[avail_idx])]

    charging_power = np.zeros(n_intervals)
    remaining = energy_to_draw

    for idx in sorted_idx:
        if remaining <= 1e-9:
            break
        can_deliver = p_max * dt
        if can_deliver >= remaining:
            charging_power[idx] = remaining / dt
            remaining = 0.0
        else:
            charging_power[idx] = p_max
            remaining -= can_deliver

    solver_time = time.perf_counter() - t_start
    return {
        "charging_power": charging_power,
        "discharging_power": np.zeros(n_intervals),
        "p_e2h": np.zeros(n_intervals),
        "p_e2g": np.zeros(n_intervals),
        "status": "optimal",
        "method": "cheapest_hours",
        "solver_time": solver_time,
    }


# ---------------------------------------------------------------------------
# Bidirectional LP Core (B3, B4, B5, B6 and Scenarios S1 - S4)
# ---------------------------------------------------------------------------

def _build_and_solve_lp(
    pv: np.ndarray,
    load: np.ndarray,
    tariff: np.ndarray,
    ev_params: dict,
    config: dict,
    method_label: str,
) -> dict:
    """Build and solve the cost-minimizing LP for EV charging with E2G/E2H support.

    Decision variables per interval t:
        x = [p_c (0..T-1), p_e2h (T..2T-1), p_e2g (2T..3T-1), g (3T..4T-1), x_grid (4T..5T-1)]

    Objective:
        minimise  Σ (tariff_t · g_t - export_rate · x_grid_t + c_deg · (p_e2h_t + p_e2g_t)) · dt

    Physical and Operational Constraints:
        - Home Bus Balance: -p_c(t) + p_e2h(t) + p_e2g(t) + g(t) - x_grid(t) = load(t) - pv(t)
        - Inverter Discharge Limit: p_e2h(t) + p_e2g(t) <= P_d_max · a(t)
        - E2H Upper Bound: p_e2h(t) <= max(0, load(t) - pv(t)) · enable_e2h
        - E2G Upper Bound: p_e2g(t) <= P_d_max · enable_e2g
        - Battery Energy Tracking:
            E(t) = E_init + Σ_{k=0}^{t-1} (η_c · p_c(k) - (p_e2h(k) + p_e2g(k)) / η_d) · dt
            E_reserve <= E(t) <= E_cap
        - Departure Requirement: E(T) >= E_target
    """
    t_start = time.perf_counter()

    dt: float = config.get("dt", 1.0)
    T = len(pv)

    # Feature flags for bidirectional operation
    bidi_cfg = config.get("bidirectional", {})
    enable_e2h: bool = bool(config.get("enable_e2h", bidi_cfg.get("enable_e2h", False)))
    enable_e2g: bool = bool(config.get("enable_e2g", bidi_cfg.get("enable_e2g", False)))

    export_rate: float = float(config.get("export_rate", config.get("tariff", {}).get("export_rate", 0.04)))
    c_deg: float = float(config.get("degradation_cost_per_kwh", bidi_cfg.get("degradation_cost_per_kwh", 0.0)))

    availability = np.asarray(ev_params["availability"], dtype=float)
    p_c_max: float = float(ev_params["max_charger_power_kw"])
    p_d_max: float = float(ev_params.get("max_discharge_power_kw", bidi_cfg.get("max_discharge_power_kw", p_c_max)))
    eta_c: float = float(ev_params["charging_efficiency"])
    eta_d: float = float(ev_params.get("discharge_efficiency", bidi_cfg.get("discharge_efficiency", eta_c)))

    battery_cap: float = float(ev_params["battery_capacity_kwh"])
    e_init: float = float(ev_params["initial_soc_kwh"])
    required_energy: float = float(ev_params["required_energy_kwh"])
    e_target: float = e_init + required_energy
    e_reserve: float = float(ev_params.get("min_soc_reserve_kwh", bidi_cfg.get("min_soc_reserve_kwh", 0.20 * battery_cap)))

    feas = check_feasibility(ev_params, dt)
    if not feas["feasible"]:
        return {
            "charging_power": np.zeros(T),
            "discharging_power": np.zeros(T),
            "p_e2h": np.zeros(T),
            "p_e2g": np.zeros(T),
            "grid_import": np.zeros(T),
            "grid_export": np.zeros(T),
            "status": "infeasible",
            "method": method_label,
            "solver_time": time.perf_counter() - t_start,
        }

    # Total variables: 5 * T
    n_vars = 5 * T

    # 1. Objective Vector c
    c = np.zeros(n_vars)
    # g (import) coefficients
    c[3 * T : 4 * T] = tariff * dt
    # x_grid (export) coefficients
    c[4 * T : 5 * T] = -export_rate * dt
    # degradation on discharge
    c[T : 2 * T] = c_deg * dt
    c[2 * T : 3 * T] = c_deg * dt

    # 2. Equality Constraints (Bus Balance)
    # -p_c + p_e2h + p_e2g + g - x_grid = load - pv
    A_eq = np.zeros((T, n_vars))
    b_eq = np.asarray(load, dtype=float) - np.asarray(pv, dtype=float)
    for t in range(T):
        A_eq[t, t] = -1.0           # -p_c
        A_eq[t, T + t] = 1.0       # +p_e2h
        A_eq[t, 2 * T + t] = 1.0   # +p_e2g
        A_eq[t, 3 * T + t] = 1.0   # +g
        A_eq[t, 4 * T + t] = -1.0  # -x_grid

    # 3. Inequality Constraints (A_ub @ x <= b_ub)
    # a) Discharging power cap: p_e2h + p_e2g <= p_d_max * a(t)
    A_dis_max = np.zeros((T, n_vars))
    b_dis_max = p_d_max * availability
    for t in range(T):
        A_dis_max[t, T + t] = 1.0
        A_dis_max[t, 2 * T + t] = 1.0

    # b) Battery upper bound: E_t <= battery_cap
    # Σ_{k=0}^{t} [ eta_c * dt * p_c(k) - (dt / eta_d) * (p_e2h(k) + p_e2g(k)) ] <= battery_cap - e_init
    A_bat_upper = np.zeros((T, n_vars))
    b_bat_upper = np.full(T, battery_cap - e_init)
    for t in range(T):
        for k in range(t + 1):
            A_bat_upper[t, k] = eta_c * dt
            A_bat_upper[t, T + k] = -dt / eta_d
            A_bat_upper[t, 2 * T + k] = -dt / eta_d

    # c) Battery lower bound: E_t >= e_reserve
    # - Σ_{k=0}^{t} [ ... ] <= e_init - e_reserve
    A_bat_lower = np.zeros((T, n_vars))
    b_bat_lower = np.full(T, e_init - e_reserve)
    for t in range(T):
        for k in range(t + 1):
            A_bat_lower[t, k] = -eta_c * dt
            A_bat_lower[t, T + k] = dt / eta_d
            A_bat_lower[t, 2 * T + k] = dt / eta_d

    # d) Departure constraint: E_T >= e_target
    A_depart = np.zeros((1, n_vars))
    b_depart = np.array([-(e_target - e_init)])
    for k in range(T):
        A_depart[0, k] = -eta_c * dt
        A_depart[0, T + k] = dt / eta_d
        A_depart[0, 2 * T + k] = dt / eta_d

    # e) Physical export limit: grid export cannot exceed solar surplus + EV-to-grid discharge
    # x_grid(t) - p_e2g(t) <= max(0, pv(t) - load(t))
    A_export_lim = np.zeros((T, n_vars))
    b_export_lim = np.maximum(0.0, np.asarray(pv, dtype=float) - np.asarray(load, dtype=float))
    for t in range(T):
        A_export_lim[t, 4 * T + t] = 1.0   # +x_grid
        A_export_lim[t, 2 * T + t] = -1.0  # -p_e2g

    A_ub = np.vstack([A_dis_max, A_bat_upper, A_bat_lower, A_depart, A_export_lim])
    b_ub = np.concatenate([b_dis_max, b_bat_upper, b_bat_lower, b_depart, b_export_lim])

    # 4. Variable Bounds
    bounds: list[Tuple[float, Optional[float]]] = []

    # p_c bounds
    for t in range(T):
        bounds.append((0.0, p_c_max * availability[t]))

    # p_e2h bounds (capped by net demand if enabled, else 0)
    for t in range(T):
        if enable_e2h:
            net_deficit = max(0.0, float(load[t] - pv[t]))
            max_e2h = min(p_d_max * availability[t], net_deficit)
            bounds.append((0.0, max_e2h))
        else:
            bounds.append((0.0, 0.0))

    # p_e2g bounds (capped by discharge rating if enabled, else 0)
    for t in range(T):
        if enable_e2g:
            bounds.append((0.0, p_d_max * availability[t]))
        else:
            bounds.append((0.0, 0.0))

    # g (grid import) bounds
    for t in range(T):
        bounds.append((0.0, None))

    # x_grid (grid export) bounds
    for t in range(T):
        bounds.append((0.0, None))

    # 5. Solve via High-Performance HiGHS LP Solver
    result: OptimizeResult = linprog(
        c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options={"presolve": True},
    )

    solver_time = time.perf_counter() - t_start

    if result.success:
        charging_power = np.clip(result.x[:T], 0.0, p_c_max)
        p_e2h = np.clip(result.x[T : 2 * T], 0.0, p_d_max)
        p_e2g = np.clip(result.x[2 * T : 3 * T], 0.0, p_d_max)
        discharging_power = p_e2h + p_e2g
        grid_import = np.clip(result.x[3 * T : 4 * T], 0.0, None)
        grid_export = np.clip(result.x[4 * T : 5 * T], 0.0, None)
        status = "optimal"
    else:
        charging_power = np.zeros(T)
        p_e2h = np.zeros(T)
        p_e2g = np.zeros(T)
        discharging_power = np.zeros(T)
        grid_import = np.zeros(T)
        grid_export = np.zeros(T)
        status = "infeasible"

    return {
        "charging_power": charging_power,
        "discharging_power": discharging_power,
        "p_e2h": p_e2h,
        "p_e2g": p_e2g,
        "grid_import": grid_import,
        "grid_export": grid_export,
        "status": status,
        "method": method_label,
        "solver_time": solver_time,
    }


# ---------------------------------------------------------------------------
# B3 – Forecast-driven LP
# ---------------------------------------------------------------------------

def solve_forecast_driven(inputs: dict) -> dict:
    """Cost-minimising LP using PV *forecast*."""
    return _build_and_solve_lp(
        pv=np.asarray(inputs["pv_forecast"], dtype=float),
        load=np.asarray(inputs["load"], dtype=float),
        tariff=np.asarray(inputs["tariff"], dtype=float),
        ev_params=inputs["ev_params"],
        config=inputs.get("config", {}),
        method_label="forecast_driven",
    )


# ---------------------------------------------------------------------------
# B5 – Conservative fallback (zero-solar LP)
# ---------------------------------------------------------------------------

def solve_conservative_fallback(inputs: dict) -> dict:
    """LP with PV forecast set to zero (worst-case solar assumption)."""
    T = len(np.asarray(inputs["pv_forecast"]))
    return _build_and_solve_lp(
        pv=np.zeros(T),
        load=np.asarray(inputs["load"], dtype=float),
        tariff=np.asarray(inputs["tariff"], dtype=float),
        ev_params=inputs["ev_params"],
        config=inputs.get("config", {}),
        method_label="conservative_fallback",
    )


# ---------------------------------------------------------------------------
# B6 – Oracle (uses actual PV)
# ---------------------------------------------------------------------------

def solve_oracle(inputs: dict) -> dict:
    """LP using actual PV generation — oracle benchmark only."""
    return _build_and_solve_lp(
        pv=np.asarray(inputs["actual_pv"], dtype=float),
        load=np.asarray(inputs["load"], dtype=float),
        tariff=np.asarray(inputs["tariff"], dtype=float),
        ev_params=inputs["ev_params"],
        config=inputs.get("config", {}),
        method_label="oracle",
    )


# ---------------------------------------------------------------------------
# B4 – Reliability-aware switching controller
# ---------------------------------------------------------------------------

def solve_reliability_aware(
    inputs: dict,
    reliability_score: float,
    threshold: float,
) -> dict:
    """Switch between forecast-driven and conservative LP based on reliability."""
    if reliability_score >= threshold:
        result = solve_forecast_driven(inputs)
        result["used_fallback"] = False
    else:
        result = solve_conservative_fallback(inputs)
        result["used_fallback"] = True

    result["method"] = "reliability_aware"
    result["reliability_score"] = reliability_score
    result["threshold"] = threshold
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_METHODS: Dict[str, Any] = {
    "fixed": solve_fixed_schedule,
    "cheapest_hours": solve_cheapest_hours,
    "forecast_driven": solve_forecast_driven,
    "conservative_fallback": solve_conservative_fallback,
    "oracle": solve_oracle,
    "reliability_aware": solve_reliability_aware,
}


def solve_schedule(inputs: dict, method: str, config: dict, **kwargs) -> dict:
    """Dispatch to the appropriate scheduling method."""
    if method not in _METHODS:
        raise ValueError(
            f"Unknown scheduling method '{method}'. "
            f"Available: {list(_METHODS.keys())}"
        )

    inputs_copy = dict(inputs)
    merged_config = dict(inputs_copy.get("config", {}))
    merged_config.update(config)
    inputs_copy["config"] = merged_config

    fn = _METHODS[method]

    if method == "reliability_aware":
        return fn(inputs_copy, **kwargs)
    else:
        return fn(inputs_copy)
