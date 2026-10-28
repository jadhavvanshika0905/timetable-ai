"""Member 2 -- shared constants for the ML part."""
from pathlib import Path

try:  # inside Django: backend/apps/ml  ->  backend/apps/scheduler
    from apps.scheduler.hints import DEFAULT_WEIGHTS, RISK_LEVELS
except ImportError:
    try:  # running next to the scheduler folder
        from scheduler.hints import DEFAULT_WEIGHTS, RISK_LEVELS
    except ImportError:  # stand-alone fallback (keep identical to hints.py)
        RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
        DEFAULT_WEIGHTS = {"repeat_day": 20, "avoid": 6, "prefer": 3,
                           "idle_gap": 5, "faculty_balance": 4}

MODEL_DIR = Path(__file__).resolve().parent / "models_store"
DEMAND_MODEL_FILE = MODEL_DIR / "demand_model.joblib"
RISK_MODEL_FILE = MODEL_DIR / "risk_model.joblib"
RANDOM_SEED = 42

# Demand model
MIN_TERMS_FOR_ML = 3        # fewer past terms than this -> use moving-average fallback
DEMAND_SAFETY_FACTOR = 1.05  # +5 % head-room so a room is never too small

# Workload risk
RISK_NAMES = list(RISK_LEVELS)
