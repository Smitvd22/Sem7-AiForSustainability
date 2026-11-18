# Reproducibility Report

## 1. Computational Environment
- **Operating System**: Windows 11 (64-bit).
- **Python Version**: 3.12.10.
- **Core Dependencies**:
  - `numpy`: 2.5.2
  - `pandas`: 3.0.5
  - `scipy`: 1.18.0
  - `scikit-learn`: 1.9.0
  - `matplotlib`: 3.11.1
  - `seaborn`: 0.13.2
  - `pytest`: 9.2.0

---

## 2. Deterministic Seed Management
All stochastic operations (cross-dataset resampling, weather front generation, train/test splitting, gradient-boosted regressor fitting, conformal residual sampling, bootstrap hypothesis testing, and synthetic stress noise) are governed by explicit seeds:
- Global random seed: `42`
- NumPy RandomState seeds: `42`, `123`, `456`, `789`, `1024`
- Bootstrap resamples: `1000` replicates with fixed seed `42`

---

## 3. Step-by-Step Reproduction Guide

### Step 1: Environment Verification
```powershell
python --version
python -c "import numpy, pandas, scipy, sklearn, matplotlib, seaborn; print('Dependencies verified successfully!')"
```

### Step 2: Execute Unit Tests
```powershell
python -m pytest
```
Expected output: `29 passed in ~3.5 seconds`.

### Step 3: Run Full End-to-End Experimental Pipeline
```powershell
python -m src.cli run-all --config configs/default.json
```
This executes:
1. Data validation and raw benchmark ingestion (`data/raw/` $\rightarrow$ `data/processed/`).
2. Forecaster fitting and Conformal Prediction calibration ($q_\alpha = 0.5964\text{ kW}$).
3. Validation threshold selection ($\tau^* = 0.8283$).
4. Test set evaluation for Controllers B1 through B6.
5. Error stress testing (low, moderate, high, correlated, regime shift).
6. Threshold, EV demand, and tariff sensitivity sweeps.
7. Ablation study.
8. Bidirectional Scenarios S1, S2, S3, S4 evaluation and paired statistical tests.
9. Publication figure generation (`results/figures/fig1` through `fig11` in dual PNG & PDF formats).
10. Paper synchronization (`results/` $\rightarrow$ `paper/`).

### Step 4: Inspect Generated Outputs
- Result tables: `results/tables/table5` through `table10` (CSV).
- Result figures: `results/figures/fig1` through `fig11` (PNG & PDF).
- Experiment manifest: `results/logs/manifest.json`.
- Completion checklist: `results/logs/completion_checklist.json`.
