#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from .close_lib import (
        CloseError,
        dump_json,
        ensure_dir,
        evaluate_date_gate,
        expand_path,
        parse_period,
        round_money,
        yyyy_mm,
    )
    from .fetch_fx import resolve_fx
    from .google_sync import append_sheet_row, build_debt_row, build_invoice_row, read_last_month_amount, upload_invoice_file
    from .ynab_sync import create_tracking_transaction
except ImportError:  # pragma: no cover
    from close_lib import (
        CloseError,
        dump_json,
        ensure_dir,
        evaluate_date_gate,
        expand_path,
        parse_period,
        round_money,
        yyyy_mm,
    )
    from fetch_fx import resolve_fx
    from google_sync import append_sheet_row, build_debt_row, build_invoice_row, read_last_month_amount, upload_invoice_file
    from ynab_sync import create_tracking_transaction

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monthly close for friend invoicing and USD debt")
    p.add_argument("--mode", choices=["monthly-close"], default="monthly-close")
    p.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config.yaml"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-amount-change", action="store_true")
    p.add_argument("--invoice-dir", help="Folder containing ARCA-generated invoices in PDF")
    p.add_argument("--skip-ynab", action="store_true")
    p.add_argument("--skip-google", action="store_true")
    p.add_argument("--period", help="YYYY-MM. Defaults to current month in configured timezone")
    p.add_argument("--today", help="YYYY-MM-DD override for testing date gate")
    return p.parse_args()


def _parse_scalar(value: str) -> Any:
    raw = value.strip()
    if raw == "":
        return ""
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")) and len(raw) >= 2:
        return raw[1:-1]
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if raw.lower() in {"null", "none"}:
        return None
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if raw.startswith("${") and raw.endswith("}"):
        return raw
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _next_nonempty(lines: List[Tuple[int, str]], index: int) -> Tuple[int | None, str | None]:
    i = index
    while i < len(lines):
        indent, text = lines[i]
        if text:
            return indent, text
        i += 1
    return None, None


def _parse_yaml_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    container: Any = {}
    is_list = False

    while index < len(lines):
        cur_indent, text = lines[index]
        if not text:
            index += 1
            continue
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise CloseError(f"invalid indentation near: {text}")

        if text.startswith("- "):
            if not is_list:
                container = []
                is_list = True
            item_text = text[2:].strip()
            if ":" in item_text:
                key, raw = [part.strip() for part in item_text.split(":", 1)]
                item: Dict[str, Any] = {key: _parse_scalar(raw) if raw else None}
                index += 1
                next_indent, _ = _next_nonempty(lines, index)
                if next_indent is not None and next_indent > indent:
                    nested, index = _parse_yaml_block(lines, index, indent + 2)
                    if not isinstance(nested, dict):
                        raise CloseError("expected dict object for list item")
                    for k, v in nested.items():
                        item[k] = v
                container.append(item)
            elif item_text == "":
                index += 1
                nested, index = _parse_yaml_block(lines, index, indent + 2)
                container.append(nested)
            else:
                container.append(_parse_scalar(item_text))
                index += 1
            continue

        if is_list:
            break

        if ":" not in text:
            raise CloseError(f"invalid line: {text}")
        key, raw = [part.strip() for part in text.split(":", 1)]
        if raw:
            container[key] = _parse_scalar(raw)
            index += 1
            continue

        index += 1
        next_indent, _ = _next_nonempty(lines, index)
        if next_indent is None or next_indent <= indent:
            container[key] = {}
            continue
        nested, index = _parse_yaml_block(lines, index, indent + 2)
        container[key] = nested

    return container, index


def _load_config(path: str) -> Dict[str, Any]:
    """Load and parse the config file.

    Blue/green strategy:
      Green path — use PyYAML (``yaml.safe_load``) when available; it handles the
      full YAML spec and resolves ``${VAR}`` strings correctly as plain scalars.
      Blue path  — fall back to the built-in minimal parser when PyYAML is not
      installed, preserving backward compatibility without requiring an extra dep.
    """
    config_path = expand_path(path)
    if not config_path.exists():
        raise CloseError(f"missing config file: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    if text.strip().startswith("{"):
        return json.loads(text)

    # Green: prefer PyYAML for correct, spec-compliant parsing.
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise CloseError("root config must be a map")
        return parsed
    except ImportError:
        pass  # fall through to blue path

    # Blue: built-in minimal parser (no external deps).
    normalized: List[Tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            normalized.append((0, ""))
            continue
        indent = len(line) - len(line.lstrip(" "))
        normalized.append((indent, line.strip()))
    parsed, _ = _parse_yaml_block(normalized, 0, 0)
    if not isinstance(parsed, dict):
        raise CloseError("root config must be a map")
    return parsed


def _resolve_amounts(person: Dict[str, Any], fx_rate: float, period: str, args: argparse.Namespace, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fallback = float(person.get("fallback_amount_ars", 0))
    last_amount_ars = read_last_month_amount(person=person, period=period, config=config)
    proposed_ars = float(last_amount_ars if last_amount_ars is not None else fallback)
    proposed_usd = float(round_money(proposed_ars / fx_rate if fx_rate else 0, 2))

    changed = last_amount_ars is not None and abs(fallback - float(last_amount_ars)) > 0.009
    if changed and not args.confirm_amount_change:
        raise CloseError(
            f"amount changed for {person['name']} (historical {last_amount_ars}, proposed {proposed_ars}). "
            "rerun with --confirm-amount-change"
        )
    return {
        "amount_ars": proposed_ars,
        "amount_usd": proposed_usd,
        "changed": changed,
        "historical_amount_ars": last_amount_ars,
    }


def _load_template(skill_root: Path, key: str) -> str:
    template_path = skill_root / "assets" / "message_templates.md"
    content = template_path.read_text(encoding="utf-8")
    marker = f"## {key}"
    if marker not in content:
        raise CloseError(f"missing whatsapp template key: {key}")
    after = content.split(marker, 1)[1].strip()
    return after.split("## ", 1)[0].strip()


def _render_message(template: str, values: Dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    # Blue/green: convert legacy literal \n sequences from old templates to real newlines.
    # Templates should use actual newlines (green), but this handles the blue (legacy) case.
    rendered = rendered.replace("\\n", "\n")
    return rendered


def _collect_invoices(invoice_dir: Path | None) -> List[Path]:
    if not invoice_dir or not invoice_dir.exists():
        return []
    return sorted(p for p in invoice_dir.glob("*.pdf") if p.is_file())


def main() -> int:
    args = parse_args()
    config = _load_config(args.config)

    timezone = config.get("timezone", "America/Argentina/Buenos_Aires")
    gate_window = int(config.get("business_day_window", 3))
    today_override = date.fromisoformat(args.today) if args.today else None
    gate = evaluate_date_gate(timezone, gate_window, today=today_override)

    period_start = parse_period(args.period, timezone)
    period = yyyy_mm(period_start)

    skill_root = Path(__file__).resolve().parents[1]
    artifacts_dir = skill_root / "artifacts"
    ensure_dir(artifacts_dir)
    artifact_path = artifacts_dir / f"monthly-close-{period}.json"

    if not gate.should_run:
        response = {
            "summary": {"period": period, "status": "skipped", "reason": gate.reason},
            "actions_taken": [],
            "actions_blocked": ["date_gate"],
        }
        artifact_path.write_text(dump_json(response) + "\n", encoding="utf-8")
        print(dump_json(response))
        return 0

    fx_payload = resolve_fx(places=int(config.get("currency", {}).get("rounding", 2)))
    fx_rate = float(fx_payload["rate"])

    actions_taken: List[str] = ["date_gate_ok", "fx_calculated"]
    actions_blocked: List[str] = []
    people_summary: List[Dict[str, Any]] = []
    whatsapp_messages: Dict[str, str] = {}

    invoice_input_dir = expand_path(args.invoice_dir) if args.invoice_dir else expand_path(config["invoice"]["watch_dir"])
    invoice_files = _collect_invoices(invoice_input_dir)

    for person in config.get("people", []):
        person_amounts = _resolve_amounts(person, fx_rate, period, args, config=config)
        note = "Monto mensual por defecto (histórico)"

        debt_row = build_debt_row(
            period=period,
            amount_ars=person_amounts["amount_ars"],
            amount_usd=person_amounts["amount_usd"],
            fx_rate=fx_rate,
            note=note,
        )

        if args.skip_google:
            debt_result = {"status": "skipped", "reason": "skip_google flag"}
            actions_blocked.append(f"sheets_debt_{person['alias']}_skipped")
        else:
            debt_result = append_sheet_row(
                spreadsheet_id=person["sheet_id"],
                tab_name=config["sheets"]["debt_registry"],
                row_values=debt_row,
                config=config,
                dry_run=args.dry_run,
            )
            actions_taken.append(f"sheets_debt_{person['alias']}_{debt_result['status']}")

        template = _load_template(skill_root, person.get("whatsapp_template_key", "cierre_facturacion"))
        whatsapp_messages[person["alias"]] = _render_message(
            template,
            {
                "name": person["name"],
                "period": period,
                "amount_ars": f"{round_money(person_amounts['amount_ars'], 2):.2f}",
                "amount_usd": f"{round_money(person_amounts['amount_usd'], 2):.2f}",
                "fx_rate": f"{round_money(fx_rate, 2):.2f}",
                "invoice_reference": "pendiente_emision_ARCA",
            },
        )

        ynab_result = {"status": "skipped", "reason": "skip_ynab flag"}
        if not args.skip_ynab:
            entry_sign = int(config.get("ynab", {}).get("tracking_entry_sign", -1))
            token = os.path.expandvars(str(config.get("ynab", {}).get("personal_access_token", "")))
            if token.startswith("${"):
                token = os.getenv(token.strip("${}"), "")
            ynab_result = create_tracking_transaction(
                personal_access_token=token,
                budget_id=config["ynab"]["budget_id"],
                account_id=person["ynab_account_id"],
                amount_ars=person_amounts["amount_ars"] * entry_sign,
                payee_name=person["name"],
                memo=f"Deuda USD {period}",
                day=today_override or datetime.now().date(),
                dry_run=args.dry_run,
            )
            actions_taken.append(f"ynab_{person['alias']}_{ynab_result['status']}")

        people_summary.append(
            {
                "person": person["name"],
                "alias": person["alias"],
                "amount_ars": person_amounts["amount_ars"],
                "amount_usd": person_amounts["amount_usd"],
                "debt_row": debt_row,
                "sheets_result": debt_result,
                "ynab_result": ynab_result,
            }
        )

    # Build a lookup: alias → list of filename tokens to match against.
    # Green path: use explicit filename_aliases from config (e.g. {"santi-favelukes": "fave"}).
    # Blue path (fallback): if no alias entry exists, fall back to the last segment of the alias.
    _alias_cfg: Dict[str, Any] = (config.get("invoice") or {}).get("filename_aliases", {})

    def _matches_invoice(person: Dict[str, Any], filename: str) -> bool:
        alias = person["alias"]
        token = _alias_cfg.get(alias) or alias.split("-")[-1]
        return str(token).lower() in filename.lower()

    invoice_results: List[Dict[str, Any]] = []
    for invoice in invoice_files:
        owner = next((p for p in config["people"] if _matches_invoice(p, invoice.name)), None)
        if not owner:
            invoice_results.append({"file": invoice.name, "status": "ignored", "reason": "owner_not_detected"})
            continue

        if args.skip_google:
            upload_result = {"status": "skipped", "reason": "skip_google flag", "drive_url": ""}
        else:
            upload_result = upload_invoice_file(invoice, config["drive"]["invoice_folder_id"], config, args.dry_run)
            actions_taken.append(f"drive_upload_{invoice.name}_{upload_result['status']}")

        owner_summary = next(p for p in people_summary if p["alias"] == owner["alias"])
        invoice_row = build_invoice_row(
            period=period,
            person_name=owner["name"],
            invoice_filename=invoice.name,
            invoice_drive_url=upload_result.get("drive_url", ""),
            amount_ars=owner_summary["amount_ars"],
            amount_usd=owner_summary["amount_usd"],
            issue_date=today_override or datetime.now().date(),
        )

        if args.skip_google:
            invoice_sheet_result = {"status": "skipped", "reason": "skip_google flag"}
        else:
            inv_cfg = config["sheets"]["invoice_registry"]
            invoice_sheet_result = append_sheet_row(
                spreadsheet_id=inv_cfg["spreadsheet_id"],
                tab_name=inv_cfg["tab_name"],
                row_values=invoice_row,
                config=config,
                dry_run=args.dry_run,
            )
            actions_taken.append(f"sheets_invoice_{invoice.name}_{invoice_sheet_result['status']}")

        invoice_results.append(
            {
                "file": invoice.name,
                "owner": owner["name"],
                "upload_result": upload_result,
                "invoice_sheet_result": invoice_sheet_result,
            }
        )

    response = {
        "summary": {
            "period": period,
            "timezone": timezone,
            "fx": fx_payload,
            "people": people_summary,
            "invoices_processed": len(invoice_results),
        },
        "whatsapp_messages": whatsapp_messages,
        "invoice_results": invoice_results,
        "manual_checklist": [
            "Emitir facturas en ARCA (manual).",
            "Enviar facturas por WhatsApp usando los mensajes generados.",
            "Ajustar categorías del budget mensual en YNAB (manual).",
        ],
        "actions_taken": sorted(set(actions_taken)),
        "actions_blocked": sorted(set(actions_blocked)),
    }

    artifact_path.write_text(dump_json(response) + "\n", encoding="utf-8")
    print(dump_json(response))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CloseError as exc:
        print(dump_json({"error": str(exc)}))
        raise SystemExit(2)
