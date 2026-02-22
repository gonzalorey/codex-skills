#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

try:
    from .close_lib import CloseError, dump_json, parse_amount, round_money
except ImportError:  # pragma: no cover
    from close_lib import CloseError, dump_json, parse_amount, round_money

DOLARHOY_URL = "https://dolarhoy.com/"
# Bluelytics public API — stable JSON endpoint, no scraping required.
BLUELYTICS_URL = "https://api.bluelytics.com.ar/v2/latest"


def calculate_pacted_fx(
    blue_buy: float,
    blue_sell: float,
    official_buy: float,
    official_sell: float,
    places: int = 2,
) -> float:
    avg = (blue_buy + blue_sell + official_buy + official_sell) / 4
    return float(round_money(avg, places))


def _extract_price_pair(section: str) -> tuple[float, float]:
    values = re.findall(r"\$\s*([0-9.,]+)", section)
    if len(values) < 2:
        raise CloseError("insufficient price points in section")
    return float(parse_amount(values[0])), float(parse_amount(values[1]))


def parse_dolarhoy_html(html: str) -> Dict[str, float]:
    blue_match = re.search(r"D[oó]lar Blue(.{0,1500}?)D[oó]lar", html, flags=re.IGNORECASE | re.DOTALL)
    official_match = re.search(r"D[oó]lar Oficial(.{0,1500}?)D[oó]lar", html, flags=re.IGNORECASE | re.DOTALL)

    if not blue_match:
        blue_match = re.search(r"D[oó]lar Blue(.{0,2500})", html, flags=re.IGNORECASE | re.DOTALL)
    if not official_match:
        official_match = re.search(r"D[oó]lar Oficial(.{0,2500})", html, flags=re.IGNORECASE | re.DOTALL)

    if not blue_match or not official_match:
        raise CloseError("could not find Blue/Oficial sections in dolarhoy HTML")

    blue_buy, blue_sell = _extract_price_pair(blue_match.group(1))
    official_buy, official_sell = _extract_price_pair(official_match.group(1))
    return {
        "blue_buy": blue_buy,
        "blue_sell": blue_sell,
        "official_buy": official_buy,
        "official_sell": official_sell,
    }


def fetch_bluelytics_prices() -> Dict[str, float]:
    """Green fallback: Bluelytics JSON API.

    Returns the same dict shape as ``parse_dolarhoy_html`` so callers are
    source-agnostic.  Raises ``CloseError`` on any network or parse failure.
    """
    req = urllib.request.Request(BLUELYTICS_URL, headers={"User-Agent": "monotributo-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise CloseError(f"bluelytics fetch failed: {exc}") from exc

    try:
        blue = data["blue"]
        official = data["oficial"]
        return {
            "blue_buy": float(blue["value_buy"]),
            "blue_sell": float(blue["value_sell"]),
            "official_buy": float(official["value_buy"]),
            "official_sell": float(official["value_sell"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise CloseError(f"unexpected bluelytics response shape: {exc}") from exc


def fetch_market_prices() -> Dict[str, float]:
    """Fetch market prices with blue/green fallback strategy.

    Blue path  — dolarhoy.com HTML scraping (original behaviour).
    Green path — Bluelytics JSON API (stable, no HTML parsing).

    Attempt order:
      1. Local HTML file override (``DOLARHOY_HTML_PATH`` env var) — useful for
         tests and offline runs.
      2. dolarhoy.com live scrape (blue).
      3. Bluelytics API (green fallback) — used automatically when step 2 fails.
    """
    html_path = os.getenv("DOLARHOY_HTML_PATH")
    if html_path:
        html = Path(html_path).read_text(encoding="utf-8")
        return parse_dolarhoy_html(html)

    # Blue: try dolarhoy scraping first.
    dolarhoy_error: Exception | None = None
    try:
        req = urllib.request.Request(DOLARHOY_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")
        return parse_dolarhoy_html(html)
    except (CloseError, urllib.error.URLError, Exception) as exc:
        dolarhoy_error = exc

    # Green: fall back to Bluelytics JSON API.
    try:
        return fetch_bluelytics_prices()
    except CloseError as fallback_exc:
        raise CloseError(
            f"all FX sources failed — dolarhoy: {dolarhoy_error}; bluelytics: {fallback_exc}"
        ) from fallback_exc


def resolve_fx(places: int = 2) -> Dict[str, Any]:
    prices = fetch_market_prices()
    rate = calculate_pacted_fx(
        prices["blue_buy"],
        prices["blue_sell"],
        prices["official_buy"],
        prices["official_sell"],
        places=places,
    )
    return {"prices": prices, "rate": rate}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch and calculate pacted USD exchange rate")
    p.add_argument("--rounding", type=int, default=2)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    payload = resolve_fx(places=args.rounding)
    print(dump_json(payload))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CloseError as exc:
        print(dump_json({"error": str(exc)}))
        raise SystemExit(2)
