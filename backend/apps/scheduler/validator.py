"""Independent validation of generated or manually edited timetables (v1)."""
from collections import Counter, defaultdict
from itertools import combinations


def validate_timetable(data: dict, timetable: list) -> list[str]:
    """Return human-readable issues. An empty list means v1 checks passed.

    v2 validates breaks and faculty unavailability. Multi-period practical
    blocks and preference optimization are not independently checked.
    """
    issues = []
    courses = {course["id"]: course for course in data["courses"]}
    faculty = {person["id"] for person in data["faculty"]}
    rooms = {room["id"]: room for room in data["rooms"]}
    days = set(data["slots"]["days"])
    periods = set(data["slots"]["periods"])
    counts = Counter()
    used_room = set()
    used_faculty = set()
    used_course = set()
    used_section = set()
    slots_by_course = defaultdict(set)
    breaks = {(s["day"], s["period"]) for s in data["slots"].get("breaks", [])}
    unavailable = {
        faculty_member["id"]: {
            (pref["day"], pref["period"])
            for pref in faculty_member.get("preferences", []) if pref["level"] == "NO"
        }
        for faculty_member in data["faculty"]
    }

    for row, entry in enumerate(timetable, start=1):
        if not isinstance(entry, dict):
            issues.append(f"Entry {row}: expected an object.")
            continue
        cid = entry.get("course_id")
        fid = entry.get("faculty_id")
        rid = entry.get("room_id")
        day = entry.get("day")
        period = entry.get("period")
        if cid not in courses or rid not in rooms or fid not in faculty or day not in days or period not in periods:
            issues.append(f"Entry {row}: unknown course/faculty/room/day/period.")
            continue
        course = courses[cid]
        room = rooms[rid]
        slot = (day, period)
        counts[cid] += 1
        slots_by_course[cid].add(slot)
        if slot in breaks:
            issues.append(f"Entry {row}: class scheduled during a break at {day} period {period}.")
        if slot in unavailable.get(fid, set()):
            issues.append(f"Entry {row}: faculty {fid} unavailable at {day} period {period}.")
        if course["faculty_id"] != fid:
            issues.append(f"Entry {row}: incorrect faculty for course {cid}.")
        if room["capacity"] < course["expected_students"]:
            issues.append(f"Entry {row}: room {rid} too small for course {cid}.")
        if course.get("requires_lab", False) and room["type"] != "lab":
            issues.append(f"Entry {row}: course {cid} requires a lab.")
        for group, seen, key in (
            ("room", used_room, (rid, slot)),
            ("faculty", used_faculty, (fid, slot)),
            ("course", used_course, (cid, slot)),
        ):
            if key in seen:
                issues.append(f"Entry {row}: {group} double-booked at {day} period {period}.")
            seen.add(key)
        if course.get("section_id"):
            key = (course["section_id"], slot)
            if key in used_section:
                issues.append(f"Entry {row}: section {course['section_id']} has overlapping classes.")
            used_section.add(key)

    for cid, course in courses.items():
        if counts[cid] != course["hours_per_week"]:
            issues.append(f"Course {cid}: expected {course['hours_per_week']} sessions, got {counts[cid]}.")

    # All sessions of a course share its scheduled slots; if a student
    # enrolled in two courses, their slot sets must not overlap.
    student_courses = defaultdict(set)
    for choice in data.get("student_choices", []):
        student_courses[choice["student_id"]].update(choice["course_ids"])
    for student_id, selected in student_courses.items():
        for a, b in combinations(sorted(selected), 2):
            if slots_by_course[a] & slots_by_course[b]:
                issues.append(f"Student {student_id}: {a} clashes with {b}.")
    return issues
