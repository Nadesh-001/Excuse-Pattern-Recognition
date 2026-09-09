import unittest
import sys
import os

# Add the parent directory to the path so we can import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.task_formulas import calculate_efficiency_score

class TestEfficiencyScore(unittest.TestCase):
    def test_efficiency_zero_tasks(self):
        # 0 tasks should safely return 100.0
        self.assertEqual(calculate_efficiency_score(0, 0), 100.0)
        self.assertEqual(calculate_efficiency_score(0, 5), 100.0)

    def test_efficiency_perfect(self):
        # no rationalizations = 100%
        self.assertEqual(calculate_efficiency_score(10, 0), 100.0)

    def test_efficiency_partial(self):
        # 2 rationalizations out of 10 = 80%
        self.assertEqual(calculate_efficiency_score(10, 2), 80.0)
        # 5 out of 10 = 50%
        self.assertEqual(calculate_efficiency_score(10, 5), 50.0)

    def test_efficiency_zero(self):
        # 10 out of 10 = 0%
        self.assertEqual(calculate_efficiency_score(10, 10), 0.0)

    def test_efficiency_negative_ceiling(self):
        # More rationalizations than tasks, should be capped at 0.0 min
        self.assertEqual(calculate_efficiency_score(10, 15), 0.0)

if __name__ == '__main__':
    unittest.main()
