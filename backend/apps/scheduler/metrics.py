"""Quality metrics for a timetable (pure Python, no OR-Tools).

Used by tests, by the API (to show admins how good a timetable is) and by the
benchmark. Break periods are NOT counted as idle gaps: a student with classes
before and after a lunch break has no idle gap.
"""
import math
from collections import Counter, defaultdict


def teaching_positions(data):
    """(day, period) -> index among that day's non-break periods."""
    breaks = {(b["day"], b["period"]) for b in data["slots"].get("breaks", [])}
    positions = {}
    for day in data["slots"]["days"]:
        n = 0
        for period in data["slots"]["periods"]:
            if (day, period) in breaks:
                continue
            positions[(day, period)] = n
            n += 1
    return positions


def compute_metrics(data, timetable):
    positions = teaching_positions(data)
    slots_by_course = defaultdict(set)
    for entry in timetable:
        slots_by_course[entry["course_id"]].add((entry["day"], entry["period"]))

    student_courses = defaultdict(set)
    for choice in data.get("student_choices", []):
        student_courses[choice["student_id"]].update(choice["course_ids"])

    gaps_total = gaps_max = students_with_gaps = 0
    for selected in student_courses.values():
        occupied = set()
        for cid in selected:
            occupied |= slots_by_course[cid]
        by_day = defaultdict(list)
        for day, period in occupied:
            if (day, period) in positions:
                by_day[day].append(positions[(day, period)])
        gaps = sum(max(ps) - min(ps) + 1 - len(ps) for ps in by_day.values())
        gaps_total += gaps
        gaps_max = max(gaps_max, gaps)
        students_with_gaps += 1 if gaps else 0

    courses = {c["id"]: c for c in data["courses"]}
    weekly_load = Counter()
    for course in courses.values():
        weekly_load[course["faculty_id"]] += course["hours_per_week"]
    daily = Counter()
    for entry in timetable:
        daily[(entry["faculty_id"], entry["day"])] += 1
    n_days = max(1, len(data["slots"]["days"]))
    max_daily, overload = {}, 0
    for fid, total in weekly_load.items():
        cap = math.ceil(total / n_days)
        loads = [daily[(fid, day)] for day in data["slots"]["days"]]
        max_daily[fid] = max(loads) if loads else 0
        overload += sum(max(0, load - cap) for load in loads)

    levels = {f["id"]: {(p["day"], p["period"]): p["level"] for p in f.get("preferences", [])}
              for f in data["faculty"]}
    avoid = prefer = 0
    for entry in timetable:
        level = levels.get(entry["faculty_id"], {}).get((entry["day"], entry["period"]))
        avoid += level == "AVOID"
        prefer += level == "PREFER"

    return {
        "student_idle_gaps_total": gaps_total,
        "student_idle_gaps_max": gaps_max,
        "students_with_gaps": students_with_gaps,
        "faculty_max_daily_load": max_daily,
        "faculty_overload_periods": overload,
        "avoid_violations": avoid,
        "prefer_hits": prefer,
    }