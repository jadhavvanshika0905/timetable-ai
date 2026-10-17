# Member 1 — Scheduling input contract v1 (backward-compatible v1.1 extension)

## Purpose

This package defines the current **solver input** and a separate **real-data staging inventory**. It is designed to be copied into the existing `timetable-ai` repository; it does not create a new repository and does not overwrite the original `contracts/sample_input.json`.

## Files

- `contracts/scheduler_input_v1.schema.json`: JSON Schema for current Python solver input. Supports the existing sample input.
- `contracts/scheduler_demo_input_v1.json`: **synthetic scheduling** example with anonymized IDs. The section label and its 65-student size correspond to a source record; the course assignments, faculty, teaching-hour requirements, lab group and usable demo rooms are illustrative, not confirmed college facts.
- `contracts/cse_first_year_pilot_inventory.json`: **sourced aggregate records** for first-year CSE A/B/C/D/F (July-Dec 2026). This is intentionally **NOT** a valid solver input.

## The stable contract (v1)

```json
{
  "slots": {"days": ["Mon", "Tue"], "periods": [1, 2, 3]},
  "faculty": [{"id": "F1", "name": "Faculty 1"}],
  "rooms": [{"id": "R1", "capacity": 75, "type": "classroom"}],
  "courses": [{"id": "OFFERING_1", "name": "Course 1", "faculty_id": "F1", "hours_per_week": 3, "expected_students": 65, "requires_lab": false}],
  "student_choices": [{"student_id": "ANON_001", "course_ids": ["OFFERING_1"]}]
}
```

### Critical ID rule

`courses[].id` is a **unique scheduled offering**, not necessarily a catalog subject code. When one subject is taught in two sections, give distinct offering IDs (example: `CSE101__I-CS-A`, `CSE101__I-CS-B`) and optionally store the shared catalog code under `catalog_code`. The examples are format examples, not confirmed actual course assignments. The `section_id` and `catalog_code` metadata are accepted by the contract but are not interpreted by the current solver.

### Field mapping (Member 2 → Member 1)

| Member 2 normalized field | Solver v1 field | Status / interpretation |
|---|---|---|
| Faculty employee ID | `faculty[].id` | Required unique nonempty ID |
| Room code | `rooms[].id` | Required |
| Room seating capacity | `rooms[].capacity` | Required positive integer; unknown capacities cannot be silently assumed |
| Room category | `rooms[].type` | Normalize to `classroom`, `lab`, `seminar` |
| Specific section course offering | `courses[].id` | Unique per offering (not only catalog code) |
| Source course code | `courses[].catalog_code` | Optional traceability field |
| Section identifier | `courses[].section_id` | Optional metadata; full section-aware constraints not yet implemented |
| Teaching faculty | `courses[].faculty_id` | Required before a course can be scheduled |
| Number of one-period sessions per week | `courses[].hours_per_week` | Required; **not** credits |
| Students attending that offering | `courses[].expected_students` | Required; actual confirmed count preferred |
| Needs a lab | `courses[].requires_lab` | Optional Boolean |
| Anonymous enrolled student-to-offering mapping | `student_choices[]` | Needed for actual personalized no-clash logic; empty list means no personal clashes are enforced |
| Day/period definitions | `slots.days`, `slots.periods` | Must be finalized with college schedule |

### Current solver v1 constraints (in the initial step-1 solver)

- Each course offering with `hours_per_week = k` creates exactly `k` **one-period** sessions.
- A room and a faculty member cannot be used twice at the same day/period.
- Two sessions of a given offering cannot share a day/period.
- `student_choices` is used to avoid conflicting offerings for explicitly listed students.
- Rooms must fit course expected attendance; lab offerings require a room with type `lab`.
- New in v1.1: `slots.breaks[]` reserved periods and `faculty[].preferences[]` with `NO` (unavailable), `AVOID`, `PREFER`; one-period theory sessions are spread across days when feasible.
- Still not implemented: consecutive multi-period labs, detailed section/batch scheduling, ML scores, manually locked entries, room preferences, and full infeasibility diagnosis.

### CSE pilot fact-check / readiness

Source: `CLASSROOMS_LAB-SECTIONS.xlsx` → `NEW Classroom Allotment_JULY 20` → rows 6–10. The four 65-student sections A/B/C/D have assigned rooms of capacity 64; section F lists 60 students in a 66-seat room. These are source records, **not** evidence of a feasible schedule.

**Do not pass** `cse_first_year_pilot_inventory.json` directly to `generate_timetable()`: it intentionally lacks course–faculty–section and hours/week relations. Member 2 should prepare a complete normalized `courses[]` list after verification.

### Test locally (PowerShell, repository root)

```powershell
python -m json.tool contracts\scheduler_demo_input_v1.json > $null
python -m json.tool contracts\cse_first_year_pilot_inventory.json > $null
.\.venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'backend'); from apps.scheduler.solver import generate_timetable; x=json.load(open('contracts/scheduler_demo_input_v1.json',encoding='utf-8')); r=generate_timetable(x); print(r['status'], len(r['timetable']))"
```

Expected with Member 1's step-1 solver: a feasible/optimal status and 5 entries, provided the solver files from Step 1 have been installed. The GitHub starter stub itself returns `NOT_IMPLEMENTED`.

### Output contract

Keep the existing `contracts/sample_output.json` shape for now:

```json
{"status":"OPTIMAL", "timetable":[{"course_id":"DEMO_CSE_A_C1", "faculty_id":"DEMO_F1", "room_id":"DEMO_R1", "day":"Mon", "period":1}], "infeasibility_reasons":[]}
```

`status` is a CP-SAT result label, not proof that the schedule has been independently verified. All scheduled session entries must be returned (one entry shown above only as a shape example).

### Team coordination / privacy

- Member 1 owns solver and constraint validation; Member 2 owns source data cleaning and mapping, Member 3 owns Django APIs/UI.
- Do not commit original student Excel/PDF files with names, phone numbers or emails into the **public** GitHub repository. Use anonymized identifiers, aggregate counts and synthetic examples.
- Discuss contract changes before modifying required fields: Member 2's importer and Member 3's API must use the same version.

## v1.1 optional scheduling fields (Member 2 / Member 3, coordinate first)

The fields below are **optional**. Existing JSON files still work without them:

```json
{
  "slots": {"days": ["Mon", "Tue"], "periods": [1,2,3], "breaks": [{"day":"Mon", "period":2}]},
  "faculty": [{"id":"F1", "name":"Faculty 1", "preferences":[
    {"day":"Mon", "period":1, "level":"NO"},
    {"day":"Tue", "period":3, "level":"PREFER"}
  ]}],
  "rooms": [{"id":"R1", "capacity":70, "type":"classroom"}],
  "courses": [{"id":"OFFERING_1", "faculty_id":"F1", "hours_per_week":1, "expected_students":50}]
}
```

- `NO`: disallowed (hard constraint).
- `AVOID`: penalized with weight 6, but still permitted when needed.
- `PREFER`: rewarded with weight 3; hard constraints always win.
- Repeat theory course sessions on same day: penalty weight 20 per extra session, where avoidable. Practical courses (`requires_lab: true`) have no spreading penalty, but consecutive lab blocks are **not** yet enforced.
- The solver output schema is unchanged.
- Schema files validate shape; the solver also checks whether days and periods referenced in preferences/breaks actually exist.
