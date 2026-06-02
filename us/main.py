# -*- coding: utf-8 -*-
"""
Market Brief V1 — 실행 진입점

사용법:
  python main.py --market us          # 최근 미국장 EOD 수집
  python main.py --date 20260530      # 특정 날짜 (YYYYMMDD)
"""

import argparse
import os
import time
from datetime import datetime

import pandas as pd

from . import analyzer
from . import collector as data_collector
from . import config
from . import report
from . import report_mode1
from . import report_mode2


REPORT_MODES = {
    "classic": report,
    "mode1": report_mode1,
    "mode2": report_mode2,
}

def load_theme_map(date_str: str, collector_module, source_name: str):
    maps = []

    try:
        manual = pd.read_csv(config.THEME_MAP_FILE, dtype={"종목코드": str})
        maps.append(manual[["종목코드", "종목명", "테마"]])
    except FileNotFoundError:
        pass

    try:
        auto = collector_module.collect_theme_map(date_str)
        if not auto.empty:
            maps.append(auto)
    except Exception as exc:
        print(f"  · [안내] {source_name} 업종 테마 수집 실패: {exc}")

    if not maps:
        return pd.DataFrame(columns=["종목코드", "종목명", "테마"])

    theme_map = pd.concat(maps, ignore_index=True)
    theme_map["종목코드"] = theme_map["종목코드"].astype(str).str.upper().str.strip()
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


def attach_market_indices(by_market, collector_module, date_str: str, historical: bool):
    if not hasattr(collector_module, "collect_market_indices"):
        return by_market

    try:
        indices = collector_module.collect_market_indices(date_str, historical=historical)
    except Exception as exc:
        print(f"  · [안내] 시장 지수 수집 실패: {exc}")
        return by_market

    for market, values in indices.items():
        if market in by_market:
            by_market[market].update({
                "index_value": values.get("value"),
                "index_change": values.get("change"),
                "index_rate": values.get("rate"),
            })
    return by_market


def attach_market_flows(by_market, collector_module, date_str: str, historical: bool):
    if not hasattr(collector_module, "collect_market_flows"):
        return by_market

    try:
        flows = collector_module.collect_market_flows(date_str, historical=historical)
    except Exception as exc:
        print(f"  · [안내] 투자자별 수급 수집 실패: {exc}")
        return by_market

    for market, values in flows.items():
        if market in by_market:
            by_market[market].update({
                "flow_personal": values.get("personal"),
                "flow_foreign": values.get("foreign"),
                "flow_institution": values.get("institution"),
            })
    return by_market


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
    ap.add_argument("--date", type=parse_date, help="기준일 YYYYMMDD (예: 20260529)")
    ap.add_argument("--mode", choices=sorted(REPORT_MODES), default="mode1",
                    help="HTML 리포트 디자인 모드 (기본: mode1)")
    ap.add_argument("--force", action="store_true",
                    help="기존 날짜 CSV/리포트를 다시 수집")
    ap.add_argument("--collector", action="store_true",
                    help="CSV 수집/저장 단계까지만 실행하고 리포트 생성은 건너뜀")
    args = ap.parse_args(argv)

    started = time.time()
    date_str = data_collector.resolve_date(args.date)
    session = "close"

    data_dir = os.path.join(config.OUTPUT_DIR, config.DATA_OUTPUT_DIR)
    report_dir = os.path.join(config.OUTPUT_DIR, config.REPORT_OUTPUT_DIR)
    theme_dir = os.path.join(config.OUTPUT_DIR, config.THEME_OUTPUT_DIR)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(theme_dir, exist_ok=True)

    csv_path = os.path.join(data_dir, f"market_{date_str}.csv")
    theme_map_path = os.path.join(theme_dir, f"theme_map_{date_str}.csv")
    html_path = os.path.join(report_dir, f"{config.REPORT_FILENAME_PREFIX} [{date_str}]_{args.mode}.html")

    print(f"▶ Market Brief V1  |  {date_str}")

    # 1) 수집
    if os.path.exists(csv_path) and not args.force:
        df = pd.read_csv(csv_path, dtype={"종목코드": str})
        df["종목코드"] = df["종목코드"].astype(str)
        print(f"  · 기존 CSV 사용: {csv_path}")
        print(f"  · 로드 종목 수: {len(df):,}")
    else:
        if args.force and os.path.exists(csv_path):
            print("  · --force 지정: 기존 CSV를 무시하고 재수집")
        try:
            df = data_collector.collect(date_str, historical=True)
        except RuntimeError as exc:
            raise SystemExit(f"  · [오류] 미국장 EOD 수집 실패: {exc}") from exc
        print(f"  · 수집 종목 수: {len(df):,}")
        report.write_csv(df, csv_path)

    if args.collector:
        elapsed = time.time() - started
        print("  · --collector 지정: CSV 수집 단계에서 종료")
        print(f"CSV : {csv_path}")
        print(f"{elapsed:.1f}초")
        return

    # 2) 분석
    overall, by_market = analyzer.market_strength(df)
    by_market = attach_market_indices(by_market, data_collector, date_str, bool(args.date))
    by_market = attach_market_flows(by_market, data_collector, date_str, bool(args.date))
    tiers = analyzer.build_tiers(df)
    top_value = analyzer.top_trading_value(df, n=30)
    top_value_common = analyzer.top_trading_value(df, n=30, common_only=True)
    theme_map = load_theme_map(date_str, data_collector, "polygon")
    theme_map = complete_theme_map(df, theme_map)
    print(f"  · 테마 매핑 수: {len(theme_map):,}")
    top, bottom = analyzer.theme_analysis(df, theme_map)

    # 3) 출력
    report.write_theme_map(theme_map, theme_map_path)
    renderer = REPORT_MODES[args.mode]
    renderer.write_html(
        html_path,
        date_str=date_str,
        session=session,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        overall=overall,
        by_market=by_market,
        tiers=tiers,
        top=top,
        bottom=bottom,
        top_value=top_value,
        top_value_common=top_value_common,
    )

    elapsed = time.time() - started
    print(f"  · 시장 강도: 상승 {overall['up']:,}({overall['up_pct']}%) "
          f"/ 하락 {overall['down']:,}({overall['down_pct']}%) "
          f"/ 보합 {overall['flat']:,}({overall['flat_pct']}%)")
    print(f"✔ CSV : {csv_path}")
    print(f"✔ THEME: {theme_map_path}")
    print(f"✔ HTML({args.mode}): {html_path}")
    print(f"⏱ {elapsed:.1f}초")


if __name__ == "__main__":
    main()
