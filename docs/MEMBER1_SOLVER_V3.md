# Member 1 — Scheduling Engine v3: consecutive practical blocks

## New optional input field

For any course with `requires_lab: true`, add `"lab_block_size": 2` to require
**each two lab hours to run as one indivisible block**. Default is 1, so old
v1 and v2 input JSON still runs without modification.

- `hours_per_week` means **total occupied periods**, not number of blocks.
- Must be divisible by `lab_block_size`: e.g. 4 hours with size 2 means two blocks.
- A block must be on one day, in one lab room, with one faculty member, in
  numerically consecutive periods; no breaks or unavailable faculty inside.
- All block periods count towards faculty, room, section, course and student
  conflict checks.
- Flat output contract unchanged: one row per occupied period.
- For `lab_block_size: 1` the existing per-period lab behavior is unchanged.
- For plain theory courses, multi-period blocks are not supported in v3.
- If no suitable consecutive window exists, returns `INFEASIBLE`; malformed
  block settings return `INVALID_INPUT`.

## Install in existing repo (PowerShell)

Review `git status` first and save your current work. Extract package from
repo root; this replaces only Member 1 files and the shared schema.

```powershell
Expand-Archive -Path "$HOME\Downloads\member1_scheduler_v3.zip" -DestinationPath . -Force
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_solver.py -v
```

## Run demo

```powershell
.\.venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'backend'); from apps.scheduler.solver import generate_timetable; data=json.load(open('contracts/scheduler_demo_input_v3.json',encoding='utf-8')); print(json.dumps(generate_timetable(data),indent=2))"
```

The demo has 3 theory periods and one 2-period practical block. Expect **5
flat timetable entries** and `OPTIMAL` or `FEASIBLE`, with the practical entries
consecutive in one lab on one day.

## Limitations

- No multi-section lab batching or separate lab group allocations yet.
- A lab block size is defined in period units, not absolute clock minutes.
- Period labels must be sequential integers for adjacency.
- Faculty soft preferences apply to every occupied period; theory spread
  preference remains best-effort.
- Validation assumes flat timetable rows include all hours. It detects split
  lab blocks by checking consecutive same-room same-faculty runs.
