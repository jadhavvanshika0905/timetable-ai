
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from apps.scheduler.solver import generate_timetable


class TestFacultyWorkloadV7(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        path = ROOT / "contracts" / "scheduler_demo_input_v1.json"
        cls.demo = json.loads(path.read_text(encoding="utf-8"))

    def test_workload_exceeded(self):
        data = copy.deepcopy(self.demo)
        data["faculty"][0]["max_hours_per_week"] = 2

        result = generate_timetable(data)

        self.assertEqual(result["status"], "INFEASIBLE")
        self.assertTrue(
            any("max_hours_per_week" in reason
                for reason in result["infeasibility_reasons"])
        )

    def test_workload_within_limit(self):
        data = copy.deepcopy(self.demo)
        data["faculty"][0]["max_hours_per_week"] = 3
        data["faculty"][1]["max_hours_per_week"] = 2

        result = generate_timetable(data)

        self.assertIn(result["status"], ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result["timetable"]), 5)

    def test_invalid_workload_limit(self):
        data = copy.deepcopy(self.demo)
        data["faculty"][0]["max_hours_per_week"] = 0

        result = generate_timetable(data)

        self.assertEqual(result["status"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
