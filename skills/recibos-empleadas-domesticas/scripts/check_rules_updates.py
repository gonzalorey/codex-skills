#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from payroll_lib import check_rules_updates, dump_json


def main() -> int:
    p = argparse.ArgumentParser(description="Check ARCA/CNTCP rule source changes")
    p.add_argument("--state-dir", default=str(Path(__file__).resolve().parents[1] / ".state"))
    args = p.parse_args()
    result = check_rules_updates(Path(args.state_dir))
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
