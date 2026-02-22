"""Tests for google_sync fixes: drive_url from webhook response (blue/green)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.google_sync import upload_invoice_file


_CONFIG = {
    "google": {"service_account_json": "/nonexistent/sa.json"},
}

_FOLDER_ID = "drive-folder-1"


class TestUploadInvoiceFileWebhook(unittest.TestCase):
    def test_dry_run_returns_mock_drive_url(self) -> None:
        result = upload_invoice_file(Path("/tmp/invoice_fave_2026-02.pdf"), _FOLDER_ID, _CONFIG, dry_run=True)
        self.assertEqual("dry_run", result["status"])
        self.assertIn("drive_url", result)
        self.assertIn("dry-run", result["drive_url"])

    def test_webhook_extracts_drive_url_from_json(self) -> None:
        """Green path: webhook returns JSON with drive_url – it must be propagated."""
        webhook_response = json.dumps({"drive_url": "https://drive.google.com/file/d/abc123/view"}).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = webhook_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("os.getenv", return_value="https://webhook.example.com/upload"):
                result = upload_invoice_file(Path("/tmp/invoice.pdf"), _FOLDER_ID, _CONFIG, dry_run=False)

        self.assertEqual("webhook", result["status"])
        self.assertEqual("https://drive.google.com/file/d/abc123/view", result["drive_url"])

    def test_webhook_missing_drive_url_returns_empty_string(self) -> None:
        """Blue path: webhook returns JSON without drive_url → empty string fallback."""
        webhook_response = json.dumps({"ok": True}).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = webhook_response
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("os.getenv", return_value="https://webhook.example.com/upload"):
                result = upload_invoice_file(Path("/tmp/invoice.pdf"), _FOLDER_ID, _CONFIG, dry_run=False)

        self.assertEqual("webhook", result["status"])
        self.assertEqual("", result["drive_url"])

    def test_webhook_non_json_response_returns_empty_drive_url(self) -> None:
        """Blue path: webhook returns non-JSON body → empty string, no crash."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"OK"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("os.getenv", return_value="https://webhook.example.com/upload"):
                result = upload_invoice_file(Path("/tmp/invoice.pdf"), _FOLDER_ID, _CONFIG, dry_run=False)

        self.assertEqual("webhook", result["status"])
        self.assertEqual("", result["drive_url"])

    def test_no_webhook_no_google_deps_skips_gracefully(self) -> None:
        """When no webhook URL and Google deps unavailable → status skipped."""
        with patch("os.getenv", return_value=None):
            result = upload_invoice_file(Path("/tmp/invoice.pdf"), _FOLDER_ID, _CONFIG, dry_run=False)
        self.assertEqual("skipped", result["status"])
        self.assertIn("drive_url", result)


if __name__ == "__main__":
    unittest.main()
