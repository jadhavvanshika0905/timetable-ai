"""PART 1 - OR-Tools CP-SAT solver. Input/Output: contracts/*.json ka format."""
from ortools.sat.python import cp_model


def generate_timetable(data: dict) -> dict:
    model = cp_model.CpModel()
    # TODO: variables x[course, day, period, room], hard + soft constraints
    # TODO: solver = cp_model.CpSolver(); status = solver.Solve(model)
    return {"status": "NOT_IMPLEMENTED", "timetable": [], "infeasibility_reasons": []}
