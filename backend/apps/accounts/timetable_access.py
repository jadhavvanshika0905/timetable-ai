"""Who may see which timetable rows.   (Pure functions, easy to test.)

TEMPORARY STORE: the generated timetable is kept in Django's cache. In Step 4 it
moves to database models; only get_timetable()/save_timetable() change.
"""
from django.core.cache import cache

from .roles import ADMIN, FACULTY, STUDENT, get_role


def _key(term_id):
    return f"timetable:latest:{int(term_id)}"


def save_timetable(term_id, solver_result):
    cache.set(_key(term_id), solver_result, timeout=None)


def get_timetable(term_id):
    return cache.get(_key(term_id))


def student_course_ids(student_id, term_id):
    from apps.institution.models import StudentCourseChoice
    return {str(c) for c in StudentCourseChoice.objects.filter(
        student_id=student_id, term_id=term_id).values_list("course_id", flat=True)}


def rows_for_user(user, term_id, rows):
    """Admin -> all rows.  Faculty -> own classes.  Student -> own enrolled courses."""
    role = get_role(user)
    if role == ADMIN:
        return list(rows)
    if role == FACULTY:
        fid = str(user.profile.faculty_id)
        return [r for r in rows if str(r["faculty_id"]) == fid]
    if role == STUDENT:
        mine = student_course_ids(user.profile.student_id, term_id)
        return [r for r in rows if str(r["course_id"]) in mine]
    return []


def enrich(rows):
    """Add human-readable names (course code/name, room code, faculty name)."""
    from apps.institution.models import Course, Faculty, Room
    courses = {str(c["id"]): c for c in Course.objects.filter(
        pk__in=[r["course_id"] for r in rows]).values("id", "code", "name")}
    rooms = {str(r["id"]): r["code"] for r in Room.objects.values("id", "code")}
    people = {str(f["id"]): f["name"] for f in Faculty.objects.filter(
        pk__in=[r["faculty_id"] for r in rows]).values("id", "name")}
    out = []
    for r in rows:
        c = courses.get(str(r["course_id"]), {})
        out.append({**r, "course_code": c.get("code"), "course_name": c.get("name"),
                    "room_code": rooms.get(str(r["room_id"])),
                    "faculty_name": people.get(str(r["faculty_id"]))})
    return out
