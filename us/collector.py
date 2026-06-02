# -*- coding: utf-8 -*-
"""미국 시장 EOD 데이터 수집기.

Polygon grouped daily endpoint로 특정 거래일의 전체 미국 주식 OHLCV를 가져옵니다.
API key는 POLYGON_API_KEY 환경변수로 전달합니다.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

COLUMNS = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량", "거래대금"]
THEME_COLUMNS = ["종목코드", "종목명", "테마"]

POLYGON_BASE_URL = "https://api.polygon.io"
REQUEST_TIMEOUT = 30
LOOKBACK_DAYS = 10

EXCHANGE_MAP = {
    "XNYS": "NYSE",
    "XNAS": "NASDAQ",
    "XASE": "AMEX",
    "ARCX": "ARCA",
    "BATS": "BATS",
}


def resolve_date(date_str: str | None = None) -> str:
    """명시 날짜가 없으면 최근 사용 가능한 미국장 EOD 날짜를 찾는다."""
    if date_str:
        return date_str

    today = datetime.utcnow().date()
    for offset in range(1, LOOKBACK_DAYS + 1):
        candidate = today - timedelta(days=offset)
        ymd = candidate.strftime("%Y%m%d")
        try:
            _read_grouped_day(_format_api_date(ymd))
            return ymd
        except RuntimeError:
            continue
    raise RuntimeError("최근 미국장 EOD 데이터를 찾지 못했습니다")


def collect(date_str: str, historical: bool = False) -> pd.DataFrame:
    """미국 전 종목 EOD 데이터를 수집한다."""
    target = _format_api_date(date_str)
    target_rows = _read_grouped_day(target)
    prev_date, prev_rows = _read_previous_grouped_day(datetime.strptime(target, "%Y-%m-%d"))
    metadata = _read_ticker_metadata()

    prev_close = {
        row["T"]: _to_float(row.get("c"))
        for row in prev_rows
        if row.get("T") and _to_float(row.get("c")) is not None
    }

    rows = []
    for item in target_rows:
        ticker = item.get("T")
        close = _to_float(item.get("c"))
        volume = _to_float(item.get("v")) or 0
        if not ticker or close is None:
            continue

        previous = prev_close.get(ticker)
        if not previous:
            continue

        meta = metadata.get(ticker, {})
        rate = round((close - previous) / previous * 100, 2)
        rows.append({
            "종목코드": ticker,
            "종목명": meta.get("name") or ticker,
            "시장": meta.get("market") or "US",
            "현재가": close,
            "등락률": rate,
            "거래량": int(volume),
            "거래대금": int(close * volume),
        })

    out = pd.DataFrame(rows, columns=COLUMNS)
    if out.empty:
        raise RuntimeError(f"미국장 EOD 정규화 결과가 비어 있습니다: {target}, prev={prev_date}")
    return out[COLUMNS]


def collect_theme_map(date_str: str) -> pd.DataFrame:
    return pd.DataFrame(columns=THEME_COLUMNS)


def _read_previous_grouped_day(target: datetime) -> tuple[str, list[dict]]:
    for offset in range(1, LOOKBACK_DAYS + 1):
        candidate = target - timedelta(days=offset)
        api_date = candidate.strftime("%Y-%m-%d")
        try:
            return api_date, _read_grouped_day(api_date)
        except RuntimeError:
            continue
    raise RuntimeError(f"{target:%Y-%m-%d} 기준 전 거래일 EOD 데이터를 찾지 못했습니다")


def _read_grouped_day(api_date: str) -> list[dict]:
    data = _polygon_get(
        f"/v2/aggs/grouped/locale/us/market/stocks/{api_date}",
        params={"adjusted": "true", "include_otc": "false"},
    )
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"Polygon grouped daily 결과가 비어 있습니다: {api_date}")
    return results


def _read_ticker_metadata() -> dict[str, dict]:
    metadata = {}
    params = {
        "market": "stocks",
        "locale": "us",
        "active": "true",
        "limit": 1000,
    }
    path = "/v3/reference/tickers"

    while path:
        data = _polygon_get(path, params=params)
        for item in data.get("results") or []:
            ticker = item.get("ticker")
            if not ticker:
                continue
            metadata[ticker] = {
                "name": item.get("name") or ticker,
                "market": _norm_exchange(item.get("primary_exchange")),
            }

        next_url = data.get("next_url")
        if not next_url:
            break
        path = next_url.replace(POLYGON_BASE_URL, "")
        params = {}
        time.sleep(0.15)

    return metadata


def _polygon_get(path: str, params: dict | None = None) -> dict:
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY 환경변수가 필요합니다")

    query = dict(params or {})
    query["apiKey"] = api_key
    response = requests.get(
        f"{POLYGON_BASE_URL}{path}",
        params=query,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") in {"ERROR", "NOT_AUTHORIZED"}:
        raise RuntimeError(data.get("error") or data.get("message") or "Polygon API 오류")
    return data


def _format_api_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")


def _norm_exchange(value) -> str:
    if not value:
        return "US"
    return EXCHANGE_MAP.get(str(value).upper(), "US")


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)
