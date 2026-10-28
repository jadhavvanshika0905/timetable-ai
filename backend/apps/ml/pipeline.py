"""Member 2 -> Member 1 bridge: train models and build the ``ml_hints`` dict.

    hints = build_ml_hints(data, demand_model, risk_model, demand_history)
    result = generate_timetable(data, ml_hints=hints)

The returned dict has exactly the keys hints.py accepts:
    faculty_risk, predicted_demand, weights
"""
from collections import Counter

from .config import DEFAULT_WEIGHTS
from .demand import DemandPredictor
from .history import make_demand_history, make_faculty_history
from .workload import WorkloadRiskModel

try:
    from apps.scheduler.hints import validate_ml_hints
except ImportError:
    try:
        from scheduler.hints import validate_ml_hints
    except ImportError:
        validate_ml_hints = None


def train_all(data=None, demand_history=None, faculty_history=None, n_terms=8, seed=42,
              save=False):
    """Train both models. Missing history is generated (dummy) from ``data``."""
    if demand_history is None:
        if data is None:
            raise ValueError("Give demand_history or the solver input `data`.")
        demand_history = make_demand_history(data["courses"], n_terms=n_terms, seed=seed)
    if faculty_history is None:
        faculty_history = make_faculty_history(seed=seed)
    demand = DemandPredictor().fit(demand_history)
    risk = WorkloadRiskModel().fit(faculty_history)
    if save:
        demand.save()
        risk.save()
    return demand, risk, demand_history


def _max_room_capacity(data, course):
    caps = [r["capacity"] for r in data["rooms"]
            if not course.get("requires_lab") or r["type"] == "lab"]
    return max(caps) if caps else 0


def suggest_weights(risk_by_faculty):
    """Raise the load-balance weight when many faculty are HIGH risk."""
    weights = {}
    if risk_by_faculty:
        high_share = Counter(risk_by_faculty.values())["HIGH"] / len(risk_by_faculty)
        if high_share >= 0.30:
            weights["faculty_balance"] = DEFAULT_WEIGHTS["faculty_balance"] + 3
        elif high_share >= 0.15:
            weights["faculty_balance"] = DEFAULT_WEIGHTS["faculty_balance"] + 1
    return weights


def build_ml_hints(data, demand_model, risk_model, demand_history, overrides=None,
                   only_when_higher=True):
    """Predictions -> solver hints, with admin overrides applied LAST.

    * predicted demand is clipped to the biggest usable room, otherwise a
      too-high forecast would make the timetable infeasible.
    * only_when_higher: the solver never lowers expected_students, so entries
      that are not higher than the current value are dropped (keeps the dict small).
    """
    risk = risk_model.predict(data)
    predicted = demand_model.predict_next(demand_history, data["courses"])
    demand, clipped = {}, []
    for c in data["courses"]:
        cid = str(c["id"])
        value = predicted.get(cid, c["expected_students"])
        cap = _max_room_capacity(data, c)
        if cap and value > cap:
            clipped.append(cid)
            value = cap
        if not only_when_higher or value > c["expected_students"]:
            demand[cid] = int(value)
    hints = {"faculty_risk": risk, "predicted_demand": demand,
             "weights": suggest_weights(risk)}
    for key in ("faculty_risk", "predicted_demand", "weights"):
        if overrides and overrides.get(key):
            hints[key] = {**hints[key], **{str(k): v for k, v in overrides[key].items()}}
    if validate_ml_hints is not None:
        problems = validate_ml_hints(data, hints)
        if problems:
            raise ValueError(f"Invalid ml_hints: {problems}")
    hints["_notes"] = {"clipped_to_room_capacity": clipped}
    return hints


def hints_for_solver(hints):
    """Drop the informational ``_notes`` key (hints.py rejects unknown keys)."""
    return {k: v for k, v in hints.items() if not k.startswith("_")}
