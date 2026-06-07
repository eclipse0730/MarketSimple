# -*- coding: utf-8 -*-
"""
분석 모듈
- market_strength : 시장 강도 (상승/하락/보합 집계, 전체 + 시장별)
- build_tiers     : 등락률 티어표 (S~G)
- theme_analysis  : 테마별 평균 등락률 (상위/하위 10개)
"""

import pandas as pd

from . import config

FUND_PREFIXES = (
    "KODEX", "TIGER", "ACE", "RISE", "SOL", "PLUS", "HANARO", "KOSEF",
    "TIMEFOLIO", "ARIRANG", "KBSTAR", "KINDEX", "TREX", "FOCUS", "UNICORN",
    # 추가 ETF/액티브 운용사 브랜드 (KIWOOM 미국S&P500 등 보통주 오분류 방지)
    # 끝에 공백을 둔 prefix("BNK ", "키움 ")는 동명 보통주(BNK금융지주·키움증권)를
    # 살리고 "브랜드 + 상품명"(BNK 온디바이스AI…)만 걸러내기 위함이다.
    "KIWOOM ", "KOACT", "TIME ", "1Q ", "WON ", "HK ", "IBK ", "BNK ", "MIDAS ",
    "TRUSTON ", "VITA ", "N2 ", "DAISHIN",
    "마이티", "히어로즈", "키움 ", "더제이", "에셋플러스", "파워 ",
)
NON_COMMON_KEYWORDS = (
    "ETN", "스팩", "SPAC", "리츠", "인프라", "선박투자", "부동산투자",
)
# 종목명이 이 접미사로 끝나면 ETF/펀드로 본다(새 브랜드가 생겨도 잡히는 안전망).
FUND_SUFFIXES = ("액티브",)


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

    if any(upper.startswith(prefix.upper()) for prefix in FUND_PREFIXES):
        return False
    if any(keyword in upper for keyword in NON_COMMON_KEYWORDS):
        return False
    if text.endswith(FUND_SUFFIXES):
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


def market_strength(df, prev_df=None):
    """전체 시장 강도와 시장별 강도를 반환. prev_df 가 있으면 상승/하락 수 전일 대비(delta)를 붙인다."""
    summary_df = _summary_universe(df)
    prev_summary = _summary_universe(prev_df) if prev_df is not None else None

    def counts_with_delta(sub, prev_sub):
        c = _counts(sub)
        if prev_sub is not None and len(prev_sub):
            p = _counts(prev_sub)
            c["up_delta"] = c["up"] - p["up"]
            c["down_delta"] = c["down"] - p["down"]
        return c

    overall = counts_with_delta(
        summary_df,
        prev_summary,
    )
    by_market = {}
    for m in config.MARKETS:
        prev_sub = prev_summary[prev_summary["시장"] == m] if prev_summary is not None else None
        by_market[m] = counts_with_delta(summary_df[summary_df["시장"] == m], prev_sub)
    return overall, by_market


def _turnover(sub):
    """거래대금 합계 / 시가총액 합계 × 100 (%). 계산 불가면 None."""
    if "거래대금" not in sub.columns or "시가총액" not in sub.columns or not len(sub):
        return None
    cap_total = pd.to_numeric(sub["시가총액"], errors="coerce").sum()
    val_total = pd.to_numeric(sub["거래대금"], errors="coerce").sum()
    if cap_total and cap_total > 0:
        return round(float(val_total / cap_total) * 100, 2)
    return None


def _diagnose_one(sub, prev_sub=None):
    """한 시장(또는 부분집합)의 진단 지표를 계산한다. 입력은 보통주만 걸러진 DataFrame.
    prev_sub 가 있으면 회전율 전일 대비(turnover_delta)를 붙인다."""
    out = {"caps": [], "limit_up": None, "limit_down": None, "turnover": None}

    if "시가총액" in sub.columns and len(sub):
        cap = sub.copy()
        cap["시가총액"] = pd.to_numeric(cap["시가총액"], errors="coerce")
        cap = cap.dropna(subset=["시가총액"])
        buckets = [
            ("대형주", cap["시가총액"] >= config.CAP_LARGE),
            ("중형주", (cap["시가총액"] >= config.CAP_MID) & (cap["시가총액"] < config.CAP_LARGE)),
            ("소형주", cap["시가총액"] < config.CAP_MID),
        ]
        for label, mask in buckets:
            grp = cap[mask]
            out["caps"].append({
                "label": label,
                "count": int(len(grp)),
                "avg_rate": round(float(grp["등락률"].mean()), 2) if len(grp) else 0.0,
                "up_pct": round(float((grp["등락률"] > 0).mean() * 100), 1) if len(grp) else 0.0,
            })

    if len(sub):
        out["limit_up"] = int((sub["등락률"] >= config.LIMIT_UP_RATE).sum())
        out["limit_down"] = int((sub["등락률"] <= config.LIMIT_DOWN_RATE).sum())

    out["turnover"] = _turnover(sub)
    if prev_sub is not None and out["turnover"] is not None:
        prev_to = _turnover(prev_sub)
        if prev_to is not None:
            out["turnover_delta"] = round(out["turnover"] - prev_to, 2)

    return out


def market_diagnosis(df, prev_df=None):
    """시장별(코스피/코스닥) 진단: 시총 구간별 강도 + 상한가/하한가 + 거래대금 회전율.

    - 시총 구간(대형/중형/소형)별 종목 수·평균 등락률 → '오늘 누가 끌고 갔나'.
    - 상한가/하한가 근접 종목 수 → 과열/패닉 신호.
    - 회전율 = 거래대금 / 시가총액 → 시장의 손바뀜 정도(prev_df 있으면 전일 대비도).
    보통주 기준(ETF/우선주 등 제외). config.MARKETS 별로 나눠서 반환한다.
    """
    base = _summary_universe(df)
    prev_base = _summary_universe(prev_df) if prev_df is not None else None
    result = {}
    for m in config.MARKETS:
        prev_sub = prev_base[prev_base["시장"] == m] if prev_base is not None else None
        result[m] = _diagnose_one(base[base["시장"] == m], prev_sub)
    return result


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


def volume_surge_top(df, prev_dfs, n=None, common_only=False):
    """당일 거래량 / 최근 거래일 평균 거래량 = '거래량 배율' 상위 n개를 반환.

    df       : 당일 스냅샷 (거래량/거래대금 포함)
    prev_dfs : 과거 일자 DataFrame 리스트 (각각 종목코드·거래량 컬럼 필요)
    반환 컬럼: 기존 + [평균거래량, 거래량배율]
    """
    n = n or config.VOLUME_SURGE_TOP_N
    if "거래량" not in df.columns or not prev_dfs:
        return df.head(0)

    base = _summary_universe(df) if common_only else df
    base = base.copy()

    # 종목코드별 과거 평균 거래량 (가용한 일자만 평균)
    frames = []
    for pdf in prev_dfs:
        if "종목코드" in pdf.columns and "거래량" in pdf.columns:
            frames.append(pdf[["종목코드", "거래량"]])
    if not frames:
        return df.head(0)

    hist = pd.concat(frames, ignore_index=True)
    hist["종목코드"] = hist["종목코드"].astype(str).str.zfill(6)
    avg_vol = (
        hist.groupby("종목코드")["거래량"]
        .mean()
        .reset_index()
        .rename(columns={"거래량": "평균거래량"})
    )

    base["종목코드"] = base["종목코드"].astype(str).str.zfill(6)
    merged = base.merge(avg_vol, on="종목코드", how="inner")

    # 노이즈 필터: 당일 거래대금 하한, 과거 평균 거래량 하한
    merged = merged[merged["평균거래량"] >= config.VOLUME_SURGE_MIN_PREV_VOLUME]
    if "거래대금" in merged.columns:
        merged = merged[merged["거래대금"] >= config.VOLUME_SURGE_MIN_VALUE]
    if merged.empty:
        return df.head(0)

    merged["거래량배율"] = (merged["거래량"] / merged["평균거래량"]).round(2)
    ranked = merged.sort_values("거래량배율", ascending=False).head(n)
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
