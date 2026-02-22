from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestDryRunE2E(unittest.TestCase):
    def test_dry_run_in_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = textwrap.dedent(
                """
                timezone: America/Argentina/Buenos_Aires
                business_day_window: 3
                currency:
                  rounding: 2
                invoice:
                  watch_dir: ./tests/fixtures
                people:
                  - name: Santi Favelukes
                    alias: santi-favelukes
                    sheet_id: sheet-1
                    preferred_row_headers:
                      period: [Periodo, Mes]
                      amount_ars: [Monto ARS, ARS]
                      amount_usd: [Monto USD, USD]
                      fx_rate: [Cotizacion, Dolar pactado, FX]
                      note: [Nota, Observaciones]
                    fallback_amount_ars: 100000
                    whatsapp_template_key: cierre_facturacion
                    ynab_account_id: account-1
                google:
                  service_account_json: ./missing.json
                sheets:
                  debt_registry: Deuda
                  invoice_registry:
                    spreadsheet_id: invoice-sheet
                    tab_name: Facturas
                drive:
                  invoice_folder_id: drive-folder
                ynab:
                  personal_access_token: ""
                  budget_id: budget-1
                  tracking_entry_sign: -1
                """
            ).strip()
            config_path = tmp_path / "config.yaml"
            config_path.write_text(config, encoding="utf-8")

            env = dict(os.environ)
            env["DOLARHOY_HTML_PATH"] = str(Path("tests/fixtures/dolarhoy_sample.html").resolve())

            cmd = [
                "python3",
                "scripts/run_monthly_close.py",
                "--mode",
                "monthly-close",
                "--dry-run",
                "--config",
                str(config_path),
                "--today",
                "2026-02-27",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1], env=env)
            self.assertEqual(0, proc.returncode, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual("2026-02", payload["summary"]["period"])
            self.assertEqual(1, len(payload["summary"]["people"]))
            self.assertIn("santi-favelukes", payload["whatsapp_messages"])

    def test_dry_run_outside_window_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text(
                "timezone: America/Argentina/Buenos_Aires\nbusiness_day_window: 3\npeople: []\ninvoice:\n  watch_dir: .\n",
                encoding="utf-8",
            )
            cmd = [
                "python3",
                "scripts/run_monthly_close.py",
                "--mode",
                "monthly-close",
                "--dry-run",
                "--config",
                str(config_path),
                "--today",
                "2026-02-20",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
            self.assertEqual(0, proc.returncode, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual("skipped", payload["summary"]["status"])


if __name__ == "__main__":
    unittest.main()
