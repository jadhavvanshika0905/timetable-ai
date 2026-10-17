
# Member 1 — Scheduling Engine Final Handover

## Project
AI-Based Timetable Generation System (SIH 2025 PS 25091)

## Module Responsibility
Member 1: Scheduling Engine using Google OR-Tools CP-SAT.

## 1. Implemented Components

- solver.py: Generates timetable using CP-SAT.
- constraints.py: Applies hard scheduling constraints.
- validator.py: Independently validates timetable entries.
- services.py: Converts Django institution records into solver input.
- tests.py: Django and PostgreSQL integration tests.

## 2. Working Flow

1. Django database provides courses, faculty, rooms,
   time slots, student choices and faculty preferences.
2. services.py converts database records into solver input.
3. solver.py validates the input and checks basic feasibility.
4. OR-Tools CP-SAT searches for a valid timetable.
5. constraints.py prevents scheduling conflicts.
6. validator.py checks the generated timetable.
7. The solver returns the result as a Python dictionary.

The scheduling service does not save or publish timetables.

## 3. Implemented Scheduling Rules

- No faculty double-booking.
- No room double-booking.
- No course double-booking.
- No overlapping classes for the same section.
- No timetable clashes for students taking common courses.
- Room capacity requirements.
- Laboratory room requirements.
- Consecutive practical/laboratory periods.
- Faculty unavailability (NO).
- Faculty weekly workload limits.
- Scheduled breaks.
- Faculty AVOID and PREFER soft preferences.
- Theory lectures spread across days when feasible.

## 4. Main Integration Functions

Located in backend/apps/scheduler/services.py:

- build_solver_input_from_records(...)
- build_solver_input_from_db(term_id, ...)
- generate_timetable_for_term(term_id, ...)

Optional solver settings:

- max_time_seconds: default 10.0
- num_search_workers: default 1

For larger scheduling problems, callers may supply
a longer time limit and multiple search workers.

## 5. Output Contract

The returned dictionary contains:

- status
- timetable
- infeasibility_reasons

Successful statuses:
OPTIMAL or FEASIBLE.

Each timetable entry contains:
course_id, faculty_id, room_id, day, period.

For consecutive practical blocks, each occupied
period is represented by a separate output entry.

Database primary keys are converted to strings.

## 6. Testing Completed

- 36 solver and advanced constraint tests passed.
- 9 database adapter tests passed.
- 6 Django integration tests passed.

Total: 51 automated tests passed across the
completed verification runs.

Performance benchmark results:

25 courses: 50 entries, 3.113 seconds.
50 courses: 100 entries, 5.869 seconds.
100 courses: 200 entries, 8.532 seconds.

All three successful benchmarks had zero
independent timetable validation errors.

The 100-course successful benchmark used
60 seconds as the time limit and 8 search workers.
Earlier benchmarks used default solver settings.

Performance depends on hardware, timetable
complexity and solver configuration.

## 7. Integration Requirements for Member 2

The Django institution models provide the
underlying scheduling data.

Current limitations to coordinate:

- No separate CourseOffering/Section database model.
- No persistent lab_block_size field.
- StudentCourseChoice may not include core courses.
- TimeSlot records are global, not term-specific.
- Section-specific offering and enrollment mapping
  is not yet available in the current adapter.

These need team-level integration decisions.

## 8. Integration Requirements for Member 3

The scheduling engine returns validated output,
but does not write it to PostgreSQL.

Member 3 is responsible for integrating:

- Timetable and TimetableEntry persistence.
- Timetable version management.
- Draft and publish workflows.
- Database transaction handling.
- Mapping output IDs to Django model objects.

Only valid OPTIMAL or FEASIBLE results should
proceed to timetable persistence and review.

## 9. Important Notes

- INFEASIBLE means no schedule satisfies the
  constraints established by the solver.
- UNKNOWN may occur when the solver cannot
  establish a result within its time limit.
- Solver outputs must be independently validated.
- Production deployment and full team-level
  integration require separate verification.
