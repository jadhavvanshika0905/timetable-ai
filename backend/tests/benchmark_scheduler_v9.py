
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from apps.scheduler.solver import generate_timetable
from apps.scheduler.validator import validate_timetable


def create_demo_data(num_courses=25):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    faculty_count = max(10, (num_courses + 5) // 6)

    faculty = [
        {
            "id": f"F{i:02d}",
            "name": f"Demo Faculty {i}",
            "max_hours_per_week": 16,
        }
        for i in range(1, faculty_count + 1)
    ]

    rooms = [
        {
            "id": f"R{i:02d}",
            "capacity": 40,
            "type": "classroom",
        }
        for i in range(1, 9)
    ]

    rooms += [
        {
            "id": f"L{i:02d}",
            "capacity": 40,
            "type": "lab",
        }
        for i in range(1, 4)
    ]

    courses = []

    for i in range(num_courses):
        is_lab = i % 5 == 0

        courses.append({
            "id": f"C{i + 1:03d}",
            "name": f"Demo Course {i + 1}",
            "faculty_id": faculty[i % faculty_count]["id"],
            "section_id": f"SEC{i // 5 + 1:02d}",
            "hours_per_week": 2,
            "expected_students": 25,
            "requires_lab": is_lab,
            "lab_block_size": 2 if is_lab else 1,
        })

    student_choices = []

    sections = sorted(set(c["section_id"] for c in courses))

    for section in sections:
        selected_courses = [
            c["id"] for c in courses
            if c["section_id"] == section
        ]

        for j in range(5):
            student_choices.append({
                "student_id": f"ANON_{section}_{j}",
                "course_ids": selected_courses,
            })

    return {
        "slots": {
            "days": days,
            "periods": [1, 2, 3, 4, 5, 6],
            "breaks": [
                {"day": day, "period": 3}
                for day in days
            ],
        },
        "faculty": faculty,
        "rooms": rooms,
        "courses": courses,
        "student_choices": student_choices,
    }


if __name__ == "__main__":
    data = create_demo_data(100)

    print("Courses:", len(data["courses"]))
    print("Faculty:", len(data["faculty"]))
    print("Rooms:", len(data["rooms"]))
    print("Students:", len(data["student_choices"]))

    start = time.perf_counter()
    result = generate_timetable(
        data,
        max_time_seconds=60.0,
        num_search_workers=8
    )
    elapsed = time.perf_counter() - start

    print("Solver Status:", result["status"])
    print("Generated Entries:", len(result["timetable"]))
    print("Execution Time:", round(elapsed, 3), "seconds")

    if result["status"] in ("OPTIMAL", "FEASIBLE"):
        errors = validate_timetable(
            data, result["timetable"]
        )
        print("Validation Errors:", len(errors))
        print("Expected Entries:", 2 * len(data["courses"]))
    else:
        print("Reasons:", result["infeasibility_reasons"])
