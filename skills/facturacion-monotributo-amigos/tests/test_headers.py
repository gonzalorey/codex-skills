from __future__ import annotations

import unittest

from scripts.close_lib import detect_header_indexes


class TestHeaderDetection(unittest.TestCase):
    def test_detect_variant_headers(self) -> None:
        headers = ["Mes", "ARS", "USD", "Dolar pactado", "Observaciones"]
        preferred = {
            "period": ["Periodo", "Mes"],
            "amount_ars": ["Monto ARS", "ARS"],
            "amount_usd": ["Monto USD", "USD"],
            "fx_rate": ["Cotizacion", "Dolar pactado"],
            "note": ["Nota", "Observaciones"],
        }
        indexes = detect_header_indexes(headers, preferred)
        self.assertEqual(0, indexes["period"])
        self.assertEqual(1, indexes["amount_ars"])
        self.assertEqual(2, indexes["amount_usd"])
        self.assertEqual(3, indexes["fx_rate"])
        self.assertEqual(4, indexes["note"])


if __name__ == "__main__":
    unittest.main()
