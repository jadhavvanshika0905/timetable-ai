"""Member 1 -- conflict-free timetable generator with consecutive practical blocks (v3).

Use from repository root (Windows PowerShell):
    .\\.venv\\Scripts\\python.exe backend\\apps\\scheduler\\solver.py

Input contract: contracts/scheduler_input_v1.schema.json
Output shape: contracts/sample_output.json
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from ortools.sat.python import cp_model

try:  # Allow both Django import and direct `python solver.py` execution.
    from .constraints import add_hard_constraints
    from .validator import validate_timetable
except ImportError:
    from constraints import add_hard_constraints
    from validator import validate_timetable


def _response(status, timetable=None, reasons=None):
    return {"status": status,
            "timetable": [] if timetable is None else timetable,
            "infeasibility_reasons": [] if reasons is None else reasons}


def _ids_valid(items):
    ids = [item.get("id") for item in items]
    return (all(isinstance(x, str) and bool(x.strip()) for x in ids)
            and len(set(ids)) == len(ids))


def _slot_policy(data):
    """Breaks and faculty preferences as indexed (day, period) pairs."""
    breaks = {(entry["day"], entry["period"]) for entry in data["slots"].get("breaks", [])}
    preferences = {}
    for member in data["faculty"]:
        preferences[member["id"]] = {
            (entry["day"], entry["period"]): entry["level"]
            for entry in member.get("preferences", [])
        }
    return breaks, preferences


def _validate_input(data):
    if not isinstance(data, dict):
        return ["Input must be a JSON object."]
    if not isinstance(data.get("slots"), dict):
        return ["slots must be an object."]
    days, periods = data["slots"].get("days"), data["slots"].get("periods")
    if not isinstance(days, list) or not days or not all(isinstance(d, str) and d.strip() for d in days) or len(set(days)) != len(days):
        return ["slots.days must be nonempty, unique day names."]
    if not isinstance(periods, list) or not periods or not all(type(p) is int and p > 0 for p in periods) or len(set(periods)) != len(periods):
        return ["slots.periods must be unique positive integers."]
    for name in ("faculty", "rooms", "courses", "student_choices"):
        if not isinstance(data.get(name, [] if name == "student_choices" else None), list):
            return [f"{name} must be a list."]
        if not all(isinstance(item, dict) for item in data.get(name, [])):
            return [f"Every {name} item must be an object."]
    for name in ("faculty", "rooms", "courses"):
        if not _ids_valid(data[name]):
            return [f"{name} IDs must be unique nonempty strings."]
    # Optional slot policies. All references must point to defined day/periods.
    valid_slots = {(day, period) for day in days for period in periods}
    def check_policy(entries, label, levels=None):
        if not isinstance(entries, list):
            return f"{label} must be a list."
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                return f"{label}: entries must be objects."
            day, period = entry.get("day"), entry.get("period")
            if not isinstance(day, str) or type(period) is not int:
                return f"{label}: day must be a string and period must be an integer."
            key = (day, period)
            if key not in valid_slots:
                return f"{label}: unknown day/period."
            if key in seen:
                return f"{label}: duplicate day/period."
            if levels is not None and (not isinstance(entry.get("level"), str)
                                       or entry["level"] not in levels):
                return f"{label}: level must be NO, AVOID or PREFER."
            seen.add(key)
        return None

    error = check_policy(data["slots"].get("breaks", []), "slots.breaks")
    if error:
        return [error]
    for member in data["faculty"]:
        error = check_policy(member.get("preferences", []),
                             f"Faculty {member['id']} preferences", {"NO", "AVOID", "PREFER"})
        if error:
            return [error]
    for member in data["faculty"]:
        limit = member.get("max_hours_per_week")

        if limit is not None and (
            type(limit) is not int or limit <= 0
        ):
            return [
                f"Faculty {member['id']}: "
                "max_hours_per_week must be a positive integer."
            ]
    faculty_ids = {f["id"] for f in data["faculty"]}
    course_ids = {c["id"] for c in data["courses"]}
    for room in data["rooms"]:
        if type(room.get("capacity")) is not int or room["capacity"] <= 0:
            return [f"Room {room['id']}: capacity must be positive integer."]
        if room.get("type") not in ("classroom", "lab", "seminar"):
            return [f"Room {room['id']}: type must be classroom/lab/seminar."]
    for course in data["courses"]:
        cid = course["id"]
        if course.get("faculty_id") not in faculty_ids:
            return [f"Course {cid}: faculty_id not found."]
        if type(course.get("hours_per_week")) is not int or course["hours_per_week"] <= 0:
            return [f"Course {cid}: hours_per_week must be positive integer."]
        if type(course.get("expected_students")) is not int or course["expected_students"] < 0:
            return [f"Course {cid}: expected_students must be a nonnegative integer."]
        if type(course.get("requires_lab", False)) is not bool:
            return [f"Course {cid}: requires_lab must be true/false."]
        block_size = course.get("lab_block_size", 1)
        if type(block_size) is not int or block_size < 1:
            return [f"Course {cid}: lab_block_size must be a positive integer."]
        if block_size > 1 and not course.get("requires_lab", False):
            return [f"Course {cid}: lab_block_size > 1 requires requires_lab=true."]
        if course["hours_per_week"] % block_size != 0:
            return [f"Course {cid}: hours_per_week must be divisible by lab_block_size."]
        if "section_id" in course and (not isinstance(course["section_id"], str) or not course["section_id"].strip()):
            return [f"Course {cid}: section_id must be a nonempty string when supplied."]
    for choice in data.get("student_choices", []):
        selected = choice.get("course_ids")
        if (not isinstance(choice.get("student_id"), str) or not choice["student_id"].strip()
                or not isinstance(selected, list) or any(not isinstance(cid, str) or cid not in course_ids for cid in selected)):
            return ["Student choices have invalid student_id or unknown course IDs."]
    return []


def _precheck(data, candidate_rooms):
    courses = data["courses"]
    days = data["slots"]["days"]
    periods = data["slots"]["periods"]
    breaks, preferences = _slot_policy(data)
    all_slots = {(day, period) for day in days for period in periods} - breaks
    n_slots = len(all_slots)
    n_rooms = len(data["rooms"])
    if not n_slots:
        return ["No teaching slots remain after excluding breaks."]
    for course in courses:
        if not candidate_rooms[course["id"]]:
            return [f"Course {course['id']}: no room meets capacity/lab requirement."]
        block_size = course.get("lab_block_size", 1)
        if block_size > 1:
            fid = course["faculty_id"]
            possible_starts = [
                (day, index)
                for day in days for index in range(len(periods) - block_size + 1)
                if all(
                    periods[index + offset] == periods[index] + offset
                    and (day, periods[index + offset]) in all_slots
                    and preferences[fid].get((day, periods[index + offset])) != "NO"
                    for offset in range(block_size)
                )
            ]
            if not possible_starts:
                return [f"Course {course['id']}: no {block_size}-period consecutive lab block "
                        "available without a break or faculty unavailability."]
        if course["hours_per_week"] > n_slots:
            return [f"Course {course['id']}: needs more distinct periods than exist outside breaks."]
        faculty_allowed = sum(preferences[course["faculty_id"]].get(slot) != "NO"
                              for slot in all_slots)
        if course["hours_per_week"] > faculty_allowed:
            return [f"Course {course['id']}: needs {course['hours_per_week']} sessions, "
                    f"but faculty {course['faculty_id']} has only {faculty_allowed} available slots."]
    if sum(c["hours_per_week"] for c in courses) > n_rooms * n_slots:
        return ["Total required sessions exceed room-time capacity."]
    load = Counter()
    sections = Counter()
    course_by_id = {c["id"]: c for c in courses}
    for course in courses:
        load[course["faculty_id"]] += course["hours_per_week"]
        if course.get("section_id"):
            sections[course["section_id"]] += course["hours_per_week"]
    faculty_limits = {
        f["id"]: f.get("max_hours_per_week")
        for f in data["faculty"]
    }
    for fid, count in load.items():
        limit = faculty_limits[fid]

        if limit is not None and count > limit:
            return [
                f"Faculty {fid}: {count} periods exceed "
                f"max_hours_per_week={limit}."
            ]

        allowed = sum(preferences[fid].get(slot) != "NO" for slot in all_slots)
        if count > allowed:
            return [
                f"Faculty {fid}: {count} periods required "
                f"but only {allowed} available."
            ]
    for section, count in sections.items():
        if count > n_slots:
            return [f"Section {section}: {count} periods required but only {n_slots} available."]
    student_courses = defaultdict(set)
    for choice in data.get("student_choices", []):
        student_courses[choice["student_id"]].update(choice["course_ids"])
    for student_id, selected in student_courses.items():
        total = sum(course_by_id[cid]["hours_per_week"] for cid in selected)
        if total > n_slots:
            return [f"Student {student_id}: {total} periods required but only {n_slots} available."]
    return []


def generate_timetable(data: dict) -> dict:
    """Generate a timetable preserving the v1/v2 flat output contract.

    Courses without lab_block_size use independent one-period sessions. For
    lab_block_size=k>1, hours_per_week/k indivisible k-period blocks are
    scheduled, while output still contains one row for each occupied period.
    """
    issues = _validate_input(data)
    if issues:
        return _response("INVALID_INPUT", reasons=issues)

    courses = data["courses"]
    rooms = data["rooms"]
    days = data["slots"]["days"]
    periods = data["slots"]["periods"]
    if not courses:
        return _response("OPTIMAL")

    candidate_rooms = {}
    for course in courses:
        candidate_rooms[course["id"]] = [r for r, room in enumerate(rooms)
            if room["capacity"] >= course["expected_students"]
            and (not course.get("requires_lab", False) or room["type"] == "lab")]
    issues = _precheck(data, candidate_rooms)
    if issues:
        return _response("INFEASIBLE", reasons=issues)

    # One CP-SAT decision represents ONE indivisible session/block. The
    # output is expanded into one timetable row for every occupied period.
    sessions, durations = [], []
    for course_index, course in enumerate(courses):
        duration = course.get("lab_block_size", 1)
        for _ in range(course["hours_per_week"] // duration):
            sessions.append(course_index)
            durations.append(duration)

    breaks, preferences = _slot_policy(data)
    model = cp_model.CpModel()
    variables = {}  # (session_index, day_index, START_period_index, room_index)
    for s, cidx in enumerate(sessions):
        cid = courses[cidx]["id"]
        duration = durations[s]
        faculty_id = courses[cidx]["faculty_id"]
        for d in range(len(days)):
            for p in range(len(periods) - duration + 1):
                # Period numbers must be numerically consecutive. A break or
                # unavailable faculty time anywhere in the block rules out it.
                window = [(days[d], periods[p + offset]) for offset in range(duration)]
                if any(periods[p + offset] != periods[p] + offset for offset in range(duration)):
                    continue
                if any(slot in breaks or preferences[faculty_id].get(slot) == "NO"
                       for slot in window):
                    continue
                for r in candidate_rooms[cid]:
                    variables[(s, d, p, r)] = model.NewBoolVar(f"s{s}_d{d}_p{p}_r{r}")

    student_courses = defaultdict(set)
    for choice in data.get("student_choices", []):
        student_courses[choice["student_id"]].update(choice["course_ids"])
    add_hard_constraints(model, variables, sessions, courses,
                         data["faculty"], rooms, days, periods,
                         student_courses.values(), durations=durations)

    # Soft constraints: discourage putting a theory course repeatedly on the
    # same day (weight 20); faculty AVOID (weight 6), PREFER (reward 3).
    # Blocks remain indivisible even when soft optimization is enabled.
    objective_terms = []
    by_course_day = defaultdict(list)
    for (session_idx, day_idx, period_idx, room_idx), variable in variables.items():
        by_course_day[(sessions[session_idx], day_idx)].append(variable)
    for course_index, course in enumerate(courses):
        if course.get("requires_lab", False):
            continue
        if course["hours_per_week"] <= 1:
            continue
        for d in range(len(days)):
            selected = by_course_day.get((course_index, d), [])
            if selected:
                excess = model.NewIntVar(0, course["hours_per_week"] - 1,
                                         f"repeat_course{course_index}_day{d}")
                model.Add(excess >= sum(selected) - 1)
                objective_terms.append(20 * excess)
    for (s, d, p, r), var in variables.items():
        fid = courses[sessions[s]]["faculty_id"]
        for offset in range(durations[s]):
            level = preferences[fid].get((days[d], periods[p + offset]))
            if level == "AVOID":
                objective_terms.append(6 * var)
            elif level == "PREFER":
                objective_terms.append(-3 * var)
    if objective_terms:
        model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 7
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        timetable = []
        for (s, d, p, r), decision in variables.items():
            if solver.Value(decision):
                c = courses[sessions[s]]
                for offset in range(durations[s]):
                    timetable.append({"course_id": c["id"],
                                      "faculty_id": c["faculty_id"],
                                      "room_id": rooms[r]["id"],
                                      "day": days[d], "period": periods[p + offset]})
        day_idx = {d: i for i, d in enumerate(days)}
        period_idx = {p: i for i, p in enumerate(periods)}
        timetable.sort(key=lambda e: (day_idx[e["day"]], period_idx[e["period"]], e["course_id"]))
        issues = validate_timetable(data, timetable)
        if issues:
            return _response("MODEL_INVALID", reasons=["Output validation failed:"] + issues)
        return _response(solver.StatusName(status), timetable=timetable)
    if status == cp_model.INFEASIBLE:
        return _response("INFEASIBLE", reasons=["No schedule satisfies all supplied hard constraints."])
    return _response(solver.StatusName(status), reasons=["Solver found no schedule within time limit or model was invalid."])


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    primary = root / "contracts" / "scheduler_demo_input_v1.json"
    fallback = root / "contracts" / "sample_input.json"
    data = json.loads((primary if primary.exists() else fallback).read_text(encoding="utf-8"))
    print(json.dumps(generate_timetable(data), indent=2))
