"""Run:  python manage.py test apps.accounts -v 2"""
from datetime import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.institution.models import (AcademicTerm, Course, Department, Faculty,
                                     Room, Student, StudentCourseChoice, TimeSlot)
from . import timetable_access as access
from .models import UserProfile

User = get_user_model()
PW = "Str0ng!Passw0rd"


class Base(APITestCase):
    @classmethod
    def setUpTestData(cls):
        dept = Department.objects.create(code="ACC", name="Acc Dept")
        cls.term = AcademicTerm.objects.create(name="ACC-T1")
        cls.f1 = Faculty.objects.create(employee_id="ACC-F1", name="Fac One", department=dept)
        cls.f2 = Faculty.objects.create(employee_id="ACC-F2", name="Fac Two", department=dept)
        cls.room = Room.objects.create(code="ACC-R1", capacity=40, room_type="CLASSROOM")
        cls.c1 = Course.objects.create(code="ACC-C1", name="C1", department=dept, faculty=cls.f1,
                                       hours_per_week=2, expected_students=2)
        cls.c2 = Course.objects.create(code="ACC-C2", name="C2", department=dept, faculty=cls.f2,
                                       hours_per_week=2, expected_students=2)
        cls.s1 = Student.objects.create(roll_no="ACC-S1", name="Stu One", department=dept)
        cls.s2 = Student.objects.create(roll_no="ACC-S2", name="Stu Two", department=dept)
        StudentCourseChoice.objects.create(student=cls.s1, course=cls.c1, term=cls.term)
        StudentCourseChoice.objects.create(student=cls.s2, course=cls.c2, term=cls.term)
        cls.admin = User.objects.create_user("admin1", password=PW)
        UserProfile.objects.create(user=cls.admin, role="ADMIN")
        cls.fac_user = User.objects.create_user("fac1", password=PW)
        UserProfile.objects.create(user=cls.fac_user, role="FACULTY", faculty=cls.f1)
        cls.stu_user = User.objects.create_user("stu1", password=PW)
        UserProfile.objects.create(user=cls.stu_user, role="STUDENT", student=cls.s1)
        cls.noprofile = User.objects.create_user("ghost", password=PW)

    def setUp(self):
        cache.clear()
        self.rows = [
            {"course_id": str(self.c1.id), "faculty_id": str(self.f1.id),
             "room_id": str(self.room.id), "day": "Mon", "period": 1},
            {"course_id": str(self.c2.id), "faculty_id": str(self.f2.id),
             "room_id": str(self.room.id), "day": "Mon", "period": 2},
        ]
        access.save_timetable(self.term.id, {"status": "OPTIMAL", "timetable": self.rows})

    def login(self, username, password=PW):
        return self.client.post("/api/auth/login/", {"username": username, "password": password},
                                format="json")

    def as_user(self, username):
        token = self.login(username).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class LoginTests(Base):
    def test_login_returns_tokens_and_role(self):
        res = self.login("fac1")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["role"], "FACULTY")
        self.assertEqual(res.data["user"]["faculty_id"], self.f1.id)

    def test_wrong_password_is_401(self):
        self.assertEqual(self.login("fac1", "wrong").status_code, 401)

    def test_user_without_role_cannot_login(self):
        self.assertEqual(self.login("ghost").status_code, 400)

    def test_superuser_without_profile_is_admin(self):
        User.objects.create_superuser("root", password=PW)
        self.assertEqual(self.login("root").data["user"]["role"], "ADMIN")

    def test_me_needs_token(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.as_user("stu1")
        me = self.client.get("/api/auth/me/")
        self.assertEqual((me.status_code, me.data["role"]), (200, "STUDENT"))

    def test_refresh_works(self):
        refresh = self.login("admin1").data["refresh"]
        res = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)


class RoleRuleTests(Base):
    def test_only_admin_creates_users(self):
        body = {"username": "new1", "password": PW, "role": "ADMIN"}
        self.as_user("fac1")
        self.assertEqual(self.client.post("/api/auth/users/", body, format="json").status_code, 403)
        self.as_user("admin1")
        res = self.client.post("/api/auth/users/", body, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.login("new1").data["user"]["role"], "ADMIN")

    def test_create_faculty_user_needs_valid_link_and_no_duplicates(self):
        self.as_user("admin1")
        url = "/api/auth/users/"
        base = {"username": "f2login", "password": PW, "role": "FACULTY"}
        self.assertEqual(self.client.post(url, base, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {**base, "faculty_id": self.f1.id},
                                          format="json").status_code, 400)   # f1 already linked
        self.assertEqual(self.client.post(url, {**base, "faculty_id": self.f2.id},
                                          format="json").status_code, 201)

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
         "OPTIONS": {"min_length": 8}}])
    def test_weak_password_rejected(self):
        self.as_user("admin1")
        res = self.client.post("/api/auth/users/", {"username": "weak", "password": "123",
                                                    "role": "ADMIN"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_faculty_and_student_cannot_generate_or_see_full_timetable(self):
        for who in ("fac1", "stu1"):
            self.as_user(who)
            self.assertEqual(self.client.post("/api/timetable/generate/",
                                              {"term_id": self.term.id}, format="json").status_code, 403)
            self.assertEqual(self.client.get(f"/api/timetable/?term_id={self.term.id}").status_code, 403)

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get(f"/api/timetable/mine/?term_id={self.term.id}").status_code, 401)

    def test_user_without_profile_with_valid_token_is_403(self):
        from rest_framework_simplejwt.tokens import AccessToken
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.noprofile)}")
        self.assertEqual(self.client.get(f"/api/timetable/mine/?term_id={self.term.id}").status_code, 403)

    def test_profile_validation(self):
        with self.assertRaises(Exception):
            UserProfile.objects.create(user=User.objects.create_user("x1", password=PW),
                                       role="FACULTY")       # no faculty linked


class OwnTimetableTests(Base):
    def test_admin_sees_everything(self):
        self.as_user("admin1")
        res = self.client.get(f"/api/timetable/?term_id={self.term.id}")
        self.assertEqual(len(res.data["timetable"]), 2)
        self.assertEqual(res.data["timetable"][0]["course_code"], "ACC-C1")
        mine = self.client.get(f"/api/timetable/mine/?term_id={self.term.id}")
        self.assertEqual(len(mine.data["timetable"]), 2)

    def test_faculty_sees_only_own_classes(self):
        self.as_user("fac1")
        rows = self.client.get(f"/api/timetable/mine/?term_id={self.term.id}").data["timetable"]
        self.assertEqual([r["course_code"] for r in rows], ["ACC-C1"])
        self.assertEqual(rows[0]["faculty_name"], "Fac One")

    def test_student_sees_only_enrolled_courses(self):
        self.as_user("stu1")
        rows = self.client.get(f"/api/timetable/mine/?term_id={self.term.id}").data["timetable"]
        self.assertEqual([r["course_code"] for r in rows], ["ACC-C1"])

    def test_missing_term_and_missing_timetable(self):
        self.as_user("stu1")
        self.assertEqual(self.client.get("/api/timetable/mine/").status_code, 400)
        self.assertEqual(self.client.get("/api/timetable/mine/?term_id=999").status_code, 404)


class GenerateTests(Base):
    def test_admin_generate_saves_result(self):
        cache.clear()
        fake = {"result": {"status": "OPTIMAL", "timetable": self.rows, "metrics": {"x": 1}},
                "ml_hints": {"faculty_risk": {"1": "LOW"}, "predicted_demand": {}, "weights": {},
                             "_notes": {"clipped_to_room_capacity": []}}}
        self.as_user("admin1")
        with mock.patch("apps.ml.service.generate_with_ml", return_value=fake) as gen:
            res = self.client.post("/api/timetable/generate/",
                                   {"term_id": self.term.id, "max_time_seconds": 5}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["saved"])
        self.assertNotIn("_notes", res.data["ml_hints"])
        self.assertEqual(gen.call_args.kwargs["max_time_seconds"], 5.0)
        self.assertEqual(len(access.get_timetable(self.term.id)["timetable"]), 2)

    def test_failed_solve_is_not_saved(self):
        cache.clear()
        fake = {"result": {"status": "INFEASIBLE", "timetable": [], "infeasibility_reasons": ["r"]},
                "ml_hints": None}
        self.as_user("admin1")
        with mock.patch("apps.ml.service.generate_with_ml", return_value=fake):
            res = self.client.post("/api/timetable/generate/", {"term_id": self.term.id,
                                                                "use_ml": False}, format="json")
        self.assertFalse(res.data["saved"])
        self.assertIsNone(access.get_timetable(self.term.id))

    def test_generate_needs_term_id(self):
        self.as_user("admin1")
        self.assertEqual(self.client.post("/api/timetable/generate/", {}, format="json").status_code, 400)

    def test_real_end_to_end_small_term(self):
        """No mocks: real DB -> ML -> solver -> stored -> faculty sees own rows."""
        cache.clear()
        for day in ("Mon", "Tue", "Wed", "Thu", "Fri"):
            for p in range(1, 6):
                TimeSlot.objects.create(day=day, period=p, start_time=time(8 + p), end_time=time(9 + p),
                                        is_break=(p == 3))
        self.as_user("admin1")
        res = self.client.post("/api/timetable/generate/", {
            "term_id": self.term.id, "max_time_seconds": 20, "use_ml": True,
            "course_ids": [self.c1.id, self.c2.id]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn(res.data["status"], ("OPTIMAL", "FEASIBLE"))
        self.as_user("fac1")
        rows = self.client.get(f"/api/timetable/mine/?term_id={self.term.id}").data["timetable"]
        self.assertTrue(rows)
        self.assertTrue(all(r["course_code"] == "ACC-C1" for r in rows))
