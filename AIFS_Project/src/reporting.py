"""
Reporting module for generating machine-readable summaries and tables.

Creates CSV/JSON tables and LaTeX table fragments from experiment results.
"""

import numpy as np
import pandas as pd
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def results_to_dataframe(results: Dict[str, List[dict]], config: dict) -> pd.DataFrame:
    """Convert controller results dict to a flat DataFrame.
    
    Args:
        results: Dict mapping controller_name -> list of daily result dicts
        config: Configuration dict
    
    Returns:
        DataFrame with one row per (controller, day) combination
    """
    rows = []
    dt = config.get('data', {}).get('time_resolution_hours', 1.0)
    
    for ctrl_name, daily_results in results.items():
        for i, r in enumerate(daily_results):
            row = {
                'controller': ctrl_name,
                'day_index': i,
                'date': r.get('date', ''),
                'total_cost': r.get('total_cost', np.nan),
                'net_cost': r.get('net_cost', r.get('total_cost', np.nan)),
                'export_revenue': r.get('export_revenue', 0.0),
                'degradation_cost': r.get('degradation_cost', 0.0),
                'grid_import_kwh': np.sum(r.get('grid_import', [])) * dt if 'grid_import' in r else np.nan,
                'export_kwh': np.sum(r.get('export', [])) * dt if 'export' in r else 0.0,
                'peak_grid_kw': np.max(r.get('grid_import', [0])) if 'grid_import' in r else np.nan,
                'peak_export_kw': np.max(r.get('export', [0])) if 'export' in r else 0.0,
                'pv_to_ev_kwh': np.sum(r.get('pv_to_ev', [])) * dt if 'pv_to_ev' in r else np.nan,
                'discharging_kwh': np.sum(r.get('discharging_power', [])) * dt if 'discharging_power' in r else 0.0,
                'e2h_kwh': np.sum(r.get('p_e2h', [])) * dt if 'p_e2h' in r else 0.0,
                'e2g_kwh': np.sum(r.get('p_e2g', [])) * dt if 'p_e2g' in r else 0.0,
                'deadline_met': r.get('deadline_met', None),
                'unmet_energy_kwh': r.get('unmet_energy_kwh', np.nan),
                'final_soc_kwh': r.get('final_soc_kwh', np.nan),
                'method': r.get('method', ''),
                'used_fallback': r.get('used_fallback', None),
            }
            rows.append(row)
    
    return pd.DataFrame(rows)


def aggregate_summary_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """Create aggregate summary table by controller.
    
    Args:
        results_df: DataFrame from results_to_dataframe
    
    Returns:
        Summary DataFrame with one row per controller
    """
    summary = results_df.groupby('controller').agg(
        n_days=('day_index', 'count'),
        mean_cost=('total_cost', 'mean'),
        std_cost=('total_cost', 'std'),
        median_cost=('total_cost', 'median'),
        mean_net_cost=('net_cost', 'mean'),
        mean_grid_import=('grid_import_kwh', 'mean'),
        mean_peak_grid=('peak_grid_kw', 'mean'),
        mean_pv_to_ev=('pv_to_ev_kwh', 'mean'),
        mean_discharging=('discharging_kwh', 'mean'),
        mean_e2h=('e2h_kwh', 'mean'),
        mean_e2g=('e2g_kwh', 'mean'),
        deadline_success_rate=('deadline_met', 'mean'),
        mean_unmet_energy=('unmet_energy_kwh', 'mean'),
    ).round(4)
    
    return summary


def save_csv_table(df: pd.DataFrame, path: str, index: bool = True) -> str:
    """Save DataFrame as CSV table.
    
    Args:
        df: DataFrame to save
        path: Output file path
        index: Whether to include index
    
    Returns:
        Path to saved file
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=index)
    return path


def save_json_results(data: dict, path: str) -> str:
    """Save results dict as JSON.
    
    Args:
        data: Results dictionary (must be JSON-serializable)
        path: Output file path
    
    Returns:
        Path to saved file
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Convert numpy types for JSON serialization
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            result = convert(obj)
            if result is not obj:
                return result
            return super().default(obj)
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)
    return path


def generate_latex_table(df: pd.DataFrame, caption: str, label: str,
                         column_format: Optional[str] = None) -> str:
    """Generate LaTeX table string from DataFrame.
    
    Args:
        df: DataFrame to convert
        caption: Table caption
        label: LaTeX label for cross-referencing
        column_format: LaTeX column format string (e.g., 'lcccc')
    
    Returns:
        LaTeX table string
    """
    n_cols = len(df.columns) + (1 if df.index.name else 0)
    if column_format is None:
        column_format = 'l' + 'c' * (n_cols - 1)
    
    latex = df.to_latex(
        caption=caption,
        label=label,
        column_format=column_format,
        float_format='%.4f',
        bold_rows=False,
        escape=True,
    )
    
    return latex


def generate_experiment_manifest(config: dict, results_dir: str) -> dict:
    """Generate experiment manifest documenting all settings and outputs.
    
    Args:
        config: Full configuration dict
        results_dir: Directory containing results
    
    Returns:
        Manifest dict
    """
    manifest = {
        'generated_at': datetime.now().isoformat(),
        'config': config,
        'output_files': [],
        'status': 'complete',
    }
    
    # List all output files
    for root, dirs, files in os.walk(results_dir):
        for f in files:
            fpath = os.path.join(root, f)
            manifest['output_files'].append({
                'path': fpath,
                'size_bytes': os.path.getsize(fpath),
                'modified': datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
            })
    
    return manifest


def generate_completion_checklist(results_dir: str, config: dict) -> dict:
    """Generate project completion checklist.
    
    Args:
        results_dir: Results directory
        config: Configuration
    
    Returns:
        Checklist dict with status for each component
    """
    base_dir = os.path.dirname(results_dir)
    
    checklist = {
        'source_code': {
            'data.py': _check_file(os.path.join(base_dir, 'src', 'data.py')),
            'preprocessing.py': _check_file(os.path.join(base_dir, 'src', 'preprocessing.py')),
            'forecasting.py': _check_file(os.path.join(base_dir, 'src', 'forecasting.py')),
            'uncertainty.py': _check_file(os.path.join(base_dir, 'src', 'uncertainty.py')),
            'scheduler.py': _check_file(os.path.join(base_dir, 'src', 'scheduler.py')),
            'simulation.py': _check_file(os.path.join(base_dir, 'src', 'simulation.py')),
            'metrics.py': _check_file(os.path.join(base_dir, 'src', 'metrics.py')),
            'experiments.py': _check_file(os.path.join(base_dir, 'src', 'experiments.py')),
            'statistics.py': _check_file(os.path.join(base_dir, 'src', 'statistics.py')),
            'plotting.py': _check_file(os.path.join(base_dir, 'src', 'plotting.py')),
            'reporting.py': _check_file(os.path.join(base_dir, 'src', 'reporting.py')),
            'cli.py': _check_file(os.path.join(base_dir, 'src', 'cli.py')),
        },
        'tests': {
            'test_data.py': _check_file(os.path.join(base_dir, 'tests', 'test_data.py')),
            'test_forecasting.py': _check_file(os.path.join(base_dir, 'tests', 'test_forecasting.py')),
            'test_uncertainty.py': _check_file(os.path.join(base_dir, 'tests', 'test_uncertainty.py')),
            'test_scheduler.py': _check_file(os.path.join(base_dir, 'tests', 'test_scheduler.py')),
            'test_simulation.py': _check_file(os.path.join(base_dir, 'tests', 'test_simulation.py')),
            'test_metrics.py': _check_file(os.path.join(base_dir, 'tests', 'test_metrics.py')),
            'test_reproducibility.py': _check_file(os.path.join(base_dir, 'tests', 'test_reproducibility.py')),
        },
        'results': {
            'raw_results': _check_dir(os.path.join(results_dir, 'raw')),
            'processed_results': _check_dir(os.path.join(results_dir, 'processed')),
            'tables': _check_dir(os.path.join(results_dir, 'tables')),
            'figures': _check_dir(os.path.join(results_dir, 'figures')),
        },
        'documentation': {
            'README.md': _check_file(os.path.join(base_dir, 'README.md')),
            'research_design.md': _check_file(os.path.join(base_dir, 'docs', 'research_design.md')),
            'literature_review.md': _check_file(os.path.join(base_dir, 'docs', 'literature_review.md')),
            'data_sources.md': _check_file(os.path.join(base_dir, 'docs', 'data_sources.md')),
        },
        'paper': {
            'main.tex': _check_file(os.path.join(base_dir, 'paper', 'main.tex')),
            'references.bib': _check_file(os.path.join(base_dir, 'paper', 'references.bib')),
        },
    }
    
    return checklist


def _check_file(path: str) -> str:
    """Check if a file exists and return status."""
    if os.path.exists(path):
        size = os.path.getsize(path)
        if size > 0:
            return 'Implemented'
        return 'Empty'
    return 'Not implemented'


def _check_dir(path: str) -> str:
    """Check if a directory exists and has contents."""
    if os.path.exists(path):
        contents = os.listdir(path)
        if contents:
            return f'Implemented ({len(contents)} files)'
        return 'Empty'
    return 'Not implemented'


def build_paper(results_directory: str, config: dict) -> dict:
    """Assemble paper components from verified results.
    
    Args:
        results_directory: Path to results directory
        config: Configuration dict
    
    Returns:
        Dict with paths to paper components
    """
    paper_dir = config.get('output', {}).get('paper_dir', 'paper')
    
    components = {
        'tables': [],
        'figures': [],
        'status': 'draft',
    }
    
    # Copy figures to paper/figures
    figures_src = os.path.join(results_directory, 'figures')
    figures_dst = os.path.join(paper_dir, 'figures')
    os.makedirs(figures_dst, exist_ok=True)
    
    if os.path.exists(figures_src):
        import shutil
        for f in os.listdir(figures_src):
            src = os.path.join(figures_src, f)
            dst = os.path.join(figures_dst, f)
            shutil.copy2(src, dst)
            components['figures'].append(dst)
    
    # Copy tables
    tables_src = os.path.join(results_directory, 'tables')
    tables_dst = os.path.join(paper_dir, 'tables')
    os.makedirs(tables_dst, exist_ok=True)
    
    if os.path.exists(tables_src):
        import shutil
        for f in os.listdir(tables_src):
            src = os.path.join(tables_src, f)
            dst = os.path.join(tables_dst, f)
            shutil.copy2(src, dst)
            components['tables'].append(dst)
    
    return components

