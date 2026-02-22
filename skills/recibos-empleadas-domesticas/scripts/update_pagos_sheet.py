#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from payroll_lib import build_pagos_row, compute_payroll_for_person, dump_json, load_local_json, parse_period


def main() -> int:
    p = argparse.ArgumentParser(description="Build or dispatch payload to append Pagos row")
    p.add_argument("--person", choices=["mariza", "irma"], required=True)
    p.add_argument("--period", required=True)
    p.add_argument("--input", required=True, help="JSON normalized source")
    p.add_argument("--apply", action="store_true", help="Dispatch to SHEETS_WRITE_WEBHOOK_URL")
    args = p.parse_args()

    payload = load_local_json(Path(args.input))
    breakdown = compute_payroll_for_person(args.person, parse_period(args.period), payload)
    row = build_pagos_row(breakdown)
    out = {"person": args.person, "period": args.period, "row": row}

    if args.apply:
        webhook = os.getenv("SHEETS_WRITE_WEBHOOK_URL")
        if not webhook:
            print(dump_json({"status": "blocked", "reason": "missing SHEETS_WRITE_WEBHOOK_URL", "payload": out}))
            return 1
        req = urllib.request.Request(
            webhook,
            data=json.dumps(out).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
            body = resp.read().decode("utf-8", errors="replace")
        print(dump_json({"status": "dispatched", "response": body, "payload": out}))
        return 0

    print(dump_json({"status": "prepared", "payload": out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
