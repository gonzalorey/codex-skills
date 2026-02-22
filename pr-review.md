# PR Review: facturacion-monotributo-amigos

**PR:** [#1 — Codex/facturacion monotributo amigos](https://github.com/gonzalorey/codex-skills/pull/1)
**Branch:** `codex/facturacion-monotributo-amigos`
**Reviewer:** Claude

---

## Summary

The skill is well-structured and the core orchestration logic is sound. However, there are several issues that need to be addressed before this is production-ready: two bugs that make advertised safety features non-functional, a security concern with committed IDs, and a template rendering bug that will corrupt WhatsApp messages.

---

## 🔴 Must Fix

### 1. `config.yaml` — Real resource IDs committed to the repo

**Files:** `config.yaml` lines 14, 26, 41, 44, 47

Real Google Spreadsheet IDs, Google Drive folder ID, and YNAB budget ID are committed in plaintext. While the YNAB personal access token correctly uses `${YNAB_PERSONAL_ACCESS_TOKEN}`, the other IDs are hardcoded.

**Recommended fix:** Move all resource IDs to environment variables or a gitignored local config file. Provide a `config.yaml.example` with placeholder values.

```yaml
# config.yaml.example
ynab:
  personal_access_token: ${YNAB_PERSONAL_ACCESS_TOKEN}
  budget_id: ${YNAB_BUDGET_ID}

people:
  - name: Contact Name
    sheet_id: ${CONTACT_SHEET_ID}
    ynab_account_id: ${CONTACT_YNAB_ACCOUNT_ID}
```

---

### 2. `assets/message_templates.md` — `\n` literals won't render as newlines

**File:** `assets/message_templates.md` lines 6–10

The templates contain literal `\n` (backslash + n), not actual newlines:

```
Hola {name}, te paso la factura del mes {period}.\n
Monto facturado: ARS {amount_ars}\n
```

The `_render_message()` function in `run_monthly_close.py` does a simple `str.replace()` and does **not** convert `\n` to actual newlines. The resulting WhatsApp message will contain literal `\n` characters.

**Recommended fix:** Either use actual newlines in the template, or add conversion in `_render_message()`:

```python
def _render_message(template: str, values: Dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered.replace("\\n", "\n")  # add this line
```

---

### 3. `scripts/google_sync.py` — `read_last_month_amount` is a non-functional placeholder

**File:** `scripts/google_sync.py` lines 168–170

```python
def read_last_month_amount(*_: Any, **__: Any) -> Optional[float]:
    # Placeholder for real read path. Keep deterministic fallback behavior in v1.
    return None
```

This always returns `None`. As a result, the amount-change guard in `_resolve_amounts()` can **never trigger** — the protection advertised by `--confirm-amount-change` is completely inactive. This is a significant correctness issue: the skill documents a safety feature that doesn't work.

**Required:** Implement the real sheet-read logic before shipping, or at minimum add a prominent warning in the SKILL.md that `--confirm-amount-change` is non-functional in v1.

---

### 4. `scripts/run_monthly_close.py` — Amount-change gate always evaluates to False

**File:** `scripts/run_monthly_close.py` line 179

```python
changed = last_amount_ars is not None and abs(fallback - float(last_amount_ars)) > 0.009
```

Directly caused by issue #3: since `read_last_month_amount()` always returns `None`, `last_amount_ars is not None` is always `False`, so `changed` is always `False`. The `if changed and not args.confirm_amount_change` block never executes.

This issue resolves automatically once #3 is fixed.

---

## 🟡 Should Fix

### 5. `scripts/google_sync.py` — Drive URL lost in webhook mode

**File:** `scripts/google_sync.py` line 143

```python
return {"status": "webhook", "response": body, "drive_url": ""}
```

When `DRIVE_UPLOAD_WEBHOOK_URL` is configured and the upload succeeds, the returned `drive_url` is an empty string. This empty URL is then written into the invoice registry Sheet, making the link non-functional.

**Recommended fix:** Either parse the `drive_url` from the webhook response body, or document that webhook mode does not support Drive URL tracking.

---

### 6. `scripts/run_monthly_close.py` — Fragile invoice-to-owner matching

**File:** `scripts/run_monthly_close.py` line 324

```python
owner = next((p for p in config["people"] if p["alias"].split("-")[-1] in invoice.name.lower()), None)
```

This takes only the last word of the alias (e.g., `"favelukes"` from `"santi-favelukes"`) and checks if it appears anywhere in the filename. Issues:

1. Any PDF whose name contains that substring gets assigned to that person, including unrelated files.
2. If both aliases share a suffix, whichever person appears first in the list wins all matching files.
3. Non-matching PDFs are silently ignored (`owner_not_detected`) instead of surfacing as a warning.

`config.yaml` already defines `filename_aliases` (`fave`, `olivieri`) which should be used here instead:

```python
owner = next(
    (p for p in config["people"]
     if any(alias in invoice.name.lower()
            for alias in config["invoice"]["filename_aliases"].get(p["alias"], [p["alias"].split("-")[-1]]))),
    None,
)
```

---

### 7. `scripts/run_monthly_close.py` — Custom YAML parser should use PyYAML

**File:** `scripts/run_monthly_close.py` lines 90–161

The custom `_parse_yaml_block` / `_parse_scalar` implementation is ~100 lines handling a subset of YAML. Known gaps: no tab-indentation support, no multi-line block scalars, no string-escape sequences, and list-item nested-key parsing is fragile.

`pyyaml` is widely available (`pip install pyyaml`) and `yaml.safe_load()` handles the full YAML spec safely:

```python
import yaml

def _load_config(path: str) -> Dict[str, Any]:
    config_path = expand_path(path)
    if not config_path.exists():
        raise CloseError(f"missing config file: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise CloseError("root config must be a map")
    return parsed
```

---

### 8. `scripts/fetch_fx.py` — Fragile regex HTML scraping

**File:** `scripts/fetch_fx.py` lines 38–52

The parser uses regex on raw HTML from `dolarhoy.com`. Any layout change will break FX calculation silently or raise a `CloseError`. The `(.{0,1500}?)` lookahead between sections is a fragile assumption.

**Recommended mitigations:**
- Use `html.parser` or `beautifulsoup4` for more robust DOM traversal.
- Add a fallback to a stable public API (e.g., `api.bcra.gob.ar` for official rates, or `bluelytics.com.ar` for blue rate).
- Add a `--fx-rate` CLI flag to allow manual override when scraping fails.

---

### 9. `scripts/ynab_sync.py` — Missing HTTP error handling

**File:** `scripts/ynab_sync.py` line 59

```python
with urllib.request.urlopen(req, timeout=20) as response:
    body = response.read().decode("utf-8", errors="ignore")
return {"status": "ok", "response": body, "transaction": transaction}
```

`urlopen()` raises `urllib.error.HTTPError` for non-2xx responses (401, 422, etc.). This exception propagates uncaught through `create_tracking_transaction()` → `main()`, producing an unformatted traceback instead of the structured JSON error format used everywhere else.

**Recommended fix:**

```python
import urllib.error

try:
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8", errors="ignore")
    return {"status": "ok", "response": body, "transaction": transaction}
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="ignore")
    return {"status": "error", "http_status": exc.code, "response": body, "transaction": transaction}
```

---

## 🔵 Minor / Suggestions

### 10. Missing `requirements.txt` for optional dependencies

The skill optionally uses `google-auth` and `google-api-python-client`. There is no `requirements.txt`, `pyproject.toml`, or install instructions in `SKILL.md`. Users who want the real Google API integration (not the fallback webhook mode) won't know what to install.

**Suggested addition to `SKILL.md`:**

```markdown
## Dependencias opcionales

Para integración real con Google Sheets/Drive:

```bash
pip install google-auth google-api-python-client
```
```

---

### 11. `config.yaml` — `fallback_amount_ars: 0` is a footgun

Both people have `fallback_amount_ars: 0`. If `read_last_month_amount()` is ever implemented and returns `None` (e.g., first-ever run with no historical data), the proposed invoice amount will be 0 ARS. This will silently pass the amount-change gate and create a YNAB transaction for 0. Set `fallback_amount_ars` to the actual expected monthly amounts, or require it to be non-zero.

---

## Tests

The existing test coverage is good for the functions tested (`close_lib`, `fetch_fx`, `headers`, date gate). However:

- There are no tests for the custom YAML parser (`_parse_yaml_block`, `_parse_scalar`).
- `test_amount_change_gate.py` patches `runner.read_last_month_amount` directly — it works, but this tight coupling will break if the function is moved.
- The E2E test uses a hardcoded future date `2026-02-27` — this is fine for now but worth a comment explaining why that date is in the window.
