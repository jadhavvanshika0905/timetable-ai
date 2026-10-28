from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Create a login with a role.  Examples:\n" \
           "  create_role_user --username boss --password 'Str0ng!Pass1' --role ADMIN\n" \
           "  create_role_user --username f1 --password '...' --role FACULTY --employee-id EMP01\n" \
           "  create_role_user --username s1 --password '...' --role STUDENT --roll-no 21CS001"

    def add_arguments(self, p):
        p.add_argument("--username", required=True)
        p.add_argument("--password", required=True)
        p.add_argument("--role", required=True, choices=["ADMIN", "FACULTY", "STUDENT"])
        p.add_argument("--employee-id", help="Faculty.employee_id (FACULTY role)")
        p.add_argument("--roll-no", help="Student.roll_no (STUDENT role)")

    @transaction.atomic
    def handle(self, *a, **o):
        from apps.institution.models import Faculty, Student
        User = get_user_model()
        if User.objects.filter(username=o["username"]).exists():
            raise CommandError(f"User {o['username']} already exists.")
        try:
            validate_password(o["password"])
        except ValidationError as exc:
            raise CommandError("Weak password: " + " ".join(exc.messages))
        faculty = student = None
        if o["role"] == "FACULTY":
            faculty = Faculty.objects.filter(employee_id=o["employee_id"]).first()
            if not faculty:
                raise CommandError("Faculty with that --employee-id not found.")
        if o["role"] == "STUDENT":
            student = Student.objects.filter(roll_no=o["roll_no"]).first()
            if not student:
                raise CommandError("Student with that --roll-no not found.")
        user = User.objects.create_user(username=o["username"], password=o["password"])
        UserProfile.objects.create(user=user, role=o["role"], faculty=faculty, student=student)
        self.stdout.write(self.style.SUCCESS(f"Created {o['role']} user '{o['username']}'."))
