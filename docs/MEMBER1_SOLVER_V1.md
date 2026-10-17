# Member 1 — Scheduling Engine v1

Files in this ZIP extend the **existing** `timetable-ai` repository. They replace only:

- `backend/apps/scheduler/solver.py`
- `backend/apps/scheduler/constraints.py`
- `backend/apps/scheduler/validator.py`
- `backend/tests/test_solver.py`

There are no changes to the Django database models, frontend, or JSON data contract.

## Input
`contracts/scheduler_demo_input_v1.json` generated in the preceding data-contract step (fallback: `contracts/sample_input.json` for running the script). `generate_timetable(data)` returns `status`, `timetable`, `infeasibility_reasons`.

## What is implemented
- One period per session; number of weekly sessions = `hours_per_week`.
- Exactly one scheduled room/period for every session.
- Faculty, room and offering cannot be double-booked.
- Sections with the same `section_id` cannot overlap (new check; assumes entire section attends the offering).
- Students with overlapping elected courses are scheduled conflict-free, **but only for records in `student_choices`**.
- Lab course needs `requires_lab: true`; compatible room must fit course enrollment.
- Prechecks for invalid input, impossible room capacity, and obvious shortage of periods.
- Independent validator checks solver output and can later validate manual edits.

## Important limitations
- No faculty unavailable slots / preferences, breaks, consecutive labs, true subgroup scheduling, soft objective, or ML scores in the current contract.
- Data in `scheduler_demo_input_v1.json` is synthetic for course/faculty details, not verified college assignment data.
- If a student is absent from `student_choices`, their cross-section elective conflicts cannot be verified.
- For a shared section `section_id`, parallel disjoint-batch lab sessions are intentionally *not* permitted in v1. Extend grouping model before enabling those.
- `OPTIMAL` is the CP-SAT status for this feasibility-only model, not a promise of best faculty preferences.
- Detailed solver infeasibility diagnosis may require extra modeling; current response provides prechecks or a generic message.
- No repository push is performed by this ZIP.

## Windows PowerShell: install / test

From the repository root, ideally with a clean `git status`:

```powershell
Expand-Archive -Path "$HOME\Downloads\member1_scheduler_v1.zip" -DestinationPath . -Force
.\.venv\Scripts\python.exe backend\apps\scheduler\solver.py
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_solver.py -v
```

For source control, stage only these files plus any documentation you intend to commit. Always pull from `main` before starting and coordinate with collaborators before editing shared files.
