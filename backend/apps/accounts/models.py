from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserProfile(models.Model):
    """Role of a login user.

    ADMIN   -> everything
    FACULTY -> only own timetable   (must be linked to an institution.Faculty)
    STUDENT -> only own timetable   (must be linked to an institution.Student)

    A Django *superuser* without a profile is treated as ADMIN (see roles.py).
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        FACULTY = "FACULTY", "Faculty"
        STUDENT = "STUDENT", "Student"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="profile")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    faculty = models.OneToOneField("institution.Faculty", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="login_profile")
    student = models.OneToOneField("institution.Student", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="login_profile")

    def clean(self):
        if self.role == self.Role.FACULTY and not self.faculty_id:
            raise ValidationError("A FACULTY user must be linked to a Faculty record.")
        if self.role == self.Role.STUDENT and not self.student_id:
            raise ValidationError("A STUDENT user must be linked to a Student record.")
        if self.role == self.Role.ADMIN and (self.faculty_id or self.student_id):
            raise ValidationError("An ADMIN user must not be linked to Faculty/Student.")

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["user"])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} ({self.role})"

