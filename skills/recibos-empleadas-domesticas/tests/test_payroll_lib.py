#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.payroll_lib import (
    compute_payroll_for_person,
    parse_ars,
    parse_period,
)

ROOT = Path(__file__).resolve().parent


class TestPayrollLib(unittest.TestCase):
    def test_parse_ars(self) -> None:
        self.assertEqual(parse_ars(" AR$1.234,50"), 1234.5)
        self.assertEqual(parse_ars("- AR$24.000,00"), -24000.0)
        self.assertEqual(parse_ars(""), 0.0)

    def test_irma_feb_2026_with_events(self) -> None:
        payload = json.loads((ROOT / "fixtures" / "irma_2026-02.json").read_text(encoding="utf-8"))
        result = compute_payroll_for_person("irma", parse_period("2026-02"), payload)
        self.assertEqual(result.basico, 779400.0)
        self.assertEqual(result.antiguedad, 7794.0)
        self.assertEqual(result.viaticos, 71878.0)
        self.assertEqual(result.eventos, 12000.0)
        self.assertEqual(result.total, 871072.0)

    def test_mariza_no_absence_from_reference_matrix(self) -> None:
        payload = json.loads((ROOT / "fixtures" / "mariza_2026-02.json").read_text(encoding="utf-8"))
        result = compute_payroll_for_person("mariza", parse_period("2026-02"), payload)
        self.assertEqual(result.basico, 215760.0)
        self.assertEqual(result.eventos, 0.0)
        self.assertEqual(result.total, 215760.0)


if __name__ == "__main__":
    unittest.main()
