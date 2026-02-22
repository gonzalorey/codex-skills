#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from payroll_lib import (
    PayrollError,
    compute_payroll_for_person,
    dump_json,
    load_local_json,
    parse_period,
    payroll_to_dict,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute payroll from normalized JSON input")
    p.add_argument("--period", required=True, help="YYYY-MM")
    p.add_argument("--person", choices=["mariza", "irma"], required=True)
    p.add_argument("--input", required=True, help="Path to normalized JSON with keys: Referencia Matrix, Eventos, Pagos")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    period = parse_period(args.period)
    payload = load_local_json(Path(args.input))
    result = compute_payroll_for_person(args.person, period, payload)
    print(dump_json(payroll_to_dict(result)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PayrollError as exc:
        print(dump_json({"error": str(exc)}))
        raise SystemExit(2)
