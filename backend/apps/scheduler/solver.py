"""Member 1 -- conflict-free timetable generator (v4).

Use from repository root (Windows PowerShell):
    .\\.venv\\Scripts\\python.exe backend\\apps\\scheduler\\solver.py

Input contract: contracts/scheduler_input_v1.schema.json
Output shape: contracts/sample_output.json (+ an additive "metrics" key on success)

v4 adds (all backward compatible):
  * REQ-2.5  student idle-gap minimisation and faculty load balancing
  * REQ-2.7  specific infeasibility reasons (analytic checks + minimal conflict set)
  * speed    two-stage solve (fast first solution, then optimise with a hint),
             0 = auto workers, optional symmetry breaking (off by default)
  * ML hook  ``ml_hints`` (see hints.py) for Member 2's predictions
"""
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from ortools.sat.python import cp_model

try:  # Allow both Django import and direct `python solver.py` execution.
    from .constraints import add_hard_constraints, candidate_rooms_for
    from .diagnostics import (diagnose_infeasibility, relaxation_from_enforced,
                              room_capacity_reasons)
    from .hints import (DEFAULT_RISK_MULTIPLIER, RISK_MULTIPLIER, apply_ml_hints,
                        validate_ml_hints)
    from .metrics import compute_metrics, teaching_positions
    from .validator import validate_timetable
except ImportError:
    from constraints import add_hard_constraints, candidate_rooms_for
    from diagnostics import (diagnose_infeasibility, relaxation_from_enforced,
                             room_capacity_reasons)
    from hints import (DEFAULT_RISK_MULTIPLIER, RISK_MULTIPLIER, apply_ml_hints,
                       validate_ml_hints)
    from metrics import compute_metrics, teaching_positions
    from validator import validate_timetable


def _response(status, timetable=None, reasons=None, metrics=None):
    result = {"status": status,
              "timetable": [] if timetable is None else timetable,
              "infeasibility_reasons": [] if reasons is None else reasons}
    if metrics is not None:
        result["metrics"] = metrics
    return result


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


class _Context:
    """Everything built for one CP-SAT model."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _build_context(data, *, relax=frozenset(), drop_student_groups=frozenset(),
                   drop_faculty_no=frozenset(), symmetry=False):
    """Build the hard-constraint model. ``relax``/``drop_*`` are used only by diagnostics."""
    courses = data["courses"]
    rooms = data["rooms"]
    days = data["slots"]["days"]
    periods = data["slots"]["periods"]
    breaks, preferences = _slot_policy(data)
    if "breaks" in relax:
        breaks = set()
    for fid in drop_faculty_no:
        preferences[fid] = {k: v for k, v in preferences[fid].items() if v != "NO"}
    candidate_rooms = candidate_rooms_for(data, ignore_capacity="rooms" in relax)

    # One CP-SAT decision represents ONE indivisible session/block. The
    # output is expanded into one timetable row for every occupied period.
    sessions, durations = [], []
    for course_index, course in enumerate(courses):
        duration = course.get("lab_block_size", 1)
        for _ in range(course["hours_per_week"] // duration):
            sessions.append(course_index)
            durations.append(duration)

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
    student_sets = [selected for selected in student_courses.values()
                    if frozenset(selected) not in drop_student_groups]
    idx = add_hard_constraints(model, variables, sessions, courses,
                               data["faculty"], rooms, days, periods,
                               student_sets, durations=durations,
                               skip_sections="sections" in relax)

    # OPTIONAL symmetry breaking (symmetry_breaking=True): sessions of the same
    # course are interchangeable, so force them into increasing time order. No
    # solution is lost, but it adds large linear constraints and was NOT shown to
    # help on real runs, so it is off by default. Measure with benchmark.py first.
    if symmetry:
        start_terms = defaultdict(list)
        for (s, d, p, r), var in variables.items():
            start_terms[s].append((d * len(periods) + p) * var)
        for s in range(len(sessions) - 1):
            if sessions[s] == sessions[s + 1] and durations[s] == durations[s + 1]:
                model.Add(sum(start_terms[s]) < sum(start_terms[s + 1]))

    return _Context(model=model, variables=variables, sessions=sessions,
                    durations=durations, courses=courses, rooms=rooms, days=days,
                    periods=periods, breaks=breaks, preferences=preferences,
                    student_sets=student_sets, idx=idx)


def _idle_gap_terms(ctx, data, weight, max_groups):
    """Penalty for idle periods inside a student's day (breaks are not gaps)."""
    model, by_cp = ctx.model, ctx.idx["by_course_period"]
    position = teaching_positions(data)
    n_periods = len(ctx.periods)
    groups = Counter(frozenset(selected) for selected in ctx.student_sets if len(selected) >= 2)
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1], sorted(kv[0])))[:max_groups]
    terms = []
    for g_i, (group, count) in enumerate(ranked):
        group_weight = weight * min(count, 5)
        for d, day in enumerate(ctx.days):
            occupied = []  # (position among teaching periods, 0/1 occupancy var)
            for p, period in enumerate(ctx.periods):
                pos = position.get((day, period))
                if pos is None:
                    continue
                literals = [v for cid in group for v in by_cp.get((cid, d, p), ())]
                if not literals:
                    continue
                occ = model.NewBoolVar(f"occ_g{g_i}_d{d}_p{p}")
                model.Add(occ == sum(literals))  # student clash rules keep this <= 1
                occupied.append((pos, occ))
            if len(occupied) < 2:
                continue
            first = model.NewIntVar(0, n_periods, f"first_g{g_i}_d{d}")
            last = model.NewIntVar(0, n_periods, f"last_g{g_i}_d{d}")
            idle = model.NewIntVar(0, n_periods, f"idle_g{g_i}_d{d}")
            for pos, occ in occupied:
                model.Add(first <= pos).OnlyEnforceIf(occ)
                model.Add(last >= pos).OnlyEnforceIf(occ)
            # idle = (span of the day) - (periods actually attended)
            model.Add(idle >= last - first + 1 - sum(occ for _, occ in occupied))
            terms.append(group_weight * idle)
    return terms


def _balance_terms(ctx, weights, risk):
    """Penalty for a faculty teaching more than an even daily share."""
    model, by_faculty = ctx.model, ctx.idx["by_faculty_slot"]
    weekly = Counter()
    for course in ctx.courses:
        weekly[course["faculty_id"]] += course["hours_per_week"]
    n_periods = len(ctx.periods)
    terms = []
    for fid, total in sorted(weekly.items()):
        cap = math.ceil(total / len(ctx.days))
        multiplier = RISK_MULTIPLIER.get(risk.get(fid), DEFAULT_RISK_MULTIPLIER)
        for d in range(len(ctx.days)):
            literals = [v for p in range(n_periods) for v in by_faculty.get((fid, d, p), ())]
            if len(literals) <= cap:
                continue
            over = model.NewIntVar(0, n_periods, f"over_{fid}_d{d}")
            model.Add(over >= sum(literals) - cap)
            terms.append(weights["faculty_balance"] * multiplier * over)
    return terms


def _add_soft_objective(ctx, data, weights, risk, max_gap_groups):
    """Build every soft term. Called AFTER the first (hard-only) solution is found."""
    model, courses = ctx.model, ctx.courses
    days, periods = ctx.days, ctx.periods
    sessions, durations, preferences = ctx.sessions, ctx.durations, ctx.preferences
    terms = []

    # Discourage a theory course repeatedly on the same day.
    by_course_day = defaultdict(list)
    for (session_idx, day_idx, period_idx, room_idx), variable in ctx.variables.items():
        by_course_day[(sessions[session_idx], day_idx)].append(variable)
    for course_index, course in enumerate(courses):
        if course.get("requires_lab", False) or course["hours_per_week"] <= 1:
            continue
        for d in range(len(days)):
            selected = by_course_day.get((course_index, d), [])
            if selected:
                excess = model.NewIntVar(0, course["hours_per_week"] - 1,
                                         f"repeat_course{course_index}_day{d}")
                model.Add(excess >= sum(selected) - 1)
                terms.append(weights["repeat_day"] * excess)

    # Faculty AVOID (penalty) and PREFER (reward).
    for (s, d, p, r), var in ctx.variables.items():
        fid = courses[sessions[s]]["faculty_id"]
        for offset in range(durations[s]):
            level = preferences[fid].get((days[d], periods[p + offset]))
            if level == "AVOID":
                terms.append(weights["avoid"] * var)
            elif level == "PREFER":
                terms.append(-weights["prefer"] * var)

    terms.extend(_idle_gap_terms(ctx, data, weights["idle_gap"], max_gap_groups))
    terms.extend(_balance_terms(ctx, weights, risk))
    return terms


def _extract_timetable(solver, ctx):
    timetable = []
    for (s, d, p, r), decision in ctx.variables.items():
        if solver.Value(decision):
            c = ctx.courses[ctx.sessions[s]]
            for offset in range(ctx.durations[s]):
                timetable.append({"course_id": c["id"],
                                  "faculty_id": c["faculty_id"],
                                  "room_id": ctx.rooms[r]["id"],
                                  "day": ctx.days[d], "period": ctx.periods[p + offset]})
    day_idx = {d: i for i, d in enumerate(ctx.days)}
    period_idx = {p: i for i, p in enumerate(ctx.periods)}
    timetable.sort(key=lambda e: (day_idx[e["day"]], period_idx[e["period"]], e["course_id"]))
    return timetable


def _make_probe(data, seconds, workers):
    """Feasibility probe used by diagnostics: solve with only some rules enforced."""
    def probe(enforced):
        relax, drop_groups, drop_faculty = relaxation_from_enforced(data, enforced)
        ctx = _build_context(data, relax=relax, drop_student_groups=drop_groups,
                             drop_faculty_no=drop_faculty)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 7
        solver.parameters.stop_after_first_solution = True
        status = solver.Solve(ctx.model)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        return "UNKNOWN"
    return probe


def generate_timetable(
    data: dict,
    *,
    max_time_seconds: float = 10.0,
    num_search_workers: int = 1,
    ml_hints: dict = None,
    optimize: bool = True,
    diagnose: bool = True,
    max_gap_groups: int = 300,
    diagnose_time_seconds: float = 30.0,
    symmetry_breaking: bool = False,
    log_search: bool = False
) -> dict:
    """Generate a timetable preserving the v1/v2 flat output contract.

    Courses without lab_block_size use independent one-period sessions. For
    lab_block_size=k>1, hours_per_week/k indivisible k-period blocks are
    scheduled, while output still contains one row for each occupied period.

    num_search_workers: 1 = deterministic (tests), 0 = use every CPU core (production).
    optimize=False skips all soft goals and returns the first feasible timetable.
    ml_hints: optional Member 2 predictions, see hints.py.
    symmetry_breaking: experimental, off by default (see _build_context).
    log_search: print the CP-SAT search log (for diagnosing slow runs).
    On success the result also has "metrics" (idle gaps, faculty load, ...).
    """
    started = time.monotonic()
    issues = _validate_input(data)
    if issues:
        return _response("INVALID_INPUT", reasons=issues)
    issues = validate_ml_hints(data, ml_hints)
    if issues:
        return _response("INVALID_INPUT", reasons=issues)
    data, weights, risk = apply_ml_hints(data, ml_hints)

    if not data["courses"]:
        return _response("OPTIMAL")

    candidate_rooms = candidate_rooms_for(data)
    issues = _precheck(data, candidate_rooms) or room_capacity_reasons(data)
    if issues:
        return _response("INFEASIBLE", reasons=issues)

    # Stage 1: hard constraints only. With an objective to follow, stop at the
    # first solution so the user always gets a valid timetable quickly.
    ctx = _build_context(data, symmetry=symmetry_breaking)
    stage1 = cp_model.CpSolver()
    stage1.parameters.log_search_progress = bool(log_search)
    stage1.parameters.max_time_in_seconds = max_time_seconds
    stage1.parameters.num_search_workers = num_search_workers
    stage1.parameters.random_seed = 7
    stage1.parameters.stop_after_first_solution = bool(optimize)
    status = stage1.Solve(ctx.model)

    if status == cp_model.INFEASIBLE:
        reasons = []
        if diagnose:
            probe_seconds = min(5.0, max(1.0, max_time_seconds / 4))
            reasons = diagnose_infeasibility(
                data, _make_probe(data, probe_seconds, max(1, num_search_workers)),
                time_budget=diagnose_time_seconds)
        return _response("INFEASIBLE", reasons=reasons or
                         ["No schedule satisfies all supplied hard constraints."])
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _response(stage1.StatusName(status),
                         reasons=["Solver found no schedule within time limit or model was invalid."])

    solver, final_status, stages = stage1, stage1.StatusName(status), 1

    # Stage 2: add the soft goals, hint with the stage-1 solution and improve it.
    if optimize:
        terms = _add_soft_objective(ctx, data, weights, risk, max_gap_groups)
        remaining = max_time_seconds - stage1.WallTime()
        if not terms:
            final_status = "OPTIMAL"  # nothing to optimise
        elif remaining >= 0.5:
            ctx.model.Minimize(sum(terms))
            for variable in ctx.variables.values():
                ctx.model.AddHint(variable, stage1.Value(variable))
            stage2 = cp_model.CpSolver()
            stage2.parameters.max_time_in_seconds = remaining
            stage2.parameters.num_search_workers = num_search_workers
            stage2.parameters.random_seed = 7
            stage2.parameters.repair_hint = True
            stage2.parameters.log_search_progress = bool(log_search)
            status2 = stage2.Solve(ctx.model)
            if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                solver, final_status, stages = stage2, stage2.StatusName(status2), 2

    timetable = _extract_timetable(solver, ctx)
    issues = validate_timetable(data, timetable)
    if issues:
        return _response("MODEL_INVALID", reasons=["Output validation failed:"] + issues)
    metrics = compute_metrics(data, timetable)
    metrics["solve_seconds"] = round(time.monotonic() - started, 2)
    metrics["stages"] = stages
    return _response(final_status, timetable=timetable, metrics=metrics)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    primary = root / "contracts" / "scheduler_demo_input_v1.json"
    fallback = root / "contracts" / "sample_input.json"
    data = json.loads((primary if primary.exists() else fallback).read_text(encoding="utf-8"))
    print(json.dumps(generate_timetable(data), indent=2))