"""Multi-term dummy history generator (only ONE real term exists today).

Produces the two tables the models learn from:

  demand_history : one row per (course, term)
      course_id, term_index, term_name, is_elective, hours_per_week,
      requires_lab, enrolled, cohort_size, semester_type (0 odd / 1 even)
  faculty_history: one row per (faculty, term)
      faculty_id, term_index, weekly_hours, max_hours, n_courses, n_students,
      n_lab_courses, restricted_slots, total_slots, risk   (LOW/MEDIUM/HIGH)

The generator is deterministic for a given seed, so tests are repeatable.
"""
import math
import random

import pandas as pd


def make_demand_history(courses, n_terms=8, seed=42):
    """Fake past enrollments for the given courses (list of solver course dicts).

    Each course gets a hidden "popularity" + slow trend + yearly (odd/even
    semester) seasonality + noise. Electives are more volatile than core.
    """
    rng = random.Random(seed)
    rows = []
    for c in courses:
        base = max(8, c.get("expected_students", 30))
        is_elective = int(c.get("type", "elective") == "elective"
                          or c.get("is_elective", False))
        popularity = rng.uniform(0.6, 1.5) if is_elective else rng.uniform(0.95, 1.05)
        trend = rng.uniform(-0.04, 0.07) if is_elective else rng.uniform(-0.01, 0.015)
        season = rng.uniform(-0.15, 0.15) if is_elective else 0.0
        noise = 0.12 if is_elective else 0.04
        cohort = int(base / popularity * 1.4)
        for t in range(n_terms):
            sem_type = t % 2
            level = base * popularity * (1 + trend) ** t
            level *= 1 + (season if sem_type else -season)
            level *= 1 + rng.gauss(0, noise)
            enrolled = max(5, int(round(level)))
            rows.append({
                "course_id": str(c["id"]), "term_index": t, "term_name": f"T{t + 1}",
                "is_elective": is_elective,
                "hours_per_week": c.get("hours_per_week", 3),
                "requires_lab": int(bool(c.get("requires_lab", False))),
                "enrolled": enrolled, "cohort_size": max(cohort, enrolled),
                "semester_type": sem_type,
            })
    return pd.DataFrame(rows)


def risk_score(weekly_hours, max_hours, n_courses, n_students, n_labs,
               restricted_slots, total_slots):
    """Transparent workload score in [0, 1+]. Used for labels AND explanations.

    utilisation (hours / max hours)      45 %
    teaching volume (students taught)    20 %
    course diversity (preparations)      15 %
    lab burden                           10 %
    availability squeeze (NO/AVOID cells) 10 %
    """
    util = weekly_hours / max(1, max_hours)
    volume = min(1.5, n_students / 200.0)
    diversity = min(1.5, n_courses / 5.0)
    lab = min(1.5, n_labs / 3.0)
    squeeze = restricted_slots / max(1, total_slots)
    return (0.45 * util + 0.20 * volume + 0.15 * diversity
            + 0.10 * lab + 0.10 * squeeze * 2)


def score_to_label(score):
    if score < 0.45:
        return "LOW"
    if score < 0.70:
        return "MEDIUM"
    return "HIGH"


def make_faculty_history(n_faculty=60, n_terms=6, seed=42, total_slots=40):
    """Fake (faculty, term) workload rows with labels from risk_score + noise.

    Noise is added to the score before labelling so the classifier has to
    LEARN a smooth boundary instead of memorising the formula.
    """
    rng = random.Random(seed)
    rows = []
    for f in range(n_faculty):
        max_hours = rng.choice([12, 14, 16, 18, 20])
        habit = rng.uniform(0.4, 1.1)          # how loaded this person usually is
        for t in range(n_terms):
            weekly = max(2, int(round(max_hours * habit * rng.uniform(0.8, 1.15))))
            n_courses = max(1, min(7, int(round(weekly / rng.uniform(2.5, 4.5)))))
            n_labs = rng.randint(0, min(n_courses, 3))
            n_students = int(sum(rng.randint(20, 70) for _ in range(n_courses)))
            restricted = rng.randint(0, 14)
            score = risk_score(weekly, max_hours, n_courses, n_students, n_labs,
                               restricted, total_slots)
            score += rng.gauss(0, 0.05)
            rows.append({
                "faculty_id": f"F{f}", "term_index": t, "weekly_hours": weekly,
                "max_hours": max_hours, "n_courses": n_courses,
                "n_students": n_students, "n_lab_courses": n_labs,
                "restricted_slots": restricted, "total_slots": total_slots,
                "risk": score_to_label(score),
            })
    return pd.DataFrame(rows)
