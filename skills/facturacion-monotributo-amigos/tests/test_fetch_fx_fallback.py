"""Tests for fetch_fx blue/green fallback strategy (dolarhoy → Bluelytics)."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from scripts.close_lib import CloseError
from scripts.fetch_fx import fetch_bluelytics_prices, fetch_market_prices


_BLUELYTICS_RESPONSE = {
    "blue": {"value_buy": 1200.0, "value_sell": 1260.0},
    "oficial": {"value_buy": 980.0, "value_sell": 1020.0},
}


def _mock_urlopen_bluelytics(req, timeout=None):
    body = json.dumps(_BLUELYTICS_RESPONSE).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = body
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestFetchFxFallback(unittest.TestCase):
    def test_fetch_bluelytics_prices_parses_response(self) -> None:
        """Green: Bluelytics returns expected dict shape."""
        with patch("urllib.request.urlopen", side_effect=_mock_urlopen_bluelytics):
            prices = fetch_bluelytics_prices()
        self.assertEqual(1200.0, prices["blue_buy"])
        self.assertEqual(1260.0, prices["blue_sell"])
        self.assertEqual(980.0, prices["official_buy"])
        self.assertEqual(1020.0, prices["official_sell"])

    def test_fetch_bluelytics_raises_on_bad_shape(self) -> None:
        """Bluelytics response with wrong keys → CloseError."""
        bad_response = {"wrong_key": {}}

        def _bad_urlopen(req, timeout=None):
            body = json.dumps(bad_response).encode("utf-8")
            mock = MagicMock()
            mock.read.return_value = body
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

        with patch("urllib.request.urlopen", side_effect=_bad_urlopen):
            with self.assertRaises(CloseError):
                fetch_bluelytics_prices()

    def test_fetch_market_prices_falls_back_to_bluelytics_on_dolarhoy_failure(self) -> None:
        """Blue path fails (dolarhoy) → green path (Bluelytics) used automatically."""
        call_count = {"n": 0}

        def _selective_urlopen(req, timeout=None):
            call_count["n"] += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "dolarhoy" in url:
                raise urllib.error.URLError("simulated dolarhoy outage")
            # Bluelytics call
            return _mock_urlopen_bluelytics(req, timeout)

        with patch("urllib.request.urlopen", side_effect=_selective_urlopen):
            prices = fetch_market_prices()

        self.assertEqual(1200.0, prices["blue_buy"])
        self.assertGreaterEqual(call_count["n"], 1)

    def test_fetch_market_prices_raises_when_both_fail(self) -> None:
        """Both sources fail → CloseError with composite message."""
        def _always_fail(req, timeout=None):
            raise urllib.error.URLError("network down")

        with patch("urllib.request.urlopen", side_effect=_always_fail):
            with self.assertRaises(CloseError) as ctx:
                fetch_market_prices()
        self.assertIn("all FX sources failed", str(ctx.exception))

    def test_local_html_override_takes_priority(self, tmp_path=None) -> None:
        """DOLARHOY_HTML_PATH env var bypasses network entirely."""
        import os
        import tempfile

        html = """
        <h2>Dólar Blue</h2><span>$ 1.300,00</span><span>$ 1.360,00</span>
        <h2>Dólar Oficial</h2><span>$ 950,00</span><span>$ 990,00</span>
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            html_path = f.name

        try:
            with patch.dict(os.environ, {"DOLARHOY_HTML_PATH": html_path}):
                prices = fetch_market_prices()
            self.assertEqual(1300.0, prices["blue_buy"])
        finally:
            os.unlink(html_path)


if __name__ == "__main__":
    unittest.main()
