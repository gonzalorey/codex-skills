#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from payroll_lib import SPREADSHEET_CONFIG, dump_json


def main() -> int:
    p = argparse.ArgumentParser(description="Build or dispatch Drive upload payload")
    p.add_argument("--person", choices=["mariza", "irma"], required=True)
    p.add_argument("--period", required=True)
    p.add_argument("--pdf-path", required=True)
    p.add_argument("--apply", action="store_true", help="Dispatch to DRIVE_UPLOAD_WEBHOOK_URL")
    args = p.parse_args()

    cfg = SPREADSHEET_CONFIG[args.person]
    payload = {
        "person": cfg["name"],
        "period": args.period,
        "drive_folder_id": cfg["drive_folder_id"],
        "pdf_path": str(Path(args.pdf_path).resolve()),
        "file_name": f"ReciboPago_{args.period.replace('-', '')}.pdf",
    }

    if args.apply:
        webhook = os.getenv("DRIVE_UPLOAD_WEBHOOK_URL")
        if not webhook:
            print(dump_json({"status": "blocked", "reason": "missing DRIVE_UPLOAD_WEBHOOK_URL", "payload": payload}))
            return 1
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
            body = resp.read().decode("utf-8", errors="replace")
        print(dump_json({"status": "dispatched", "response": body, "payload": payload}))
        return 0

    print(dump_json({"status": "prepared", "payload": payload}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
