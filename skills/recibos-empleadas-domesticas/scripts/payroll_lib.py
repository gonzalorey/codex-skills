#!/usr/bin/env python3
from __future__ import annotations

import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

SPREADSHEET_CONFIG = {
    "mariza": {
        "name": "Mariza",
        "role": "cleaning_lady",
        "sheet_id": "1nsz2T2qn1LLpFDKfAXWZwbn8Obvch4-o0-77NAjGLSE",
        "drive_folder_id": "16Os9VpI8gArL_DZvMxb4DVD7hRFo3fxd",
        "whatsapp": "+54 9 11 3400-0914",
    },
    "irma": {
        "name": "Irma",
        "role": "nanny",
        "sheet_id": "1rLfGzbbRH9WnYIMmK1Vcf34ecCOzHVX_I6uvSh35erk",
        "drive_folder_id": "1CmeneePlD8Zc5R8PUGXfMQ48ngkHo4la",
        "whatsapp": "+54 9 11 3461-8519",
    },
}

LEGAL_SOURCES = [
    "https://www.arca.gob.ar/casasparticulares/categorias-y-remuneraciones/",
    "https://www.arca.gob.ar/casasparticulares/ayuda/empleador/vacaciones.asp",
    "https://www.arca.gob.ar/casasparticulares/ayuda/empleador/aguinaldo.asp",
    "https://www.boletinoficial.gob.ar/",
]

SPANISH_MONTHS = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sept",
    10: "oct",
    11: "nov",
    12: "dic",
}


@dataclass
class PayrollBreakdown:
    person_key: str
    person_name: str
    period: str
    basico: float
    antiguedad: float
    viaticos: float
    eventos: float
    subtotal: float
    otros: float
    total: float
    dias_habiles: float
    horas_dia: float
    horas_trabajadas: float
    event_items: List[Dict[str, Any]]
    autopilot_items: List[Dict[str, Any]]


class PayrollError(RuntimeError):
    pass


def parse_period(period: Optional[str]) -> dt.date:
    if period:
        try:
            year, month = period.split("-")
            return dt.date(int(year), int(month), 1)
        except Exception as exc:
            raise PayrollError(f"Invalid period '{period}', expected YYYY-MM") from exc
    today = dt.date.today()
    return dt.date(today.year, today.month, 1)


def parse_ars(value: Any) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace("AR$", "").replace("$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    if s in {"", "-", "--"}:
        return 0.0
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def format_ars(value: float) -> str:
    neg = value < 0
    v = abs(round(value, 2))
    whole, frac = f"{v:.2f}".split(".")
    chunks: List[str] = []
    while whole:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    grouped = ".".join(reversed(chunks))
    sign = "- " if neg else ""
    return f"{sign}AR${grouped},{frac}"


def parse_number(value: Any) -> float:
    s = str(value or "").strip().replace(" ", "")
    if not s:
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date_local(value: str) -> Optional[dt.date]:
    v = str(value or "").strip()
    if not v:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def normalize_key(text: str) -> str:
    t = text.lower().strip()
    repl = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "/": "_",
        " ": "_",
        "-": "_",
        "%": "pct",
    }
    for k, v in repl.items():
        t = t.replace(k, v)
    t = re.sub(r"[^a-z0-9_]+", "", t)
    return re.sub(r"_+", "_", t).strip("_")


def fetch_sheet_csv(sheet_id: str, tab_name: str) -> str:
    qs = urllib.parse.urlencode({"tqx": "out:csv", "sheet": tab_name})
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "codex-payroll-skill/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
        return resp.read().decode("utf-8", errors="replace")


def csv_to_rows(raw_csv: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(raw_csv.splitlines())
    out = []
    for row in reader:
        if not row:
            continue
        if all(str(v or "").strip() == "" for v in row.values()):
            continue
        out.append({k.strip(): (v or "").strip() for k, v in row.items() if k is not None})
    return out


def load_person_data(person_key: str) -> Dict[str, Any]:
    cfg = SPREADSHEET_CONFIG[person_key]
    tabs = ["Referencia Matrix", "Eventos", "Pagos"]
    data: Dict[str, Any] = {}
    for tab in tabs:
        raw = fetch_sheet_csv(cfg["sheet_id"], tab)
        data[tab] = csv_to_rows(raw)
    return data


def period_label(period_start: dt.date) -> str:
    return f"{SPANISH_MONTHS[period_start.month]} {period_start.year}"


def find_reference_row(reference_rows: List[Dict[str, str]], period_start: dt.date) -> Dict[str, str]:
    label = period_label(period_start)
    for row in reference_rows:
        if str(row.get("Período", "")).strip().lower() == label:
            return row
    raise PayrollError(f"No reference row for period '{label}'")


def get_float(row: Dict[str, str], *candidates: str) -> float:
    for key in candidates:
        if key in row and str(row.get(key, "")).strip() != "":
            v = row.get(key, "")
            if "AR$" in str(v) or "$" in str(v):
                return parse_ars(v)
            return parse_number(v)
    return 0.0


def collect_events(events_rows: List[Dict[str, str]], period_start: dt.date) -> List[Dict[str, Any]]:
    items = []
    for row in events_rows:
        event_date = parse_date_local(row.get("Fecha", ""))
        if not event_date:
            continue
        if event_date.year != period_start.year or event_date.month != period_start.month:
            continue
        amount = parse_ars(row.get("Monto adicional/descuento", ""))
        items.append(
            {
                "date": event_date.isoformat(),
                "type": row.get("Tipo de evento", ""),
                "description": row.get("Descripción", ""),
                "amount": round(amount, 2),
            }
        )
    return items


def _compute_base(reference_row: Dict[str, str]) -> Dict[str, float]:
    basico = get_float(reference_row, "Salario básico")
    horas_dia = get_float(reference_row, "Horas/día", "Horas diarias")
    basico_hora = get_float(reference_row, "Básico/hora", "Básico hora")
    dias_habiles = get_float(reference_row, "Días hábiles")
    dias_semana = get_float(reference_row, "Días por semana")
    semanas_mes = get_float(reference_row, "Semanas al mes")

    if basico <= 0 and horas_dia > 0 and basico_hora > 0:
        if dias_habiles > 0:
            basico = dias_habiles * horas_dia * basico_hora
        elif dias_semana > 0 and semanas_mes > 0:
            basico = dias_semana * semanas_mes * horas_dia * basico_hora

    antig_pct = get_float(reference_row, "Antiguedad")
    antiguedad = basico * (antig_pct / 100.0) if antig_pct > 0 else 0.0

    viaticos = get_float(reference_row, "Viáticos totales")
    if viaticos <= 0:
        viaticos_dia = get_float(reference_row, "Viáticos/día", "Viáticos por día")
        if viaticos_dia > 0:
            if dias_habiles > 0:
                viaticos = dias_habiles * viaticos_dia
            elif dias_semana > 0 and semanas_mes > 0:
                viaticos = dias_semana * semanas_mes * viaticos_dia

    return {
        "basico": round(basico, 2),
        "antiguedad": round(antiguedad, 2),
        "viaticos": round(viaticos, 2),
        "dias_habiles": round(dias_habiles if dias_habiles > 0 else (dias_semana * semanas_mes), 2),
        "horas_dia": round(horas_dia, 2),
    }


def compute_periodic_items(period_start: dt.date, subtotal: float, event_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    has_aguinaldo = any("aguinaldo" in str(e.get("type", "")).lower() for e in event_items)
    items: List[Dict[str, Any]] = []
    if period_start.month in {6, 12} and not has_aguinaldo:
        items.append(
            {
                "type": "Aguinaldo auto",
                "description": "Estimado automático (50% del subtotal mensual). Revisar antes de aprobar.",
                "amount": round(subtotal * 0.5, 2),
            }
        )
    return items


def compute_payroll_for_person(person_key: str, period_start: dt.date, person_data: Dict[str, Any]) -> PayrollBreakdown:
    ref_row = find_reference_row(person_data["Referencia Matrix"], period_start)
    base = _compute_base(ref_row)
    subtotal = round(base["basico"] + base["antiguedad"] + base["viaticos"], 2)

    event_items = collect_events(person_data["Eventos"], period_start)
    event_sum = round(sum(item["amount"] for item in event_items), 2)
    periodic_items = compute_periodic_items(period_start, subtotal, event_items)
    periodic_sum = round(sum(item["amount"] for item in periodic_items), 2)

    otros = periodic_sum
    total = round(subtotal + event_sum + otros, 2)

    return PayrollBreakdown(
        person_key=person_key,
        person_name=SPREADSHEET_CONFIG[person_key]["name"],
        period=period_start.strftime("%Y-%m"),
        basico=base["basico"],
        antiguedad=base["antiguedad"],
        viaticos=base["viaticos"],
        eventos=event_sum,
        subtotal=subtotal,
        otros=otros,
        total=total,
        dias_habiles=base["dias_habiles"],
        horas_dia=base["horas_dia"],
        horas_trabajadas=round(base["dias_habiles"] * base["horas_dia"], 2),
        event_items=event_items,
        autopilot_items=periodic_items,
    )


def payroll_to_dict(b: PayrollBreakdown) -> Dict[str, Any]:
    return {
        "person_key": b.person_key,
        "person_name": b.person_name,
        "period": b.period,
        "basico": b.basico,
        "antiguedad": b.antiguedad,
        "viaticos": b.viaticos,
        "eventos": b.eventos,
        "subtotal": b.subtotal,
        "otros": b.otros,
        "total": b.total,
        "dias_habiles": b.dias_habiles,
        "horas_dia": b.horas_dia,
        "horas_trabajadas": b.horas_trabajadas,
        "event_items": b.event_items,
        "autopilot_items": b.autopilot_items,
    }


def build_pagos_row(b: PayrollBreakdown) -> Dict[str, str]:
    p_date = dt.date(int(b.period[:4]), int(b.period[5:]), calendar.monthrange(int(b.period[:4]), int(b.period[5:]))[1])
    receipt_name = f"ReciboPago_{b.period.replace('-', '')}.pdf"

    if b.person_key == "mariza":
        return {
            "Fecha": f"{p_date.day}/{p_date.month}/{p_date.year}",
            "Mes": str(p_date.month),
            "Año": str(p_date.year),
            "Básico": format_ars(b.basico),
            "Antiguedad": format_ars(b.antiguedad),
            "Viáticos": format_ars(b.viaticos),
            "Eventos": format_ars(b.eventos),
            "Subtotal": format_ars(b.subtotal),
            "Otros": format_ars(b.otros),
            "Total": format_ars(b.total),
            "Notas": "",
            "Recibo": receipt_name,
        }

    return {
        "Fecha": f"{p_date.day}/{p_date.month}/{p_date.year}",
        "Mes": str(p_date.month),
        "Año": str(p_date.year),
        "Días hábiles": str(b.dias_habiles),
        "Ausencias": "0",
        "Total días trabajados": str(b.dias_habiles),
        "Horas trabajadas": str(b.horas_trabajadas),
        "Básico": format_ars(b.basico),
        "Antiguedad": format_ars(b.antiguedad),
        "Viáticos": format_ars(b.viaticos),
        "Subtotal": format_ars(b.subtotal),
        "Otros": format_ars(b.eventos + b.otros),
        "Total": format_ars(b.total),
        "Notas": "",
        "Recibo": receipt_name,
    }


def validation_payload(results: List[PayrollBreakdown], rules_check: Dict[str, Any], mode: str) -> Dict[str, Any]:
    short = {}
    detail = {}
    global_state = "OK"

    rules_state = "OK" if rules_check.get("status") == "no_change" else "REVISAR"
    short["normativa"] = rules_state

    for b in results:
        checks = {
            "insumos": "OK" if b.basico > 0 else "REVISAR",
            "cuadre": "OK" if round(b.subtotal + b.eventos + b.otros, 2) == round(b.total, 2) else "REVISAR",
            "coincidencia_arca_vs_pagos": "OK" if mode == "dry-run" else "REVISAR",
            "evidencia": "OK" if mode == "dry-run" else "REVISAR",
        }
        if "REVISAR" in checks.values():
            global_state = "REVISAR"
        detail[b.person_key] = checks
        short[b.person_name] = "OK" if "REVISAR" not in checks.values() else "REVISAR"

    if rules_state != "OK":
        global_state = "REVISAR"

    return {
        "global_status": global_state,
        "validation_short": short,
        "validation_detail": detail,
    }


def check_rules_updates(state_dir: Path) -> Dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "rules_hash.json"

    snippets: List[Dict[str, str]] = []
    hasher = hashlib.sha256()
    for source in LEGAL_SOURCES:
        snippet = ""
        try:
            req = urllib.request.Request(source, headers={"User-Agent": "codex-payroll-skill/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
                content = resp.read(4096).decode("utf-8", errors="replace")
                snippet = re.sub(r"\s+", " ", content[:350]).strip()
        except (urllib.error.URLError, TimeoutError, ValueError):
            snippet = "No se pudo consultar la fuente en esta corrida."
        snippets.append({"source": source, "snippet": snippet})
        hasher.update((source + "::" + snippet).encode("utf-8"))

    new_hash = hasher.hexdigest()
    old_hash = None
    if state_file.exists():
        old_hash = json.loads(state_file.read_text(encoding="utf-8")).get("hash")

    state_file.write_text(json.dumps({"hash": new_hash}, ensure_ascii=True, indent=2), encoding="utf-8")

    if old_hash and old_hash == new_hash:
        return {"status": "no_change", "sources": LEGAL_SOURCES}

    summary = "Se detectaron cambios o primera ejecución en fuentes ARCA/CNTCP. Revisar vigencias antes de aprobar."
    return {
        "status": "textual_summary",
        "summary": summary,
        "sources": LEGAL_SOURCES,
        "snippets": snippets,
    }


def build_whatsapp_payload(results: List[PayrollBreakdown]) -> Dict[str, Any]:
    deliveries = []
    for b in results:
        cfg = SPREADSHEET_CONFIG[b.person_key]
        deliveries.append(
            {
                "person": b.person_name,
                "phone": cfg["whatsapp"],
                "text": "",
                "attachment": f"ReciboPago_{b.period.replace('-', '')}.pdf",
                "status": "prepared_not_sent",
            }
        )
    return {"deliveries": deliveries, "send_enabled": False}


def today_gate(period_start: dt.date, ignore_day_gate: bool) -> Dict[str, Any]:
    if ignore_day_gate:
        return {"should_run": True, "message": "ignore_day_gate=true"}
    today = dt.date.today()
    if today.day != 1 and (today.year, today.month) == (period_start.year, period_start.month):
        return {"should_run": False, "message": "No payroll due this run"}
    return {"should_run": True, "message": "date gate passed"}


def load_local_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2)
