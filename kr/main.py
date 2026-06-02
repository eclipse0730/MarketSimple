# -*- coding: utf-8 -*-
"""
Market Brief V1 — 실행 진입점

사용법:
  python main.py                      # 현재 시각 기준 스냅샷 수집
  python main.py --date 20260530      # 특정 날짜 (YYYYMMDD)
"""

import argparse
import glob
import os
import re
import sys
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
    theme_map["종목코드"] = theme_map["종목코드"].astype(str).str.zfill(6)
    theme_map["테마"] = theme_map["테마"].astype(str).str.strip()
    theme_map = theme_map[theme_map["테마"] != ""]
    return theme_map.drop_duplicates(subset=["종목코드", "테마"]).reset_index(drop=True)


def load_sector_map(date_str, collector_module, refresh=False):
    """섹터(업종) 매핑을 불러온다. 기본은 캐시(sector_map.csv) 사용,
    refresh=True 이거나 캐시가 없으면 네이버 업종을 재수집해 캐시를 갱신한다."""
    path = config.SECTOR_MAP_FILE

    if refresh or not os.path.exists(path):
        try:
            sector_map = collector_module.collect_sector_map(date_str)
        except Exception as exc:
            print(f"  · [안내] 섹터 수집 실패: {exc}")
            sector_map = pd.DataFrame(columns=["종목코드", "종목명", "섹터"])
        if not sector_map.empty:
            sector_map.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  · 섹터 재수집·캐시 저장: {path}")
    else:
        sector_map = pd.read_csv(path, dtype={"종목코드": str})

    if sector_map.empty:
        return sector_map
    sector_map["종목코드"] = sector_map["종목코드"].astype(str).str.zfill(6)
    sector_map["섹터"] = sector_map["섹터"].astype(str).str.strip()
    return sector_map[sector_map["섹터"] != ""].reset_index(drop=True)


def load_big_theme_map():
    """대테마(17 대분류) 매핑을 불러온다. 없으면 빈 DataFrame."""
    path = config.BIG_THEME_MAP_FILE
    if not os.path.exists(path):
        return pd.DataFrame(columns=["종목코드", "종목명", "대테마"])
    big = pd.read_csv(path, dtype={"종목코드": str})
    big["종목코드"] = big["종목코드"].astype(str).str.zfill(6)
    return big


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


def load_prev_market_frames(data_dir: str, date_str: str, days: int):
    """기준일 이전의 market_YYYYMMDD.csv 들을 최신순으로 최대 days개 로드한다.

    거래량 평균 계산용. 파일이 days개 미만이면 있는 만큼만 반환한다.
    """
    pattern = os.path.join(data_dir, "market_*.csv")
    found = []
    for path in glob.glob(pattern):
        m = re.search(r"market_(\d{8})\.csv$", os.path.basename(path))
        if m and m.group(1) < date_str:   # 기준일 이전만
            found.append((m.group(1), path))

    found.sort(reverse=True)   # 최신 날짜 우선
    frames = []
    for _d, path in found[:days]:
        try:
            pdf = pd.read_csv(path, dtype={"종목코드": str})
            pdf["종목코드"] = pdf["종목코드"].astype(str).str.zfill(6)
            frames.append(pdf)
        except Exception as exc:
            print(f"  · [안내] 과거 CSV 로드 실패({path}): {exc}")
    return frames


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
    # Windows 콘솔(cp949)에서 ✔ ⏱ · 등 유니코드 출력이 깨지지 않도록 UTF-8로.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="Market Brief V1")
    ap.add_argument("--date", type=parse_date, help="기준일 YYYYMMDD (예: 20260529)")
    ap.add_argument("--mode", choices=sorted(REPORT_MODES), default="mode1",
                    help="HTML 리포트 디자인 모드 (기본: mode1)")
    ap.add_argument("--force", action="store_true",
                    help="기존 날짜 CSV/리포트를 현재 스냅샷으로 갱신")
    ap.add_argument("--collector", action="store_true",
                    help="CSV 수집/저장 단계까지만 실행하고 리포트 생성은 건너뜀")
    ap.add_argument("--refresh-sector", action="store_true",
                    help="섹터(업종) 매핑을 네이버에서 재수집해 sector_map.csv 갱신")
    args = ap.parse_args(argv)

    started = time.time()
    date_str = args.date or datetime.now().strftime("%Y%m%d")
    session = "snapshot"

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
        df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
        print(f"  · 기존 CSV 사용: {csv_path}")
        print(f"  · 로드 종목 수: {len(df):,}")
    else:
        if args.force and os.path.exists(csv_path):
            print("  · --force 지정: 기존 CSV를 무시하고 재수집")
        df = data_collector.collect(date_str, historical=bool(args.date))
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
    tiers_common = analyzer.build_tiers(df, common_only=True)
    top_value = analyzer.top_trading_value(df, n=30)
    top_value_common = analyzer.top_trading_value(df, n=30, common_only=True)

    prev_frames = load_prev_market_frames(data_dir, date_str, config.VOLUME_SURGE_AVG_DAYS)
    if len(prev_frames) >= config.VOLUME_SURGE_MIN_DAYS:
        top_volume = analyzer.volume_surge_top(df, prev_frames)
        top_volume_common = analyzer.volume_surge_top(df, prev_frames, common_only=True)
        print(f"  · 거래량 급증: 과거 {len(prev_frames)}거래일 평균 대비 / "
              f"전종목 {len(top_volume)} · 보통주 {len(top_volume_common)}")
    else:
        top_volume = top_volume_common = None
        print(f"  · 거래량 급증: 과거 CSV {len(prev_frames)}개 (최소 "
              f"{config.VOLUME_SURGE_MIN_DAYS}개 필요) — 섹션 생략")
    theme_map = load_theme_map(date_str, data_collector, "naver")
    print(f"  · 테마 매핑 수: {len(theme_map):,}  (수기 큐레이션, 미분류 제외)")

    sector_map = load_sector_map(date_str, data_collector, refresh=args.refresh_sector)
    print(f"  · 섹터 매핑 수: {len(sector_map):,}")
    sector_tiers, sector_market_avg = analyzer.sector_tier_table(df, sector_map)

    big_theme_map = load_big_theme_map()
    big_theme = analyzer.big_theme_heatmap(df, big_theme_map) if len(big_theme_map) else None
    if big_theme is not None:
        print(f"  · 대테마: {len(big_theme)}개 / 매핑 종목 {len(big_theme_map):,}")

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
        tiers_common=tiers_common,
        sector_tiers=sector_tiers,
        sector_market_avg=sector_market_avg,
        big_theme=big_theme,
        top_value=top_value,
        top_value_common=top_value_common,
        top_volume=top_volume,
        top_volume_common=top_volume_common,
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
