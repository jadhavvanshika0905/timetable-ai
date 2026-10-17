"""Tests for Member 1's v1 CP-SAT scheduling engine.
Run from the repository root:
    .\\.venv\\Scripts\\python.exe -m unittest discover -s backend/tests -p test_solver.py -v
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from apps.scheduler.solver import generate_timetable  # noqa: E402
from apps.scheduler.validator import validate_timetable  # noqa: E402


class TestSchedulerV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = json.loads((ROOT / "contracts" / "scheduler_demo_input_v1.json").read_text(encoding="utf-8"))
        cls.legacy = json.loads((ROOT / "contracts" / "sample_input.json").read_text(encoding="utf-8"))
        cls.v2 = json.loads((ROOT / "contracts" / "scheduler_demo_input_v2.json").read_text(encoding="utf-8"))

    def test_demo_generates_five_sessions(self):
        result = generate_timetable(self.demo)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result["timetable"]), 5)
        self.assertEqual(validate_timetable(self.demo, result["timetable"]), [])

    def test_original_repo_sample_is_still_supported(self):
        result = generate_timetable(self.legacy)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result["timetable"]), 5)

    def test_lab_only_in_lab(self):
        result = generate_timetable(self.demo)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertTrue(all(entry["room_id"] == "DEMO_L1"
            for entry in result["timetable"] if entry["course_id"] == "DEMO_CSE_A_C2"))

    def test_no_eligible_room_is_infeasible(self):
        data = copy.deepcopy(self.demo)
        data["rooms"][0]["capacity"] = 64
        self.assertEqual(generate_timetable(data)["status"], "INFEASIBLE")

    def test_same_section_different_courses_cannot_overlap(self):
        data = copy.deepcopy(self.demo)
        data["student_choices"] = []  # section rule alone must prevent overlap
        result = generate_timetable(data)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        course_slots = {}
        for entry in result["timetable"]:
            course_slots.setdefault(entry["course_id"], set()).add((entry["day"], entry["period"]))
        a, b = course_slots.values()
        self.assertFalse(a & b)

    def test_student_choices_block_cross_section_conflict(self):
        data = copy.deepcopy(self.legacy)
        result = generate_timetable(data)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(validate_timetable(data, result["timetable"]), [])

    def test_too_many_sessions_for_faculty(self):
        data = copy.deepcopy(self.legacy)
        data["slots"] = {"days": ["Mon"], "periods": [1, 2]}
        self.assertEqual(generate_timetable(data)["status"], "INFEASIBLE")

    def test_unknown_faculty_is_invalid(self):
        data = copy.deepcopy(self.demo)
        data["courses"][0]["faculty_id"] = "MISSING"
        self.assertEqual(generate_timetable(data)["status"], "INVALID_INPUT")

    def test_duplicate_course_ids_invalid(self):
        data = copy.deepcopy(self.demo)
        data["courses"][1]["id"] = data["courses"][0]["id"]
        self.assertEqual(generate_timetable(data)["status"], "INVALID_INPUT")

    def test_validator_flags_manual_room_clash(self):
        result = generate_timetable(self.demo)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        edited = copy.deepcopy(result["timetable"])
        edited[1]["day"] = edited[0]["day"]
        edited[1]["period"] = edited[0]["period"]
        edited[1]["room_id"] = edited[0]["room_id"]
        self.assertTrue(any("room double-booked" in issue for issue in validate_timetable(self.demo, edited)))


    def test_v2_demo_respects_breaks_and_faculty_unavailable(self):
        result = generate_timetable(self.v2)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result["timetable"]), 5)
        self.assertEqual(validate_timetable(self.v2, result["timetable"]), [])
        self.assertFalse(any(e["day"] == "Wed" and e["period"] == 3 for e in result["timetable"]))
        self.assertFalse(any(e["faculty_id"] == "DEMO_F1" and e["day"] == "Mon" and e["period"] == 1
                             for e in result["timetable"]))

    def test_theory_lectures_spread_across_days(self):
        result = generate_timetable(self.v2)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        theory_days = [e["day"] for e in result["timetable"] if e["course_id"] == "DEMO_CSE_A_C1"]
        self.assertEqual(len(set(theory_days)), 3)

    def test_all_faculty_slots_unavailable_is_infeasible(self):
        data = copy.deepcopy(self.legacy)
        for person in data["faculty"]:
            person["preferences"] = [
                {"day": day, "period": period, "level": "NO"}
                for day in data["slots"]["days"] for period in data["slots"]["periods"]
            ]
        result = generate_timetable(data)
        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertTrue(result["infeasibility_reasons"])

    def test_invalid_preference_slot_rejected(self):
        data = copy.deepcopy(self.v2)
        data["faculty"][0]["preferences"].append({"day": "Sunday", "period": 1, "level": "NO"})
        self.assertEqual(generate_timetable(data)["status"], "INVALID_INPUT")

    def test_duplicate_preference_rejected(self):
        data = copy.deepcopy(self.v2)
        data["faculty"][0]["preferences"].append({"day": "Mon", "period": 1, "level": "AVOID"})
        self.assertEqual(generate_timetable(data)["status"], "INVALID_INPUT")

    def test_invalid_break_rejected(self):
        data = copy.deepcopy(self.v2)
        data["slots"]["breaks"] = [{"day": "Mon", "period": 99}]
        self.assertEqual(generate_timetable(data)["status"], "INVALID_INPUT")

    def test_validator_flags_break_and_unavailable(self):
        result = generate_timetable(self.v2)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        timetable = copy.deepcopy(result["timetable"])
        timetable[0]["day"] = "Wed"
        timetable[0]["period"] = 3
        self.assertTrue(any("during a break" in error for error in validate_timetable(self.v2, timetable)))
        timetable[0]["day"] = "Mon"
        timetable[0]["period"] = 1
        timetable[0]["course_id"] = "DEMO_CSE_A_C1"
        timetable[0]["faculty_id"] = "DEMO_F1"
        self.assertTrue(any("unavailable" in error for error in validate_timetable(self.v2, timetable)))

    def test_soft_preference_prefers_slot(self):
        data = copy.deepcopy(self.legacy)
        data["slots"] = {"days": ["Mon"], "periods": [1, 2]}
        data["courses"] = [dict(data["courses"][0], hours_per_week=1)]
        data["faculty"][0]["preferences"] = [{"day": "Mon", "period": 2, "level": "PREFER"}]
        data["student_choices"] = []
        result = generate_timetable(data)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(result["timetable"][0]["period"], 2)

if __name__ == "__main__":
    unittest.main()
