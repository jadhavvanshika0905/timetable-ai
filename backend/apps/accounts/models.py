"""PART 3 - Roles (Admin/Faculty/Student) aur audit log (SRS 5.3).
Custom User model nahi liya taaki existing migrations na tootein; Django ka default User + Profile."""
from django.conf import settings
from django.db import models


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        FACULTY = "FACULTY", "Faculty"
        STUDENT = "STUDENT", "Student"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=7, choices=Role.choices, default=Role.STUDENT)
    faculty = models.OneToOneField("institution.Faculty", null=True, blank=True, on_delete=models.SET_NULL)
    student = models.OneToOneField("institution.Student", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30)       # CREATE / UPDATE / DELETE / GENERATE / PUBLISH
    entity = models.CharField(max_length=50)       # "Course", "Timetable" ...
    entity_id = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
