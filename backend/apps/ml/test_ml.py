"""Member 2 tests -- no Django / database needed.

Run from the folder that contains `ml/` and `scheduler/`:
    python -m unittest ml.test_ml -v
Inside the Django repo:   python manage.py test apps.ml -v 2
Solver-integration tests are skipped if OR-Tools is missing.
"""
import copy
import random
import tempfile
import unittest
from pathlib import Path

from .db import history_from_rows
from .demand import DemandPredictor
from .history import make_demand_history, make_faculty_history
from .pipeline import build_ml_hints, hints_for_solver, train_all
from .workload import WorkloadRiskModel

try:
    from scheduler.solver import generate_timetable
    from scheduler.validator import validate_timetable
    from scheduler.hints import validate_ml_hints
    from scheduler.benchmark import make_synthetic
    HAVE_SOLVER = True
except ImportError:
    try:
        from apps.scheduler.solver import generate_timetable
        from apps.scheduler.validator import validate_timetable
        from apps.scheduler.hints import validate_ml_hints
        from apps.scheduler.benchmark import make_synthetic
        HAVE_SOLVER = True
    except ImportError:
        HAVE_SOLVER = False


def courses(n=40, seed=0):
    return [{"id": f"C{i}", "expected_students": random.Random(i + seed).randint(20, 60),
             "hours_per_week": 3, "type": "elective" if i % 3 == 0 else "major"}
            for i in range(n)]


class HistoryTests(unittest.TestCase):
    def test_deterministic(self):
        a = make_demand_history(courses(), n_terms=6, seed=5)
        b = make_demand_history(courses(), n_terms=6, seed=5)
        self.assertTrue(a.equals(b))
        self.assertEqual(len(a), 40 * 6)

    def test_faculty_history_has_all_three_levels(self):
        h = make_faculty_history()
        self.assertEqual(set(h["risk"]), {"LOW", "MEDIUM", "HIGH"})


class DemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cs = courses()
        cls.hist = make_demand_history(cls.cs, n_terms=8)
        cls.model = DemandPredictor().fit(cls.hist)

    def test_ml_beats_naive_baselines(self):
        m = self.model.metrics_
        self.assertEqual(m["mode"], "gradient_boosting")
        self.assertLess(m["mae_ml"], m["mae_last_term"])
        self.assertLess(m["mae_ml"], m["mae_moving_avg"])
        self.assertLess(m["severe_short_pct_ml"], m["severe_short_pct_last_term"])

    def test_predictions_are_positive_ints_for_every_course(self):
        pred = self.model.predict_next(self.hist, self.cs)
        self.assertEqual(set(pred), {c["id"] for c in self.cs})
        self.assertTrue(all(type(v) is int and v >= 1 for v in pred.values()))

    def test_cold_start_uses_moving_average(self):
        short = self.hist[self.hist["term_index"] < 2]
        m = DemandPredictor().fit(short)
        self.assertEqual(m.metrics_["mode"], "moving_average")
        self.assertIsNone(m.model)
        self.assertEqual(len(m.predict_next(short, self.cs)), len(self.cs))

    def test_course_without_history_keeps_expected_students(self):
        new = {"id": "NEW", "expected_students": 37, "hours_per_week": 3}
        self.assertEqual(self.model.predict_next(self.hist, [new])["NEW"], 37)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.joblib"
            self.model.save(path)
            loaded = DemandPredictor.load(path)
        self.assertEqual(self.model.predict_next(self.hist, self.cs),
                         loaded.predict_next(self.hist, self.cs))


class WorkloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = WorkloadRiskModel().fit(make_faculty_history())

    def test_accuracy_and_beats_rule(self):
        m = self.model.metrics_
        self.assertGreaterEqual(m["accuracy"], 0.8)
        self.assertGreater(m["accuracy"], m["rule_baseline_accuracy"])

    def _data(self):
        return {"slots": {"days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                          "periods": [1, 2, 3, 4, 5, 6], "breaks": []},
                "faculty": [{"id": "BUSY", "max_hours_per_week": 14,
                             "preferences": [{"day": "Mon", "period": 1, "level": "NO"}]},
                            {"id": "FREE", "max_hours_per_week": 20, "preferences": []}],
                "rooms": [],
                "courses": [{"id": f"B{i}", "faculty_id": "BUSY", "hours_per_week": 3,
                             "expected_students": 65, "requires_lab": i == 0}
                            for i in range(5)]
                           + [{"id": "F0", "faculty_id": "FREE", "hours_per_week": 2,
                               "expected_students": 25}]}

    def test_busy_is_high_and_free_is_low(self):
        risk = self.model.predict(self._data())
        self.assertEqual(risk["BUSY"], "HIGH")
        self.assertEqual(risk["FREE"], "LOW")

    def test_explain_rows(self):
        rows = self.model.explain(self._data())
        self.assertEqual({r["faculty_id"] for r in rows}, {"BUSY", "FREE"})
        busy = next(r for r in rows if r["faculty_id"] == "BUSY")
        self.assertEqual(busy["utilisation_pct"], round(15 / 14 * 100))


class DbAdapterTests(unittest.TestCase):
    def test_history_counts_distinct_students_per_term(self):
        rows = [{"term_id": 1, "student_id": s, "course_id": 7} for s in (1, 2, 2, 3)]
        rows += [{"term_id": 2, "student_id": 1, "course_id": 7}]
        meta = [{"id": 7, "hours_per_week": 3, "requires_lab": False, "course_type": "ELECTIVE"}]
        df = history_from_rows(rows, meta, term_order=[1, 2])
        got = {int(r.term_index): int(r.enrolled) for r in df.itertuples()}
        self.assertEqual(got, {0: 3, 1: 1})
        self.assertEqual(int(df["is_elective"].iloc[0]), 1)


@unittest.skipUnless(HAVE_SOLVER, "scheduler package / OR-Tools not importable")
class HintsAndSolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_synthetic(n_courses=12, n_cohorts=4, students_per_cohort=20)
        for i, c in enumerate(cls.data["courses"]):
            c["type"] = "elective" if i % 3 == 0 else "major"
        cls.demand, cls.risk, cls.hist = train_all(cls.data)

    def test_hints_pass_solver_validation(self):
        hints = hints_for_solver(build_ml_hints(self.data, self.demand, self.risk, self.hist))
        self.assertEqual(validate_ml_hints(self.data, hints), [])
        self.assertLessEqual(set(hints), {"faculty_risk", "predicted_demand", "weights"})
        self.assertTrue(set(hints["faculty_risk"].values()) <= {"LOW", "MEDIUM", "HIGH"})

    def test_demand_is_clipped_to_biggest_room(self):
        data = copy.deepcopy(self.data)
        hist = self.hist.copy()
        hist.loc[hist["course_id"] == "C0", "enrolled"] *= 20      # absurd growth
        hints = build_ml_hints(data, self.demand, self.risk, hist)
        self.assertLessEqual(hints["predicted_demand"]["C0"], 60)
        self.assertIn("C0", hints["_notes"]["clipped_to_room_capacity"])

    def test_admin_override_wins(self):
        ov = {"faculty_risk": {"F0": "HIGH"}, "predicted_demand": {"C1": 33},
              "weights": {"idle_gap": 9}}
        hints = build_ml_hints(self.data, self.demand, self.risk, self.hist, overrides=ov)
        self.assertEqual(hints["faculty_risk"]["F0"], "HIGH")
        self.assertEqual(hints["predicted_demand"]["C1"], 33)
        self.assertEqual(hints["weights"]["idle_gap"], 9)

    def test_bad_override_is_rejected(self):
        with self.assertRaises(ValueError):
            build_ml_hints(self.data, self.demand, self.risk, self.hist,
                           overrides={"faculty_risk": {"F0": "EXTREME"}})

    def test_solver_returns_valid_timetable_with_hints(self):
        hints = hints_for_solver(build_ml_hints(self.data, self.demand, self.risk, self.hist))
        # No practical time limit: optimize=False stops at the first valid
        # timetable, so this runs exactly as long as it needs and no longer.
        res = generate_timetable(self.data, max_time_seconds=3600, num_search_workers=0,
                                 optimize=False, ml_hints=hints)
        self.assertIn(res["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(validate_timetable(self.data, res["timetable"]), [])

    def test_predicted_demand_moves_class_to_bigger_room(self):
        data = {"slots": {"days": ["Mon"], "periods": [1], "breaks": []},
                "faculty": [{"id": "F", "preferences": []}],
                "rooms": [{"id": "SMALL", "capacity": 30, "type": "classroom"},
                          {"id": "BIG", "capacity": 60, "type": "classroom"}],
                "courses": [{"id": "A", "faculty_id": "F", "hours_per_week": 1,
                             "expected_students": 25, "requires_lab": False}],
                "student_choices": []}
        plain = generate_timetable(data, num_search_workers=1)
        boosted = generate_timetable(data, num_search_workers=1,
                                     ml_hints={"predicted_demand": {"A": 50}})
        self.assertEqual(boosted["timetable"][0]["room_id"], "BIG")
        self.assertIn(plain["timetable"][0]["room_id"], ("SMALL", "BIG"))


if __name__ == "__main__":
    unittest.main()