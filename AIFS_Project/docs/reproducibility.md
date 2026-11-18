# Reproducibility Guide and Environment Specification

## 1. Environment Details
- **Operating System**: Windows 11 / x86_64
- **Python Version**: Python 3.12.10
- **Package Manager**: pip 26.2.1
- **Optimization Engine**: SciPy HiGHS simplex/interior-point linear programming solver (`scipy.optimize.linprog`)
- **Total Hardware Cost**: ₹0
- **Hardware Profile**: 100% CPU execution feasible on standard laptops (no GPU required).

---

## 2. Dependencies (`requirements.txt`)
- `numpy>=1.26.0`
- `pandas>=2.2.0`
- `scipy>=1.12.0`
- `scikit-learn>=1.4.0`
- `matplotlib>=3.8.0`
- `seaborn>=0.13.0`
- `pytest>=8.0.0`
- `nbformat>=5.9.0`
- `jupyter>=1.0.0`

---

## 3. Step-by-Step Reproduction Commands

```bash
# 1. Clone repository and navigate to root
cd D:\U23AI118\AiForSustainability\Project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run all unit tests (verify 23/23 tests pass)
pytest -v

# 4. Run full end-to-end research pipeline
python -m src.cli run-all --config configs/default.json

# 5. Alternatively, run individual stages
python -m src.cli validate-data --config configs/default.json
python -m src.cli train --config configs/default.json
python -m src.cli run-experiments --config configs/default.json
python -m src.cli analyze --config configs/default.json
python -m src.cli build-paper --config configs/default.json
```

All raw outputs, processed metrics, publication CSV tables, and PNG figures are deterministically re-created upon execution.

