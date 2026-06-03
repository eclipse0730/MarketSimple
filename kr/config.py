# -*- coding: utf-8 -*-
"""
설정 파일
- 동작을 바꾸고 싶으면 보통 이 파일만 고치면 됩니다.
"""

import os

BASE_DIR = os.path.dirname(__file__)


def _load_dotenv():
    """프로젝트 루트의 .env 를 환경변수로 로드(외부 의존성 없이 경량 파싱).

    이미 환경에 있는 값은 덮어쓰지 않는다(터미널 export 가 우선).
    KEY=VALUE 형식, # 주석·빈 줄 무시.
    """
    root = os.path.dirname(BASE_DIR)
    for path in (os.path.join(root, ".env"), os.path.join(BASE_DIR, ".env")):
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ.setdefault(key, val)
        except OSError:
            pass


_load_dotenv()

MARKET_KEY = "kr"
MARKET_NAME = "한국 증시"
MARKET_SUBTITLE = "KOSPI · KOSDAQ"
MARKETS = ("KOSPI", "KOSDAQ")
REPORT_FILENAME_PREFIX = "한국증시 DailyTier"
STOCK_URL_TEMPLATE = "https://finance.naver.com/item/main.naver?code={code6}"

# 배포 사이트 기준 URL (카톡 공유 OG 태그의 og:url/og:image 절대경로용).
# 예: "https://username.github.io/MarketSimple" 또는 커스텀 도메인.
# 환경변수 SITE_BASE_URL 로도 덮어쓸 수 있다. 비우면 OG의 url/image는 생략.
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").rstrip("/")

# ──────────────────────────────────────────────
# 외부 연동 (배포 페이지 기능). 모두 환경변수로 주입하며, 비어있으면 자동 비활성.
# ──────────────────────────────────────────────
# Google Analytics 4 측정 ID (G-XXXXXXXXXX). 있으면 페이지에 GA4 스크립트 삽입.
GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "").strip()
# Web3Forms Access Key (UUID). 있으면 피드백 팝업 폼 노출.
WEB3FORMS_KEY = os.environ.get("WEB3FORMS_KEY", "").strip()
# 피드백 알림을 받을 이메일 (폼 제출 시 이 주소로 전송).
FEEDBACK_EMAIL = os.environ.get("FEEDBACK_EMAIL", "ruin2055@gmail.com").strip()


def report_filename(date_str: str, mode: str) -> str:
    """리포트 HTML 파일명 규칙(단일 출처). 날짜 네비게이션 링크도 이걸 쓴다."""
    return f"{REPORT_FILENAME_PREFIX} [{date_str}]_{mode}.html"

# ──────────────────────────────────────────────
# 티어 정의: (티어이름, 하한[포함], 상한[미포함])
# 모든 등락률은 정확히 하나의 티어에만 들어갑니다. (0.00% 는 C 티어)
# 한국 시장 상/하한가가 ±30% 이므로 끝 티어는 999 로 열어둡니다.
# ──────────────────────────────────────────────
TIERS = [
    ("S",   25.0,  999.0),   # +25.00 ~ +30.00
    ("A",   15.0,   25.0),   # +15.00 ~ +24.99
    ("B",    5.0,   15.0),   #  +5.00 ~ +14.99
    ("C",    0.0,    5.0),   #  +0.00 ~  +4.99
    ("D",    0.0,   -5.0),   #  -0.01 ~  -4.99
    ("E",   -5.0,  -15.0),   #  -5.00 ~ -14.99
    ("F",  -15.0,  -25.0),   # -15.00 ~ -24.99
    ("G",  -25.0, -999.0),   # -25.00 ~ -30.00
]

# 상승 티어 / 하락 티어 (정렬 방향이 다릅니다)
UP_TIERS = ["S", "A", "B", "C"]      # 등락률 내림차순 (높은 순)
DOWN_TIERS = ["D", "E", "F", "G"]    # 등락률 오름차순 (낙폭 큰 순)

# ──────────────────────────────────────────────
# 섹터 티어: 섹터평균 − 시장평균 = 초과수익(%p) 기준.
# 섹터 평균은 ±30% 가 아니라 보통 ±3%p 안쪽이라 종목과 다른 경계를 쓴다.
# 시장 방향성을 제거해 '시장 대비 주도/소외 섹터'를 보여준다. (C/D 가 시장 수준)
# ──────────────────────────────────────────────
SECTOR_TIERS = [
    ("S",   3.0,  999.0),   # +3.0%p 이상  (시장 압도적 아웃퍼폼)
    ("A",   1.5,    3.0),   # +1.5 ~ +3.0%p
    ("B",   0.5,    1.5),   # +0.5 ~ +1.5%p
    ("C",   0.0,    0.5),   #  0.0 ~ +0.5%p (시장 상위)
    ("D",  -0.5,    0.0),   # -0.5 ~  0.0%p (시장 하위)
    ("E",  -1.5,   -0.5),   # -1.5 ~ -0.5%p
    ("F",  -3.0,   -1.5),   # -3.0 ~ -1.5%p
    ("G", -999.0,  -3.0),   # -3.0%p 이하  (시장 압도적 언더퍼폼)
]

# 티어표에서 티어당 최대로 보여줄 종목 수 (None 이면 전부)
MAX_PER_TIER = None

# ──────────────────────────────────────────────
# 거래량 증가율(거래량 급증) 섹션
#   당일 거래량 / 최근 N거래일 평균 거래량 = 배율(x).
#   과거 CSV(market_YYYYMMDD.csv)들을 읽어 평균을 낸다. 파일이 N개 미만이면
#   가용한 만큼만 평균에 쓴다(최소 VOLUME_SURGE_MIN_DAYS개는 있어야 계산).
# ──────────────────────────────────────────────
VOLUME_SURGE_TOP_N = 30        # 노출할 상위 종목 수
VOLUME_SURGE_AVG_DAYS = 20     # 평균에 쓸 과거 거래일 수(당일 제외)
VOLUME_SURGE_MIN_DAYS = 1      # 최소 이 일수의 과거 데이터가 있어야 계산
VOLUME_SURGE_MIN_VALUE = 1_000_000_000  # 당일 거래대금 하한(잡주 노이즈 제거): 10억원
VOLUME_SURGE_MIN_PREV_VOLUME = 1000     # 과거 평균 거래량 하한(0 나눗셈/거래정지 제거)

# 테마 분석에 포함할 최소 종목 수 (이보다 적으면 평균이 불안정해 제외)
MIN_THEME_STOCKS = 2

# 섹터 분석에 포함할 최소 종목 수 (섹터는 전수 분류라 더 크게 잡는다)
MIN_SECTOR_STOCKS = 3

# 테마 매핑 파일 (종목코드, 종목명, 테마) — 수기 관리, 한 종목이 여러 테마에 중복 가능
THEME_MAP_FILE = os.path.join(BASE_DIR, "theme_map.csv")

# 섹터 매핑 파일 (종목코드, 종목명, 섹터) — 네이버 업종 자동 수집 캐시, 한 종목 1섹터
SECTOR_MAP_FILE = os.path.join(BASE_DIR, "sector_map.csv")

# 대테마 매핑 파일 (종목코드, 종목명, 대테마) — 섹터를 17개 대분류로 묶은 전수 분류
BIG_THEME_MAP_FILE = os.path.join(BASE_DIR, "big_theme_map.csv")

# 결과물 저장 폴더
OUTPUT_DIR = os.path.join("output", "kr")
DATA_OUTPUT_DIR = "data"
REPORT_OUTPUT_DIR = "report"
THEME_OUTPUT_DIR = "theme"
