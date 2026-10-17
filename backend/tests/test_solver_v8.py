
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from apps.scheduler.solver import generate_timetable
from apps.scheduler.validator import validate_timetable


class TestAdvancedSchedulerV8(unittest.TestCase):

    def setUp(self):
        self.data = {
            "slots": {
                "days": ["Mon"],
                "periods": [1],
            },
            "faculty": [
                {"id": "F1", "name": "Faculty One"},
                {"id": "F2", "name": "Faculty Two"},
            ],
            "rooms": [
                {"id": "R1", "capacity": 40, "type": "classroom"},
                {"id": "R2", "capacity": 40, "type": "classroom"},
            ],
            "courses": [
                {
                    "id": "C1",
                    "faculty_id": "F1",
                    "hours_per_week": 1,
                    "expected_students": 20,
                    "requires_lab": False,
                },
                {
                    "id": "C2",
                    "faculty_id": "F2",
                    "hours_per_week": 1,
                    "expected_students": 20,
                    "requires_lab": False,
                },
            ],
            "student_choices": [],
        }

    def test_student_clash_is_infeasible(self):
        data = copy.deepcopy(self.data)

        data["student_choices"] = [
            {
                "student_id": "S1",
                "course_ids": ["C1", "C2"],
            }
        ]

        result = generate_timetable(data)

        self.assertEqual(result["status"], "INFEASIBLE")

    def test_parallel_classes_without_student_clash(self):
        data = copy.deepcopy(self.data)

        data["student_choices"] = [
            {"student_id": "S1", "course_ids": ["C1"]},
            {"student_id": "S2", "course_ids": ["C2"]},
        ]

        result = generate_timetable(data)

        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result["timetable"]), 2)

        self.assertEqual(
            {e["period"] for e in result["timetable"]},
            {1},
        )

        self.assertEqual(
            len({e["room_id"] for e in result["timetable"]}),
            2,
        )

    def test_invalid_faculty_limit_type(self):
        data = copy.deepcopy(self.data)

        data["faculty"][0]["max_hours_per_week"] = "five"

        result = generate_timetable(data)

        self.assertEqual(result["status"], "INVALID_INPUT")

    def test_manual_wrong_faculty_detected(self):
        data = copy.deepcopy(self.data)

        result = generate_timetable(data)

        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))

        edited = copy.deepcopy(result["timetable"])

        for entry in edited:
            if entry["course_id"] == "C1":
                entry["faculty_id"] = "F2"
                break

        errors = validate_timetable(data, edited)

        self.assertTrue(
            any("incorrect faculty" in error for error in errors)
        )

    def test_validator_detects_faculty_overload(self):
        data = copy.deepcopy(self.data)

        data["faculty"][0]["max_hours_per_week"] = 1
        data["faculty"][1]["max_hours_per_week"] = 1

        result = generate_timetable(data)

        self.assertIn(
            result["status"], ("OPTIMAL", "FEASIBLE")
        )

        edited = copy.deepcopy(result["timetable"])

        # Manually assign F2's class to F1.
        for entry in edited:
            if entry["course_id"] == "C2":
                entry["faculty_id"] = "F1"

        errors = validate_timetable(data, edited)

        self.assertTrue(
            any("max_hours_per_week" in error for error in errors),
            errors
        )



if __name__ == "__main__":
    unittest.main()
