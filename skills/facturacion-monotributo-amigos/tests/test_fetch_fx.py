from __future__ import annotations

import unittest

from scripts.fetch_fx import calculate_pacted_fx, parse_dolarhoy_html


class TestFetchFx(unittest.TestCase):
    def test_calculate_pacted_fx(self) -> None:
        fx = calculate_pacted_fx(1200.0, 1260.0, 980.0, 1020.0)
        self.assertEqual(1115.0, fx)

    def test_parse_html_sections(self) -> None:
        html = """
        <h2>Dólar Blue</h2><span>$ 1.200,00</span><span>$ 1.260,00</span>
        <h2>Dólar Oficial</h2><span>$ 980,00</span><span>$ 1.020,00</span>
        """
        parsed = parse_dolarhoy_html(html)
        self.assertEqual(1200.0, parsed["blue_buy"])
        self.assertEqual(1260.0, parsed["blue_sell"])
        self.assertEqual(980.0, parsed["official_buy"])
        self.assertEqual(1020.0, parsed["official_sell"])


if __name__ == "__main__":
    unittest.main()
