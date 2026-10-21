"""Specific infeasibility reasons (SRS REQ-2.7).

Two layers:
  1. ``room_capacity_reasons`` - instant analytic check (no solver needed).
  2. ``diagnose_infeasibility`` - when CP-SAT proves the model INFEASIBLE, find a
     MINIMAL set of conflicting rules by relaxing them and re-solving
     (deletion filter with chunking). Every rule in the returned set is
     necessary: relaxing any one of them makes a timetable possible.

The solver supplies a ``probe(enforced_items) -> "FEASIBLE"|"INFEASIBLE"|"UNKNOWN"``
function, so this module itself never imports OR-Tools.

Item kinds:  ("student", (course ids...))   students who take these together
             ("faculty_no", faculty_id)     that faculty's NO (unavailable) slots
             ("breaks",)  ("rooms",)  ("sections",)
"""
import time
from collections import defaultdict

try:
    from .constraints import candidate_rooms_for
except ImportError:  # direct execution / plain unittest
    from constraints import candidate_rooms_for


def _teaching_slot_count(data):
    breaks = {(b["day"], b["period"]) for b in data["slots"].get("breaks", [])}
    total = len(data["slots"]["days"]) * len(data["slots"]["periods"])
    return total - len(breaks)


def room_capacity_reasons(data):
    """Hall-type check: courses that can only use room set S need <= |S| * slots."""
    candidates = candidate_rooms_for(data)
    n_slots = _teaching_slot_count(data)
    rooms = data["rooms"]
    sets = {frozenset(v) for v in candidates.values() if v}
    reasons = []
    for room_set in sorted(sets, key=lambda s: (len(s), sorted(s))):
        members = [c for c in data["courses"] if frozenset(candidates[c["id"]]) <= room_set]
        need = sum(c["hours_per_week"] for c in members)
        have = len(room_set) * n_slots
        if need > have:
            room_ids = ", ".join(rooms[i]["id"] for i in sorted(room_set))
            names = ", ".join(c["name"] for c in members)
            reasons.append(
                f"Rooms [{room_ids}] offer only {have} room-periods per week, but the "
                f"courses that can use only these rooms ({names}) need {need}."
            )
    return reasons


def collect_items(data):
    """All relaxable rules for this input (student groups, faculty NO, ...)."""
    items = []
    groups = set()
    student_courses = defaultdict(set)
    for choice in data.get("student_choices", []):
        student_courses[choice["student_id"]].update(choice["course_ids"])
    for selected in student_courses.values():
        if len(selected) >= 2:
            groups.add(tuple(sorted(selected)))
    items.extend(("student", g) for g in sorted(groups))
    for member in data["faculty"]:
        if any(p["level"] == "NO" for p in member.get("preferences", [])):
            items.append(("faculty_no", member["id"]))
    if data["slots"].get("breaks"):
        items.append(("breaks",))
    if any(c.get("section_id") for c in data["courses"]):
        items.append(("sections",))
    items.append(("rooms",))
    return items


def relaxation_from_enforced(data, enforced):
    """Translate 'which items stay enforced' into solver build options."""
    all_items = collect_items(data)
    relax = set()
    for kind in ("breaks", "sections", "rooms"):
        if (kind,) in all_items and (kind,) not in enforced:
            relax.add(kind)
    drop_groups = {frozenset(i[1]) for i in all_items if i[0] == "student" and i not in enforced}
    drop_faculty = {i[1] for i in all_items if i[0] == "faculty_no" and i not in enforced}
    return frozenset(relax), frozenset(drop_groups), frozenset(drop_faculty)


def minimal_conflict(items, probe, out_of_time):
    """Deletion filter with chunking. Returns (core, complete)."""
    core = list(items)
    chunk = max(1, len(core) // 2)
    while True:
        i = 0
        while i < len(core):
            if out_of_time():
                return core, False
            trial = core[:i] + core[i + chunk:]
            if probe(frozenset(trial)) == "INFEASIBLE":
                core = trial          # this chunk is not needed for the conflict
            else:
                i += chunk            # needed (or inconclusive): keep it
        if chunk == 1:
            return core, True
        chunk = max(1, chunk // 2)


def _describe(item, data):
    courses = {c["id"]: c for c in data["courses"]}
    faculty = {f["id"]: f for f in data["faculty"]}
    kind = item[0]
    if kind == "student":
        names = ", ".join(courses[c]["name"] for c in item[1])
        return (f"Students who take [{names}] together: these courses cannot all be "
                "placed in different time slots.")
    if kind == "faculty_no":
        fid = item[1]
        return (f"Faculty {faculty[fid].get('name') or fid} ({fid}) is marked unavailable (NO) "
                "in too many slots for the courses assigned.")
    if kind == "breaks":
        return "The break periods remove teaching slots that the other rules need."
    if kind == "sections":
        return "Section rule: a section cannot attend two classes at the same time."
    return "Room capacity / lab-room requirements leave too few usable rooms."


def diagnose_infeasibility(data, probe, *, time_budget=30.0):
    """Return a list of human-readable reasons (empty list if nothing found)."""
    deadline = time.monotonic() + time_budget

    def out_of_time():
        return time.monotonic() > deadline

    items = collect_items(data)
    everything_relaxed = probe(frozenset())
    if everything_relaxed == "INFEASIBLE":
        return [
            "Infeasible even after ignoring breaks, faculty unavailability, room capacity and "
            "student clashes: the basic load is too tight. Check total teaching hours per "
            "faculty and per room against the available slots, and lab_block_size values."
        ]
    if everything_relaxed != "FEASIBLE":
        return ["Could not analyse the conflict within the time budget; increase "
                "diagnose_time_seconds."]

    core, complete = minimal_conflict(items, probe, out_of_time)
    header = ("Conflict found. Relaxing ANY ONE of these rules makes a timetable possible:"
              if complete else
              "Conflict found (analysis hit its time budget, so the list may contain extra rules):")
    return [header] + [f"- {_describe(item, data)}" for item in core]