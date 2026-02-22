"""Tests for _load_config blue/green PyYAML strategy."""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import scripts.run_monthly_close as runner


_SAMPLE_YAML = textwrap.dedent("""
    timezone: America/Argentina/Buenos_Aires
    business_day_window: 3
    people:
      - name: Santi Favelukes
        alias: santi-favelukes
        sheet_id: sheet-1
        fallback_amount_ars: 100000
    invoice:
      watch_dir: ./tests/fixtures
    sheets:
      debt_registry: Deuda
    ynab:
      budget_id: budget-1
      tracking_entry_sign: -1
""").strip()


class TestLoadConfig(unittest.TestCase):
    def _write_config(self, content: str) -> str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        tmp.write(content)
        tmp.flush()
        return tmp.name

    def test_loads_valid_yaml(self) -> None:
        path = self._write_config(_SAMPLE_YAML)
        cfg = runner._load_config(path)
        self.assertEqual("America/Argentina/Buenos_Aires", cfg["timezone"])
        self.assertEqual(3, cfg["business_day_window"])
        self.assertEqual(1, len(cfg["people"]))
        self.assertEqual("santi-favelukes", cfg["people"][0]["alias"])

    def test_green_pyyaml_path(self) -> None:
        """Green: PyYAML should be importable in test env; config parses correctly."""
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml not installed – testing green path requires it")
        path = self._write_config(_SAMPLE_YAML)
        cfg = runner._load_config(path)
        self.assertIn("people", cfg)

    def test_blue_builtin_parser_fallback(self) -> None:
        """Blue: simulate PyYAML absent by temporarily hiding it from sys.modules."""
        saved = sys.modules.pop("yaml", None)
        try:
            path = self._write_config(_SAMPLE_YAML)
            cfg = runner._load_config(path)
            self.assertEqual("America/Argentina/Buenos_Aires", cfg["timezone"])
        finally:
            if saved is not None:
                sys.modules["yaml"] = saved

    def test_missing_config_raises(self) -> None:
        with self.assertRaises(runner.CloseError):
            runner._load_config("/nonexistent/path/config.yaml")

    def test_json_config_also_works(self) -> None:
        import json
        data = {"timezone": "UTC", "people": []}
        path = self._write_config(json.dumps(data))
        cfg = runner._load_config(path)
        self.assertEqual("UTC", cfg["timezone"])


if __name__ == "__main__":
    unittest.main()
