"""Synthetic college generator + speed benchmark (SRS target: 100 courses < 60 s).

Run from this folder:
    python benchmark.py                    # 100 courses, 30 s budget
    python benchmark.py 30 30              # 30 courses, 30 s budget
    python benchmark.py 30 30 --workers 8  # fixed number of CPU workers (0 = auto)
    python benchmark.py 30 30 --symmetry   # experimental symmetry breaking
    python benchmark.py 30 30 --log        # print the CP-SAT search log
"""
import argparse
import random
import time

try:
    from .solver import generate_timetable
    from .validator import validate_timetable
except ImportError:
    from solver import generate_timetable
    from validator import validate_timetable


def make_synthetic(n_courses=100, n_cohorts=12, students_per_cohort=25, seed=1):
    """A feasible-by-construction-ish college: cohorts share a fixed course set."""
    rng = random.Random(seed)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    periods = list(range(1, 9))
    breaks = [{"day": d, "period": 4} for d in days]          # lunch
    n_theory = round(n_courses * 0.6)
    n_faculty = max(10, n_courses * 2 // 5)

    faculty = [{"id": f"F{i}", "name": f"Faculty {i}", "preferences": []}
               for i in range(n_faculty)]
    for member in faculty:                                      # a few soft preferences
        for _ in range(3):
            slot = {"day": rng.choice(days), "period": rng.choice([1, 2, 7, 8]),
                    "level": rng.choice(["AVOID", "PREFER"])}
            if not any(p["day"] == slot["day"] and p["period"] == slot["period"]
                       for p in member["preferences"]):
                member["preferences"].append(slot)

    rooms = ([{"id": f"R{i}", "capacity": 60, "type": "classroom"} for i in range(12)]
             + [{"id": f"L{i}", "capacity": 40, "type": "lab"} for i in range(4)])

    courses = []
    for i in range(n_courses):
        is_lab = i >= n_theory
        courses.append({
            "id": f"C{i}", "name": f"Course {i}", "faculty_id": f"F{i % n_faculty}",
            "hours_per_week": 2 if is_lab else 3,
            "expected_students": students_per_cohort,
            "requires_lab": is_lab, "lab_block_size": 2 if is_lab else 1,
        })

    theory = [c["id"] for c in courses if not c["requires_lab"]]
    labs = [c["id"] for c in courses if c["requires_lab"]]
    choices, sid = [], 0
    for cohort in range(n_cohorts):
        base = set(theory[cohort::n_cohorts][:5]) | set(labs[cohort::n_cohorts][:3])
        for _ in range(students_per_cohort):
            choices.append({"student_id": f"S{sid}", "course_ids": sorted(base)})
            sid += 1
    return {"slots": {"days": days, "periods": periods, "breaks": breaks},
            "faculty": faculty, "rooms": rooms, "courses": courses,
            "student_choices": choices}


def run(n_courses=100, seconds=30.0, workers=0, **options):
    data = make_synthetic(n_courses)
    started = time.monotonic()
    result = generate_timetable(data, max_time_seconds=seconds, num_search_workers=workers,
                                **options)
    elapsed = time.monotonic() - started
    problems = validate_timetable(data, result["timetable"]) if result["timetable"] else []
    return data, result, elapsed, problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("courses", nargs="?", type=int, default=100)
    parser.add_argument("seconds", nargs="?", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--symmetry", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args()
    n, budget = args.courses, args.seconds
    _, outcome, took, problems = run(n, budget, args.workers,
                                     symmetry_breaking=args.symmetry, log_search=args.log)
    print(f"courses={n} status={outcome['status']} time={took:.1f}s "
          f"rows={len(outcome['timetable'])} validator_issues={len(problems)}")
    print("metrics:", outcome.get("metrics"))
    for reason in outcome["infeasibility_reasons"][:10]:
        print("reason:", reason)