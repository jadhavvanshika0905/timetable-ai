"""CP-SAT hard constraints for the scheduling input contract v1.

A single solver variable may occupy multiple consecutive periods (v3).
Breaks and faculty NO availability are filtered before variable creation.
"""
from collections import defaultdict
from itertools import combinations


def add_hard_constraints(model, variables, sessions, courses, faculty, rooms, days, periods,
                         student_courses, durations=None):
    """Add exact assignment, resource and student/section non-overlap rules.

    variables: dict[(session_idx, day_idx, period_idx, room_idx)] -> BoolVar
    sessions: list of course indices (one per independent session/block)
    durations: each session's consecutive period count (default: 1)
    student_courses: iterable of sets containing course IDs for each student
    """
    if durations is None:
        durations = [1] * len(sessions)
    if len(durations) != len(sessions):
        raise ValueError("durations must match the number of sessions")
    by_session = defaultdict(list)
    by_room_slot = defaultdict(list)
    by_faculty_slot = defaultdict(list)
    by_course_slot = defaultdict(list)
    by_section_slot = defaultdict(list)
    by_course_period = defaultdict(list)

    for (s, d, p, r), var in variables.items():
        course = courses[sessions[s]]
        course_id = course["id"]
        by_session[s].append(var)
        # Add the same start decision to every occupied period. That makes
        # faculty, room, course, section and student clashes impossible even
        # in the MIDDLE of a lab block.
        for offset in range(durations[s]):
            occupied_p = p + offset
            by_room_slot[(r, d, occupied_p)].append(var)
            by_faculty_slot[(course["faculty_id"], d, occupied_p)].append(var)
            by_course_slot[(course_id, d, occupied_p)].append(var)
            by_course_period[(course_id, d, occupied_p)].append(var)
            if course.get("section_id"):
                by_section_slot[(course["section_id"], d, occupied_p)].append(var)

    for s in range(len(sessions)):
        model.AddExactlyOne(by_session[s])

    for index in (by_room_slot, by_faculty_slot, by_course_slot, by_section_slot):
        for group in index.values():
            if len(group) > 1:
                model.AddAtMostOne(group)

    # Compress repeated student choices into unique *pairs of courses*.
    # A student taking A and B forces A and B into different timeslots.
    pairs = set()
    for selected in student_courses:
        for a, b in combinations(sorted(selected), 2):
            pairs.add((a, b))
    for a, b in sorted(pairs):
        for d in range(len(days)):
            for p in range(len(periods)):
                conflict_vars = by_course_period.get((a, d, p), []) + by_course_period.get((b, d, p), [])
                if len(conflict_vars) > 1:
                    model.AddAtMostOne(conflict_vars)
