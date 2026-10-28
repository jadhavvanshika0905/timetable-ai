"""Faculty workload-risk classifier (Member 2, task 2).

Output per faculty: LOW / MEDIUM / HIGH  (the exact strings hints.py expects).

Features (all computable from the solver input of ONE term):
  utilisation      weekly hours / max_hours_per_week
  n_courses        number of different courses (preparations)
  n_students       total students taught
  n_lab_courses    lab courses (heavy supervision)
  restricted_ratio share of week blocked (NO) or disliked (AVOID)

Labels: no real "burnout" labels exist, so training labels come from the
transparent score in history.py (+ noise).  Replace the history table with real
labelled data later (e.g. admin overrides) and retrain -- code stays the same.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from .config import MODEL_DIR, RANDOM_SEED, RISK_MODEL_FILE, RISK_NAMES
from .history import risk_score, score_to_label

FEATURES = ["utilisation", "n_courses", "n_students", "n_lab_courses",
            "restricted_ratio", "weekly_hours", "max_hours"]
DEFAULT_MAX_HOURS = 16   # used when a faculty has no max_hours_per_week


def features_from_history(df):
    out = df.copy()
    out["utilisation"] = out["weekly_hours"] / out["max_hours"].clip(lower=1)
    out["restricted_ratio"] = out["restricted_slots"] / out["total_slots"].clip(lower=1)
    return out


def features_from_solver_input(data):
    """One row per faculty from a solver-input dict (see contracts schema)."""
    n_slots = len(data["slots"]["days"]) * len(data["slots"]["periods"])
    n_slots -= len(data["slots"].get("breaks", []))
    rows = []
    for f in data["faculty"]:
        mine = [c for c in data["courses"] if c["faculty_id"] == f["id"]]
        weekly = sum(c["hours_per_week"] for c in mine)
        restricted = sum(1 for p in f.get("preferences", [])
                         if p["level"] in ("NO", "AVOID"))
        rows.append({
            "faculty_id": str(f["id"]), "weekly_hours": weekly,
            "max_hours": f.get("max_hours_per_week") or DEFAULT_MAX_HOURS,
            "n_courses": len(mine),
            "n_students": sum(c["expected_students"] for c in mine),
            "n_lab_courses": sum(1 for c in mine if c.get("requires_lab")),
            "restricted_slots": restricted, "total_slots": max(1, n_slots),
        })
    return features_from_history(pd.DataFrame(rows))


class WorkloadRiskModel:
    def __init__(self):
        self.model = None
        self.metrics_ = {}

    def fit(self, history, test_fraction_terms=1):
        df = features_from_history(history)
        last = df["term_index"].max()
        train = df[df["term_index"] <= last - test_fraction_terms]
        test = df[df["term_index"] > last - test_fraction_terms]
        probe = self._new().fit(train[FEATURES], train["risk"])
        pred = probe.predict(test[FEATURES])
        # rule baseline: the plain hours/max_hours ratio
        rule = np.where(test["utilisation"] < 0.6, "LOW",
                        np.where(test["utilisation"] < 0.85, "MEDIUM", "HIGH"))
        self.metrics_ = {
            "train_rows": int(len(train)), "test_rows": int(len(test)),
            "accuracy": round(float(accuracy_score(test["risk"], pred)), 3),
            "macro_f1": round(float(f1_score(test["risk"], pred, average="macro")), 3),
            "rule_baseline_accuracy": round(float(accuracy_score(test["risk"], rule)), 3),
            "confusion_matrix_LOW_MED_HIGH": confusion_matrix(
                test["risk"], pred, labels=RISK_NAMES).tolist(),
        }
        self.model = self._new().fit(df[FEATURES], df["risk"])
        return self

    @staticmethod
    def _new():
        return RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=3,
                                      class_weight="balanced", random_state=RANDOM_SEED)

    def predict(self, data):
        """{faculty_id: 'LOW'|'MEDIUM'|'HIGH'} for a solver-input dict."""
        table = features_from_solver_input(data)
        if self.model is None:                       # rule fallback
            labels = [score_to_label(risk_score(
                r.weekly_hours, r.max_hours, r.n_courses, r.n_students,
                r.n_lab_courses, r.restricted_slots, r.total_slots))
                for r in table.itertuples()]
        else:
            labels = list(self.model.predict(table[FEATURES]))
        return dict(zip(table["faculty_id"], labels))

    def explain(self, data):
        """Per-faculty reason string (feature values + importances) for the admin UI."""
        table = features_from_solver_input(data)
        preds = self.predict(data)
        top = []
        if self.model is not None:
            imp = sorted(zip(FEATURES, self.model.feature_importances_), key=lambda x: -x[1])
            top = [f"{n} ({v:.0%})" for n, v in imp[:3]]
        rows = []
        for r in table.itertuples():
            rows.append({"faculty_id": r.faculty_id, "risk": preds[r.faculty_id],
                         "weekly_hours": r.weekly_hours, "max_hours": r.max_hours,
                         "utilisation_pct": round(r.utilisation * 100),
                         "n_courses": r.n_courses, "n_students": r.n_students,
                         "model_top_features": top})
        return rows

    def save(self, path=RISK_MODEL_FILE):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "metrics": self.metrics_}, path)

    @classmethod
    def load(cls, path=RISK_MODEL_FILE):
        blob = joblib.load(path)
        obj = cls()
        obj.model, obj.metrics_ = blob["model"], blob["metrics"]
        return obj
