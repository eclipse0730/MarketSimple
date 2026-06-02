# -*- coding: utf-8 -*-
"""
네이버 금융 데이터 수집 모듈

전 종목 현재 스냅샷은 네이버 금융의 시장별 시가총액 페이지를 페이지네이션해서
수집합니다. 과거 날짜는 네이버 일봉 API가 종목 단위로만 제공되므로 현재 상장
종목 유니버스를 기준으로 종목별 일봉을 조회합니다.
"""

from __future__ import annotations

import ast
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import requests

COLUMNS = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량", "거래대금", "시가총액", "상장주식수"]
THEME_COLUMNS = ["종목코드", "종목명", "테마"]
SECTOR_COLUMNS = ["종목코드", "종목명", "섹터"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MARKETS = {"KOSPI": 0, "KOSDAQ": 1}
FLOW_MARKETS = {"KOSPI": "01", "KOSDAQ": "02"}
MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver"
INVESTOR_FLOW_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver"
DAILY_URL = "https://api.finance.naver.com/siseJson.naver"
SECTOR_LIST_URL = "https://finance.naver.com/sise/sise_group.naver"
SECTOR_DETAIL_URL = "https://finance.naver.com/sise/sise_group_detail.naver"
HISTORY_WORKERS = 8
SECTOR_WORKERS = 8

_SECTOR_LIST_RE = re.compile(r'sise_group_detail\.naver\?type=upjong&no=(\d+)">([^<]+)</a>')
_SECTOR_ITEM_RE = re.compile(r'/item/main\.naver\?code=(\d{6})">([^<]+)</a>')


def collect(date_str: str, historical: bool = False) -> pd.DataFrame:
    """네이버 금융에서 전 종목 데이터를 수집한다."""
    today = datetime.now().strftime("%Y%m%d")
    if historical and date_str != today:
        return _collect_history(date_str)
    return _collect_snapshot()


def collect_theme_map(date_str: str) -> pd.DataFrame:
    """네이버 수집기는 트렌드성 '테마' 일괄 데이터를 제공하지 않는다.

    테마는 수기(theme_map.csv)로 관리한다. 섹터(업종)는 collect_sector_map 참고.
    """
    return pd.DataFrame(columns=THEME_COLUMNS)


def collect_sector_map(date_str: str | None = None) -> pd.DataFrame:
    """네이버 업종 분류를 수집해 종목 1:1 섹터 매핑을 만든다.

    종목코드, 종목명, 섹터 3컬럼. 한 종목은 정확히 하나의 섹터에 속한다.
    섹터는 거의 바뀌지 않으므로 보통 캐시(sector_map.csv)로 쓰고 가끔만 재수집한다.
    date_str 은 API 대칭을 위한 인자로 결과에는 영향을 주지 않는다.
    """
    sectors = _read_sector_list()
    rows = []
    with ThreadPoolExecutor(max_workers=SECTOR_WORKERS) as executor:
        futures = {executor.submit(_read_sector_detail, no): name for no, name in sectors}
        for future in as_completed(futures):
            name = futures[future]
            try:
                items = future.result()
            except Exception:
                continue
            for code, stock_name in items:
                rows.append((code, stock_name, name))

    if not rows:
        return pd.DataFrame(columns=SECTOR_COLUMNS)

    out = pd.DataFrame(rows, columns=SECTOR_COLUMNS)
    out["종목코드"] = out["종목코드"].astype(str).str.zfill(6)
    out["종목명"] = out["종목명"].astype(str).str.strip()
    out["섹터"] = out["섹터"].astype(str).str.strip()
    out = out.drop_duplicates(subset=["종목코드"]).reset_index(drop=True)
    return out.sort_values(["섹터", "종목명"]).reset_index(drop=True)


def _read_sector_list() -> list[tuple[str, str]]:
    response = requests.get(
        SECTOR_LIST_URL,
        params={"type": "upjong"},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"
    pairs = _SECTOR_LIST_RE.findall(response.text)
    if not pairs:
        raise RuntimeError("네이버 업종 목록을 찾지 못했습니다")
    return [(no, name.strip()) for no, name in pairs]


def _read_sector_detail(no: str) -> list[tuple[str, str]]:
    response = requests.get(
        SECTOR_DETAIL_URL,
        params={"type": "upjong", "no": no},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"
    return [(code, name.strip()) for code, name in _SECTOR_ITEM_RE.findall(response.text)]


def collect_market_indices(date_str: str, historical: bool = False) -> dict:
    """KOSPI/KOSDAQ 지수 값을 수집한다."""
    today = datetime.now().strftime("%Y%m%d")
    if historical and date_str != today:
        return _collect_index_history(date_str)
    return _collect_index_snapshot()


def collect_market_flows(date_str: str, historical: bool = False) -> dict:
    """KOSPI/KOSDAQ 투자자별 순매수 금액을 수집한다. 단위는 억원."""
    return {
        market: _read_investor_flow(date_str, sosok)
        for market, sosok in FLOW_MARKETS.items()
    }


def _collect_snapshot() -> pd.DataFrame:
    frames = []
    for market, sosok in MARKETS.items():
        page = 1
        while True:
            part = _read_market_page(market, sosok, page)
            if part.empty:
                break
            frames.append(part)
            page += 1
            if page > 200:
                raise RuntimeError(f"네이버 {market} 페이지 수가 비정상적으로 많습니다")
            time.sleep(0.05)

    if not frames:
        raise RuntimeError("네이버 현재 스냅샷 조회 결과가 비어 있습니다")

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["시장", "등락률", "현재가"]).reset_index(drop=True)
    if out.empty:
        raise RuntimeError("네이버 현재 스냅샷 정규화 결과가 비어 있습니다")
    return out[COLUMNS]


def _read_market_page(market: str, sosok: int, page: int) -> pd.DataFrame:
    response = requests.get(
        MARKET_SUM_URL,
        params={"sosok": sosok, "page": page},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"

    tables = pd.read_html(StringIO(response.text))
    table = next((t for t in tables if "종목명" in t.columns and "현재가" in t.columns), None)
    if table is None:
        raise RuntimeError("네이버 시장 페이지에서 종목 테이블을 찾지 못했습니다")

    table = table.dropna(subset=["종목명", "현재가"]).reset_index(drop=True)
    if table.empty:
        return pd.DataFrame(columns=COLUMNS)

    codes = _extract_codes(response.text)
    if len(codes) < len(table):
        raise RuntimeError(
            f"네이버 시장 페이지 종목코드 수가 부족합니다: market={market}, page={page}, "
            f"codes={len(codes)}, rows={len(table)}"
        )

    out = pd.DataFrame({
        "종목코드": codes[:len(table)],
        "종목명": table["종목명"].astype(str).str.strip(),
        "시장": market,
        "현재가": table["현재가"].map(_to_number),
        "등락률": table["등락률"].map(_to_rate),
        "거래량": table["거래량"].map(_to_number) if "거래량" in table.columns else 0,
    })
    out["거래대금"] = (out["현재가"].fillna(0) * out["거래량"].fillna(0)).astype("int64")

    # 네이버 표기 단위 → 원/주 단위로 통일 (시총: 억원, 상장주식수: 천주)
    if "시가총액" in table.columns:
        cap_eok = table["시가총액"].map(_to_number)
        out["시가총액"] = (cap_eok.fillna(0) * 100_000_000).astype("int64")
    else:
        out["시가총액"] = 0
    if "상장주식수" in table.columns:
        shares_k = table["상장주식수"].map(_to_number)
        out["상장주식수"] = (shares_k.fillna(0) * 1000).astype("int64")
    else:
        out["상장주식수"] = 0

    return out[COLUMNS]


def _read_investor_flow(date_str: str, sosok: str) -> dict:
    response = requests.get(
        INVESTOR_FLOW_URL,
        params={"bizdate": date_str, "sosok": sosok, "page": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"

    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError("네이버 투자자별 매매동향 테이블을 찾지 못했습니다")

    table = tables[0].dropna(how="all")
    if table.empty:
        raise RuntimeError("네이버 투자자별 매매동향 결과가 비어 있습니다")

    target_label = datetime.strptime(date_str, "%Y%m%d").strftime("%y.%m.%d")
    selected = None
    for row in table.itertuples(index=False, name=None):
        if str(row[0]).strip() == target_label:
            selected = row
            break
    if selected is None:
        selected = next((row for row in table.itertuples(index=False, name=None) if not pd.isna(row[0])), None)
    if selected is None:
        raise RuntimeError("네이버 투자자별 매매동향 날짜 행을 찾지 못했습니다")

    return {
        "personal": _to_number(selected[1]) or 0,
        "foreign": _to_number(selected[2]) or 0,
        "institution": _to_number(selected[3]) or 0,
    }


def _collect_index_snapshot() -> dict:
    return {market: _read_index_page(market) for market in ("KOSPI", "KOSDAQ")}


def _read_index_page(market: str) -> dict:
    response = requests.get(
        "https://finance.naver.com/sise/sise_index.naver",
        params={"code": market},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"

    value_match = re.search(r'<em id="now_value">([^<]+)</em>', response.text)
    change_match = re.search(
        r'<span class="fluc" id="change_value_and_rate">\s*<span>([^<]+)</span>\s*([+-]?[0-9.,]+)%',
        response.text,
        re.S,
    )
    if value_match is None or change_match is None:
        raise RuntimeError(f"네이버 {market} 지수 값을 찾지 못했습니다")

    value = _to_float(value_match.group(1))
    change = _to_float(change_match.group(1))
    rate = _to_float(change_match.group(2))
    if rate is not None and rate < 0:
        change = -abs(change)
    return {"value": value, "change": change, "rate": rate}


def _collect_index_history(date_str: str) -> dict:
    target = datetime.strptime(date_str, "%Y%m%d")
    return {
        market: _read_index_daily_row(market, target)
        for market in ("KOSPI", "KOSDAQ")
    }


def _read_index_daily_row(market: str, target: datetime) -> dict:
    start = (target - timedelta(days=14)).strftime("%Y%m%d")
    end = target.strftime("%Y%m%d")
    response = requests.get(
        DAILY_URL,
        params={
            "symbol": market,
            "requestType": 1,
            "startTime": start,
            "endTime": end,
            "timeframe": "day",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()

    data = _parse_sise_json(response.text)
    if len(data) < 2:
        raise RuntimeError(f"네이버 {market} 지수 일봉 조회 결과가 비어 있습니다")

    header = data[0]
    values = [dict(zip(header, row)) for row in data[1:] if len(row) == len(header)]
    target_row = next((row for row in values if str(row.get("날짜")) == end), None)
    if target_row is None:
        raise RuntimeError(f"네이버 {market} 지수에 {end} 데이터가 없습니다")

    target_idx = values.index(target_row)
    if target_idx == 0:
        raise RuntimeError(f"네이버 {market} 지수의 전일 종가를 찾지 못했습니다")

    close = _to_float(target_row.get("종가"))
    prev_close = _to_float(values[target_idx - 1].get("종가"))
    if close is None or not prev_close:
        raise RuntimeError(f"네이버 {market} 지수 종가를 파싱하지 못했습니다")

    change = round(close - prev_close, 2)
    rate = round(change / prev_close * 100, 2)
    return {"value": close, "change": change, "rate": rate}


def _collect_history(date_str: str) -> pd.DataFrame:
    target = datetime.strptime(date_str, "%Y%m%d")
    universe = _collect_snapshot()[["종목코드", "종목명", "시장"]]
    rows = []

    print(f"  · 네이버 과거 일봉 종목별 조회: {len(universe):,}개")
    with ThreadPoolExecutor(max_workers=HISTORY_WORKERS) as executor:
        futures = {
            executor.submit(_read_daily_row, row.종목코드, target): row
            for row in universe.itertuples(index=False)
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            base = futures[future]
            daily = future.result()
            if daily is not None:
                rows.append({
                    "종목코드": base.종목코드,
                    "종목명": base.종목명,
                    "시장": base.시장,
                    **daily,
                })
            if idx % 200 == 0:
                print(f"    - 진행 {idx:,}/{len(universe):,}, 수집 {len(rows):,}")

    out = pd.DataFrame(rows, columns=COLUMNS)
    if out.empty:
        raise RuntimeError("네이버 과거 일봉 조회 결과가 비어 있습니다 (휴장일이거나 날짜 오류)")
    # 과거 일봉 API엔 시총·상장주식수가 없다 → 0으로 채워 컬럼 일관성 유지
    out["시가총액"] = out["시가총액"].fillna(0).astype("int64")
    out["상장주식수"] = out["상장주식수"].fillna(0).astype("int64")
    return out[COLUMNS]


def _read_daily_row(code: str, target: datetime) -> dict | None:
    start = (target - timedelta(days=14)).strftime("%Y%m%d")
    end = target.strftime("%Y%m%d")
    response = requests.get(
        DAILY_URL,
        params={
            "symbol": code,
            "requestType": 1,
            "startTime": start,
            "endTime": end,
            "timeframe": "day",
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"https://finance.naver.com/item/main.naver?code={code}",
        },
        timeout=15,
    )
    response.raise_for_status()

    data = _parse_sise_json(response.text)
    if len(data) < 2:
        return None

    header = data[0]
    values = [dict(zip(header, row)) for row in data[1:] if len(row) == len(header)]
    target_row = next((row for row in values if str(row.get("날짜")) == end), None)
    if target_row is None:
        return None

    target_idx = values.index(target_row)
    if target_idx == 0:
        return None

    prev_close = _to_number(values[target_idx - 1].get("종가"))
    close = _to_number(target_row.get("종가"))
    volume = _to_number(target_row.get("거래량")) or 0
    if not prev_close or close is None:
        return None

    rate = round((close - prev_close) / prev_close * 100, 2)
    return {
        "현재가": close,
        "등락률": rate,
        "거래량": volume,
        "거래대금": int(close * volume),
    }


def _parse_sise_json(text: str) -> list:
    cleaned = text.strip()
    if not cleaned:
        return []
    try:
        parsed = ast.literal_eval(cleaned)
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError("네이버 일봉 응답을 파싱하지 못했습니다") from exc
    return parsed if isinstance(parsed, list) else []


def _extract_codes(html: str) -> list[str]:
    seen = set()
    codes = []
    for code in re.findall(r"/item/main\.naver\?code=([0-9A-Z]{6})", html):
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _to_number(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    if text in ("", "nan", "N/A"):
        return None
    return int(float(text))


def _to_float(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if text in ("", "nan", "N/A"):
        return None
    return float(text)


def _to_rate(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("%", "").replace(",", "").strip()
    text = text.replace("＋", "+").replace("－", "-")
    if text in ("", "nan", "N/A"):
        return None
    return float(text)
