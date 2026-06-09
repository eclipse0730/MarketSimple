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
from html import unescape

import pandas as pd

from . import analyzer
from . import collector as data_collector
from . import config
from . import report_shared

# 리포트 HTML 은 단일 렌더러(report_shared)로 생성한다. 시각 테마(파스텔/다크/전문가/
# 세피아)는 페이지에 모두 임베드돼 런타임에 카멜레온으로 전환되므로, 초기 테마는
# report_shared.write_html 의 기본값(report_themes.DEFAULT_THEME)을 그대로 따른다.


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


def _to_float_text(text):
    text = unescape(str(text)).replace(",", "").replace("%", "").replace("억", "").strip()
    if text in ("", "N/A"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_local_market_indices(date_str: str):
    """네이버 지수 수집 실패 시 같은 날짜 로컬 HTML에서 지수 값을 복구한다."""
    candidates = [
        os.path.join("docs", config.MARKET_KEY, date_str, "index.html"),
        os.path.join(config.OUTPUT_DIR, config.REPORT_OUTPUT_DIR, config.report_filename(date_str)),
    ]
    block_re = re.compile(
        r"<h3>(KOSPI|KOSDAQ)</h3>.*?"
        r'<span class="mkt-index mono">([^<]+)</span>.*?'
        r'<span class="mkt-rate mono [^"]+">([^<]+)</span>.*?'
        r'<span class="mkt-change mono [^"]+">([^<]+)</span>',
        re.S,
    )

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                html = f.read()
        except OSError:
            continue

        indices = {}
        for market, value, rate, change in block_re.findall(html):
            parsed = {
                "value": _to_float_text(value),
                "rate": _to_float_text(rate),
                "change": _to_float_text(change),
            }
            if all(v is not None for v in parsed.values()):
                indices[market] = parsed
        if indices:
            print(f"  · [안내] 로컬 HTML 지수값 사용: {path}")
            return indices
    return {}


def load_local_market_flows(date_str: str):
    """네이버 수급 수집 실패 시 같은 날짜 로컬 HTML에서 투자자별 수급을 복구한다."""
    candidates = [
        os.path.join("docs", config.MARKET_KEY, date_str, "index.html"),
        os.path.join(config.OUTPUT_DIR, config.REPORT_OUTPUT_DIR, config.report_filename(date_str)),
    ]
    card_re = re.compile(
        r'<div class="mkt-card">.*?<h3>(KOSPI|KOSDAQ)</h3>.*?'
        r'<div class="mkt-flow">(.*?)</div>',
        re.S,
    )
    item_re = re.compile(
        r'<span class="flow-item"><span>(기관|외인|개인)</span>'
        r'<b class="mono [^"]+">([^<]+)</b></span>',
        re.S,
    )
    key_map = {"기관": "institution", "외인": "foreign", "개인": "personal"}

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                html = f.read()
        except OSError:
            continue

        flows = {}
        for market, flow_html in card_re.findall(html):
            parsed = {}
            for label, value in item_re.findall(flow_html):
                parsed[key_map[label]] = _to_float_text(value)
            if parsed:
                flows[market] = parsed
        if flows:
            print(f"  · [안내] 로컬 HTML 수급값 사용: {path}")
            return flows
    return {}


def attach_market_indices(by_market, collector_module, date_str: str, historical: bool):
    if not hasattr(collector_module, "collect_market_indices"):
        return by_market

    try:
        indices = collector_module.collect_market_indices(date_str, historical=historical)
    except Exception as exc:
        print(f"  · [안내] 시장 지수 수집 실패: {exc}")
        indices = load_local_market_indices(date_str)
        if not indices:
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
        flows = load_local_market_flows(date_str)
        if not flows:
            return by_market

    for market, values in flows.items():
        if market in by_market:
            by_market[market].update({
                "flow_personal": values.get("personal"),
                "flow_foreign": values.get("foreign"),
                "flow_institution": values.get("institution"),
            })
    return by_market


def attach_market_flow_history(by_market, collector_module, date_str: str, days: int = 7):
    """수급 카드 모달용 최근 7거래일 투자자별 순매수 히스토리를 붙인다(best-effort).

    실패해도 본문 수급값(attach_market_flows)에는 영향이 없고, 모달만 비활성된다.
    """
    if not hasattr(collector_module, "collect_market_flow_history"):
        return by_market
    try:
        history = collector_module.collect_market_flow_history(date_str, days=days)
    except Exception as exc:
        print(f"  · [안내] 투자자별 수급 히스토리 수집 실패: {exc}")
        return by_market

    for market, rows in history.items():
        if market in by_market:
            by_market[market]["flow_history"] = rows
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


def is_holiday_duplicate(df, data_dir: str, date_str: str) -> bool:
    """수집 데이터가 직전 거래일과 사실상 동일하면 휴장/장전으로 판단.

    네이버 스냅샷은 휴장일·장 시작 전에 전일 종가를 그대로 주므로, 현재가가
    직전 거래일과 (공통 종목 기준) 100% 일치하면 새 거래 데이터가 아니다.
    """
    prev = load_prev_market_frames(data_dir, date_str, 1)
    if not prev:
        return False
    p = prev[0]
    cur = df.copy()
    cur["종목코드"] = cur["종목코드"].astype(str).str.zfill(6)
    merged = cur.merge(p[["종목코드", "현재가"]], on="종목코드", suffixes=("", "_prev"))
    if len(merged) < 100:          # 비교 표본이 너무 적으면 판단 보류
        return False
    same_ratio = (merged["현재가"] == merged["현재가_prev"]).mean()
    return same_ratio >= 0.999     # 사실상 전부 동일 = 휴장/장전 복제


def available_report_dates(data_dir: str) -> list[str]:
    """리포트를 만들 수 있는(=CSV가 있는) 날짜 목록을 오름차순으로 반환."""
    dates = []
    for path in glob.glob(os.path.join(data_dir, "market_*.csv")):
        m = re.search(r"market_(\d{8})\.csv$", os.path.basename(path))
        if m:
            dates.append(m.group(1))
    return sorted(dates)


def build_date_nav(date_str: str, all_dates: list[str]) -> dict:
    """현재 날짜 기준 이전/다음 리포트 파일명(같은 폴더 상대경로)을 계산.

    이전/다음이 없으면 None. 링크 대상 HTML은 일괄 빌드 시 함께 생성된다.
    """
    prev_link = next_link = None
    if date_str in all_dates:
        i = all_dates.index(date_str)
        if i > 0:
            prev_link = config.report_filename(all_dates[i - 1])
        if i < len(all_dates) - 1:
            next_link = config.report_filename(all_dates[i + 1])
    return {
        "prev_date": all_dates[all_dates.index(date_str) - 1] if prev_link else None,
        "prev_link": prev_link,
        "next_date": all_dates[all_dates.index(date_str) + 1] if next_link else None,
        "next_link": next_link,
    }


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
    html_path = os.path.join(report_dir, config.report_filename(date_str))

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

        # 휴장/장전 복제 방지: 스냅샷이 직전 거래일과 동일하면 리포트를 만들지 않는다.
        # (과거 --date 빌드는 의도된 것이라 검사하지 않는다)
        if not args.date and is_holiday_duplicate(df, data_dir, date_str):
            print(f"  · 직전 거래일과 데이터 동일 — 휴장/장전으로 판단, 생성 중단")
            return

        report_shared.write_csv(df, csv_path)

    if args.collector:
        elapsed = time.time() - started
        print("  · --collector 지정: CSV 수집 단계에서 종료")
        print(f"CSV : {csv_path}")
        print(f"{elapsed:.1f}초")
        return

    # 2) 분석
    # 과거 프레임(최신순). prev_frames[0] = 전일 → 시장 강도·진단의 전일 대비에 사용.
    prev_frames = load_prev_market_frames(data_dir, date_str, config.VOLUME_SURGE_AVG_DAYS)
    prev_df = prev_frames[0] if prev_frames else None

    overall, by_market = analyzer.market_strength(df, prev_df)
    by_market = attach_market_indices(by_market, data_collector, date_str, bool(args.date))
    by_market = attach_market_flows(by_market, data_collector, date_str, bool(args.date))
    by_market = attach_market_flow_history(by_market, data_collector, date_str)
    diagnosis = analyzer.market_diagnosis(df, prev_df)
    tiers = analyzer.build_tiers(df)
    tiers_common = analyzer.build_tiers(df, common_only=True)
    top_value = analyzer.top_trading_value(df, n=30)
    top_value_common = analyzer.top_trading_value(df, n=30, common_only=True)

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
    big_theme_common = analyzer.big_theme_heatmap(df, big_theme_map, common_only=True) if len(big_theme_map) else None
    if big_theme is not None:
        print(f"  · 대테마: {len(big_theme)}개 / 보통주 {len(big_theme_common)}개 / 매핑 종목 {len(big_theme_map):,}")

    group_members = {
        "diagnosis": analyzer.diagnosis_members(df),
        "sector": analyzer.group_members(df, sector_map, "섹터") if len(sector_map) else {},
        "big": analyzer.group_members(df, big_theme_map, "대테마") if len(big_theme_map) else {},
        "big_common": analyzer.group_members(df, big_theme_map, "대테마", common_only=True) if len(big_theme_map) else {},
    }

    # 3) 출력
    report_shared.write_theme_map(theme_map, theme_map_path)
    date_nav = build_date_nav(date_str, available_report_dates(data_dir))
    report_shared.write_html(
        html_path,
        date_str=date_str,
        session=session,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        overall=overall,
        by_market=by_market,
        diagnosis=diagnosis,
        tiers=tiers,
        tiers_common=tiers_common,
        sector_tiers=sector_tiers,
        sector_market_avg=sector_market_avg,
        big_theme=big_theme,
        big_theme_common=big_theme_common,
        group_members=group_members,
        top_value=top_value,
        top_value_common=top_value_common,
        top_volume=top_volume,
        top_volume_common=top_volume_common,
        date_nav=date_nav,
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
