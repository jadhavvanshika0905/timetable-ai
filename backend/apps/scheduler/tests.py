from django.test import TestCase

# Create your tests here.

from datetime import time

from django.test import TestCase

from apps.institution.models import (
    Department, AcademicTerm, Faculty, Room,
    Course, Student, StudentCourseChoice, TimeSlot
)
from apps.scheduler.services import (
    build_solver_input_from_db,
    generate_timetable_for_term,
)


class SchedulerDatabaseIntegrationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        dept = Department.objects.create(
            code="TESTCSE", name="Test Computer Science"
        )

        cls.term = AcademicTerm.objects.create(
            name="TEST-2026"
        )

        f1 = Faculty.objects.create(
            employee_id="TEST-F01",
            name="Test Faculty A",
            department=dept,
        )
        f2 = Faculty.objects.create(
            employee_id="TEST-F02",
            name="Test Faculty B",
            department=dept,
        )

        Room.objects.create(
            code="TEST-R101",
            capacity=40,
            room_type="CLASSROOM",
        )
        Room.objects.create(
            code="TEST-L101",
            capacity=40,
            room_type="LAB",
        )

        specs = [
            ("TEST-DSA", f1, 3, False),
            ("TEST-DBMS", f2, 3, False),
            ("TEST-PYLAB", f1, 2, True),
            ("TEST-AI", f2, 2, False),
        ]

        cls.courses = []

        for code, faculty, hours, lab in specs:
            course = Course.objects.create(
                code=code,
                name=code,
                department=dept,
                faculty=faculty,
                hours_per_week=hours,
                requires_lab=lab,
                expected_students=2,
            )
            cls.courses.append(course)

        cls.lab = next(
            c for c in cls.courses if c.requires_lab
        )

        for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            for period in range(1, 6):
                TimeSlot.objects.create(
                    day=day,
                    period=period,
                    start_time=time(8 + period, 0),
                    end_time=time(9 + period, 0),
                    is_break=(period == 3),
                )

        for i in range(2):
            student = Student.objects.create(
                roll_no=f"TEST-S{i + 1}",
                name=f"Test Student {i + 1}",
                department=dept,
            )

            for course in cls.courses:
                StudentCourseChoice.objects.create(
                    student=student,
                    course=course,
                    term=cls.term,
                )

    def generate(self):
        return generate_timetable_for_term(
            self.term.id,
            lab_block_sizes={self.lab.id: 2},
        )

    def test_database_adapter(self):
        data = build_solver_input_from_db(
            self.term.id,
            lab_block_sizes={self.lab.id: 2},
        )

        self.assertEqual(len(data["courses"]), 4)
        self.assertEqual(len(data["faculty"]), 2)
        self.assertEqual(len(data["rooms"]), 2)
        self.assertEqual(len(data["student_choices"]), 2)

    def test_timetable_generation(self):
        result = self.generate()

        self.assertIn(
            result["status"], ["OPTIMAL", "FEASIBLE"]
        )
        self.assertEqual(len(result["timetable"]), 10)
        self.assertEqual(result["infeasibility_reasons"], [])

    def test_no_clashes_or_break_classes(self):
        result = self.generate()
        self.assertIn(
            result["status"], ["OPTIMAL", "FEASIBLE"]
        )

        faculty_slots = set()
        room_slots = set()
        student_slots = set()

        for entry in result["timetable"]:
            day = entry["day"]
            period = entry["period"]

            self.assertNotEqual(period, 3)

            faculty_key = (
                entry["faculty_id"], day, period
            )
            room_key = (
                entry["room_id"], day, period
            )
            student_key = (day, period)

            self.assertNotIn(faculty_key, faculty_slots)
            self.assertNotIn(room_key, room_slots)
            self.assertNotIn(student_key, student_slots)

            faculty_slots.add(faculty_key)
            room_slots.add(room_key)
            student_slots.add(student_key)

    def test_consecutive_lab_periods(self):
        result = self.generate()
        self.assertIn(
            result["status"], ["OPTIMAL", "FEASIBLE"]
        )

        lab_entries = [
            entry for entry in result["timetable"]
            if entry["course_id"] == str(self.lab.id)
        ]

        self.assertEqual(len(lab_entries), 2)
        self.assertEqual(
            lab_entries[0]["day"],
            lab_entries[1]["day"],
        )
        self.assertEqual(
            abs(
                lab_entries[0]["period"]
                - lab_entries[1]["period"]
            ),
            1,
        )

    def test_invalid_term(self):
        result = generate_timetable_for_term(-1)

        self.assertEqual(
            result["status"], "INVALID_INPUT"
        )
        self.assertEqual(result["timetable"], [])
