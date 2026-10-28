"""Django adapter (lazy imports; the rest of the ML package never needs Django).

Uses ONLY fields already used by scheduler/services.py:
  StudentCourseChoice(term_id, student_id, course_id)
  Course(id, hours_per_week, requires_lab, course_type)
Terms are ordered by AcademicTerm primary key (oldest = smallest pk). If your
AcademicTerm has a start-date field, change ``order_by`` below.
"""
import pandas as pd


def history_from_rows(choice_rows, course_rows, term_order):
    """Pure function (testable without Django).

    choice_rows : [{term_id, student_id, course_id}, ...]
    course_rows : [{id, hours_per_week, requires_lab, course_type}, ...]
    term_order  : [term_id oldest -> newest]
    """
    index = {t: i for i, t in enumerate(term_order)}
    meta = {str(c["id"]): c for c in course_rows}
    seen = {}
    for r in choice_rows:
        key = (str(r["course_id"]), r["term_id"])
        seen.setdefault(key, set()).add(str(r["student_id"]))
    rows = []
    for (cid, term), students in seen.items():
        if cid not in meta or term not in index:
            continue
        m = meta[cid]
        rows.append({
            "course_id": cid, "term_index": index[term], "term_name": str(term),
            "is_elective": int(str(m.get("course_type", "")).lower() == "elective"),
            "hours_per_week": m["hours_per_week"],
            "requires_lab": int(bool(m.get("requires_lab"))),
            "enrolled": len(students), "cohort_size": len(students),
            "semester_type": index[term] % 2,
        })
    return pd.DataFrame(rows)


def load_demand_history_from_db(exclude_term_id=None):
    from apps.institution.models import AcademicTerm, Course, StudentCourseChoice
    terms = list(AcademicTerm.objects.order_by("pk").values_list("pk", flat=True))
    if exclude_term_id is not None:                       # the term being scheduled
        terms = [t for t in terms if t != exclude_term_id]
    choices = StudentCourseChoice.objects.filter(term_id__in=terms).values(
        "term_id", "student_id", "course_id")
    courses = Course.objects.values("id", "hours_per_week", "requires_lab", "course_type")
    return history_from_rows(list(choices), list(courses), terms)
