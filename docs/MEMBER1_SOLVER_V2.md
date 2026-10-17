# Member 1 Scheduling Engine — Step 3 (v2)

## What changed

This is a backward-compatible update for the current `timetable-ai` repository. All 10 v1 tests remain. New tests cover unavailable slots, breaks, soft preferences, and better theory lecture distribution.

| Field | Example | Meaning |
|---|---|---|
| `slots.breaks` | `[{"day":"Wed","period":3}]` | Entire college break; no lectures may be scheduled there |
| `faculty[].preferences` | `[{"day":"Mon","period":1,"level":"NO"}]` | Faculty unavailable for a period |
| `faculty[].preferences` | `[{"day":"Tue","period":2,"level":"AVOID"}]` | Allowed but discouraged |
| `faculty[].preferences` | `[{"day":"Fri","period":3,"level":"PREFER"}]` | Allowed and rewarded |

The CP-SAT model excludes break slots and `NO` faculty slots from assignment variables (hard conditions). It minimizes repeat theory lectures on a single day (+20 penalty per additional lecture), avoids `AVOID` slots (+6 penalty) and favors `PREFER` slots (-3 reward). Weights are **illustrative starting values**, not verified college policy. `validator.py` independently checks for break/unavailable violations.

Existing `contracts/sample_input.json` and `contracts/scheduler_demo_input_v1.json` stay supported. This ZIP does not replace either original demo. New `contracts/scheduler_demo_input_v2.json` has synthetic preferences and a break.

## Install (Windows PowerShell, project root)

First ensure `git status` is clean or back up your local edits, because `Expand-Archive -Force` overwrites the files listed in the ZIP. This ZIP updates `solver.py`, `validator.py`, `test_solver.py`, the v1 JSON schema, and the Member 1 data-contract document. It also adds one new v2 example and this document.

```powershell
cd C:\Users\bhatn\books-project\timetable-ai
Expand-Archive -Path "$HOME\Downloads\member1_scheduler_v2.zip" -DestinationPath . -Force
```

## Run all tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_solver.py -v
```

## Run v2 demonstration

```powershell
.\.venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'backend'); from apps.scheduler.solver import generate_timetable; x=json.load(open('contracts/scheduler_demo_input_v2.json',encoding='utf-8')); print(json.dumps(generate_timetable(x),indent=2))"
```

Expected: `OPTIMAL` or `FEASIBLE`, five sessions, no entries during Wed period 3; `DEMO_F1` never Mon period 1; theory course `DEMO_CSE_A_C1` preferably across three different days. Soft preferences are best effort, hard availability/break rules are mandatory.

## IMPORTANT limitations / next step

- A lab with 2 hours/week is still modeled as **two independent one-period sessions**. There is **no guarantee of consecutive practical periods** yet. We should implement consecutive lab blocks next.
- Actual college teaching schedules still require complete section-to-course, course-to-faculty, weekly period, faculty availability, and real day/period information. This demo is synthetic.
- CP-SAT `OPTIMAL` means optimal for **the implemented objective**, not necessarily ideal for every college requirement.
- Solver caps search at 10 seconds and may return `FEASIBLE` or `UNKNOWN`; actual end-to-end tests must be run in an environment with OR-Tools installed.
- Do not upload private student rosters to a public GitHub repo. Use anonymized IDs and aggregate counts.
