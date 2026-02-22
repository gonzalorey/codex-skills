#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCliDryRun(unittest.TestCase):
    def test_dry_run_gate_message(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts" / "run_monthly_payroll.py"),
                "--mode",
                "dry-run",
                "--period",
                "2026-02",
                "--simulate-arca",
                "true",
                "--simulate-whatsapp",
                "true",
                "--ignore-day-gate",
                "--fixtures-dir",
                str(ROOT / "tests" / "fixtures"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("summary", payload)
        self.assertIn("workers", payload["summary"])
        self.assertEqual(len(payload["summary"]["workers"]), 2)


if __name__ == "__main__":
    unittest.main()
