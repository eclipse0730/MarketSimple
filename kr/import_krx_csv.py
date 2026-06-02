# -*- coding: utf-8 -*-
"""KRX 정보데이터시스템 '전종목 시세' CSV → 내부 market_YYYYMMDD.csv 변환기.

KRX 로그인(nProtect 암호화) 때문에 자동 수집이 막혀 있어, 과거 일자 데이터는
KRX 웹에서 직접 내려받은 CSV를 이 스크립트로 변환해 적재한다.

KRX 다운로드 경로:
  data.krx.co.kr → [정보데이터시스템] → 기본통계 → 주식 → 종목시세
  → [12001] 전종목 시세 → 조회일자 선택 → CSV 다운로드

사용법:
  python -m kr.import_krx_csv 원본.csv --date 20260601
  python -m kr.import_krx_csv 원본.csv            # 파일명/내용에서 날짜 추정 시도
  python -m kr.import_krx_csv 폴더/                # 폴더 안 모든 *.csv 일괄 변환

출력: output/kr/data/market_YYYYMMDD.csv (기존 수집기와 동일 포맷)
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import pandas as pd

from . import config

# 내부 표준 컬럼 (collector.COLUMNS 와 동일)
OUT_COLUMNS = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량", "거래대금", "시가총액", "상장주식수"]

# 필수 컬럼(없으면 변환 실패). 거래대금/시총/상장주식수는 보정·0 처리 가능해 제외.
REQUIRED = ["종목코드", "종목명", "시장", "현재가", "등락률", "거래량"]

# KRX 시장구분 라벨 → 내부 시장명. KRX는 'KOSPI'/'KOSDAQ'/'KONEX' 또는
# '유가증권'/'코스닥' 등으로 표기가 갈리므로 둘 다 받는다.
MARKET_MAP = {
    "KOSPI": "KOSPI", "유가증권": "KOSPI", "유가증권시장": "KOSPI", "STK": "KOSPI",
    "KOSDAQ": "KOSDAQ", "코스닥": "KOSDAQ", "코스닥시장": "KOSDAQ", "KSQ": "KOSDAQ",
    "KOSDAQ GLOBAL": "KOSDAQ", "코스닥글로벌": "KOSDAQ",
}

# KRX CSV 컬럼명 후보 → 내부 컬럼. KRX 다운로드 버전마다 헤더가 조금씩 다르다.
COL_ALIASES = {
    "종목코드": ["종목코드", "단축코드", "표준코드"],
    "종목명": ["종목명", "한글종목명", "한글 종목약명", "종목약명"],
    "시장": ["시장구분", "시장", "시장명"],
    "현재가": ["종가", "현재가"],
    "등락률": ["등락률", "등락율", "대비율", "등락률(%)"],
    "거래량": ["거래량", "거래량(주)"],
    "거래대금": ["거래대금", "거래대금(원)"],
    "시가총액": ["시가총액", "시가총액(원)"],
    "상장주식수": ["상장주식수", "상장주식수(주)"],
}


def _pick(df_cols, candidates):
    """df 컬럼들 중 후보 리스트와 일치(공백 무시)하는 첫 컬럼명을 반환."""
    norm = {re.sub(r"\s+", "", c): c for c in df_cols}
    for cand in candidates:
        key = re.sub(r"\s+", "", cand)
        if key in norm:
            return norm[key]
    return None


def _read_krx_csv(path: str) -> pd.DataFrame:
    """KRX CSV(보통 euc-kr/cp949, 일부 utf-8-sig)를 견고하게 읽는다."""
    for enc in ("cp949", "euc-kr", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 마지막 시도: 인코딩 오류 무시
    return pd.read_csv(path, dtype=str, encoding="cp949", encoding_errors="ignore")


def _to_number(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace('"', "").strip()
    text = text.replace("＋", "+").replace("－", "-").replace("%", "")
    if text in ("", "nan", "N/A", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _guess_date(path: str, df: pd.DataFrame) -> str | None:
    """파일명에서 YYYYMMDD 또는 YYYY-MM-DD 패턴을 찾아 날짜를 추정."""
    base = os.path.basename(path)
    m = re.search(r"(\d{4})[-.]?(\d{2})[-.]?(\d{2})", base)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    return None


def convert(path: str, date_str: str | None = None) -> tuple[str, int]:
    """KRX CSV 한 개를 내부 포맷으로 변환·저장하고 (출력경로, 행수)를 반환."""
    raw = _read_krx_csv(path)
    cols = list(raw.columns)

    mapping = {}
    for internal, cands in COL_ALIASES.items():
        found = _pick(cols, cands)
        if found is None and internal in REQUIRED:
            raise ValueError(
                f"필수 컬럼 '{internal}'을(를) 찾지 못했습니다. KRX CSV 헤더: {cols}"
            )
        mapping[internal] = found

    out = pd.DataFrame()
    out["종목코드"] = raw[mapping["종목코드"]].astype(str).str.extract(r"(\d{6})", expand=False)
    out["종목코드"] = out["종목코드"].fillna(
        raw[mapping["종목코드"]].astype(str).str.zfill(6)
    )
    out["종목명"] = raw[mapping["종목명"]].astype(str).str.strip()

    market_raw = raw[mapping["시장"]].astype(str).str.strip()
    out["시장"] = market_raw.map(lambda v: MARKET_MAP.get(v, MARKET_MAP.get(v.upper(), v)))

    out["현재가"] = raw[mapping["현재가"]].map(_to_number)
    out["등락률"] = raw[mapping["등락률"]].map(_to_number)
    out["거래량"] = raw[mapping["거래량"]].map(_to_number)

    if mapping.get("거래대금"):
        out["거래대금"] = raw[mapping["거래대금"]].map(_to_number)
    else:
        out["거래대금"] = None
    # 거래대금이 비면 현재가×거래량으로 보정 (수집기와 동일 규칙)
    need = out["거래대금"].isna()
    out.loc[need, "거래대금"] = (
        out.loc[need, "현재가"].fillna(0) * out.loc[need, "거래량"].fillna(0)
    )

    # 시가총액(원)·상장주식수(주): KRX CSV는 원/주 단위 그대로. 없으면 0.
    out["시가총액"] = raw[mapping["시가총액"]].map(_to_number) if mapping.get("시가총액") else None
    out["상장주식수"] = raw[mapping["상장주식수"]].map(_to_number) if mapping.get("상장주식수") else None

    # 내부 시장(KOSPI/KOSDAQ)만 남긴다
    out = out[out["시장"].isin(config.MARKETS)]
    out = out.dropna(subset=["종목코드", "시장", "등락률", "현재가"]).reset_index(drop=True)

    # 타입 정리
    out["거래량"] = out["거래량"].fillna(0).astype("int64")
    out["거래대금"] = out["거래대금"].fillna(0).astype("int64")
    out["현재가"] = out["현재가"].astype("int64")
    out["시가총액"] = out["시가총액"].fillna(0).astype("int64")
    out["상장주식수"] = out["상장주식수"].fillna(0).astype("int64")

    if out.empty:
        raise ValueError("변환 결과가 비어 있습니다 (시장/필수값 누락 가능).")

    date_str = date_str or _guess_date(path, out)
    if not date_str or not re.fullmatch(r"\d{8}", date_str):
        raise ValueError(
            f"날짜를 알 수 없습니다. --date YYYYMMDD 로 지정하세요. (추정: {date_str})"
        )

    data_dir = os.path.join(config.OUTPUT_DIR, config.DATA_OUTPUT_DIR)
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, f"market_{date_str}.csv")
    out[OUT_COLUMNS].to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path, len(out)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="KRX 전종목 시세 CSV → market_YYYYMMDD.csv 변환")
    ap.add_argument("source", help="KRX CSV 파일 또는 폴더 경로")
    ap.add_argument("--date", help="기준일 YYYYMMDD (단일 파일에 날짜가 없을 때)")
    args = ap.parse_args(argv)

    if os.path.isdir(args.source):
        paths = sorted(glob.glob(os.path.join(args.source, "*.csv")))
        if not paths:
            print(f"폴더에 CSV가 없습니다: {args.source}")
            return
        for p in paths:
            try:
                out_path, n = convert(p, None)
                print(f"✔ {os.path.basename(p)} → {out_path}  ({n:,}종목)")
            except Exception as exc:
                print(f"✘ {os.path.basename(p)}: {exc}")
    else:
        out_path, n = convert(args.source, args.date)
        print(f"✔ {out_path}  ({n:,}종목)")


if __name__ == "__main__":
    main()
