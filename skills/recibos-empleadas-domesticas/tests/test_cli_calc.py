#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCliCalc(unittest.TestCase):
    def test_calc_cli_output(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "irma_2026-02.json"
        proc = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts" / "calc_payroll.py"),
                "--period",
                "2026-02",
                "--person",
                "irma",
                "--input",
                str(fixture),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["person_name"], "Irma")
        self.assertEqual(payload["total"], 871072.0)


if __name__ == "__main__":
    unittest.main()
