from __future__ import annotations

import argparse
import unittest

import scripts.run_monthly_close as runner


class TestAmountChangeGate(unittest.TestCase):
    def test_amount_change_requires_confirmation(self) -> None:
        args = argparse.Namespace(confirm_amount_change=False)
        person = {"name": "Santi Favelukes", "fallback_amount_ars": 120000}

        original = runner.read_last_month_amount
        try:
            runner.read_last_month_amount = lambda **_: 110000.0
            with self.assertRaises(runner.CloseError):
                runner._resolve_amounts(person=person, fx_rate=1000.0, period="2026-02", args=args)
        finally:
            runner.read_last_month_amount = original


if __name__ == "__main__":
    unittest.main()
