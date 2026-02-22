"""Tests for _render_message – covers legacy \\n literal backward compat (blue/green)."""
from __future__ import annotations

import unittest

import scripts.run_monthly_close as runner


class TestRenderMessage(unittest.TestCase):
    def test_basic_substitution(self) -> None:
        template = "Hola {name}, periodo {period}."
        result = runner._render_message(template, {"name": "Santi", "period": "2026-02"})
        self.assertEqual("Hola Santi, periodo 2026-02.", result)

    def test_real_newlines_pass_through(self) -> None:
        """Green path: template already uses real newlines – no conversion needed."""
        template = "Linea uno\nLinea dos"
        result = runner._render_message(template, {})
        self.assertIn("\n", result)
        self.assertNotIn("\\n", result)

    def test_legacy_backslash_n_converted(self) -> None:
        """Blue path: legacy templates stored literal \\n sequences – they must be expanded."""
        template = "Linea uno\\nLinea dos"
        result = runner._render_message(template, {})
        self.assertEqual("Linea uno\nLinea dos", result)

    def test_all_placeholders_replaced(self) -> None:
        template = "{name} owes ARS {amount_ars} (USD {amount_usd}) at {fx_rate}."
        values = {"name": "Ana", "amount_ars": "100000.00", "amount_usd": "80.00", "fx_rate": "1250.00"}
        result = runner._render_message(template, values)
        self.assertEqual("Ana owes ARS 100000.00 (USD 80.00) at 1250.00.", result)

    def test_unknown_placeholder_left_intact(self) -> None:
        """Placeholders not present in values dict are left as-is."""
        template = "Hello {name}, ref: {invoice_reference}"
        result = runner._render_message(template, {"name": "Bob"})
        self.assertIn("{invoice_reference}", result)


if __name__ == "__main__":
    unittest.main()
