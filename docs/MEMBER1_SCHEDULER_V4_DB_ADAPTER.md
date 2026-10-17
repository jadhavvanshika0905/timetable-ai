# Member 1 — Step 4: Django database adapter (read-only first)

## Included changes

- `backend/apps/scheduler/services.py` — NEW functions to turn Django model records into the v3 solver's JSON input, then optionally run `generate_timetable`. **Does not save anything to PostgreSQL.**
- `backend/tests/test_scheduler_service.py` — Nine tests, mostly pure data conversion, one solver integration test.
- No changes to Member 2's `institution/models.py` or Member 3's `timetable` app.

## Functions

```python
from apps.scheduler.services import (
    build_solver_input_from_records,  # accepts rows/dicts, no database required
    build_solver_input_from_db,       # reads existing Django models
    generate_timetable_for_term,     # reads DB and calls Member 1 solver
)
```

The term-level adapter reads `StudentCourseChoice` for the selected `AcademicTerm`, gathers selected courses, assigned faculty, room inventory, timeslots and faculty preferences. It can optionally accept an explicit list of Course PKs to include required core courses that are not represented by elective choice records.

**IMPORTANT: `course_ids` here means Django database Course primary keys, not catalog course codes.** Output `course_id`, `faculty_id`, and `room_id` are strings of Django primary keys; the persistence layer must resolve them back to database objects. The JSON `catalog_code` field preserves the course code.

### Example Django Shell use (only after database tables and records exist)

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py shell
```

```python
from apps.scheduler.services import generate_timetable_for_term
result = generate_timetable_for_term(term_id=1, course_ids=[1, 2], lab_block_sizes={2: 2})
print(result["status"], len(result["timetable"]))
print(result["infeasibility_reasons"])
```

The IDs above are **illustrative**; use actual `AcademicTerm` and `Course` PKs from the seeded database. `lab_block_sizes` maps Course PK to consecutive period count. Omitting it retains the v3 default of one period even for a laboratory course, so supply it explicitly for any real multi-period lab requirements.

### Test without Docker/PostgreSQL (Windows PowerShell from project root)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_scheduler_service.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_solver.py -v
```

Expect **9 new tests** (including 1 end-to-end solver test) and the previous **28 scheduler tests**, if existing files are unchanged. Full integration against your institution's populated database is **not yet verified**.

## Current schema limitations — coordinate with Member 2 before wider rollout

1. **There is no section-level `CourseOffering` relation.** `Course.code` is unique, so one catalog course taught to CSE-A and CSE-B by different teachers cannot be represented as independent offerings with the same code. This version only handles one scheduled offering per `Course` row; do not claim a real multi-section timetable is supported yet.
2. **No lab block size field in `Course`.** Temporary `lab_block_sizes` parameter provides the v3 solver requirement; ask Member 2 to design a persistent field or section-offering/session model.
3. **StudentCourseChoice may contain only electives.** In that case, scheduling just the recorded selected courses would omit mandatory/core courses. Pass explicit `course_ids` for a pilot, but confirm the complete course set with Member 2.
4. **TimeSlot is global, not term-specific.** The adapter reads all current TimeSlot rows, including `is_break`, and treats missing day-period combinations as blocked. TimeSlot availability must be maintained for the desired academic term.
5. **No verified per-section enrollment mapping.** Section-level clashes cannot be guaranteed without section-specific offerings and memberships, even if student choices are imported. Current capacity estimate is max(`expected_students`, number of distinct recorded enrolled students) and assumes enrollment data is complete.
6. **No database write yet.** Persisting `Timetable` and `TimetableEntry` with proper atomic transactions/versioning belongs to the next integration phase with Member 3. Never publish a timetable before independent validation.

## Safe team workflow

1. Save tested v3 state on main first (already done, commit `aaa6852`).
2. Extract package from repository root; it only adds Member 1's services file and a new test module and doc.
3. Run 9 new adapter tests, then 28 old tests. Check `git diff` and staged file paths.
4. Commit only Member 1 files, then `git pull --rebase origin main` and `git push origin main` when tests pass.
5. Do not commit student spreadsheets, personal data, or real enrollment records to the **public repository**.
