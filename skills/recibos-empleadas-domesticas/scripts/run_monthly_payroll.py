#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from payroll_lib import (
    SPREADSHEET_CONFIG,
    PayrollError,
    build_pagos_row,
    build_whatsapp_payload,
    check_rules_updates,
    compute_payroll_for_person,
    dump_json,
    load_local_json,
    load_person_data,
    parse_period,
    payroll_to_dict,
    today_gate,
    validation_payload,
)


def bool_arg(v: str) -> bool:
    return str(v).lower() in {"1", "true", "yes", "y"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run monthly payroll workflow for domestic workers")
    p.add_argument("--mode", choices=["dry-run", "real"], default="dry-run")
    p.add_argument("--period", help="YYYY-MM (defaults to current month)")
    p.add_argument("--simulate-arca", default="true")
    p.add_argument("--simulate-whatsapp", default="true")
    p.add_argument("--no-write-sheets", action="store_true")
    p.add_argument("--no-upload-drive", action="store_true")
    p.add_argument("--ignore-day-gate", action="store_true")
    p.add_argument("--state-dir", default=str(Path(__file__).resolve().parents[1] / ".state"))
    p.add_argument("--fixtures-dir", help="Directory containing <person>_<YYYY-MM>.json normalized inputs")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    simulate_arca = bool_arg(args.simulate_arca)
    simulate_whatsapp = bool_arg(args.simulate_whatsapp)

    period_start = parse_period(args.period)
    gate = today_gate(period_start, args.ignore_day_gate)
    if not gate["should_run"]:
        print(
            dump_json(
                {
                    "summary": gate["message"],
                    "validation_short": {},
                    "validation_detail": {},
                    "actions_taken": [],
                    "actions_blocked": ["date_gate"],
                }
            )
        )
        return 0

    actions_taken = [f"period={period_start.strftime('%Y-%m')}"]
    actions_blocked = []

    rules = check_rules_updates(Path(args.state_dir))
    if rules.get("status") == "textual_summary":
        actions_blocked.append("await_user_approval_for_rules")

    results = []
    for person_key in ("mariza", "irma"):
        if args.fixtures_dir:
            fixture_path = Path(args.fixtures_dir) / f"{person_key}_{period_start.strftime('%Y-%m')}.json"
            person_data = load_local_json(fixture_path)
        else:
            person_data = load_person_data(person_key)
        breakdown = compute_payroll_for_person(person_key, period_start, person_data)
        results.append(breakdown)

    rows = {b.person_key: build_pagos_row(b) for b in results}

    if args.mode == "dry-run" or args.no_write_sheets:
        actions_taken.append("sheets_write_skipped")
    elif os.getenv("SHEETS_WRITE_WEBHOOK_URL"):
        actions_taken.append("sheets_write_payload_ready")
    else:
        actions_blocked.append("sheets_write_missing_webhook")

    if args.mode == "dry-run" or args.no_upload_drive:
        actions_taken.append("drive_upload_skipped")
    elif os.getenv("DRIVE_UPLOAD_WEBHOOK_URL"):
        actions_taken.append("drive_upload_payload_ready")
    else:
        actions_blocked.append("drive_upload_missing_webhook")

    if simulate_arca or args.mode == "dry-run":
        actions_taken.append("arca_simulated_until_preconfirm")
    else:
        actions_taken.append("arca_real_mode_requested")

    wa = build_whatsapp_payload(results)
    if simulate_whatsapp or args.mode == "dry-run":
        actions_taken.append("whatsapp_simulated_not_sent")
    else:
        if os.getenv("WHATSAPP_PREP_WEBHOOK_URL"):
            actions_taken.append("whatsapp_payload_ready")
        else:
            actions_blocked.append("whatsapp_missing_webhook")

    validation = validation_payload(results, rules, args.mode)

    response = {
        "summary": {
            "mode": args.mode,
            "period": period_start.strftime("%Y-%m"),
            "workers": [payroll_to_dict(r) for r in results],
            "rules_check": rules,
            "approval_gate": "required_before_whatsapp_or_transfer",
        },
        "validation_short": validation["validation_short"],
        "validation_detail": validation["validation_detail"],
        "actions_taken": actions_taken,
        "actions_blocked": actions_blocked,
        "pagos_rows": rows,
        "whatsapp_payload": wa,
    }

    print(dump_json(response))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PayrollError as exc:
        print(dump_json({"error": str(exc)}))
        raise SystemExit(2)
