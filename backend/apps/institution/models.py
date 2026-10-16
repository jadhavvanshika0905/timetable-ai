"""PART 2 - Institution data: departments, faculty, rooms, courses, students, time slots."""
from django.db import models


class Department(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AcademicTerm(models.Model):
    """Ek semester/session, e.g. '2026-ODD'. Choices aur timetable isi se jude hote hain."""
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Faculty(models.Model):
    employee_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="faculty")
    max_hours_per_week = models.PositiveSmallIntegerField(default=16)

    class Meta:
        verbose_name_plural = "faculty"

    def __str__(self):
        return f"{self.name} ({self.employee_id})"


class Room(models.Model):
    class RoomType(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Classroom"
        LAB = "LAB", "Laboratory"
        SEMINAR = "SEMINAR", "Seminar Hall"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(max_length=10, choices=RoomType.choices, default=RoomType.CLASSROOM)

    def __str__(self):
        return f"{self.code} ({self.capacity})"


class Course(models.Model):
    class CourseType(models.TextChoices):  # NEP 2020 structure (REQ-1.4)
        MAJOR = "MAJOR", "Major"
        MINOR = "MINOR", "Minor"
        SKILL = "SKILL", "Skill-Based"
        VALUE_ADDED = "VALUE", "Value-Added"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")
    course_type = models.CharField(max_length=6, choices=CourseType.choices, default=CourseType.MAJOR)
    credits = models.PositiveSmallIntegerField(default=3)
    hours_per_week = models.PositiveSmallIntegerField(default=3)
    requires_lab = models.BooleanField(default=False)
    semester = models.PositiveSmallIntegerField(default=1)
    faculty = models.ForeignKey(Faculty, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="courses")
    expected_students = models.PositiveIntegerField(default=0)  # solver room-capacity check isi se karta hai

    def __str__(self):
        return f"{self.code} - {self.name}"


class Student(models.Model):
    roll_no = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="students")
    semester = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"{self.roll_no} - {self.name}"


class StudentCourseChoice(models.Model):
    """Student ne is term mein kaun sa course chuna (major/minor/skill/value-added)."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="choices")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="choices")
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="choices")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "course", "term"],
                                               name="uniq_student_course_term")]

    def __str__(self):
        return f"{self.student_id}:{self.course_id}@{self.term_id}"


class TimeSlot(models.Model):
    class Day(models.TextChoices):
        MON = "Mon"
        TUE = "Tue"
        WED = "Wed"
        THU = "Thu"
        FRI = "Fri"
        SAT = "Sat"

    day = models.CharField(max_length=3, choices=Day.choices)
    period = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)  # lunch etc. - yahan class nahi lagegi

    class Meta:
        ordering = ["day", "period"]
        constraints = [models.UniqueConstraint(fields=["day", "period"], name="uniq_day_period")]

    def __str__(self):
        return f"{self.day} P{self.period}"


class FacultyPreference(models.Model):
    """Faculty availability / preference - solver ke soft + hard constraints ka input."""
    class Level(models.TextChoices):
        UNAVAILABLE = "NO", "Unavailable (hard)"
        AVOID = "AVOID", "Prefer not (soft)"
        PREFER = "PREFER", "Preferred (soft)"

    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="preferences")
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    level = models.CharField(max_length=6, choices=Level.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["faculty", "timeslot"], name="uniq_faculty_slot_pref")]
