# -*- coding: utf-8 -*-
"""
네이버 금융 데이터 수집 모듈

전 종목 현재 스냅샷은 네이버 금융의 시장별 시가총액 페이지를 페이지네이션해서
수집합니다. 과거 날짜는 네이버 일봉 API가 종목 단위로만 제공되므로 현재 상장
종목 유니버스를 기준으로 종목별 일봉을 조회합니다.
"""

from __future__ import annotations

import ast
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from html import unescape
from io import StringIO

import pandas as pd
import requests

from . import config

COLUMNS = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량", "거래대금", "시가총액", "상장주식수"]
THEME_COLUMNS = ["종목코드", "종목명", "테마"]
SECTOR_COLUMNS = ["종목코드", "종목명", "섹터"]
INVESTOR_DEAL_COLUMNS = ["종목코드", "종목명", "시장", "투자자", "방향", "순매매금액"]

# sise_deal_rank_iframe.naver 한 행(<tr>): 종목명 링크 + number 컬럼 3개
# (순매매 수량 / 순매매 금액 / 당일거래량). 둘째 number(금액·백만원, 순매도는 음수)를
# 금액 기준으로 쓴다.
#
# 주의: 이 페이지는 한 응답에 '직전 거래일'과 '당일' 두 날짜 표를 모두 담고,
# 각 표 앞에 YY.MM.DD 라벨이 붙는다. 두 표를 다 읽으면 다른 날짜 데이터가 섞여
# 한 종목이 순매수·순매도 양쪽 1위로 잡히는 오류가 난다. 그래서 기준일(date)
# 라벨에 해당하는 표만 파싱한다.
_DEAL_RANK_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{2}")
_DEAL_RANK_TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_DEAL_RANK_CODE_RE = re.compile(r'/item/main\.naver\?code=(\d{6})"[^>]*>([^<]+)</a>')
_DEAL_RANK_NUM_RE = re.compile(r'<td class="number">(-?[\d,]+)</td>')

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MARKETS = {"KOSPI": 0, "KOSDAQ": 1}
FLOW_MARKETS = {"KOSPI": "01", "KOSDAQ": "02"}
# 투자자 순매매 거래상위 페이지의 sosok 코드(01=코스피, 02=코스닥)와 투자자 구분 코드.
DEAL_RANK_MARKETS = {"KOSPI": "01", "KOSDAQ": "02"}
DEAL_RANK_INVESTORS = {"institution": "1000", "foreign": "9000"}
# 순매수(buy)·순매도(sell) 두 방향. 바깥 sise_deal_rank.naver 는 iframe 껍데기뿐이라
# 실제 데이터가 든 iframe URL을 직접 호출한다(type 파라미터가 여기서만 동작).
DEAL_RANK_SIDES = {"buy": "buy", "sell": "sell"}
MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver"
INVESTOR_FLOW_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver"
DEAL_RANK_URL = "https://finance.naver.com/sise/sise_deal_rank_iframe.naver"
DAILY_URL = "https://api.finance.naver.com/siseJson.naver"
# 장중 분봉 지수: 한 번의 요청으로 09:00~현재까지 1분 간격 시계열을 준다.
# 응답 = [{"localDateTime":"YYYYMMDDHHMMSS","currentPrice":2634.12, ...}, ...]
INDEX_INTRADAY_URL = "https://api.stock.naver.com/chart/domestic/index/{code}/minute"
# 종목별 최신 뉴스: 응답 = [{"total":N,"items":[{officeId,articleId,officeName,
# title,datetime("YYYYMMDDHHMM"), ...}, ...]}, ...] (섹션별 묶음).
STOCK_NEWS_URL = "https://m.stock.naver.com/api/news/stock/{code}"
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


def collect_index_intraday(date_str: str, historical: bool = False, count: int = 400) -> dict:
    """KOSPI/KOSDAQ 장중 분봉 지수 시계열을 수집한다(시장당 요청 1번).

    카드 미니 차트용. 네이버 분봉 API는 *당일* 데이터만 주므로 과거(historical)
    빌드에선 빈 dict를 돌려줘 차트가 생략된다. 각 값은 09:00→현재 순서의
    종가 리스트([float, ...])이고, 한 종목이라도 실패하면 그 시장만 빈 리스트.
    """
    today = datetime.now().strftime("%Y%m%d")
    if historical and date_str != today:
        return {}

    out = {}
    for market in config.MARKETS:
        try:
            response = requests.get(
                INDEX_INTRADAY_URL.format(code=market),
                params={"count": count},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            rows = response.json()
            out[market] = [
                float(r["currentPrice"])
                for r in rows
                if str(r.get("localDateTime", ""))[:8] == date_str
                and r.get("currentPrice") is not None
            ]
        except Exception as exc:
            print(f"  · [안내] {market} 장중 지수 수집 실패: {exc}")
            out[market] = []
    return out


def collect_stock_news(codes, names=None, per: int = 5, max_workers: int = 8) -> dict:
    """종목코드 리스트 → {code: [{title, office, datetime, url}, ...]} (상위 per개).

    네이버 모바일 종목 뉴스 API를 종목당 1번 호출(쓰레드풀 병렬)해 빌드 시점에
    HTML 임베드용 데이터를 만든다. 정적 리포트라 클라이언트 라이브 호출이 불가해
    여기서 미리 수집한다. 실패하거나 뉴스 없는 종목은 결과에서 빠진다.

    정렬: 기본 최신순 → 그 위에 '제목에 종목명 포함' 기사를 앞으로(안정 정렬이라
    같은 그룹 내에선 최신순 유지). names(코드→종목명)가 있을 때만 적용한다. 네이버가
    종목에 곁가지로 묶은 기사보다 회사명이 직접 들어간 기사를 우선 노출하기 위함.
    """
    codes = [str(c).zfill(6) for c in dict.fromkeys(codes)]  # 중복 제거(순서 유지)
    names = names or {}

    def fetch(code):
        try:
            response = requests.get(
                STOCK_NEWS_URL.format(code=code),
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()
            items = []
            for group in response.json():
                items.extend(group.get("items", []))
            items.sort(key=lambda it: str(it.get("datetime", "")), reverse=True)
            name = names.get(code, "")
            if name:
                items.sort(
                    key=lambda it: name in unescape(str(it.get("title", ""))),
                    reverse=True,
                )

            out = []
            for it in items:
                oid, aid = str(it.get("officeId", "")), str(it.get("articleId", ""))
                title = unescape(str(it.get("title", ""))).strip()
                if not (oid and aid and title):
                    continue
                out.append({
                    "title": title,
                    "office": str(it.get("officeName", "")),
                    "datetime": str(it.get("datetime", "")),
                    "url": f"https://n.news.naver.com/mnews/article/{oid}/{aid}",
                })
                if len(out) >= per:
                    break
            return code, out
        except Exception:
            return code, []

    result = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for code, items in executor.map(fetch, codes):
            if items:
                result[code] = items
    return result


def collect_market_flows(date_str: str, historical: bool = False) -> dict:
    """KOSPI/KOSDAQ 투자자별 순매수 금액을 수집한다. 단위는 억원."""
    return {
        market: _read_investor_flow(date_str, sosok)
        for market, sosok in FLOW_MARKETS.items()
    }


def collect_market_flow_history(date_str: str, days: int = 7) -> dict:
    """KOSPI/KOSDAQ 투자자별 순매수를 date_str 기준 최근 days 거래일치 수집한다.

    네이버 매매동향 페이지는 한 응답에 여러 날짜가 들어 있어, collect_market_flows
    가 한 줄만 쓰던 같은 표에서 최근 N일치를 그대로 뽑는다. 각 시장값은 최신순
    리스트([{date,personal,foreign,institution}, ...])다. 단위는 억원.
    """
    return {
        market: _read_investor_flow_rows(date_str, sosok)[:days]
        for market, sosok in FLOW_MARKETS.items()
    }


# ── 로컬 리포트 폴백 ──────────────────────────────────────────
# 네이버 수집이 실패했을 때, 같은 날짜로 이미 만들어둔 로컬 리포트 HTML 에서
# 지수·수급 값을 정규식으로 복구한다. 이 정규식은 report_shared 가 생성하는
# 마크업(class="mkt-index", "flow-item" 등)에 의존하므로, 거기 구조가 바뀌면
# 같이 손봐야 한다.

def _local_report_candidates(date_str: str) -> list[str]:
    return [
        os.path.join("docs", config.MARKET_KEY, date_str, "index.html"),
        os.path.join(config.OUTPUT_DIR, config.REPORT_OUTPUT_DIR, config.report_filename(date_str)),
    ]


def _read_local_report(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _html_to_float(text):
    """리포트 HTML 안의 숫자 텍스트(콤마·%·억·HTML 엔티티 포함)를 float 으로."""
    text = unescape(str(text)).replace(",", "").replace("%", "").replace("억", "").strip()
    if text in ("", "N/A"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


_LOCAL_INDEX_RE = re.compile(
    r"<h3>(KOSPI|KOSDAQ)</h3>.*?"
    r'<span class="mkt-index mono">([^<]+)</span>.*?'
    r'<span class="mkt-rate mono [^"]+">([^<]+)</span>.*?'
    r'<span class="mkt-change mono [^"]+">([^<]+)</span>',
    re.S,
)
_LOCAL_FLOW_CARD_RE = re.compile(
    r'<div class="mkt-card">.*?<h3>(KOSPI|KOSDAQ)</h3>.*?'
    r'<div class="mkt-flow">(.*?)</div>',
    re.S,
)
_LOCAL_FLOW_ITEM_RE = re.compile(
    r'<span class="flow-item"><span>(기관|외인|개인)</span>'
    r'<b class="mono [^"]+">([^<]+)</b></span>',
    re.S,
)
_LOCAL_FLOW_KEY = {"기관": "institution", "외인": "foreign", "개인": "personal"}


def load_local_market_indices(date_str: str) -> dict:
    """네이버 지수 수집 실패 시 같은 날짜 로컬 HTML에서 지수 값을 복구한다."""
    for path in _local_report_candidates(date_str):
        html = _read_local_report(path)
        if html is None:
            continue

        indices = {}
        for market, value, rate, change in _LOCAL_INDEX_RE.findall(html):
            parsed = {
                "value": _html_to_float(value),
                "rate": _html_to_float(rate),
                "change": _html_to_float(change),
            }
            if all(v is not None for v in parsed.values()):
                indices[market] = parsed
        if indices:
            print(f"  · [안내] 로컬 HTML 지수값 사용: {path}")
            return indices
    return {}


def load_local_market_flows(date_str: str) -> dict:
    """네이버 수급 수집 실패 시 같은 날짜 로컬 HTML에서 투자자별 수급을 복구한다."""
    for path in _local_report_candidates(date_str):
        html = _read_local_report(path)
        if html is None:
            continue

        flows = {}
        for market, flow_html in _LOCAL_FLOW_CARD_RE.findall(html):
            parsed = {}
            for label, value in _LOCAL_FLOW_ITEM_RE.findall(flow_html):
                parsed[_LOCAL_FLOW_KEY[label]] = _html_to_float(value)
            if parsed:
                flows[market] = parsed
        if flows:
            print(f"  · [안내] 로컬 HTML 수급값 사용: {path}")
            return flows
    return {}


def collect_investor_deal(date_str: str, historical: bool = False) -> pd.DataFrame:
    """기관·외국인 순매수·순매도 거래상위 종목을 수집한다.

    네이버 `sise_deal_rank_iframe.naver` 페이지는 시장(코스피/코스닥)·투자자
    (기관/외국인)·방향(순매수/순매도)별 거래상위 종목과 실제 순매매 '금액'
    (백만원)을 제공한다. 한 응답에 직전 거래일·당일 두 날짜 표가 섞여 있어
    기준일(date_str) 라벨에 해당하는 표만 골라 읽는다(_read_deal_rank).

    과거(historical=True, 기준일 ≠ 오늘)에는 이 페이지가 당일 기준이라
    빈 DataFrame 을 반환한다.

    반환 컬럼: 종목코드, 종목명, 시장, 투자자(institution/foreign),
              방향(buy/sell), 순매매금액(원)
    """
    today = datetime.now().strftime("%Y%m%d")
    if historical and date_str != today:
        return pd.DataFrame(columns=INVESTOR_DEAL_COLUMNS)

    rows = []
    for investor, gubun in DEAL_RANK_INVESTORS.items():
        for side in DEAL_RANK_SIDES:
            for market, sosok in DEAL_RANK_MARKETS.items():
                for code, name, amount in _read_deal_rank(sosok, gubun, side, date_str):
                    rows.append((code, name, market, investor, side, amount))

    if not rows:
        return pd.DataFrame(columns=INVESTOR_DEAL_COLUMNS)

    out = pd.DataFrame(rows, columns=INVESTOR_DEAL_COLUMNS)
    out["종목코드"] = out["종목코드"].astype(str).str.zfill(6)
    out["종목명"] = out["종목명"].astype(str).str.strip()
    # 투자자·방향·종목 단위로 중복 제거(같은 종목이 양 시장에 겹칠 일은 없지만 안전망).
    out = out.drop_duplicates(subset=["투자자", "방향", "종목코드"]).reset_index(drop=True)
    return out[INVESTOR_DEAL_COLUMNS]


def _read_deal_rank(sosok: str, gubun: str, side: str, date_str: str) -> list[tuple[str, str, int]]:
    response = requests.get(
        DEAL_RANK_URL,
        params={"sosok": sosok, "investor_gubun": gubun, "type": side},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "euc-kr"

    html = _deal_rank_section_for(response.text, date_str)

    rows = []
    for tr in _DEAL_RANK_TR_RE.findall(html):
        code_match = _DEAL_RANK_CODE_RE.search(tr)
        nums = _DEAL_RANK_NUM_RE.findall(tr)
        if not code_match or len(nums) < 2:
            continue
        code, name = code_match.group(1), code_match.group(2)
        amount = _to_number(nums[1])   # 둘째 number = 순매매 금액(백만원, 순매도는 음수)
        if amount:
            # 원 단위로 환산해 저장(거래대금과 같은 억/조 표기 재사용). 크기로 비교·표시.
            rows.append((code, name.strip(), abs(amount) * 1_000_000))
    return rows


def _deal_rank_section_for(html: str, date_str: str) -> str:
    """기준일 표만 남기도록 HTML 을 날짜 라벨(YY.MM.DD) 경계로 자른다.

    페이지에 직전 거래일·당일 두 날짜 표가 섞여 있어, 날짜 라벨로 구간을 나눈 뒤
    기준일에 해당하는 구간만 반환한다. 라벨이 없거나(단일 날짜) 매칭 실패 시엔
    가장 마지막(최신) 구간을 반환한다(빈손 방지).
    """
    marks = list(_DEAL_RANK_DATE_RE.finditer(html))
    if not marks:
        return html

    target = datetime.strptime(date_str, "%Y%m%d").strftime("%y.%m.%d")
    # 각 라벨 위치에서 다음 라벨 직전까지를 한 구간으로 본다.
    segments = []
    for i, m in enumerate(marks):
        start = m.start()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        segments.append((m.group(0), html[start:end]))

    for label, seg in segments:
        if label == target:
            return seg
    return segments[-1][1]   # 매칭 실패 → 최신 구간


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


def _read_investor_flow_rows(date_str: str, sosok: str) -> list[dict]:
    """매매동향 표를 받아 date_str 이하 날짜 행들을 최신순 dict 리스트로 돌려준다.

    각 dict: {date(YYYYMMDD), personal, foreign, institution}. 단위 억원.
    표는 최신일이 맨 위라 그대로 슬라이스하면 최근 N일치가 된다.
    """
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

    rows = []
    for row in table.itertuples(index=False, name=None):
        iso = _flow_date_iso(row[0])
        if iso is None or iso > date_str:
            continue
        rows.append({
            "date": iso,
            "personal": _to_number(row[1]) or 0,
            "foreign": _to_number(row[2]) or 0,
            "institution": _to_number(row[3]) or 0,
        })
    if not rows:
        raise RuntimeError("네이버 투자자별 매매동향 날짜 행을 찾지 못했습니다")
    return rows


def _flow_date_iso(cell) -> str | None:
    """매매동향 표의 'yy.mm.dd' 날짜 셀을 'YYYYMMDD'로. 날짜가 아니면 None."""
    if pd.isna(cell):
        return None
    text = str(cell).strip()
    try:
        return datetime.strptime(text, "%y.%m.%d").strftime("%Y%m%d")
    except ValueError:
        return None


def _read_investor_flow(date_str: str, sosok: str) -> dict:
    rows = _read_investor_flow_rows(date_str, sosok)
    top = rows[0]
    return {
        "personal": top["personal"],
        "foreign": top["foreign"],
        "institution": top["institution"],
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
