"""Elective demand predictor (Member 2, task 1).

Question answered: "How many students will enrol in course C NEXT term?"

Approach
  * Features per (course, term): last 3 terms' enrolment, their mean, the
    recent trend, same-parity term (t-2) enrolment, elective flag, hours, lab
    flag and whether the target term is odd/even semester.
  * Target is the RATIO  enrolled / mean(previous enrolments)  -- scale free,
    so a 200-seat and a 20-seat course teach the same model.
  * GradientBoostingRegressor.  With < MIN_TERMS_FOR_ML terms of history a
    weighted moving average is used instead (cold start).
  * Time-based evaluation: train on early terms, test on the LAST terms, and
    compare against two naive baselines (last term / moving average).
"""
import math

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from .config import (DEMAND_MODEL_FILE, DEMAND_SAFETY_FACTOR, MIN_TERMS_FOR_ML,
                      MODEL_DIR, RANDOM_SEED)

FEATURES = ["lag1_ratio", "lag2_ratio", "lag3_ratio", "trend", "same_parity_ratio",
            "is_elective", "hours_per_week", "requires_lab", "semester_type",
            "volatility", "log_base"]


def _history_for_course(series_by_term, t):
    """enrolments of terms < t, newest first."""
    return [series_by_term[k] for k in sorted(series_by_term, reverse=True) if k < t]


def _row_features(past, meta, target_term):
    """past: enrolments newest-first (>=1 value). Returns (feature dict, base)."""
    lag1 = past[0]
    lag2 = past[1] if len(past) > 1 else lag1
    lag3 = past[2] if len(past) > 2 else lag2
    base = float(np.mean(past[:3]))
    same_parity = past[1] if len(past) > 1 else lag1          # term t-2
    vol = float(np.std(past[:4]) / max(1.0, np.mean(past[:4]))) if len(past) > 1 else 0.0
    return {
        "lag1_ratio": lag1 / base, "lag2_ratio": lag2 / base, "lag3_ratio": lag3 / base,
        "trend": (lag1 - lag2) / base, "same_parity_ratio": same_parity / base,
        "is_elective": meta["is_elective"], "hours_per_week": meta["hours_per_week"],
        "requires_lab": meta["requires_lab"], "semester_type": target_term % 2,
        "volatility": vol, "log_base": math.log1p(base),
    }, base


def moving_average(past):
    """Weighted moving average with damped trend (cold-start fallback)."""
    w = [0.5, 0.3, 0.2][:len(past)]
    avg = sum(a * b for a, b in zip(w, past)) / sum(w)
    if len(past) > 1:
        avg += 0.5 * (past[0] - past[1]) * 0.5  # damped trend
    return max(0.0, avg)


def build_training_table(history):
    """Turn raw history into one supervised row per (course, term>=2)."""
    rows = []
    for cid, grp in history.groupby("course_id"):
        series = dict(zip(grp["term_index"], grp["enrolled"]))
        meta_row = grp.iloc[0]
        meta = {"is_elective": int(meta_row["is_elective"]),
                "hours_per_week": int(meta_row["hours_per_week"]),
                "requires_lab": int(meta_row["requires_lab"])}
        for t in sorted(series):
            past = _history_for_course(series, t)
            if len(past) < 2:
                continue
            feats, base = _row_features(past, meta, t)
            feats.update(course_id=cid, term_index=t, base=base, actual=series[t],
                         target_ratio=series[t] / base, last=past[0],
                         ma=moving_average(past))
            rows.append(feats)
    return pd.DataFrame(rows)


class DemandPredictor:
    def __init__(self):
        self.model = None
        self.n_terms_seen = 0
        self.safety_factor = DEMAND_SAFETY_FACTOR
        self.metrics_ = {}

    # ------------------------------------------------------------ training
    def _new_model(self):
        return GradientBoostingRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
            loss="huber", random_state=RANDOM_SEED)

    def fit(self, history, holdout_terms=2):
        """Train on all terms and store time-based validation metrics."""
        self.n_terms_seen = int(history["term_index"].nunique())
        table = build_training_table(history)
        if self.n_terms_seen < MIN_TERMS_FOR_ML or len(table) < 20:
            self.model = None
            self.metrics_ = {"mode": "moving_average", "terms": self.n_terms_seen,
                             "reason": f"need >= {MIN_TERMS_FOR_ML} terms and 20 rows for ML"}
            return self
        last = table["term_index"].max()
        if holdout_terms and table["term_index"].nunique() > holdout_terms + 1:
            train = table[table["term_index"] <= last - holdout_terms]
            test = table[table["term_index"] > last - holdout_terms]
            probe = self._new_model().fit(train[FEATURES], train["target_ratio"])
            pred = probe.predict(test[FEATURES]) * test["base"]
            mae = lambda x: float(np.mean(np.abs(test["actual"] - x)))
            self.metrics_ = {
                "mode": "gradient_boosting", "terms": self.n_terms_seen,
                "train_rows": int(len(train)), "test_rows": int(len(test)),
                "mae_ml": round(mae(pred), 2),
                "mae_last_term": round(mae(test["last"]), 2),
                "mae_moving_avg": round(mae(test["ma"]), 2),
                "mape_ml_pct": round(float(np.mean(np.abs(test["actual"] - pred)
                                                  / test["actual"])) * 100, 2),
            }
            # Learn the head-room: 80th percentile of how much we UNDER-predicted
            # (relative), capped at +25 %.  Applied to electives in predict_next().
            under = np.clip((test["actual"] - pred) / pred.clip(lower=1), 0, None)
            self.safety_factor = float(1 + min(0.25, max(DEMAND_SAFETY_FACTOR - 1,
                                                          np.percentile(under, 80))))
            safe = np.where(test["is_elective"] == 1, pred * self.safety_factor, pred)
            self.metrics_["safety_factor"] = round(self.safety_factor, 3)
            self.metrics_["room_too_small_pct_ml"] = round(
                float(np.mean(np.ceil(safe) < test["actual"])) * 100, 1)
            self.metrics_["room_too_small_pct_last_term"] = round(
                float(np.mean(test["last"] < test["actual"])) * 100, 1)
            # severe = room short by MORE than 10 % of real enrolment
            self.metrics_["severe_short_pct_ml"] = round(
                float(np.mean(np.ceil(safe) < 0.9 * test["actual"])) * 100, 1)
            self.metrics_["severe_short_pct_last_term"] = round(
                float(np.mean(test["last"] < 0.9 * test["actual"])) * 100, 1)
        else:
            self.metrics_ = {"mode": "gradient_boosting", "terms": self.n_terms_seen}
        self.model = self._new_model().fit(table[FEATURES], table["target_ratio"])
        return self

    # ---------------------------------------------------------- prediction
    def predict_next(self, history, courses, next_term=None, apply_safety=True):
        """Return {course_id: predicted_students (int)} for the coming term.

        courses : solver course dicts (need id, expected_students, ...). A course
        without history keeps its own expected_students.
        """
        if history is None or len(history) == 0 or "term_index" not in history.columns:
            return {}   # no past terms yet: nothing to predict
        next_term = int(history["term_index"].max()) + 1 if next_term is None else next_term
        by_course = {cid: g for cid, g in history.groupby("course_id")}
        out = {}
        for c in courses:
            cid = str(c["id"])
            grp = by_course.get(cid)
            if grp is None or grp.empty:
                out[cid] = int(c.get("expected_students", 0))
                continue
            series = dict(zip(grp["term_index"], grp["enrolled"]))
            past = _history_for_course(series, next_term)
            if not past:
                out[cid] = int(c.get("expected_students", 0))
                continue
            meta_row = grp.iloc[0]
            meta = {"is_elective": int(meta_row["is_elective"]),
                    "hours_per_week": int(meta_row["hours_per_week"]),
                    "requires_lab": int(meta_row["requires_lab"])}
            if self.model is None or len(past) < 2:
                value = moving_average(past)
            else:
                feats, base = _row_features(past, meta, next_term)
                ratio = float(self.model.predict(pd.DataFrame([feats])[FEATURES])[0])
                value = max(0.0, ratio * base)
            if apply_safety and meta["is_elective"]:
                value *= self.safety_factor
            out[cid] = max(1, int(math.ceil(value)))
        return out

    # ----------------------------------------------------------- persistence
    def save(self, path=DEMAND_MODEL_FILE):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "n_terms_seen": self.n_terms_seen,
                     "metrics": self.metrics_, "safety_factor": self.safety_factor}, path)

    @classmethod
    def load(cls, path=DEMAND_MODEL_FILE):
        blob = joblib.load(path)
        obj = cls()
        obj.model, obj.n_terms_seen, obj.metrics_ = (blob["model"], blob["n_terms_seen"],
                                                      blob["metrics"])
        obj.safety_factor = blob.get("safety_factor", DEMAND_SAFETY_FACTOR)
        return obj
