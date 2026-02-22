#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from payroll_lib import dump_json, load_local_json, validation_payload


def main() -> int:
    p = argparse.ArgumentParser(description="Build short + detailed validation from payroll results")
    p.add_argument("--input", required=True, help="JSON file with keys workers, rules_check, mode")
    args = p.parse_args()

    payload = load_local_json(Path(args.input))
    workers = payload.get("workers", [])

    class B:
        pass

    tmp = []
    for w in workers:
        b = B()
        for k, v in w.items():
            setattr(b, k, v)
        tmp.append(b)

    result = validation_payload(tmp, payload.get("rules_check", {"status": "no_change"}), payload.get("mode", "dry-run"))
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
