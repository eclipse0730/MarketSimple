# -*- coding: utf-8 -*-
"""
Market Brief V1 — 실행 진입점

사용법:
  python main.py                      # 현재 시각 기준으로 세션 자동 판별, 실데이터 수집
  python main.py --session morning    # 오전장 리포트 강제
  python main.py --session close      # 마감장 리포트 강제
  python main.py --date 20260530      # 특정 날짜 (YYYYMMDD)
"""

import argparse
import os
import time
from datetime import datetime

import pandas as pd

import config
import collector
import analyzer
import report


def guess_session() -> str:
    """14시 이전이면 오전장(morning), 이후면 마감장(close)."""
    return "morning" if datetime.now().hour < 14 else "close"


def load_theme_map(date_str: str):
    maps = []

    try:
        manual = pd.read_csv(config.THEME_MAP_FILE, dtype={"종목코드": str})
        maps.append(manual[["종목코드", "종목명", "테마"]])
    except FileNotFoundError:
        pass

    try:
        auto = collector.collect_theme_map(date_str)
        maps.append(auto)
    except Exception as exc:
        print(f"  · [안내] FDR 업종 테마 수집 실패: {exc}")

    if not maps:
        return pd.DataFrame(columns=["종목코드", "종목명", "테마"])

    theme_map = pd.concat(maps, ignore_index=True)
    theme_map["종목코드"] = theme_map["종목코드"].astype(str).str.zfill(6)
    theme_map["테마"] = theme_map["테마"].astype(str).str.strip()
    theme_map = theme_map[theme_map["테마"] != ""]
    return theme_map.drop_duplicates(subset=["종목코드", "테마"]).reset_index(drop=True)


def complete_theme_map(df, theme_map):
    covered = set(theme_map["종목코드"])
    missing = df[~df["종목코드"].isin(covered)]
    if missing.empty:
        return theme_map

    fallback = missing[["종목코드", "종목명"]].copy()
    fallback["테마"] = "미분류"
    return pd.concat([theme_map, fallback], ignore_index=True)


def parse_date(date_str: str) -> str:
    """YYYYMMDD 형식의 날짜 문자열을 검증해서 반환한다."""
    try:
        parsed = datetime.strptime(date_str, "%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다. 예: 20260529") from exc
    if parsed.strftime("%Y%m%d") != date_str:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다. 예: 20260529")
    return date_str


def main(argv=None):
    ap = argparse.ArgumentParser(description="Market Brief V1")
    ap.add_argument("--session", choices=["morning", "close"], help="리포트 세션")
    ap.add_argument("--date", type=parse_date, help="기준일 YYYYMMDD (예: 20260529)")
    args = ap.parse_args(argv)

    started = time.time()
    date_str = args.date or datetime.now().strftime("%Y%m%d")
    session = args.session or guess_session()

    print(f"▶ Market Brief V1  |  {date_str}  |  {session}  |  source=fdr")

    # 1) 수집
    df = collector.collect(date_str, historical=bool(args.date))
    print(f"  · 수집 종목 수: {len(df):,}")

    # 2) 분석
    overall, by_market = analyzer.market_strength(df)
    tiers = analyzer.build_tiers(df)
    theme_map = load_theme_map(date_str)
    theme_map = complete_theme_map(df, theme_map)
    print(f"  · 테마 매핑 수: {len(theme_map):,}")
    top, bottom = analyzer.theme_analysis(df, theme_map)

    # 3) 출력
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(config.OUTPUT_DIR, f"market_{date_str}_{session}.csv")
    theme_map_path = os.path.join(config.OUTPUT_DIR, f"theme_map_{date_str}.csv")
    html_path = os.path.join(config.OUTPUT_DIR, f"report_{date_str}_{session}.html")

    report.write_csv(df, csv_path)
    report.write_theme_map(theme_map, theme_map_path)
    report.write_html(
        html_path,
        date_str=date_str,
        session=session,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        overall=overall,
        by_market=by_market,
        tiers=tiers,
        top=top,
        bottom=bottom,
    )

    elapsed = time.time() - started
    print(f"  · 시장 강도: 상승 {overall['up']:,}({overall['up_pct']}%) "
          f"/ 하락 {overall['down']:,}({overall['down_pct']}%) "
          f"/ 보합 {overall['flat']:,}({overall['flat_pct']}%)")
    print(f"✔ CSV : {csv_path}")
    print(f"✔ THEME: {theme_map_path}")
    print(f"✔ HTML: {html_path}")
    print(f"⏱ {elapsed:.1f}초")


if __name__ == "__main__":
    main()
