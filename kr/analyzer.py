# -*- coding: utf-8 -*-
"""
분석 모듈
- market_strength : 시장 강도 (상승/하락/보합 집계, 전체 + 시장별)
- build_tiers     : 등락률 티어표 (S~G)
- theme_analysis  : 테마별 평균 등락률 (상위/하위 10개)
"""

from . import config

FUND_PREFIXES = (
    "KODEX", "TIGER", "ACE", "RISE", "SOL", "PLUS", "HANARO", "KOSEF",
    "TIMEFOLIO", "ARIRANG", "KBSTAR", "KINDEX", "TREX", "FOCUS", "UNICORN",
    "마이티", "히어로즈",
)
NON_COMMON_KEYWORDS = (
    "ETN", "스팩", "SPAC", "리츠", "인프라", "선박투자", "부동산투자",
)


def _tier_of(rate: float):
    return _tier_of_value(rate, config.TIERS)


def _tier_of_value(value: float, tiers):
    for name, lo, hi in tiers:
        if lo <= hi and lo <= value < hi:
            return name
        if lo > hi and hi < value <= lo:
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
    """전체 시장 강도와 시장별 강도를 반환."""
    summary_df = _summary_universe(df)
    overall = _counts(summary_df)
    by_market = {m: _counts(summary_df[summary_df["시장"] == m]) for m in config.MARKETS}
    return overall, by_market


def build_tiers(df, common_only=False):
    """티어이름 → 정렬된 DataFrame 딕셔너리 반환.

    common_only=True 이면 ETF/ETN/우선주/스팩 등을 제외한 보통주만 분류한다.
    """
    if common_only:
        df = _summary_universe(df)
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


def top_trading_value(df, n=30, common_only=False):
    """거래대금 상위 n개 종목을 DataFrame으로 반환.

    common_only=True 이면 ETF/ETN/우선주/스팩 등을 제외한 보통주만 집계한다.
    (지금은 전 종목 기준이지만, 나중에 보통주만 뽑고 싶을 때 켜면 된다.)
    """
    if "거래대금" not in df.columns:
        return df.head(0)
    base = _summary_universe(df) if common_only else df
    ranked = base.sort_values("거래대금", ascending=False).head(n)
    return ranked.reset_index(drop=True)


def _group_analysis(df, group_map, col, min_stocks, n=10):
    """그룹(테마/섹터)별 평균 등락률을 계산해 (상위n, 하위n) 반환.

    반환 DataFrame 컬럼: [col, 평균등락률, 종목수]
    """
    # 코드+그룹만 사용 (종목명 충돌 방지)
    gm = group_map[["종목코드", col]]
    merged = df.merge(gm, on="종목코드", how="inner")

    grp = (
        merged.groupby(col)
        .agg(평균등락률=("등락률", "mean"), 종목수=("등락률", "size"))
        .reset_index()
    )
    grp["평균등락률"] = grp["평균등락률"].round(2)
    grp = grp[grp["종목수"] >= min_stocks]

    top = grp.sort_values("평균등락률", ascending=False).head(n).reset_index(drop=True)
    bottom = grp.sort_values("평균등락률", ascending=True).head(n).reset_index(drop=True)
    return top, bottom


def theme_analysis(df, theme_map):
    """테마(수기·중첩)별 평균 등락률을 계산해 (상위10, 하위10) 반환."""
    return _group_analysis(df, theme_map, "테마", config.MIN_THEME_STOCKS)


def sector_analysis(df, sector_map):
    """섹터(업종·전수·1:1)별 평균 등락률을 계산해 (상위10, 하위10) 반환."""
    return _group_analysis(df, sector_map, "섹터", config.MIN_SECTOR_STOCKS)


def sector_tier_table(df, sector_map):
    """섹터를 '시장 대비 초과수익(%p)' 기준 S~G 티어로 분류한다.

    초과수익 = 섹터 평균 등락률 − 시장 평균(섹터 편입 종목 전체 평균).
    반환: (티어이름 → DataFrame[섹터, 평균등락률, 초과, 종목수]), 시장평균(float)
    """
    sm = sector_map[["종목코드", "섹터"]]
    merged = df.merge(sm, on="종목코드", how="inner")
    market_avg = round(float(merged["등락률"].mean()), 2) if len(merged) else 0.0

    grp = (
        merged.groupby("섹터")
        .agg(평균등락률=("등락률", "mean"), 종목수=("등락률", "size"))
        .reset_index()
    )
    grp = grp[grp["종목수"] >= config.MIN_SECTOR_STOCKS].copy()
    grp["평균등락률"] = grp["평균등락률"].round(2)
    grp["초과"] = (grp["평균등락률"] - market_avg).round(2)
    grp["티어"] = grp["초과"].apply(lambda v: _tier_of_value(v, config.SECTOR_TIERS))

    result = {}
    for name, _lo, _hi in config.SECTOR_TIERS:
        sub = grp[grp["티어"] == name]
        ascending = name in config.DOWN_TIERS   # 하락 티어는 초과수익 낮은(언더퍼폼 큰) 순
        result[name] = sub.sort_values("초과", ascending=ascending).reset_index(drop=True)
    return result, market_avg


def big_theme_heatmap(df, big_theme_map):
    """대테마(17개)별 집계를 히트맵용으로 전부 반환 (강한→약한 정렬).

    반환 컬럼: [대테마, 평균등락률, 종목수, 상승, 하락]
    """
    bm = big_theme_map[["종목코드", "대테마"]]
    merged = df.merge(bm, on="종목코드", how="inner")
    grp = (
        merged.groupby("대테마")
        .agg(
            평균등락률=("등락률", "mean"),
            종목수=("등락률", "size"),
            상승=("등락률", lambda s: int((s > 0).sum())),
            하락=("등락률", lambda s: int((s < 0).sum())),
        )
        .reset_index()
    )
    grp["평균등락률"] = grp["평균등락률"].round(2)
    return grp.sort_values("평균등락률", ascending=False).reset_index(drop=True)
