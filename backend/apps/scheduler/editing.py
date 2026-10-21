"""Manual timetable edits (drag-and-drop) checked by validator.py.

Pure Python: no Django, no OR-Tools. Member 3's API calls ``move_session`` before
saving, and ``valid_move_targets`` to highlight the cells where a class may be dropped.

A "session" is one class period, or a whole lab block (lab_block_size periods)
when the course has one: dragging any period of a lab block moves the entire block.
Only problems INTRODUCED by the move are reported, so a timetable that already
had an issue is not blocked from unrelated edits.
"""
import re
from collections import Counter

try:
    from .validator import validate_timetable
except ImportError:  # direct execution / plain unittest
    from validator import validate_timetable

_ENTRY_PREFIX = re.compile(r"^Entry \d+: ")


def _normalize(issue):
    return _ENTRY_PREFIX.sub("", issue)


def _issue_counter(data, timetable):
    return Counter(_normalize(i) for i in validate_timetable(data, timetable))


def _sorted(data, timetable):
    day_idx = {d: i for i, d in enumerate(data["slots"]["days"])}
    period_idx = {p: i for i, p in enumerate(data["slots"]["periods"])}
    # A moved block may run past the last period; sort such rows last so the
    # validator (not a KeyError) reports "unknown period".
    return sorted(timetable, key=lambda e: (day_idx.get(e["day"], len(day_idx)),
                                            period_idx.get(e["period"], len(period_idx) + e["period"]),
                                            e["course_id"]))


def _find_block(data, timetable, course_id, day, period):
    """Return (rows_of_the_session, error_message)."""
    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if course is None:
        return None, f"Unknown course {course_id}."
    size = course.get("lab_block_size", 1)
    rows = [e for e in timetable if e["course_id"] == course_id and e["day"] == day]
    target = next((e for e in rows if e["period"] == period), None)
    if target is None:
        return None, f"Course {course_id} has no class on {day} period {period}."
    if size == 1:
        return [target], None
    by_period = {e["period"]: e for e in rows if e["room_id"] == target["room_id"]}
    start = period
    while start - 1 in by_period:
        start -= 1
    first = start + ((period - start) // size) * size
    block = [by_period.get(p) for p in range(first, first + size)]
    if any(row is None for row in block):
        return None, f"Lab block of {course_id} on {day} is incomplete in the current timetable."
    return block, None


def _evaluate(data, timetable, old_rows, new_rows, baseline):
    rest = [e for e in timetable if not any(e is row for row in old_rows)]
    candidate = _sorted(data, rest + new_rows)
    after = _issue_counter(data, candidate)
    introduced = sorted((after - baseline).elements())
    return introduced, candidate


def move_session(data, timetable, *, course_id, from_day, from_period,
                 to_day, to_period, to_room_id=None):
    """Try moving a class (or lab block) to another slot and/or room.

    Returns {"ok": bool, "issues": [str], "timetable": list, "moved": list}.
    ``timetable`` in the result is the NEW timetable when ok, else the original.
    """
    original = list(timetable)

    def failed(*messages):
        return {"ok": False, "issues": list(messages), "timetable": original, "moved": []}

    old_rows, error = _find_block(data, timetable, course_id, from_day, from_period)
    if error:
        return failed(error)
    if to_day not in data["slots"]["days"]:
        return failed(f"Unknown day {to_day}.")
    room_id = to_room_id or old_rows[0]["room_id"]
    if room_id not in {r["id"] for r in data["rooms"]}:
        return failed(f"Unknown room {room_id}.")

    first_old = min(row["period"] for row in old_rows)
    shift = to_period - first_old
    new_rows = [dict(row, day=to_day, period=row["period"] + shift, room_id=room_id)
                for row in sorted(old_rows, key=lambda r: r["period"])]
    if from_day == to_day and shift == 0 and room_id == old_rows[0]["room_id"]:
        return failed("The class is already in that slot and room.")

    baseline = _issue_counter(data, timetable)
    introduced, candidate = _evaluate(data, timetable, old_rows, new_rows, baseline)
    if introduced:
        return failed(*introduced)
    return {"ok": True, "issues": [], "timetable": candidate, "moved": new_rows}


def valid_move_targets(data, timetable, *, course_id, from_day, from_period):
    """All (day, period, room_id) where the class/block can be dropped without a new issue.

    ``period`` is the block's FIRST period for lab blocks, matching ``move_session``'s
    ``to_period``. Use it to highlight valid cells in the drag-and-drop UI.
    """
    old_rows, error = _find_block(data, timetable, course_id, from_day, from_period)
    if error:
        return []
    baseline = _issue_counter(data, timetable)
    first_old = min(row["period"] for row in old_rows)
    ordered = sorted(old_rows, key=lambda r: r["period"])
    targets = []
    for day in data["slots"]["days"]:
        for period in data["slots"]["periods"]:
            for room in data["rooms"]:
                if (day == from_day and period == first_old
                        and room["id"] == old_rows[0]["room_id"]):
                    continue
                shift = period - first_old
                new_rows = [dict(row, day=day, period=row["period"] + shift, room_id=room["id"])
                            for row in ordered]
                introduced, _ = _evaluate(data, timetable, old_rows, new_rows, baseline)
                if not introduced:
                    targets.append({"day": day, "period": period, "room_id": room["id"]})
    return targets