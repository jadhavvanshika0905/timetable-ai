"""Pure-data tests for v4 adapter; no PostgreSQL or Django server required."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from apps.scheduler.services import (SchedulerDataError,
                                     build_solver_input_from_records)


class SchedulerServiceTests(unittest.TestCase):
    def setUp(self):
        self.records = {
            "courses": [
                {"id": 11, "code": "CSE101", "name": "Theory", "faculty_id": 1,
                 "hours_per_week": 2, "expected_students": 65,
                 "requires_lab": False, "course_type": "MAJOR"},
                {"id": 12, "code": "CSE102P", "name": "Lab", "faculty_id": 2,
                 "hours_per_week": 2, "expected_students": 25,
                 "requires_lab": True, "course_type": "SKILL"},
            ],
            "faculty": [{"id": 1, "name": "Instructor A"},
                        {"id": 2, "name": "Instructor B"}],
            "rooms": [{"id": 101, "code": "ROOM_A", "capacity": 80, "room_type": "CLASSROOM"},
                      {"id": 102, "code": "LAB_A", "capacity": 30, "room_type": "LAB"}],
            "timeslots": [{"day": day, "period": p, "is_break": day == "Mon" and p == 3}
                          for day in ("Mon", "Tue") for p in (1, 2, 3, 4)],
            "enrollments": [{"student_id": 500, "course_id": 11},
                            {"student_id": 500, "course_id": 12}],
            "preferences": [{"faculty_id": 1, "timeslot__day": "Mon",
                             "timeslot__period": 1, "level": "NO"}],
        }

    def build(self, **updates):
        r = copy.deepcopy(self.records)
        r.update(updates)
        return build_solver_input_from_records(**r, lab_block_sizes={12: 2})

    def test_pks_and_room_types_normalized(self):
        data = self.build()
        self.assertEqual([c["id"] for c in data["courses"]], ["11", "12"])
        self.assertEqual([r["type"] for r in data["rooms"]], ["classroom", "lab"])
        self.assertEqual(data["courses"][1]["lab_block_size"], 2)

    def test_enrollment_uses_anonymous_ids_and_clash_group(self):
        data = self.build()
        self.assertEqual(data["student_choices"],
                         [{"student_id": "500", "course_ids": ["11", "12"]}])

    def test_unlisted_day_period_is_blocked(self):
        r = copy.deepcopy(self.records)
        r["timeslots"] = [slot for slot in r["timeslots"]
                          if not (slot["day"] == "Tue" and slot["period"] == 4)]
        data = self.build(timeslots=r["timeslots"])
        self.assertIn({"day": "Tue", "period": 4}, data["slots"]["breaks"])

    def test_invalid_faculty_mapping_rejected(self):
        courses = copy.deepcopy(self.records["courses"])
        courses[0]["faculty_id"] = None
        with self.assertRaisesRegex(SchedulerDataError, "no valid assigned faculty"):
            self.build(courses=courses)

    def test_missing_attendance_is_rejected(self):
        courses = copy.deepcopy(self.records["courses"])
        courses[0]["expected_students"] = 0
        with self.assertRaisesRegex(SchedulerDataError, "no enrollment count"):
            self.build(courses=courses, enrollments=[])

    def test_enrolled_count_overrides_lower_expected_count(self):
        courses = copy.deepcopy(self.records["courses"])
        courses[0]["expected_students"] = 1
        enrollments = [{"student_id": i, "course_id": 11} for i in range(3)]
        data = self.build(courses=courses, enrollments=enrollments)
        self.assertEqual(data["courses"][0]["expected_students"], 3)

    def test_bad_lab_block_rejected(self):
        with self.assertRaisesRegex(SchedulerDataError, "invalid lab_block_size"):
            build_solver_input_from_records(**self.records, lab_block_sizes={12: 3})

    def test_duplicate_faculty_rejected(self):
        faculty = self.records["faculty"] + [self.records["faculty"][0]]
        with self.assertRaisesRegex(SchedulerDataError, "Duplicate faculty"):
            self.build(faculty=faculty)

    @unittest.skipUnless(importlib.util.find_spec("ortools"), "OR-Tools not installed in this environment")
    def test_end_to_end_with_solver(self):
        from apps.scheduler.solver import generate_timetable
        from apps.scheduler.validator import validate_timetable
        data = self.build()
        result = generate_timetable(data)
        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"), result)
        self.assertEqual(len(result["timetable"]), 4)
        self.assertEqual(validate_timetable(data, result["timetable"]), [])


if __name__ == "__main__":
    unittest.main()
