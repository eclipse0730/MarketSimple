# -*- coding: utf-8 -*-
"""
데이터 수집 모듈

FinanceDataReader(FDR)로 KOSPI/KOSDAQ 데이터를 수집합니다.

결과는 항상 아래 7개 컬럼의 DataFrame 으로 통일됩니다.

[참고] FDR 의 StockListing 은 "현재 시점" 스냅샷입니다.
  - 12:00 에 실행하면 → 장중(오전장) 값
  - 15:40~16:00 에 실행하면 → 마감 값
  즉 '언제 실행하느냐'가 곧 세션이 됩니다.
  날짜를 명시하면 FDR KRX 캐시의 해당 날짜 CSV를 직접 조회합니다.
"""

import io
from datetime import datetime
import pandas as pd

COLUMNS = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량", "거래대금"]
THEME_COLUMNS = ["종목코드", "종목명", "테마"]


def collect(date_str: str, historical: bool = False) -> pd.DataFrame:
    """FDR로 전 종목 데이터를 수집한다."""
    return _collect_fdr(date_str if historical else None)


def collect_theme_map(date_str: str) -> pd.DataFrame:
    """FDR KRX 설명 캐시에서 전 종목 업종 기반 테마 맵을 가져온다."""
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    url = (
        "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/"
        f"refs/heads/master/data/listing/desc/{formatted_date}.csv"
    )
    df = _read_fdr_cache_csv(url, dtype={"Code": str})
    out = pd.DataFrame({
        "종목코드": df["Code"].astype(str).str.zfill(6),
        "종목명": df["Name"],
        "시장": df["Market"].map(_norm_market),
        "테마": df["Industry"],
    })
    out = out.dropna(subset=["시장", "테마"])
    out["테마"] = out["테마"].astype(str).str.strip()
    out = out[out["테마"] != ""]
    return out[THEME_COLUMNS].drop_duplicates().reset_index(drop=True)


# ──────────────────────────────────────────────
# FinanceDataReader (기본 소스, 로그인 불필요)
# ──────────────────────────────────────────────
def _norm_market(m):
    m = str(m).upper()
    if "KOSPI" in m:
        return "KOSPI"
    if "KOSDAQ" in m:
        return "KOSDAQ"
    return None  # KONEX 등은 PRD 범위 밖 → 제외


def _collect_fdr(date_str: str | None = None) -> pd.DataFrame:
    if date_str:
        return _collect_fdr_history(date_str)
    return _collect_fdr_snapshot()


def _collect_fdr_snapshot() -> pd.DataFrame:
    import FinanceDataReader as fdr

    df = fdr.StockListing("KRX")  # 전 종목 현재 스냅샷 (로그인 불필요)
    return _normalize_fdr_listing(df, empty_message="FDR 스냅샷이 비어 있습니다")


def _normalize_fdr_listing(df: pd.DataFrame, empty_message: str) -> pd.DataFrame:
    rate_col = next((c for c in ("ChagesRatio", "ChangesRatio") if c in df.columns), None)
    if rate_col is None:
        raise RuntimeError(f"등락률 컬럼을 찾을 수 없습니다. 보유 컬럼: {list(df.columns)}")

    out = pd.DataFrame({
        "종목코드": df["Code"].astype(str).str.zfill(6),
        "종목명":  df["Name"],
        "시장":    df["Market"].map(_norm_market),
        "현재가":  df["Close"],
        "등락률":  df[rate_col],
        "거래량":  df["Volume"],
        "거래대금": df["Amount"],
    })

    # KOSPI/KOSDAQ 만, 그리고 등락률·현재가가 있는 종목만 (신규상장·거래정지 제외)
    out = out.dropna(subset=["시장", "등락률", "현재가"]).reset_index(drop=True)
    if out.empty:
        raise RuntimeError(empty_message)
    return out[COLUMNS]


def _collect_fdr_history(date_str: str) -> pd.DataFrame:
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    url = (
        "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/"
        f"refs/heads/master/data/listing/krx/{formatted_date}.csv"
    )
    df = _read_fdr_cache_csv(url, dtype={"Code": str, "Dept": str, "ChangeCode": str, "MarketId": str})
    return _normalize_fdr_listing(df, empty_message="FDR 과거 조회 결과가 비어 있습니다 (휴장일이거나 날짜 오류)")


def _read_fdr_cache_csv(url: str, dtype: dict) -> pd.DataFrame:
    import requests

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.text), dtype=dtype)
