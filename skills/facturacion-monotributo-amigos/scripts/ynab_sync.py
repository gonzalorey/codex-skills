#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import date
from typing import Any, Dict

try:
    from .close_lib import CloseError, dump_json
except ImportError:  # pragma: no cover
    from close_lib import CloseError, dump_json


def _build_transaction(account_id: str, amount_ars: float, payee_name: str, memo: str, day: date) -> Dict[str, Any]:
    milliunits = int(round(amount_ars * 1000))
    return {
        "account_id": account_id,
        "date": day.isoformat(),
        "amount": milliunits,
        "payee_name": payee_name,
        "memo": memo,
        "cleared": "cleared",
        "approved": True,
    }


def create_tracking_transaction(
    personal_access_token: str,
    budget_id: str,
    account_id: str,
    amount_ars: float,
    payee_name: str,
    memo: str,
    day: date,
    dry_run: bool,
) -> Dict[str, Any]:
    transaction = _build_transaction(account_id, amount_ars, payee_name, memo, day)
    if dry_run:
        return {"status": "dry_run", "transaction": transaction}

    if not personal_access_token:
        return {"status": "skipped", "reason": "missing ynab token", "transaction": transaction}

    url = f"https://api.ynab.com/v1/budgets/{budget_id}/transactions"
    payload = {"transaction": transaction}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {personal_access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="ignore")
        return {"status": "ok", "response": body, "transaction": transaction}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {"status": "error", "http_status": exc.code, "response": body, "transaction": transaction}
    except urllib.error.URLError as exc:
        return {"status": "error", "reason": str(exc.reason), "transaction": transaction}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="YNAB tracking sync")
    p.add_argument("--account-id", required=False)
    p.add_argument("--amount", type=float, default=1000.0)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    account_id = args.account_id or "demo-account"
    result = create_tracking_transaction(
        personal_access_token=os.getenv("YNAB_PERSONAL_ACCESS_TOKEN", ""),
        budget_id="demo-budget",
        account_id=account_id,
        amount_ars=args.amount,
        payee_name="Demo",
        memo="demo",
        day=date.today(),
        dry_run=args.dry_run,
    )
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CloseError as exc:
        print(dump_json({"error": str(exc)}))
        raise SystemExit(2)
