# -*- coding: utf-8 -*-
"""
분석 모듈
- market_strength : 시장 강도 (상승/하락/보합 집계, 전체 + 시장별)
- build_tiers     : 등락률 티어표 (S~G)
- theme_analysis  : 테마별 평균 등락률 (상위/하위 10개)
"""

import config

FUND_PREFIXES = (
    "KODEX", "TIGER", "ACE", "RISE", "SOL", "PLUS", "HANARO", "KOSEF",
    "TIMEFOLIO", "ARIRANG", "KBSTAR", "KINDEX", "TREX", "FOCUS", "UNICORN",
    "마이티", "히어로즈",
)
NON_COMMON_KEYWORDS = (
    "ETN", "스팩", "SPAC", "리츠", "인프라", "선박투자", "부동산투자",
)


def _tier_of(rate: float):
    for name, lo, hi in config.TIERS:
        if lo <= rate < hi:
            return name
    return None


def _is_common_stock_name(name: str) -> bool:
    """요약 카운트에서 ETF/ETN/우선주/SPAC 등을 제외한다."""
    text = str(name).strip()
    upper = text.upper()

    if any(upper.startswith(prefix) for prefix in FUND_PREFIXES):
        return False
    if any(keyword in upper for keyword in NON_COMMON_KEYWORDS):
        return False
    if "우선주" in text:
        return False
    if text.endswith(("우", "우B", "우C")):
        return False
    if len(text) >= 3 and text[-3:-2].isdigit() and text.endswith(("우B", "우C")):
        return False
    if len(text) >= 2 and text[-2:-1].isdigit() and text.endswith("우"):
        return False
    return True


def _summary_universe(df):
    if "종목명" not in df.columns:
        return df
    return df[df["종목명"].apply(_is_common_stock_name)]


def _counts(sub):
    """상승/하락/보합 개수와 비율(%), 평균 등락률을 반환."""
    total = len(sub)
    up = int((sub["등락률"] > 0).sum())
    down = int((sub["등락률"] < 0).sum())
    flat = int((sub["등락률"] == 0).sum())
    avg_rate = round(float(sub["등락률"].mean()), 2) if total else 0.0

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    return {
        "total": total,
        "up": up, "down": down, "flat": flat,
        "up_pct": pct(up), "down_pct": pct(down), "flat_pct": pct(flat),
        "avg_rate": avg_rate,
    }


def market_strength(df):
    """전체 시장 강도와 KOSPI/KOSDAQ 시장별 강도를 반환."""
    summary_df = _summary_universe(df)
    overall = _counts(summary_df)
    by_market = {m: _counts(summary_df[summary_df["시장"] == m]) for m in ("KOSPI", "KOSDAQ")}
    return overall, by_market


def build_tiers(df):
    """티어이름 → 정렬된 DataFrame 딕셔너리 반환."""
    df = df.copy()
    df["티어"] = df["등락률"].apply(_tier_of)

    result = {}
    for name, _lo, _hi in config.TIERS:
        sub = df[df["티어"] == name]
        ascending = name in config.DOWN_TIERS   # 하락 티어는 낙폭 큰 순(오름차순)
        sub = sub.sort_values("등락률", ascending=ascending)
        if config.MAX_PER_TIER:
            sub = sub.head(config.MAX_PER_TIER)
        result[name] = sub
    return result


def theme_analysis(df, theme_map):
    """테마별 평균 등락률을 계산해 (상위10, 하위10) 반환."""
    # 코드+테마만 사용 (종목명 충돌 방지)
    tm = theme_map[["종목코드", "테마"]]
    merged = df.merge(tm, on="종목코드", how="inner")

    grp = (
        merged.groupby("테마")
        .agg(평균등락률=("등락률", "mean"), 종목수=("등락률", "size"))
        .reset_index()
    )
    grp["평균등락률"] = grp["평균등락률"].round(2)
    grp = grp[grp["종목수"] >= config.MIN_THEME_STOCKS]

    top = grp.sort_values("평균등락률", ascending=False).head(10).reset_index(drop=True)
    bottom = grp.sort_values("평균등락률", ascending=True).head(10).reset_index(drop=True)
    return top, bottom
