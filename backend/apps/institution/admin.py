from django.contrib import admin
from . import models

for m in (models.Department, models.AcademicTerm, models.Faculty, models.Room, models.Course,
          models.Student, models.StudentCourseChoice, models.TimeSlot, models.FacultyPreference):
    admin.site.register(m)
