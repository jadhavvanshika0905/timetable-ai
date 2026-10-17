"""Member 1: Django-to-OR-Tools data adapter (v4, read-only).

No database writes and no changes to teammates' models. The pure conversion
function can be unit-tested without Django, PostgreSQL, or a running server.

The current institution schema has no CourseOffering/Section or lab_block_size
columns. Until Member 2 adds those, callers must pass an explicit offering
selection when needed and lab sizes using ``lab_block_sizes``.
"""
from collections import Counter, defaultdict

DAY_ORDER = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
ROOM_TYPES = {"CLASSROOM": "classroom", "LAB": "lab", "SEMINAR": "seminar"}
PREFERENCE_LEVELS = {"NO", "AVOID", "PREFER"}


class SchedulerDataError(ValueError):
    """Missing or inconsistent institutional input; do not run the solver."""


def _id(value):
    if value is None or str(value).strip() == "":
        raise SchedulerDataError("Encountered a missing database identifier.")
    return str(value)


def build_solver_input_from_records(*, courses, faculty, rooms, timeslots,
                                    enrollments, preferences=(), lab_block_sizes=None):
    """Normalize dictionaries (typically Django QuerySet.values() rows).

    ``courses``: id, code, name, faculty_id, hours_per_week,
      requires_lab, expected_students, course_type.
    ``faculty``: id, name.
    ``rooms``: id, code, capacity, room_type (Django uppercase values).
    ``timeslots``: day, period, is_break.
    ``enrollments``: student_id, course_id (already scoped to academic term).
    ``preferences``: faculty_id, timeslot__day, timeslot__period, level.
    ``lab_block_sizes``: optional mapping of DB course PK (as int/str) to
      required consecutive period count. If not specified, defaults to 1,
      exactly as the existing v3 solver contract does.
    """
    courses, faculty = list(courses), list(faculty)
    rooms, timeslots = list(rooms), list(timeslots)
    enrollments, preferences = list(enrollments), list(preferences)
    lab_block_sizes = {_id(k): v for k, v in (lab_block_sizes or {}).items()}
    if not courses:
        raise SchedulerDataError("No course offerings selected for scheduling.")
    if not rooms:
        raise SchedulerDataError("No rooms registered; cannot schedule classes.")
    if not timeslots:
        raise SchedulerDataError("No TimeSlot records found; define college working periods.")

    available = set()
    explicit_breaks = set()
    all_days = set()
    all_periods = set()
    for slot in timeslots:
        day, period = slot.get("day"), slot.get("period")
        if day not in DAY_ORDER or type(period) is not int or period <= 0:
            raise SchedulerDataError(f"Invalid TimeSlot day/period: {day!r}, {period!r}.")
        key = (day, period)
        if key in available:
            raise SchedulerDataError(f"Duplicate TimeSlot record: {day} period {period}.")
        available.add(key)
        all_days.add(day)
        all_periods.add(period)
        if slot.get("is_break", False):
            explicit_breaks.add(key)
    days = [day for day in DAY_ORDER if day in all_days]
    periods = sorted(all_periods)
    # The solver assumes a rectangular day x period grid. Mark unspecified
    # day/period combinations as breaks so it cannot schedule there.
    breaks = explicit_breaks | {(day, p) for day in days for p in periods if (day, p) not in available}
    day_idx = {day: i for i, day in enumerate(days)}
    breaks_list = [{"day": d, "period": p} for d, p in sorted(breaks, key=lambda x: (day_idx[x[0]], x[1]))]

    faculty_by_id = {}
    for item in faculty:
        fid = _id(item.get("id"))
        if fid in faculty_by_id:
            raise SchedulerDataError(f"Duplicate faculty ID {fid}.")
        faculty_by_id[fid] = {"id": fid, "name": item.get("name") or f"Faculty {fid}", "preferences": []}

    for pref in preferences:
        fid = _id(pref.get("faculty_id"))
        if fid not in faculty_by_id:
            # Preferences for unrelated faculty may be present in the database.
            continue
        day = pref.get("timeslot__day", pref.get("day"))
        period = pref.get("timeslot__period", pref.get("period"))
        level = pref.get("level")
        if (day, period) not in available or level not in PREFERENCE_LEVELS:
            raise SchedulerDataError(f"Invalid preference for faculty {fid}: {day} P{period} ({level}).")
        faculty_by_id[fid]["preferences"].append({"day": day, "period": period, "level": level})

    normalized_rooms = []
    for room in rooms:
        rid = _id(room.get("id"))
        kind = ROOM_TYPES.get(str(room.get("room_type", "")).upper())
        capacity = room.get("capacity")
        if kind is None or type(capacity) is not int or capacity <= 0:
            raise SchedulerDataError(f"Room {rid} has invalid type/capacity.")
        normalized_rooms.append({"id": rid, "capacity": capacity, "type": kind})

    courses_by_id = {}
    for course in courses:
        cid = _id(course.get("id"))
        if cid in courses_by_id:
            raise SchedulerDataError(f"Duplicate Course PK {cid}.")
        fid = _id(course.get("faculty_id")) if course.get("faculty_id") is not None else None
        if fid not in faculty_by_id:
            raise SchedulerDataError(f"Course {cid} has no valid assigned faculty.")
        hours = course.get("hours_per_week")
        if type(hours) is not int or hours < 1:
            raise SchedulerDataError(f"Course {cid} needs a positive hours_per_week.")
        expected = course.get("expected_students")
        if type(expected) is not int or expected < 0:
            raise SchedulerDataError(f"Course {cid} needs a nonnegative expected_students.")
        is_lab = course.get("requires_lab", False)
        if type(is_lab) is not bool:
            raise SchedulerDataError(f"Course {cid} requires_lab must be true/false.")
        size = lab_block_sizes.get(cid, 1)
        if type(size) is not int or size < 1 or (size > 1 and not is_lab) or hours % size:
            raise SchedulerDataError(f"Course {cid} has invalid lab_block_size {size}.")
        courses_by_id[cid] = {
            "id": cid, "name": course.get("name") or course.get("code") or f"Course {cid}",
            "catalog_code": str(course.get("code") or cid), "faculty_id": fid,
            "hours_per_week": hours, "expected_students": expected,
            "requires_lab": is_lab, "type": str(course.get("course_type") or "major").lower(),
            "lab_block_size": size,
        }
    unknown_sizes = set(lab_block_sizes) - set(courses_by_id)
    if unknown_sizes:
        raise SchedulerDataError(f"lab_block_sizes refers to nonselected course IDs: {sorted(unknown_sizes)}.")

    enrollment_counts = Counter()
    choices = defaultdict(set)
    for row in enrollments:
        cid = _id(row.get("course_id"))
        if cid not in courses_by_id:
            continue  # other term offerings are not part of this schedule
        sid = _id(row.get("student_id"))
        if cid not in choices[sid]:
            choices[sid].add(cid)
            enrollment_counts[cid] += 1
    for cid, course in courses_by_id.items():
        course["expected_students"] = max(course["expected_students"], enrollment_counts[cid])
        if course["expected_students"] < 1:
            raise SchedulerDataError(
                f"Course {cid} has no enrollment count and expected_students=0; "
                "confirm attendance before allocating rooms."
            )

    return {
        "slots": {"days": days, "periods": periods, "breaks": breaks_list},
        "faculty": sorted(faculty_by_id.values(), key=lambda r: r["id"]),
        "rooms": sorted(normalized_rooms, key=lambda r: r["id"]),
        "courses": sorted(courses_by_id.values(), key=lambda r: r["id"]),
        "student_choices": [
            {"student_id": sid, "course_ids": sorted(cids)}
            for sid, cids in sorted(choices.items())
        ],
    }


def build_solver_input_from_db(term_id, *, course_ids=None, lab_block_sizes=None):
    """Read term enrollments + selected Course records from existing Django models.

    If course_ids omitted, selects distinct courses from this term's
    StudentCourseChoice; this does NOT automatically include core courses
    missing from enrollment records. Pass explicit course_ids to include them.
    Database must be migrated and populated before calling this function.
    """
    from apps.institution.models import (AcademicTerm, Course, Faculty,
                                         FacultyPreference, Room, TimeSlot,
                                         StudentCourseChoice)
    if not AcademicTerm.objects.filter(pk=term_id).exists():
        raise SchedulerDataError(f"AcademicTerm {term_id} does not exist.")
    choice_qs = StudentCourseChoice.objects.filter(term_id=term_id)
    if course_ids is None:
        selected = list(choice_qs.values_list("course_id", flat=True).distinct())
    else:
        selected = list(course_ids)
    if not selected:
        raise SchedulerDataError(
            f"No courses selected for term {term_id}. Import StudentCourseChoice "
            "or pass course_ids explicitly (including mandatory courses)."
        )
    selected_ids = {_id(pk) for pk in selected}
    course_rows = list(Course.objects.filter(pk__in=selected_ids).values(
        "id", "code", "name", "faculty_id", "hours_per_week", "requires_lab",
        "expected_students", "course_type"))
    found_ids = {_id(row["id"]) for row in course_rows}
    if found_ids != selected_ids:
        raise SchedulerDataError(f"Unknown Course PKs: {sorted(selected_ids - found_ids)}.")
    faculty_ids = {row["faculty_id"] for row in course_rows if row["faculty_id"] is not None}
    return build_solver_input_from_records(
        courses=course_rows,
        faculty=list(Faculty.objects.filter(pk__in=faculty_ids).values("id", "name")),
        rooms=list(Room.objects.values("id", "code", "capacity", "room_type")),
        timeslots=list(TimeSlot.objects.values("day", "period", "is_break")),
        enrollments=list(choice_qs.filter(course_id__in=selected_ids).values("student_id", "course_id")),
        preferences=list(FacultyPreference.objects.filter(faculty_id__in=faculty_ids)
                         .values("faculty_id", "timeslot__day", "timeslot__period", "level")),
        lab_block_sizes=lab_block_sizes,
    )


def generate_timetable_for_term(term_id, *, course_ids=None, lab_block_sizes=None):
    """Return existing solver result JSON without writing to the database."""
    try:
        data = build_solver_input_from_db(term_id, course_ids=course_ids,
                                          lab_block_sizes=lab_block_sizes)
    except SchedulerDataError as exc:
        return {"status": "INVALID_INPUT", "timetable": [],
                "infeasibility_reasons": [str(exc)]}
    from .solver import generate_timetable
    return generate_timetable(data)
