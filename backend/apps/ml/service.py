"""Django entry point for Member 3's API.  NOT covered by the automated tests
(needs your real database) -- test it with the steps in README.md, section 6.

    from apps.ml.service import generate_with_ml
    result = generate_with_ml(term_id=3, overrides={"faculty_risk": {"12": "LOW"}})
    result["ml_hints"]  -> show to admin (risk table, predicted demand, weights)
    result["result"]    -> normal solver output (status, timetable, metrics)
"""
from .config import DEMAND_MODEL_FILE, RISK_MODEL_FILE
from .db import load_demand_history_from_db
from .demand import DemandPredictor
from .history import make_faculty_history
from .pipeline import build_ml_hints, hints_for_solver
from .workload import WorkloadRiskModel


def _models(history):
    demand = (DemandPredictor.load() if DEMAND_MODEL_FILE.exists()
              else DemandPredictor().fit(history))
    risk = (WorkloadRiskModel.load() if RISK_MODEL_FILE.exists()
            else WorkloadRiskModel().fit(make_faculty_history()))
    return demand, risk


def generate_with_ml(term_id, *, overrides=None, course_ids=None,
                     max_time_seconds=30.0, num_search_workers=0, use_ml=True):
    from apps.scheduler.services import (build_solver_input_from_db,
                                         generate_timetable_for_term)
    if not use_ml:
        return {"ml_hints": None,
                "result": generate_timetable_for_term(
                    term_id, course_ids=course_ids, max_time_seconds=max_time_seconds,
                    num_search_workers=num_search_workers)}
    data = build_solver_input_from_db(term_id, course_ids=course_ids)
    history = load_demand_history_from_db(exclude_term_id=term_id)
    demand, risk = _models(history)
    hints = build_ml_hints(data, demand, risk, history, overrides=overrides)
    result = generate_timetable_for_term(
        term_id, course_ids=course_ids, max_time_seconds=max_time_seconds,
        num_search_workers=num_search_workers, ml_hints=hints_for_solver(hints))
    return {"ml_hints": hints, "result": result}
