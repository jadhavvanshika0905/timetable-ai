"""Command line: train / predict / demo.

From the folder that CONTAINS the `ml` and `scheduler` folders:
    python -m ml.cli train            # trains on dummy history, saves models
    python -m ml.cli demo             # end-to-end: ML -> hints -> solver, before/after
"""
import argparse
import json
import sys

from .pipeline import build_ml_hints, hints_for_solver, train_all


def _sample_data(n_courses, seed=1):
    try:
        from scheduler.benchmark import make_synthetic
    except ImportError:
        from apps.scheduler.benchmark import make_synthetic
    data = make_synthetic(n_courses=n_courses, seed=seed)
    n_fac = max(5, n_courses // 4)                       # fewer teachers -> uneven load
    data["faculty"] = data["faculty"][:n_fac]
    for i, c in enumerate(data["courses"]):
        # F0/F1 get double share so their workload is clearly higher
        pick = i % (n_fac + 2)
        c["faculty_id"] = data["faculty"][pick if pick < n_fac else pick - n_fac]["id"]
        c["type"] = "elective" if i % 3 == 0 else "major"
        # labs live in 40-seat rooms, theory in 60-seat rooms
        c["expected_students"] = (18 + (i * 7) % 18) if c["requires_lab"] else (20 + (i * 7) % 30)
    load = {}
    for c in data["courses"]:
        load[c["faculty_id"]] = load.get(c["faculty_id"], 0) + c["hours_per_week"]
    for i, f in enumerate(data["faculty"]):               # busy people have little head-room
        hours = load.get(f["id"], 0)
        f["max_hours_per_week"] = max(4, hours + 1) if i < 2 else max(8, int(hours * 1.8))
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ml")
    ap.add_argument("command", choices=["train", "demo"])
    ap.add_argument("--courses", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=15.0)
    args = ap.parse_args(argv)

    data = _sample_data(args.courses)
    demand, risk, history = train_all(data, save=(args.command == "train"))
    print("DEMAND model metrics :", json.dumps(demand.metrics_))
    print("RISK   model metrics :", json.dumps(risk.metrics_))
    if args.command == "train":
        print("Models saved to ml/models_store/")
        return 0

    from collections import Counter
    try:
        from scheduler.solver import generate_timetable
    except ImportError:
        from apps.scheduler.solver import generate_timetable
    hints = build_ml_hints(data, demand, risk, history)
    print("\nFaculty risk counts  :", dict(Counter(hints["faculty_risk"].values())))
    print("Courses with raised demand:", len(hints["predicted_demand"]))
    print("Weights suggested    :", hints["weights"])
    print("Clipped to room cap  :", hints["_notes"]["clipped_to_room_capacity"])
    base = generate_timetable(data, max_time_seconds=args.seconds, num_search_workers=1)
    with_ml = generate_timetable(data, max_time_seconds=args.seconds, num_search_workers=1,
                                 ml_hints=hints_for_solver(hints))
    for name, res in (("WITHOUT ML", base), ("WITH ML   ", with_ml)):
        m = res.get("metrics", {})
        print(f"\n{name}: status={res['status']} rows={len(res['timetable'])}")
        print("  idle_gaps_total   :", m.get("student_idle_gaps_total"))
        print("  overload_periods  :", m.get("faculty_overload_periods"))
        print("  avoid_violations  :", m.get("avoid_violations"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
