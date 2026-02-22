#!/usr/bin/env python3
from __future__ import annotations

import calendar
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo


class CloseError(RuntimeError):
    """Workflow-level error for monthly close."""


@dataclass(frozen=True)
class DateGateResult:
    should_run: bool
    reason: str


def parse_period(period: str | None, tz_name: str) -> date:
    if period:
        return datetime.strptime(period, "%Y-%m").date().replace(day=1)
    now = datetime.now(ZoneInfo(tz_name)).date()
    return now.replace(day=1)


def round_money(value: float | Decimal, places: int = 2) -> Decimal:
    quant = Decimal("1").scaleb(-places)
    return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)


def dump_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def business_days_for_month(year: int, month: int) -> List[date]:
    _, last_day = calendar.monthrange(year, month)
    values: List[date] = []
    for d in range(1, last_day + 1):
        current = date(year, month, d)
        if current.weekday() < 5:
            values.append(current)
    return values


def is_last_n_business_days(target: date, window: int) -> bool:
    if target.weekday() >= 5:
        return False
    business_days = business_days_for_month(target.year, target.month)
    return target in business_days[-window:]


def evaluate_date_gate(tz_name: str, window: int, today: date | None = None) -> DateGateResult:
    local_today = today or datetime.now(ZoneInfo(tz_name)).date()
    if not is_last_n_business_days(local_today, window):
        return DateGateResult(
            should_run=False,
            reason=f"skip: {local_today.isoformat()} outside last {window} business days",
        )
    return DateGateResult(should_run=True, reason="ok")


def parse_amount(text: str) -> Decimal:
    normalized = text.strip().replace(" ", "")
    if not normalized:
        return Decimal("0")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    return Decimal(normalized)


def expand_path(path_value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path_value))).resolve()


def normalize_header(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch.isalnum())


def detect_header_indexes(headers: Iterable[str], preferred: Dict[str, List[str]]) -> Dict[str, int]:
    normalized_map = {normalize_header(h): idx for idx, h in enumerate(headers)}
    indexes: Dict[str, int] = {}
    for logical_key, aliases in preferred.items():
        for alias in aliases:
            alias_key = normalize_header(alias)
            if alias_key in normalized_map:
                indexes[logical_key] = normalized_map[alias_key]
                break
    missing = sorted(set(preferred.keys()) - set(indexes.keys()))
    if missing:
        raise CloseError(f"missing headers: {', '.join(missing)}")
    return indexes


def yyyy_mm(value: date) -> str:
    return value.strftime("%Y-%m")
