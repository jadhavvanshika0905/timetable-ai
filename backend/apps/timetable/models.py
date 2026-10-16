"""PART 1 + 3 - Solver ka output: timetable versions aur unki entries."""
from django.conf import settings
from django.db import models


class Timetable(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    class SolverStatus(models.TextChoices):
        OPTIMAL = "OPTIMAL", "Optimal"
        FEASIBLE = "FEASIBLE", "Feasible"
        INFEASIBLE = "INFEASIBLE", "Infeasible"
        MANUAL = "MANUAL", "Manually edited"

    term = models.ForeignKey("institution.AcademicTerm", on_delete=models.CASCADE, related_name="timetables")
    version = models.PositiveIntegerField(default=1)  # REQ-4.4 version history
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    solver_status = models.CharField(max_length=10, choices=SolverStatus.choices, default=SolverStatus.OPTIMAL)
    infeasibility_reasons = models.JSONField(default=list, blank=True)  # REQ-2.7
    solve_seconds = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["term", "version"], name="uniq_term_version")]

    def __str__(self):
        return f"{self.term_id} v{self.version} [{self.status}]"


class TimetableEntry(models.Model):
    """Ek class: kaun sa course, kaun faculty, kaun si room, kab."""
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name="entries")
    course = models.ForeignKey("institution.Course", on_delete=models.CASCADE)
    faculty = models.ForeignKey("institution.Faculty", on_delete=models.CASCADE)
    room = models.ForeignKey("institution.Room", on_delete=models.CASCADE)
    timeslot = models.ForeignKey("institution.TimeSlot", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # DB level pe hard constraints: double booking ho hi nahi sakti
            models.UniqueConstraint(fields=["timetable", "faculty", "timeslot"], name="no_faculty_clash"),
            models.UniqueConstraint(fields=["timetable", "room", "timeslot"], name="no_room_clash"),
            models.UniqueConstraint(fields=["timetable", "course", "timeslot"], name="no_course_repeat_in_slot"),
        ]
        indexes = [models.Index(fields=["timetable", "course"])]

    def __str__(self):
        return f"{self.course_id} @ {self.timeslot_id} in {self.room_id}"
