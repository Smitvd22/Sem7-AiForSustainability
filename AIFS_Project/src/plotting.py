"""
Plotting module for publication-quality figures.

Generates all figures from actual experiment outputs in both high-resolution
raster (PNG at 300 DPI) and vector (PDF) formats adhering to IEEE conference guidelines.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns


# Set IEEE publication style
plt.rcParams.update({
    'font.size': 10,
    'font.family': 'serif',
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.figsize': (7, 4.5),
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.3,
})


def _save_dual_format(fig: plt.Figure, save_path: str):
    """Save figure in both PNG and vector PDF format."""
    p = Path(save_path)
    # Ensure directory
    p.parent.mkdir(parents=True, exist_ok=True)

    # Save primary format
    fig.savefig(save_path, dpi=300, bbox_inches='tight')

    # Save PDF counterpart
    pdf_path = p.with_suffix('.pdf')
    fig.savefig(str(pdf_path), bbox_inches='tight')


def plot_pv_forecast_example(
    timestamps: np.ndarray,
    actual: np.ndarray,
    forecast: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    save_path: str,
    title: str = "PV Generation: Measured vs. Point Forecast and 90% Conformal Interval"
) -> str:
    """Plot actual PV vs forecast with conformal prediction interval."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    hours = np.arange(len(timestamps))

    ax.plot(hours, actual, 'b-', linewidth=2.0, label='Measured PV (NREL)', zorder=3)
    ax.plot(hours, forecast, 'r--', linewidth=1.8, label='Gradient-Boosted Forecast', zorder=3)
    ax.fill_between(hours, lower, upper, alpha=0.25, color='orange', label='90% Conformal Interval', zorder=2)

    ax.set_xlabel('Hour of Day (UTC)')
    ax.set_ylabel('Power (kW)')
    ax.set_title(title)
    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_xlim(0, 23)
    ax.set_ylim(bottom=0)
    ax.set_xticks(range(0, 24, 2))

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_forecast_error_distribution(
    errors: np.ndarray,
    save_path: str,
    title: str = "Empirical Solar PV Forecast Error Distribution"
) -> str:
    """Plot histogram and absolute error density for solar forecasts."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

    # Error distribution
    ax1.hist(errors, bins=40, density=True, alpha=0.75, color='#2b5c8f', edgecolor='black')
    ax1.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='Zero Bias')
    ax1.set_xlabel('Forecast Error (kW)')
    ax1.set_ylabel('Empirical Density')
    ax1.set_title('(a) Raw Error Distribution')
    ax1.legend(loc='upper left')

    # Absolute error distribution
    abs_errors = np.abs(errors)
    mae = float(np.mean(abs_errors))
    ax2.hist(abs_errors, bins=40, density=True, alpha=0.75, color='#d95f02', edgecolor='black')
    ax2.axvline(x=mae, color='red', linestyle='--', linewidth=1.5, label=f'MAE = {mae:.3f} kW')
    ax2.set_xlabel('Absolute Error |G - Ĝ| (kW)')
    ax2.set_ylabel('Empirical Density')
    ax2.set_title('(b) Absolute Error Distribution')
    ax2.legend(loc='upper right')

    fig.suptitle(title, fontsize=12, fontweight='bold', y=1.02)
    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_interval_coverage(
    coverages: Dict[str, float],
    widths: Dict[str, float],
    nominal: float,
    save_path: str
) -> str:
    """Plot prediction interval coverage vs nominal level."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

    labels = list(coverages.keys())
    cov_vals = [coverages[k] for k in labels]
    width_vals = [widths[k] for k in labels]

    colors = ['#2ca02c' if c >= nominal else '#d62728' for c in cov_vals]

    ax1.bar(labels, [c * 100 for c in cov_vals], color=colors, edgecolor='black', alpha=0.85, width=0.45)
    ax1.axhline(y=nominal * 100, color='red', linestyle='--', linewidth=1.8, label=f'Nominal ({nominal:.0%})')
    ax1.set_ylabel('Empirical Coverage (%)')
    ax1.set_title('(a) Conformal Coverage Guarantee')
    ax1.set_ylim(0, 115)
    ax1.legend(loc='lower right')

    ax2.bar(labels, width_vals, color='#1f77b4', edgecolor='black', alpha=0.85, width=0.45)
    ax2.set_ylabel('Mean Interval Width (kW)')
    ax2.set_title('(b) Average Prediction Interval Width')
    ax2.set_ylim(bottom=0)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_controller_comparison_cost(
    results: Dict[str, List[float]],
    save_path: str,
    title: str = "Daily Electricity Cost Distribution by Controller (56 Test Days)"
) -> str:
    """Box plot comparing daily costs across controllers."""
    fig, ax = plt.subplots(figsize=(9, 4.8))

    data = []
    labels = []
    clean_labels = {
        "fixed": "B1: Fixed",
        "cheapest_hours": "B2: Cheapest Hours",
        "forecast_driven": "B3: Forecast-Driven",
        "reliability_aware": "B4: Proposed Switching",
        "conservative_fallback": "B5: Fallback",
        "oracle": "B6: Oracle",
    }
    for name, costs in results.items():
        data.append(costs)
        labels.append(clean_labels.get(name, name))

    bp = ax.boxplot(data, patch_artist=True, showmeans=True,
                    meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='black', markersize=6))
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=25, ha='right')

    colors = sns.color_palette("Set2", len(data))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.set_ylabel('Daily Electricity Cost ($/day)')
    ax.set_title(title)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_solar_contribution(
    results: Dict[str, List[float]],
    save_path: str,
    title: str = "Solar Energy Delivered to EV Battery Across Controllers"
) -> str:
    """Box plot comparing solar energy delivered to EV."""
    fig, ax = plt.subplots(figsize=(9, 4.8))

    data = []
    labels = []
    clean_labels = {
        "fixed": "B1: Fixed",
        "cheapest_hours": "B2: Cheapest Hours",
        "forecast_driven": "B3: Forecast-Driven",
        "reliability_aware": "B4: Proposed Switching",
        "conservative_fallback": "B5: Fallback",
        "oracle": "B6: Oracle",
    }
    for name, vals in results.items():
        data.append(vals)
        labels.append(clean_labels.get(name, name))

    bp = ax.boxplot(data, patch_artist=True, showmeans=True,
                    meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='black', markersize=6))
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=25, ha='right')

    colors = sns.color_palette("YlOrRd", len(data))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.set_ylabel('Direct Solar to EV (kWh/day)')
    ax.set_title(title)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_peak_and_deadline(
    peak_results: Dict[str, List[float]],
    deadline_results: Dict[str, float],
    save_path: str
) -> str:
    """Combined plot of peak grid demand and charging deadline satisfaction."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    clean_labels = {
        "fixed": "B1: Fixed",
        "cheapest_hours": "B2: Cheapest",
        "forecast_driven": "B3: Forecast-LP",
        "reliability_aware": "B4: Proposed",
        "conservative_fallback": "B5: Fallback",
        "oracle": "B6: Oracle",
    }

    # Peak demand
    data = []
    labels = [clean_labels.get(k, k) for k in peak_results.keys()]
    for name in peak_results.keys():
        data.append(peak_results[name])

    bp = ax1.boxplot(data, patch_artist=True, showmeans=True,
                     meanprops=dict(marker='D', markerfacecolor='red', markeredgecolor='black', markersize=5))
    ax1.set_xticks(range(1, len(labels) + 1))
    ax1.set_xticklabels(labels, rotation=30, ha='right')
    colors = sns.color_palette("Blues_r", len(data))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax1.set_ylabel('Peak Grid Demand (kW)')
    ax1.set_title('(a) Peak Grid Import Power')

    # Deadline reliability
    names = list(deadline_results.keys())
    clean_d_labels = [clean_labels.get(k, k) for k in names]
    rates = [deadline_results[n] * 100 for n in names]
    colors2 = ['#2ca02c' if r >= 99.9 else '#d62728' for r in rates]

    ax2.bar(clean_d_labels, rates, color=colors2, edgecolor='black', alpha=0.85, width=0.55)
    ax2.axhline(y=100, color='gray', linestyle='--', alpha=0.7)
    ax2.set_ylabel('Deadline Success Rate (%)')
    ax2.set_title('(b) EV Departure Deadline Satisfaction')
    ax2.set_ylim(0, 115)
    ax2.tick_params(axis='x', rotation=30)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_stress_test(
    scenario_results: Dict[str, Dict[str, float]],
    metric: str,
    save_path: str,
    title: str = "Controller Performance Under Forecast-Error Stress Regimes"
) -> str:
    """Bar chart comparing controller performance across error scenarios."""
    fig, ax = plt.subplots(figsize=(10, 4.8))

    clean_ctrl = {
        "cheapest_hours": "B2: Cheapest Hours",
        "forecast_driven": "B3: Forecast-Driven",
        "reliability_aware": "B4: Proposed Switching",
        "conservative_fallback": "B5: Fallback",
    }

    scenarios = list(scenario_results.keys())
    raw_ctrls = list(scenario_results[scenarios[0]].keys()) if scenarios else []

    x = np.arange(len(scenarios))
    width = 0.8 / max(len(raw_ctrls), 1)

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    for i, ctrl in enumerate(raw_ctrls):
        vals = [scenario_results[s].get(ctrl, 0) for s in scenarios]
        ax.bar(x + i * width - 0.4 + width / 2, vals, width,
               label=clean_ctrl.get(ctrl, ctrl), color=colors[i % len(colors)],
               edgecolor='black', alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels([s.replace('_', ' ').title() for s in scenarios], rotation=20, ha='right')
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.legend(loc='upper left', framealpha=0.9)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_threshold_sensitivity(
    thresholds: np.ndarray,
    costs: np.ndarray,
    deadline_rates: np.ndarray,
    fallback_rates: np.ndarray,
    selected_threshold: float,
    save_path: str
) -> str:
    """Plot threshold sensitivity analysis with dual axes."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 6.0), sharex=True)

    # Cost profile
    ax1.plot(thresholds, costs, 'bo-', linewidth=1.8, markersize=5, label='Mean Daily Cost')
    ax1.axvline(x=selected_threshold, color='red', linestyle='--', linewidth=1.8,
                label=f'Optimal τ* = {selected_threshold:.3f}')
    ax1.set_ylabel('Mean Cost ($/day)')
    ax1.set_title('(a) Operating Cost vs. Reliability Threshold')
    ax1.legend(loc='upper right')

    # Rates
    ax2.plot(thresholds, deadline_rates * 100, 'gs-', linewidth=1.8, markersize=5, label='Deadline Satisfaction (%)')
    ax2.plot(thresholds, fallback_rates * 100, 'r^--', linewidth=1.8, markersize=5, label='Fallback Engagement (%)')
    ax2.axvline(x=selected_threshold, color='red', linestyle='--', linewidth=1.8)
    ax2.set_xlabel('Reliability Threshold (τ)')
    ax2.set_ylabel('Percentage (%)')
    ax2.set_title('(b) Operational Reliability and Fallback Activation')
    ax2.set_ylim(-5, 110)
    ax2.legend(loc='center left')

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_system_architecture(save_path: str) -> str:
    """Generate high-clarity architectural diagram showing bidirectional energy and information flows."""
    fig, ax = plt.subplots(figsize=(12, 6.8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Component definitions (label, x, y, w, h, bg_color)
    components = [
        ('Distribution Electric Grid\n(TOU Tariff + Feed-in NEM)', 1.0, 7.8, 3.8, 1.4, '#cce5ff'),
        ('Rooftop Solar PV (5 kW)\n(NREL PVDAQ Site 4)', 1.0, 4.4, 3.8, 1.4, '#fff3cd'),
        ('Household Domestic Demand\n(UK-DALE / REFIT Load)', 1.0, 1.0, 3.8, 1.4, '#e2e3e5'),
        ('Forecast Engine\n(HistGradientBoosting)', 6.0, 7.8, 3.8, 1.4, '#ffe5d0'),
        ('Conformal Uncertainty\n(Split Conformal q_α)', 6.0, 5.5, 3.8, 1.4, '#f8d7da'),
        ('Horizon Reliability Index\n(r̄ = 1 - w̄ / P_cap)', 6.0, 3.2, 3.8, 1.4, '#d1e7dd'),
        ('Reliability Switching Logic\n(r̄ ≥ τ* ? Forecast-LP : Fallback)', 6.0, 0.9, 3.8, 1.5, '#d4edda'),
        ('Bidirectional EV Charger\n(Level 2 7kW, E2G / E2H Enabled)', 11.2, 5.0, 4.0, 1.6, '#d1ecf1'),
        ('EV Battery Energy Storage\n(40 kWh Pack, 8 kWh Reserve)', 11.2, 1.2, 4.0, 1.8, '#d6d8db'),
    ]

    from matplotlib.patches import FancyBboxPatch

    for label, x, y, w, h, col in components:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2", facecolor=col,
                              edgecolor='black', linewidth=1.5, zorder=2)
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, label, ha='center', va='center',
                fontsize=9.5, fontweight='bold', zorder=3)

    # Annotated Energy and Control Arrows
    def draw_arrow(p1, p2, color='black', style='->', text='', offset=(0, 0)):
        ax.annotate('', xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle=style, color=color, lw=2.0), zorder=4)
        if text:
            mx = (p1[0] + p2[0]) / 2 + offset[0]
            my = (p1[1] + p2[1]) / 2 + offset[1]
            ax.text(mx, my, text, fontsize=8.5, fontweight='bold', color=color,
                    ha='center', va='center', bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.85, edgecolor='none'))

    # Information flows
    draw_arrow((4.8, 5.1), (6.0, 8.5), color='#d95f02', text='Historical PV')
    draw_arrow((7.9, 7.8), (7.9, 6.9), color='#d95f02', text='Ĝ_t')
    draw_arrow((7.9, 5.5), (7.9, 4.6), color='#7570b3', text='[l̂, û]')
    draw_arrow((7.9, 3.2), (7.9, 2.4), color='#1b9e77', text='r̄')
    draw_arrow((9.8, 1.6), (11.2, 5.2), color='#1b9e77', text='Dispatch Signal')

    # Energy flows
    draw_arrow((4.8, 8.5), (11.2, 6.2), color='#2b5c8f', style='<->', text='P_grid (Import / E2G Export)')
    draw_arrow((4.8, 5.0), (11.2, 5.6), color='#e6ab02', text='PV2EV Charging')
    draw_arrow((4.8, 4.4), (4.8, 2.4), color='#e6ab02', text='PV2H')
    draw_arrow((11.2, 5.0), (4.8, 1.7), color='#7570b3', text='E2H Discharging')
    draw_arrow((13.2, 5.0), (13.2, 3.0), color='#333333', style='<->', text='P_charge / P_discharge')

    ax.set_title('Comprehensive Architecture: Reliability-Aware Scheduling with Bidirectional E2H & E2G Energy Flows',
                 fontsize=12, fontweight='bold', pad=15)

    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_bidirectional_scenarios(
    scenario_metrics: Dict[str, Dict[str, float]],
    save_path: str
) -> str:
    """Generate multi-panel figure comparing bidirectional scenarios S1 through S4."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.0))

    scenarios = ["S1", "S2", "S3", "S4"]
    scenario_labels = [
        "S1: Baseline\n(Unidirectional)",
        "S2: E2H-Only\n(Peak Shaving)",
        "S3: E2G-Only\n(Grid Export)",
        "S4: Combined\n(E2H + E2G)",
    ]

    costs = [scenario_metrics[s]["net_cost"] for s in scenarios]
    imports = [scenario_metrics[s]["grid_import"] for s in scenarios]
    exports = [scenario_metrics[s]["grid_export"] for s in scenarios]
    e2h_energies = [scenario_metrics[s]["e2h_energy"] for s in scenarios]
    e2g_energies = [scenario_metrics[s]["e2g_energy"] for s in scenarios]
    peak_imports = [scenario_metrics[s]["peak_import"] for s in scenarios]

    x = np.arange(len(scenarios))
    palette = ["#4575b4", "#74add1", "#f46d43", "#d73027"]

    # (a) Net Operating Cost
    ax1.bar(x, costs, color=palette, edgecolor='black', alpha=0.85, width=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenario_labels)
    ax1.set_ylabel('Mean Net Cost ($/day)')
    ax1.set_title('(a) Daily Operating Cost Across Scenarios')
    for i, v in enumerate(costs):
        ax1.text(i, v + 0.1, f"${v:.2f}", ha='center', fontsize=9, fontweight='bold')

    # (b) Grid Import vs Export
    width = 0.35
    ax2.bar(x - width/2, imports, width, label='Grid Import', color='#3182bd', edgecolor='black', alpha=0.85)
    ax2.bar(x + width/2, exports, width, label='Grid Export', color='#31a354', edgecolor='black', alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenario_labels)
    ax2.set_ylabel('Energy (kWh/day)')
    ax2.set_title('(b) Grid Electricity Exchange')
    ax2.legend(loc='upper right')

    # (c) Discharged Energy Breakdown
    ax3.bar(x, e2h_energies, label='E2H (to Home)', color='#756bb1', edgecolor='black', alpha=0.85, width=0.5)
    ax3.bar(x, e2g_energies, bottom=e2h_energies, label='E2G (to Grid)', color='#fd8d3c', edgecolor='black', alpha=0.85, width=0.5)
    ax3.set_xticks(x)
    ax3.set_xticklabels(scenario_labels)
    ax3.set_ylabel('Discharged Energy (kWh/day)')
    ax3.set_title('(c) EV Battery Discharging Allocation')
    ax3.legend(loc='upper left')

    # (d) Peak Grid Demand
    ax4.bar(x, peak_imports, color='#e7298a', edgecolor='black', alpha=0.85, width=0.5)
    ax4.set_xticks(x)
    ax4.set_xticklabels(scenario_labels)
    ax4.set_ylabel('Peak Grid Import (kW)')
    ax4.set_title('(d) Coincident Peak Grid Power')

    fig.suptitle('Empirical Evaluation of Bidirectional Operating Modes (S1–S4)', fontsize=13, fontweight='bold', y=0.99)
    fig.tight_layout()
    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path


def plot_real_vs_synthetic(
    real_pv: np.ndarray,
    syn_pv: np.ndarray,
    real_load: np.ndarray,
    syn_load: np.ndarray,
    save_path: str
) -> str:
    """Plot comparison of authentic measured profiles vs synthetic counterparts."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    hours = np.arange(24)

    # PV comparison
    ax1.plot(hours, real_pv, 'b-', linewidth=2.0, label='Measured (NREL PVDAQ Site 4)', zorder=3)
    ax1.plot(hours, syn_pv, 'r--', linewidth=1.8, label='Synthetic Clear-Sky Model', zorder=2)
    ax1.set_xlabel('Hour of Day (UTC)')
    ax1.set_ylabel('Generation (kW)')
    ax1.set_title('(a) Rooftop Solar PV Comparison')
    ax1.set_xlim(0, 23)
    ax1.set_ylim(bottom=0)
    ax1.legend(loc='upper right')

    # Load comparison
    ax1_peak = np.max([real_load, syn_load])
    ax2.plot(hours, real_load, 'b-', linewidth=2.0, label='Measured (UK-DALE Smart Meter)', zorder=3)
    ax2.plot(hours, syn_load, 'r--', linewidth=1.8, label='Synthetic Gaussian Model', zorder=2)
    ax2.set_xlabel('Hour of Day (UTC)')
    ax2.set_ylabel('Demand (kW)')
    ax2.set_title('(b) Household Inflexible Load Comparison')
    ax2.set_xlim(0, 23)
    ax2.set_ylim(0, max(5.0, ax1_peak * 1.1))
    ax2.legend(loc='upper right')

    fig.suptitle('Real-World Empirical Observations vs. Synthetic Mathematical Benchmarks', fontsize=12, fontweight='bold', y=1.02)
    _save_dual_format(fig, save_path)
    plt.close(fig)
    return save_path
