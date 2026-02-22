"""Tests for ynab_sync HTTP error handling (blue/green)."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.request
from datetime import date
from unittest.mock import MagicMock, patch

from scripts.ynab_sync import _build_transaction, create_tracking_transaction


_TOKEN = "fake-token"
_BUDGET = "budget-1"
_ACCOUNT = "account-1"
_TODAY = date(2026, 2, 27)


def _make_call(**overrides):
    kwargs = dict(
        personal_access_token=_TOKEN,
        budget_id=_BUDGET,
        account_id=_ACCOUNT,
        amount_ars=100000.0,
        payee_name="Santi",
        memo="Deuda USD 2026-02",
        day=_TODAY,
        dry_run=False,
    )
    kwargs.update(overrides)
    return create_tracking_transaction(**kwargs)


class TestBuildTransaction(unittest.TestCase):
    def test_milliunits_conversion(self) -> None:
        t = _build_transaction("acct", 100000.0, "Santi", "memo", _TODAY)
        self.assertEqual(100_000_000, t["amount"])

    def test_negative_amount(self) -> None:
        t = _build_transaction("acct", -100000.0, "Santi", "memo", _TODAY)
        self.assertEqual(-100_000_000, t["amount"])

    def test_date_iso_format(self) -> None:
        t = _build_transaction("acct", 0, "X", "m", date(2026, 2, 27))
        self.assertEqual("2026-02-27", t["date"])


class TestCreateTrackingTransaction(unittest.TestCase):
    def test_dry_run_skips_network(self) -> None:
        result = _make_call(dry_run=True)
        self.assertEqual("dry_run", result["status"])
        self.assertIn("transaction", result)

    def test_missing_token_skips(self) -> None:
        result = _make_call(personal_access_token="")
        self.assertEqual("skipped", result["status"])
        self.assertIn("missing ynab token", result["reason"])

    def test_successful_post_returns_ok(self) -> None:
        """Green path: 201 response → status ok."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": {"transaction": {}}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _make_call()

        self.assertEqual("ok", result["status"])
        self.assertIn("transaction", result)

    def test_http_error_returns_error_dict(self) -> None:
        """Blue path: HTTP 4xx/5xx → structured error dict, no exception raised."""
        error_body = b'{"error": {"id": "401", "name": "unauthorized"}}'
        http_err = urllib.error.HTTPError(
            url="https://api.ynab.com/...",
            code=401,
            msg="Unauthorized",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(error_body),
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            result = _make_call()

        self.assertEqual("error", result["status"])
        self.assertEqual(401, result["http_status"])
        self.assertIn("transaction", result)

    def test_url_error_returns_error_dict(self) -> None:
        """Network failure → structured error dict with reason, no exception raised."""
        url_err = urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=url_err):
            result = _make_call()

        self.assertEqual("error", result["status"])
        self.assertIn("reason", result)
        self.assertIn("transaction", result)

    def test_500_error_captured(self) -> None:
        http_err = urllib.error.HTTPError(
            url="https://api.ynab.com/...",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b"server error"),
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            result = _make_call()

        self.assertEqual("error", result["status"])
        self.assertEqual(500, result["http_status"])


if __name__ == "__main__":
    unittest.main()
