from __future__ import annotations

import unittest
from datetime import date

from scripts.close_lib import evaluate_date_gate, is_last_n_business_days, round_money


class TestGateAndRounding(unittest.TestCase):
    def test_last_three_business_days(self) -> None:
        self.assertTrue(is_last_n_business_days(date(2026, 2, 26), 3))
        self.assertTrue(is_last_n_business_days(date(2026, 2, 27), 3))
        self.assertFalse(is_last_n_business_days(date(2026, 2, 24), 3))

    def test_gate_skip_outside_window(self) -> None:
        result = evaluate_date_gate("America/Argentina/Buenos_Aires", 3, today=date(2026, 2, 20))
        self.assertFalse(result.should_run)

    def test_rounding_half_up(self) -> None:
        self.assertEqual("1.01", f"{round_money(1.005, 2):.2f}")


if __name__ == "__main__":
    unittest.main()
