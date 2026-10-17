# Member 1 Scheduler v3.1 — Test Fixture Fix

Five v3 tests created invalid input while trying to test INFEASIBLE constraints.
They reduced the timetable to Mon-only slots or removed a course without updating
pre-existing faculty preferences and student course choices.

Changes:
- Add `_clean_reduced_fixture(data)` only to the test suite.
- Call it in the five affected v3 tests, after modifying their slot/course list.
- Do not alter solver.py or weaken its input validation.

Extract this zip at the repository root. It replaces only backend/tests/test_solver.py.

Run in Windows PowerShell:

    .\.venv\Scripts\python.exe -m unittest discover -s backend\tests -p test_solver.py -v

Expected: 28 tests. All should pass if the user has the same working v3
implementation shown in their demo output. Full OR-Tools run was not available
in the file-preparation environment; validate on the user's local machine.
