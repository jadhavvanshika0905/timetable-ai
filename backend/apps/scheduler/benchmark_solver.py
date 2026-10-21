#!/usr/bin/env python3
"""
Timetable solver benchmark harness.

  python benchmark_solver.py selftest                      # validator + generator sanity
  python benchmark_solver.py run --solver greedy           # built-in reference solver
  python benchmark_solver.py run --solver project --tiers S M L --seeds 5 --time-limit 60
  python benchmark_solver.py run --solver project --util 0.85   # tight instances
  python benchmark_solver.py inject --solver project       # infeasibility-diagnostics test
  python benchmark_solver.py run --solver project --compare results/prev.json   # regression gate

Neutral instance format (see generate()):
  days, periods, breaks[], rooms[{id,capacity,is_lab}], faculty[{id,avoid_periods[]}],
  groups[{id,size}], courses[{id,faculty,groups[],enrollment,lectures,lab_block}]
A lab course needs `lectures` 1-period sessions in normal rooms plus ONE lab_block-period
session (consecutive periods) in a lab room.

Solver contract:  solver(instance, time_limit_s, seed, mode) -> dict
  {"status": "feasible"|"optimal"|"infeasible"|"timeout"|"error",
   "schedule": [{"course","day","start","length","room","kind":"lec"|"lab"}],
   "reason": optional str}
"""
import argparse, json, os, random, statistics, sys, time
from collections import defaultdict

TIERS = {"S": 10, "M": 30, "L": 100, "XL": 300}
DAYS, PERIODS, BREAKS = 5, 8, [3]  # period index 3 = lunch


# ----------------------------------------------------------------- generator
def generate(n_courses, seed, util=0.55):
    rnd = random.Random(seed)
    n_groups = max(2, round(n_courses / 6))
    groups = [{"id": f"G{i+1}", "size": rnd.choice([30, 40, 48, 55, 60, 65])}
              for i in range(n_groups)]
    n_fac = max(3, round(n_courses / 2.2))
    faculty = [{"id": f"F{i+1}",
                "avoid_periods": rnd.sample([0, 1, 6, 7], rnd.choice([0, 1, 2]))}
               for i in range(n_fac)]
    load = {f["id"]: 0 for f in faculty}
    courses = []
    for i in range(n_courses):
        gs = [groups[i % n_groups]]
        if rnd.random() < 0.10 and n_groups > 1:  # shared elective
            other = rnd.choice([g for g in groups if g is not gs[0]])
            gs.append(other)
        has_lab = rnd.random() < 0.20
        lectures = 2 if has_lab else rnd.choice([3, 3, 4])
        lab_block = rnd.choice([2, 3]) if has_lab else 0
        hours = lectures + lab_block
        fid = min(load, key=lambda k: (load[k], rnd.random()))
        load[fid] += hours
        courses.append({"id": f"C{i+1}", "faculty": fid, "groups": [g["id"] for g in gs],
                        "enrollment": sum(g["size"] for g in gs),
                        "lectures": lectures, "lab_block": lab_block})
    slots = DAYS * (PERIODS - len(BREAKS))
    lec_h = sum(c["lectures"] for c in courses)
    lab_h = sum(c["lab_block"] for c in courses)
    max_enr = max(c["enrollment"] for c in courses)
    n_lec_rooms = max(2, -(-int(lec_h) // int(slots * util)))
    n_lab_rooms = max(1, -(-int(lab_h) // int(slots * util * 0.73))) if lab_h else 0
    rooms = []
    for i in range(n_lec_rooms):
        cap = rnd.choice([60, 70, 80, 130]) if i else max(130, max_enr)
        rooms.append({"id": f"R{i+1}", "capacity": cap, "is_lab": False})
    for i in range(n_lab_rooms):
        rooms.append({"id": f"L{i+1}", "capacity": max(70, max_enr), "is_lab": True})
    return {"days": DAYS, "periods": PERIODS, "breaks": BREAKS, "rooms": rooms,
            "faculty": faculty, "groups": groups, "courses": courses}


# ----------------------------------------------------------------- validator
def validate(inst, sched):
    """Independent hard-constraint checker + soft metrics. Never trusts the solver."""
    P, D, brk = inst["periods"], inst["days"], set(inst["breaks"])
    rooms = {r["id"]: r for r in inst["rooms"]}
    courses = {c["id"]: c for c in inst["courses"]}
    fac = {f["id"]: f for f in inst["faculty"]}
    viol, occ = defaultdict(int), {}
    got = defaultdict(lambda: {"lec": 0, "lab": 0})
    names = {"r": "room_clash", "f": "faculty_clash", "g": "student_clash"}
    gp, fp = defaultdict(set), defaultdict(set)
    pref = 0
    waste_num = waste_den = 0
    used_slots, fac_hours = set(), defaultdict(int)
    for a in sched:
        c, r = courses.get(a.get("course")), rooms.get(a.get("room"))
        if not c or not r:
            viol["unknown_id"] += 1
            continue
        d, s, l, k = a["day"], a["start"], a["length"], a["kind"]
        if not (0 <= d < D and s >= 0 and l >= 1 and s + l <= P):
            viol["out_of_range"] += 1
            continue
        if (k == "lec" and l != 1) or (k == "lab" and l != c["lab_block"]):
            viol["bad_length"] += 1
        if (k == "lab") != r["is_lab"]:
            viol["room_type"] += 1
        if r["capacity"] < c["enrollment"]:
            viol["capacity"] += 1
        got[c["id"]][k] += 1
        waste_num += (r["capacity"] - c["enrollment"]) * l
        waste_den += r["capacity"] * l
        for p in range(s, s + l):
            if p in brk:
                viol["break_class"] += 1
            if p in fac[c["faculty"]]["avoid_periods"]:
                pref += 1
            used_slots.add((r["id"], d, p))
            fac_hours[c["faculty"]] += 1
            res = [("r", r["id"]), ("f", c["faculty"])] + [("g", g) for g in c["groups"]]
            for kind, rid in res:
                key = (kind, rid, d, p)
                if key in occ:
                    viol[names[kind]] += 1
                occ[key] = c["id"]
                if kind == "g":
                    gp[(rid, d)].add(p)
                if kind == "f":
                    fp[(rid, d)].add(p)
    for c in courses.values():
        need_lab = 1 if c["lab_block"] else 0
        for kind, need in (("lec", c["lectures"]), ("lab", need_lab)):
            diff = got[c["id"]][kind] - need
            if diff < 0:
                viol["missing_session"] += -diff
            elif diff > 0:
                viol["extra_session"] += diff

    def gaps(table):
        total = 0
        for ps in table.values():
            lo, hi = min(ps), max(ps)
            total += sum(1 for p in range(lo, hi + 1) if p not in ps and p not in brk)
        return total
    hours = [fac_hours.get(f["id"], 0) for f in inst["faculty"]]
    cap_slots = len(inst["rooms"]) * D * (P - len(brk))
    soft = {"group_gaps": gaps(gp), "faculty_gaps": gaps(fp), "pref_violations": pref,
            "seat_waste": round(waste_num / waste_den, 3) if waste_den else 0,
            "room_util": round(len(used_slots) / cap_slots, 3) if cap_slots else 0,
            "load_stdev": round(statistics.pstdev(hours), 2) if hours else 0}
    soft["soft_score"] = soft["group_gaps"] + soft["faculty_gaps"] + 2 * pref
    return {"hard": dict(viol), "hard_total": sum(viol.values()), "soft": soft}


# ----------------------------------------------------------------- solvers
def greedy_solver(inst, time_limit, seed=0, mode="plain"):
    """Reference baseline: randomised greedy. Not a real optimiser."""
    rnd, t0 = random.Random(seed), time.time()
    P, D, brk = inst["periods"], inst["days"], set(inst["breaks"])
    rooms = sorted(inst["rooms"], key=lambda r: r["capacity"])
    busy, sched, unplaced = set(), [], 0
    sessions = []
    for c in inst["courses"]:
        sessions += [(c, "lec", 1)] * c["lectures"]
        if c["lab_block"]:
            sessions.append((c, "lab", c["lab_block"]))
    sessions.sort(key=lambda s: (-s[2], -len(s[0]["groups"]), -s[0]["enrollment"]))
    per_day = defaultdict(int)
    for c, kind, l in sessions:
        if time.time() - t0 > time_limit:
            return {"status": "timeout", "schedule": sched}
        cands = [(d, s) for d in range(D) for s in range(P - l + 1)
                 if not any(p in brk for p in range(s, s + l))]
        rnd.shuffle(cands)
        cands.sort(key=lambda x: per_day[(c["id"], x[0])])
        placed = False
        for d, s in cands:
            ps = range(s, s + l)
            keys = [("f", c["faculty"], d, p) for p in ps] + \
                   [("g", g, d, p) for g in c["groups"] for p in ps]
            if any(k in busy for k in keys):
                continue
            for r in rooms:
                if r["is_lab"] != (kind == "lab") or r["capacity"] < c["enrollment"]:
                    continue
                rk = [("r", r["id"], d, p) for p in ps]
                if any(k in busy for k in rk):
                    continue
                busy.update(keys + rk)
                sched.append({"course": c["id"], "day": d, "start": s, "length": l,
                              "room": r["id"], "kind": kind})
                per_day[(c["id"], d)] += 1
                placed = True
                break
            if placed:
                break
        unplaced += not placed
    return {"status": "feasible" if not unplaced else "infeasible", "schedule": sched,
            "reason": f"{unplaced} sessions unplaced" if unplaced else None}


def project_solver(inst, time_limit, seed=0, mode="plain"):
    """WIRE THIS UP to your real solver.

    1. Convert `inst` (neutral format above) into your solver's input
       (or load it into the test DB the way SchedulerDatabaseIntegrationTests does).
    2. Call your entry point with time_limit / seed / mode
       (mode: 'plain', 'optimised', 'ml' -> map to your settings).
    3. Convert the result into [{"course","day","start","length","room","kind"}].
    Return {"status":..., "schedule":..., "reason":...}.
    """
    raise NotImplementedError("Edit project_solver() in benchmark_solver.py")


SOLVERS = {"greedy": greedy_solver, "project": project_solver}


def call(solver, inst, tl, seed, mode):
    t = time.time()
    try:
        out = solver(inst, tl, seed, mode)
    except NotImplementedError:
        raise
    except Exception as e:  # solver crash is a result, not a harness failure
        out = {"status": "error", "schedule": [], "reason": repr(e)}
    return out, time.time() - t


# ----------------------------------------------------------------- run / aggregate
def aggregate(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[f'{r["tier"]}/{r["mode"]}'].append(r)
    agg = {}
    for k, rs in groups.items():
        ok = [r for r in rs if r["verified_feasible"]]
        agg[k] = {"runs": len(rs), "verified_rate": len(ok) / len(rs),
                  "median_time_s": round(statistics.median(r["time_s"] for r in rs), 2),
                  "mean_hard": round(statistics.mean(r["hard_total"] for r in rs), 2),
                  "mean_soft": round(statistics.mean(r["soft"]["soft_score"] for r in ok), 2) if ok else None,
                  "mean_seat_waste": round(statistics.mean(r["soft"]["seat_waste"] for r in ok), 3) if ok else None,
                  "soft_spread": round(statistics.pstdev([r["soft"]["soft_score"] for r in ok]), 2) if len(ok) > 1 else 0}
    return agg


def cmd_run(a):
    solver = SOLVERS[a.solver]
    rows = []
    for tier in a.tiers:
        for seed in range(a.seeds):
            inst = generate(TIERS[tier], seed, a.util)
            for mode in a.modes:
                out, dt = call(solver, inst, a.time_limit, seed, mode)
                v = validate(inst, out["schedule"])
                ok = out["status"] in ("feasible", "optimal") and v["hard_total"] == 0
                rows.append({"tier": tier, "seed": seed, "mode": mode, "status": out["status"],
                             "time_s": round(dt, 2), "hard": v["hard"], "hard_total": v["hard_total"],
                             "soft": v["soft"], "verified_feasible": ok})
                print(f"{tier} seed={seed} {mode:9s} {out['status']:10s} {dt:6.1f}s "
                      f"hard={v['hard_total']} soft={v['soft']['soft_score']}", flush=True)
    agg = aggregate(rows)
    print("\n| tier/mode | runs | verified | median s | hard | soft | seat waste | spread |")
    print("|---|---|---|---|---|---|---|---|")
    for k, g in agg.items():
        print(f"| {k} | {g['runs']} | {g['verified_rate']:.0%} | {g['median_time_s']} | "
              f"{g['mean_hard']} | {g['mean_soft']} | {g['mean_seat_waste']} | {g['soft_spread']} |")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"bench_{a.solver}_{int(time.time())}.json")
    json.dump({"args": {k: v for k, v in vars(a).items() if k != "fn"}, "rows": rows, "aggregate": agg}, open(path, "w"), indent=1)
    print("\nsaved", path)
    if a.compare:
        sys.exit(compare(agg, json.load(open(a.compare))["aggregate"]))


def compare(new, old, tol=0.10):
    bad = 0
    for k, o in old.items():
        n = new.get(k)
        if not n:
            continue
        if n["verified_rate"] < o["verified_rate"]:
            print(f"REGRESSION {k}: verified {o['verified_rate']:.0%} -> {n['verified_rate']:.0%}")
            bad = 1
        if o["mean_soft"] is not None and n["mean_soft"] is not None and \
                n["mean_soft"] > o["mean_soft"] * (1 + tol) + 1:
            print(f"REGRESSION {k}: soft {o['mean_soft']} -> {n['mean_soft']}")
            bad = 1
    print("compare:", "FAIL" if bad else "OK")
    return bad


# ----------------------------------------------------------------- injection + selftest
def inject(inst, kind):
    i = json.loads(json.dumps(inst))
    if kind == "room_capacity":
        for r in i["rooms"]:
            if not r["is_lab"]:
                r["capacity"] = 10
        return i, ("room", "capacity", "seat")
    if kind == "faculty_overload":
        for c in i["courses"]:
            c["faculty"] = i["faculty"][0]["id"]
        return i, ("faculty", "teacher", "load")
    if kind == "group_overload":
        i["courses"].append({"id": "CX", "faculty": i["faculty"][-1]["id"], "groups": [i["groups"][0]["id"]],
                             "enrollment": 30, "lectures": 40, "lab_block": 0})
        return i, ("student", "group", "overload")
    raise ValueError(kind)


def cmd_inject(a):
    solver = SOLVERS[a.solver]
    base = generate(TIERS[a.tier], 0)
    for kind in ("room_capacity", "faculty_overload", "group_overload"):
        inst, kws = inject(base, kind)
        out, dt = call(solver, inst, a.time_limit, 0, "plain")
        v = validate(inst, out["schedule"])
        detected = out["status"] == "infeasible" or v["hard_total"] > 0 and out["status"] != "feasible"
        lied = out["status"] in ("feasible", "optimal") and v["hard_total"] > 0
        reason = (out.get("reason") or "").lower()
        specific = any(k in reason for k in kws)
        print(f"{kind:17s} status={out['status']:10s} detected={detected} "
              f"specific_reason={specific} solver_claims_feasible_but_invalid={lied}\n   reason: {out.get('reason')}")


def cmd_selftest(_):
    inst = generate(TIERS["S"], 1)
    out = greedy_solver(inst, 10, 1)
    base = validate(inst, out["schedule"])
    assert out["status"] == "feasible" and base["hard_total"] == 0, base
    sched = out["schedule"]
    breaks = inst["breaks"][0]
    lecs = [a for a in sched if a["kind"] == "lec"]
    cases = {}
    x = [dict(a) for a in sched]; x[1] = {**x[1], "day": x[0]["day"], "start": x[0]["start"], "room": x[0]["room"]}
    cases["room_clash"] = x
    x = [dict(a) for a in sched]; x[0] = {**x[0], "start": breaks, "length": 1} if x[0]["kind"] == "lec" else x[0]
    cases["break_class"] = x
    x = [dict(a) for a in sched]; x.append(dict(lecs[0]))
    cases["extra_session"] = x
    x = [dict(a) for a in sched][1:]
    cases["missing_session"] = x
    x = [dict(a) for a in sched]; x[0] = {**x[0], "start": inst["periods"]}
    cases["out_of_range"] = x
    for name, s in cases.items():
        v = validate(inst, s)
        flagged = [k for k in v["hard"]]
        ok = name in v["hard"] or (name == "room_clash" and v["hard_total"] > 0)
        print(f"validator catches {name:16s}: {'OK' if ok else 'MISSED'}  {flagged}")
        assert ok
    for t, n in TIERS.items():
        i = generate(n, 0)
        assert generate(n, 0) == i, "generator not deterministic"
        print(f"tier {t}: {n} courses, {len(i['rooms'])} rooms, {len(i['faculty'])} faculty, "
              f"{len(i['groups'])} groups")
    print("selftest passed")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--solver", choices=SOLVERS, default="greedy")
    r.add_argument("--tiers", nargs="+", default=["S", "M"], choices=TIERS)
    r.add_argument("--modes", nargs="+", default=["plain"])
    r.add_argument("--seeds", type=int, default=3)
    r.add_argument("--time-limit", type=float, default=30)
    r.add_argument("--out", default="results")
    r.add_argument("--util", type=float, default=0.55, help="target room utilisation; 0.85+ = tight/hard")
    r.add_argument("--compare")
    r.set_defaults(fn=cmd_run)
    i = sub.add_parser("inject")
    i.add_argument("--solver", choices=SOLVERS, default="greedy")
    i.add_argument("--tier", default="M", choices=TIERS)
    i.add_argument("--time-limit", type=float, default=30)
    i.set_defaults(fn=cmd_inject)
    s = sub.add_parser("selftest")
    s.set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
