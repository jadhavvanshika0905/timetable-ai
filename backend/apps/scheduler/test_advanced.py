"""Member 1 tests for the v4 features (no database needed).

Run from this folder (needs OR-Tools for the solver tests):
    python -m unittest test_advanced -v
Or through Django together with the old tests:
    python manage.py test apps.scheduler -v 2

Tests that need OR-Tools are skipped automatically when it is not installed.
The 100-course speed test only runs with the environment variable RUN_SLOW=1.
"""
import os
import sys
import unittest

try:
    from apps.scheduler import diagnostics, editing, hints, metrics
    from apps.scheduler.validator import validate_timetable
except ImportError:  # running from the scheduler folder
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import diagnostics, editing, hints, metrics  # noqa: E401
    from validator import validate_timetable

try:
    import ortools  # noqa: F401
    HAVE_ORTOOLS = True
except ImportError:
    HAVE_ORTOOLS = False

if HAVE_ORTOOLS:
    try:
        from apps.scheduler.solver import generate_timetable
        from apps.scheduler import benchmark
    except ImportError:
        from solver import generate_timetable
        import benchmark


def make_data(*, days=("Mon", "Tue", "Wed", "Thu", "Fri"), periods=(1, 2, 3, 4, 5),
              breaks=(), faculty=(), rooms=(), courses=(), students=()):
    return {
        "slots": {"days": list(days), "periods": list(periods),
                  "breaks": [{"day": d, "period": p} for d, p in breaks]},
        "faculty": [dict(f, preferences=list(f.get("preferences", []))) for f in faculty],
        "rooms": list(rooms),
        "courses": list(courses),
        "student_choices": [{"student_id": sid, "course_ids": list(cids)}
                            for sid, cids in students],
    }


def course(cid, fid, hours, *, lab=False, block=1, students=10):
    return {"id": cid, "name": cid, "faculty_id": fid, "hours_per_week": hours,
            "expected_students": students, "requires_lab": lab, "lab_block_size": block}


def row(cid, fid, rid, day, period):
    return {"course_id": cid, "faculty_id": fid, "room_id": rid, "day": day, "period": period}


def editing_fixture():
    """Hand-made valid timetable (break on Mon period 3)."""
    data = make_data(
        days=("Mon", "Tue"), breaks=[("Mon", 3)],
        faculty=[{"id": "F1"}, {"id": "F2"}],
        rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
               {"id": "R2", "capacity": 30, "type": "classroom"},
               {"id": "L1", "capacity": 30, "type": "lab"}],
        courses=[course("C1", "F1", 2), course("C2", "F2", 2),
                 course("CL", "F1", 2, lab=True, block=2)],
        students=[("S1", ["C1", "C2"])],
    )
    timetable = [
        row("C1", "F1", "R1", "Mon", 1), row("C1", "F1", "R1", "Tue", 1),
        row("C2", "F2", "R1", "Mon", 2), row("C2", "F2", "R1", "Tue", 2),
        row("CL", "F1", "L1", "Tue", 3), row("CL", "F1", "L1", "Tue", 4),
    ]
    return data, timetable


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.data, self.tt = editing_fixture()

    def test_fixture_is_valid(self):
        self.assertEqual(validate_timetable(self.data, self.tt), [])

    def test_valid_move_changes_timetable(self):
        result = editing.move_session(self.data, self.tt, course_id="C1", from_day="Mon",
                                      from_period=1, to_day="Mon", to_period=4, to_room_id="R2")
        self.assertTrue(result["ok"], result["issues"])
        self.assertEqual(validate_timetable(self.data, result["timetable"]), [])
        self.assertIn(("C1", "Mon", 4, "R2"),
                      {(e["course_id"], e["day"], e["period"], e["room_id"])
                       for e in result["timetable"]})
        self.assertEqual(len(result["timetable"]), 6)

    def test_original_timetable_not_mutated(self):
        before = [dict(e) for e in self.tt]
        editing.move_session(self.data, self.tt, course_id="C1", from_day="Mon", from_period=1,
                             to_day="Mon", to_period=4)
        self.assertEqual(self.tt, before)

    def test_faculty_clash_rejected(self):
        result = editing.move_session(self.data, self.tt, course_id="C1", from_day="Tue",
                                      from_period=1, to_day="Tue", to_period=3)
        self.assertFalse(result["ok"])
        self.assertTrue(any("faculty" in i and "double-booked" in i for i in result["issues"]))
        self.assertEqual(result["timetable"], self.tt)

    def test_break_rejected(self):
        result = editing.move_session(self.data, self.tt, course_id="C2", from_day="Mon",
                                      from_period=2, to_day="Mon", to_period=3)
        self.assertFalse(result["ok"])
        self.assertTrue(any("break" in i for i in result["issues"]))

    def test_room_and_student_clash_rejected(self):
        result = editing.move_session(self.data, self.tt, course_id="C2", from_day="Mon",
                                      from_period=2, to_day="Tue", to_period=1)
        self.assertFalse(result["ok"])
        text = " ".join(result["issues"])
        self.assertIn("room", text)
        self.assertIn("Student S1", text)

    def test_lab_required_rejected(self):
        result = editing.move_session(self.data, self.tt, course_id="CL", from_day="Tue",
                                      from_period=3, to_day="Tue", to_period=3, to_room_id="R1")
        self.assertFalse(result["ok"])
        self.assertTrue(any("requires a lab" in i for i in result["issues"]))

    def test_lab_block_moves_as_one_piece(self):
        # Dragging the SECOND period of the block must still move the whole block.
        result = editing.move_session(self.data, self.tt, course_id="CL", from_day="Tue",
                                      from_period=4, to_day="Mon", to_period=4)
        self.assertTrue(result["ok"], result["issues"])
        moved = sorted((e["day"], e["period"]) for e in result["timetable"]
                       if e["course_id"] == "CL")
        self.assertEqual(moved, [("Mon", 4), ("Mon", 5)])
        self.assertEqual(validate_timetable(self.data, result["timetable"]), [])

    def test_lab_block_past_last_period_rejected(self):
        result = editing.move_session(self.data, self.tt, course_id="CL", from_day="Tue",
                                      from_period=3, to_day="Mon", to_period=5)
        self.assertFalse(result["ok"])

    def test_unknown_inputs(self):
        for kwargs in (
            dict(course_id="NOPE", from_day="Mon", from_period=1, to_day="Mon", to_period=2),
            dict(course_id="C1", from_day="Mon", from_period=5, to_day="Mon", to_period=2),
            dict(course_id="C1", from_day="Mon", from_period=1, to_day="Sun", to_period=2),
            dict(course_id="C1", from_day="Mon", from_period=1, to_day="Mon", to_period=2,
                 to_room_id="ZZ"),
            dict(course_id="C1", from_day="Mon", from_period=1, to_day="Mon", to_period=1),
        ):
            self.assertFalse(editing.move_session(self.data, self.tt, **kwargs)["ok"], kwargs)

    def test_valid_move_targets(self):
        targets = editing.valid_move_targets(self.data, self.tt, course_id="CL",
                                             from_day="Tue", from_period=3)
        keys = {(t["day"], t["period"], t["room_id"]) for t in targets}
        self.assertIn(("Tue", 4, "L1"), keys)
        self.assertIn(("Mon", 4, "L1"), keys)
        self.assertNotIn(("Mon", 3, "L1"), keys)     # break
        self.assertNotIn(("Tue", 4, "R1"), keys)     # not a lab
        self.assertNotIn(("Mon", 5, "L1"), keys)     # block would run past period 5

    def test_preexisting_issue_does_not_block_unrelated_move(self):
        broken = self.tt + [row("C2", "F2", "R2", "Mon", 4)]   # C2 now has 3 sessions
        self.assertTrue(validate_timetable(self.data, broken))
        result = editing.move_session(self.data, broken, course_id="C1", from_day="Mon",
                                      from_period=1, to_day="Mon", to_period=5, to_room_id="R2")
        self.assertTrue(result["ok"], result["issues"])


class MetricsTests(unittest.TestCase):
    def test_idle_gap_counted(self):
        data, tt = editing_fixture()
        tt = [e for e in tt if not (e["course_id"] == "C2" and e["day"] == "Mon")]
        tt.append(row("C2", "F2", "R1", "Mon", 4))       # C1 at P1, C2 at P4 -> P2 idle
        result = metrics.compute_metrics(data, tt)
        self.assertEqual(result["student_idle_gaps_total"], 1)
        self.assertEqual(result["students_with_gaps"], 1)

    def test_break_is_not_an_idle_gap(self):
        data, tt = editing_fixture()
        tt = [e for e in tt if not (e["course_id"] in ("C1", "C2") and e["day"] == "Mon")]
        tt += [row("C1", "F1", "R1", "Mon", 2), row("C2", "F2", "R1", "Mon", 4)]  # break = P3
        self.assertEqual(metrics.compute_metrics(data, tt)["student_idle_gaps_total"], 0)

    def test_faculty_load_and_preferences(self):
        data, tt = editing_fixture()
        data["faculty"][0]["preferences"] = [
            {"day": "Tue", "period": 3, "level": "AVOID"},
            {"day": "Mon", "period": 1, "level": "PREFER"}]
        result = metrics.compute_metrics(data, tt)
        self.assertEqual(result["faculty_max_daily_load"]["F1"], 3)   # C1 + 2-period lab on Tue
        self.assertEqual(result["avoid_violations"], 1)
        self.assertEqual(result["prefer_hits"], 1)
        # F1 teaches 4 periods over 2 days -> even share 2; Tue has 3 -> overload 1
        self.assertEqual(result["faculty_overload_periods"], 1)


class HintsTests(unittest.TestCase):
    def setUp(self):
        self.data, _ = editing_fixture()

    def test_valid_hints(self):
        ok = {"faculty_risk": {"F1": "HIGH"}, "predicted_demand": {"C1": 20},
              "weights": {"idle_gap": 9}}
        self.assertEqual(hints.validate_ml_hints(self.data, ok), [])
        self.assertEqual(hints.validate_ml_hints(self.data, None), [])

    def test_integer_ids_are_accepted(self):
        ok = {"faculty_risk": {1: "HIGH"}, "predicted_demand": {1: 20}}
        data, _ = editing_fixture()
        for f in data["faculty"]:
            f["id"] = {"F1": "1", "F2": "2"}[f["id"]]
        for c in data["courses"]:
            c["id"] = {"C1": "1", "C2": "2", "CL": "3"}[c["id"]]
            c["faculty_id"] = {"F1": "1", "F2": "2"}.get(c["faculty_id"], c["faculty_id"])
        self.assertEqual(hints.validate_ml_hints(data, ok), [])
        new_data, _, risk = hints.apply_ml_hints(data, dict(ok, predicted_demand={1: 99}))
        self.assertEqual(risk, {"1": "HIGH"})
        self.assertEqual(new_data["courses"][0]["expected_students"], 99)

    def test_invalid_hints(self):
        for bad in (
            "text", {"nope": 1},
            {"faculty_risk": {"F1": "EXTREME"}}, {"faculty_risk": {"ZZ": "LOW"}},
            {"predicted_demand": {"C1": -1}}, {"predicted_demand": {"ZZ": 5}},
            {"predicted_demand": {"C1": 2.5}}, {"weights": {"idle_gap": -1}},
            {"weights": {"unknown": 1}},
        ):
            self.assertTrue(hints.validate_ml_hints(self.data, bad), bad)

    def test_demand_only_raises_and_input_not_mutated(self):
        new_data, weights, risk = hints.apply_ml_hints(
            self.data, {"predicted_demand": {"C1": 50, "C2": 3}, "faculty_risk": {"F1": "LOW"},
                        "weights": {"idle_gap": 9}})
        expected = {c["id"]: c["expected_students"] for c in new_data["courses"]}
        self.assertEqual(expected["C1"], 50)
        self.assertEqual(expected["C2"], 10)          # 3 < 10: never lowered
        self.assertEqual(self.data["courses"][0]["expected_students"], 10)
        self.assertEqual(weights["idle_gap"], 9)
        self.assertEqual(risk, {"F1": "LOW"})


class DiagnosticsAnalyticTests(unittest.TestCase):
    def test_room_capacity_hall_check(self):
        data = make_data(
            days=("Mon",), periods=(1, 2, 3),
            faculty=[{"id": "F1"}, {"id": "F2"}],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
                   {"id": "R2", "capacity": 30, "type": "classroom"},
                   {"id": "L1", "capacity": 30, "type": "lab"}],
            courses=[course("A", "F1", 2, lab=True), course("B", "F2", 2, lab=True)],
        )
        reasons = diagnostics.room_capacity_reasons(data)
        self.assertEqual(len(reasons), 1)
        self.assertIn("L1", reasons[0])
        self.assertIn("need 4", reasons[0])

    def test_no_reason_when_rooms_suffice(self):
        data, _ = editing_fixture()
        self.assertEqual(diagnostics.room_capacity_reasons(data), [])

    def test_minimal_conflict_filter(self):
        # conflict exists iff items 2 and 5 are both enforced
        def probe(enforced):
            return "INFEASIBLE" if {2, 5} <= set(enforced) else "FEASIBLE"
        core, complete = diagnostics.minimal_conflict(list(range(8)), probe, lambda: False)
        self.assertEqual(sorted(core), [2, 5])
        self.assertTrue(complete)

    def test_minimal_conflict_respects_time_budget(self):
        core, complete = diagnostics.minimal_conflict(
            list(range(8)), lambda e: "INFEASIBLE", lambda: True)
        self.assertFalse(complete)
        self.assertEqual(len(core), 8)


@unittest.skipUnless(HAVE_ORTOOLS, "OR-Tools not installed")
class SolverTests(unittest.TestCase):
    def solve(self, data, **kwargs):
        kwargs.setdefault("max_time_seconds", 10.0)
        return generate_timetable(data, **kwargs)

    def assertSolved(self, data, result):
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"), result["infeasibility_reasons"])
        self.assertEqual(validate_timetable(data, result["timetable"]), [])

    def test_small_instance_valid_with_metrics(self):
        data, _ = editing_fixture()
        result = self.solve(data)
        self.assertSolved(data, result)
        self.assertEqual(len(result["timetable"]), 6)
        for key in ("student_idle_gaps_total", "faculty_max_daily_load", "solve_seconds"):
            self.assertIn(key, result["metrics"])

    def test_idle_gaps_minimised_to_zero(self):
        data = make_data(
            days=("Mon", "Tue", "Wed"), periods=(1, 2, 3, 4),
            faculty=[{"id": "F1"}, {"id": "F2"}, {"id": "F3"}],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
                   {"id": "R2", "capacity": 30, "type": "classroom"}],
            courses=[course("A", "F1", 2), course("B", "F2", 2), course("C", "F3", 2)],
            students=[("S1", ["A", "B", "C"]), ("S2", ["A", "B", "C"])],
        )
        result = self.solve(data)
        self.assertSolved(data, result)
        self.assertEqual(result["metrics"]["student_idle_gaps_total"], 0)

    def test_optimised_not_worse_than_plain(self):
        data = make_data(
            days=("Mon", "Tue"), periods=(1, 2, 3, 4, 5, 6), breaks=[("Mon", 4), ("Tue", 4)],
            faculty=[{"id": f"F{i}"} for i in range(4)],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
                   {"id": "R2", "capacity": 30, "type": "classroom"}],
            courses=[course(f"C{i}", f"F{i}", 2) for i in range(4)],
            students=[("S1", ["C0", "C1", "C2"]), ("S2", ["C1", "C2", "C3"])],
        )
        plain = self.solve(data, optimize=False)
        best = self.solve(data)
        self.assertSolved(data, plain)
        self.assertSolved(data, best)
        self.assertLessEqual(best["metrics"]["student_idle_gaps_total"],
                             metrics.compute_metrics(data, plain["timetable"])
                             ["student_idle_gaps_total"])

    def test_faculty_load_is_balanced(self):
        data = make_data(
            faculty=[{"id": "F1"}],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"}],
            courses=[course("A", "F1", 2), course("B", "F1", 2)],
        )
        result = self.solve(data)
        self.assertSolved(data, result)
        self.assertEqual(result["metrics"]["faculty_max_daily_load"]["F1"], 1)
        self.assertEqual(result["metrics"]["faculty_overload_periods"], 0)

    def test_ml_demand_selects_bigger_room(self):
        data = make_data(
            days=("Mon", "Tue"), faculty=[{"id": "F1"}],
            rooms=[{"id": "SMALL", "capacity": 25, "type": "classroom"},
                   {"id": "BIG", "capacity": 60, "type": "classroom"}],
            courses=[course("A", "F1", 2, students=20)],
        )
        result = self.solve(data, ml_hints={"predicted_demand": {"A": 50}})
        self.assertSolved(data, result)
        self.assertEqual({e["room_id"] for e in result["timetable"]}, {"BIG"})

    def test_bad_ml_hints_are_invalid_input(self):
        data, _ = editing_fixture()
        result = self.solve(data, ml_hints={"faculty_risk": {"F1": "EXTREME"}})
        self.assertEqual(result["status"], "INVALID_INPUT")

    def test_precheck_room_hall_reason(self):
        data = make_data(
            days=("Mon",), periods=(1, 2, 3),
            faculty=[{"id": "F1"}, {"id": "F2"}],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
                   {"id": "R2", "capacity": 30, "type": "classroom"},
                   {"id": "L1", "capacity": 30, "type": "lab"}],
            courses=[course("A", "F1", 2, lab=True), course("B", "F2", 2, lab=True)],
        )
        result = self.solve(data)
        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertIn("L1", " ".join(result["infeasibility_reasons"]))

    def test_specific_infeasible_reason_for_student_clash(self):
        # F1 and F2 can each teach ONLY on Mon period 1, and one student takes both
        # courses -> the two classes can never be at different times.
        only_mon1 = [{"day": d, "period": p, "level": "NO"}
                     for d in ("Mon", "Tue") for p in (1, 2) if (d, p) != ("Mon", 1)]
        data = make_data(
            days=("Mon", "Tue"), periods=(1, 2),
            faculty=[{"id": "F1", "preferences": only_mon1},
                     {"id": "F2", "preferences": only_mon1}],
            rooms=[{"id": "R1", "capacity": 30, "type": "classroom"},
                   {"id": "R2", "capacity": 30, "type": "classroom"}],
            courses=[course("C1", "F1", 1), course("C2", "F2", 1)],
            students=[("S1", ["C1", "C2"])],
        )
        result = self.solve(data, diagnose_time_seconds=20)
        self.assertEqual(result["status"], "INFEASIBLE")
        reasons = " ".join(result["infeasibility_reasons"])
        self.assertIn("Students who take [C1, C2]", reasons)
        self.assertIn("F1", reasons)
        self.assertIn("F2", reasons)
        self.assertGreater(len(result["infeasibility_reasons"]), 2)

    def test_30_course_instance_hard_constraints_hold(self):
        data = benchmark.make_synthetic(n_courses=30, n_cohorts=6, students_per_cohort=20)
        result = self.solve(data, max_time_seconds=30.0)
        self.assertSolved(data, result)

    @unittest.skipUnless(os.environ.get("RUN_SLOW") == "1", "set RUN_SLOW=1 to run")
    def test_100_courses_under_60_seconds(self):
        data, result, elapsed, problems = benchmark.run(100, seconds=60.0, workers=0)
        print(f"\n100 courses: {result['status']} in {elapsed:.1f}s, "
              f"metrics={result.get('metrics')}")
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(problems, [])
        self.assertLess(elapsed, 60.0)


if __name__ == "__main__":
    unittest.main()