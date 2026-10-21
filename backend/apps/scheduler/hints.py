"""Member 1 <-> Member 2 contract: how ML predictions reach the solver.

``ml_hints`` is an optional dict passed to ``generate_timetable``:

    {
      "faculty_risk":     {"F1": "HIGH", "F2": "LOW"},   # workload risk class
      "predicted_demand": {"C1": 55, "C7": 30},          # expected students
      "weights":          {"idle_gap": 8}                # optional admin override
    }

* faculty_risk   -> HIGH-risk faculty get a stronger load-balancing penalty.
* predicted_demand -> raises ``expected_students`` (never lowers it) so rooms
  are sized for the predicted demand.
* weights        -> overrides any key of DEFAULT_WEIGHTS (admin override).

Member 2 produces this dict (after applying any admin override) and Member 3's
API passes it through ``services.generate_timetable_for_term(ml_hints=...)``.
This module is pure Python (no OR-Tools, no Django).
"""

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
DEFAULT_WEIGHTS = {
    "repeat_day": 20,       # same theory course twice on one day
    "avoid": 6,             # faculty AVOID slot
    "prefer": 3,            # faculty PREFER slot (reward)
    "idle_gap": 5,          # per idle period in a student's day (x group size, max 5)
    "faculty_balance": 4,   # per period above a faculty's even daily share (x risk)
}
RISK_MULTIPLIER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
DEFAULT_RISK_MULTIPLIER = 2   # used when no ML risk is supplied for a faculty


def _normalize_ids(ml_hints):
    """Solver ids are strings; accept int ids from Django by stringifying dict keys."""
    out = dict(ml_hints)
    for key in ("faculty_risk", "predicted_demand"):
        if isinstance(out.get(key), dict):
            out[key] = {str(k): v for k, v in out[key].items()}
    return out


def validate_ml_hints(data, ml_hints):
    """Return a list of problems (empty list means the hints are usable)."""
    if ml_hints is None:
        return []
    if not isinstance(ml_hints, dict):
        return ["ml_hints must be an object."]
    ml_hints = _normalize_ids(ml_hints)
    unknown = set(ml_hints) - {"faculty_risk", "predicted_demand", "weights"}
    if unknown:
        return [f"ml_hints has unknown keys: {sorted(unknown)}."]
    issues = []
    faculty_ids = {f["id"] for f in data["faculty"]}
    course_ids = {c["id"] for c in data["courses"]}

    risk = ml_hints.get("faculty_risk", {})
    if not isinstance(risk, dict):
        issues.append("ml_hints.faculty_risk must be an object.")
    else:
        for fid, level in risk.items():
            if fid not in faculty_ids:
                issues.append(f"ml_hints.faculty_risk: unknown faculty {fid}.")
            elif level not in RISK_LEVELS:
                issues.append(f"ml_hints.faculty_risk: {fid} level must be LOW, MEDIUM or HIGH.")

    demand = ml_hints.get("predicted_demand", {})
    if not isinstance(demand, dict):
        issues.append("ml_hints.predicted_demand must be an object.")
    else:
        for cid, value in demand.items():
            if cid not in course_ids:
                issues.append(f"ml_hints.predicted_demand: unknown course {cid}.")
            elif type(value) is not int or value < 0:
                issues.append(f"ml_hints.predicted_demand: {cid} must be a nonnegative integer.")

    weights = ml_hints.get("weights", {})
    if not isinstance(weights, dict):
        issues.append("ml_hints.weights must be an object.")
    else:
        for key, value in weights.items():
            if key not in DEFAULT_WEIGHTS:
                issues.append(f"ml_hints.weights: unknown weight {key}.")
            elif type(value) is not int or value < 0:
                issues.append(f"ml_hints.weights: {key} must be a nonnegative integer.")
    return issues


def apply_ml_hints(data, ml_hints):
    """Return (data, weights, risk_by_faculty). Input data is never mutated."""
    weights = dict(DEFAULT_WEIGHTS)
    risk = {}
    if not ml_hints:
        return data, weights, risk
    ml_hints = _normalize_ids(ml_hints)
    weights.update(ml_hints.get("weights", {}))
    risk = dict(ml_hints.get("faculty_risk", {}))
    demand = ml_hints.get("predicted_demand", {})
    if demand:
        courses = [dict(c, expected_students=max(c["expected_students"], demand.get(c["id"], 0)))
                   for c in data["courses"]]
        data = dict(data, courses=courses)
    return data, weights, risk