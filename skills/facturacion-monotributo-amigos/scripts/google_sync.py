#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .close_lib import CloseError, dump_json, round_money
except ImportError:  # pragma: no cover
    from close_lib import CloseError, dump_json, round_money

GOOGLE_WRITE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _optional_google_clients():
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except Exception:
        return None, None
    return service_account, build


def _load_service_account(config: Dict[str, Any]):
    service_account, _ = _optional_google_clients()
    if not service_account:
        return None

    path = os.path.expanduser(os.path.expandvars(config["google"]["service_account_json"]))
    if not Path(path).exists():
        raise CloseError(f"missing service account file: {path}")

    return service_account.Credentials.from_service_account_file(path, scopes=GOOGLE_WRITE_SCOPES)


def _build_service(api: str, version: str, creds):
    _, build = _optional_google_clients()
    if not build:
        return None
    return build(api, version, credentials=creds, cache_discovery=False)


def build_debt_row(period: str, amount_ars: float, amount_usd: float, fx_rate: float, note: str = "") -> List[str]:
    return [period, f"{round_money(amount_ars, 2):.2f}", f"{round_money(amount_usd, 2):.2f}", f"{round_money(fx_rate, 2):.2f}", note]


def build_invoice_row(
    period: str,
    person_name: str,
    invoice_filename: str,
    invoice_drive_url: str,
    amount_ars: float,
    amount_usd: float,
    issue_date: date,
) -> List[str]:
    return [
        issue_date.isoformat(),
        period,
        person_name,
        invoice_filename,
        invoice_drive_url,
        f"{round_money(amount_ars, 2):.2f}",
        f"{round_money(amount_usd, 2):.2f}",
    ]


def append_sheet_row(
    spreadsheet_id: str,
    tab_name: str,
    row_values: List[str],
    config: Dict[str, Any],
    dry_run: bool,
) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "row": row_values, "tab": tab_name, "spreadsheet_id": spreadsheet_id}

    webhook = os.getenv("SHEETS_WRITE_WEBHOOK_URL")
    if webhook:
        payload = {
            "spreadsheet_id": spreadsheet_id,
            "tab_name": tab_name,
            "row_values": row_values,
        }
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        return {"status": "webhook", "response": body}

    creds = _load_service_account(config)
    if not creds:
        return {"status": "skipped", "reason": "google client dependencies missing"}

    sheets = _build_service("sheets", "v4", creds)
    if not sheets:
        return {"status": "skipped", "reason": "google sheets client unavailable"}

    result = (
        sheets.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]},
        )
        .execute()
    )
    return {"status": "ok", "updates": result.get("updates", {})}


def upload_invoice_file(file_path: Path, folder_id: str, config: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {
            "status": "dry_run",
            "file_name": file_path.name,
            "drive_url": f"https://drive.google.com/file/d/dry-run-{file_path.stem}/view",
        }

    webhook = os.getenv("DRIVE_UPLOAD_WEBHOOK_URL")
    if webhook:
        payload = {"folder_id": folder_id, "file_name": file_path.name}
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        # Green: parse drive_url from webhook JSON response when available.
        # Blue (fallback): return empty string if the webhook response doesn't include it.
        try:
            drive_url = json.loads(body).get("drive_url", "")
        except (json.JSONDecodeError, AttributeError):
            drive_url = ""
        return {"status": "webhook", "response": body, "drive_url": drive_url}

    creds = _load_service_account(config)
    if not creds:
        return {"status": "skipped", "reason": "google client dependencies missing", "drive_url": ""}

    try:
        from googleapiclient.http import MediaFileUpload  # type: ignore
    except Exception:
        return {"status": "skipped", "reason": "google drive media client unavailable", "drive_url": ""}

    drive = _build_service("drive", "v3", creds)
    if not drive:
        return {"status": "skipped", "reason": "google drive client unavailable", "drive_url": ""}

    metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), mimetype="application/pdf")
    created = drive.files().create(body=metadata, media_body=media, fields="id,webViewLink").execute()
    return {
        "status": "ok",
        "file_id": created.get("id"),
        "drive_url": created.get("webViewLink", ""),
    }


def read_last_month_amount(person: Dict[str, Any], period: str, config: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """Return the most recent ARS amount recorded in the person's debt sheet.

    Blue path (fallback): returns None when Google client dependencies are missing,
    the service account file doesn't exist, or the sheet has no data rows yet.
    Green path: reads the last row of the debt-registry tab and extracts the ARS amount.
    """
    if config is None:
        return None

    creds = _load_service_account(config)
    if not creds:
        return None

    sheets = _build_service("sheets", "v4", creds)
    if not sheets:
        return None

    spreadsheet_id = person.get("sheet_id", "")
    if not spreadsheet_id:
        return None

    try:
        from .close_lib import detect_header_indexes, normalize_header, parse_amount
    except ImportError:  # pragma: no cover
        from close_lib import detect_header_indexes, normalize_header, parse_amount

    debt_tab = (config.get("sheets") or {}).get("debt_registry", "Deuda")
    preferred = person.get("preferred_row_headers", {})

    try:
        result = (
            sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{debt_tab}!A:Z")
            .execute()
        )
    except Exception:
        return None

    rows = result.get("values", [])
    if len(rows) < 2:
        # No header + data rows yet.
        return None

    try:
        indexes = detect_header_indexes(rows[0], preferred)
    except Exception:
        return None

    ars_col = indexes.get("amount_ars")
    if ars_col is None:
        return None

    # Walk backwards to find the most recent non-empty ARS value.
    for row in reversed(rows[1:]):
        if ars_col < len(row) and row[ars_col].strip():
            try:
                return float(parse_amount(row[ars_col]))
            except Exception:
                continue
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Google Sheets/Drive helpers for monthly close")
    p.add_argument("--preview-row", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.preview_row:
        row = build_debt_row(period="2026-02", amount_ars=100000.0, amount_usd=80.0, fx_rate=1250.0)
        print(dump_json({"preview": row}))
        return 0
    print(dump_json({"ok": True, "message": "google_sync helpers ready"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
