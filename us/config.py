# -*- coding: utf-8 -*-
"""US 시장 설정."""

import os

BASE_DIR = os.path.dirname(__file__)
MARKET_KEY = "us"
MARKET_NAME = "미국 증시"
MARKET_SUBTITLE = "NYSE · NASDAQ · AMEX"
MARKETS = ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "US")
STOCK_URL_TEMPLATE = "https://finance.yahoo.com/quote/{symbol}"


def report_filename(date_str: str) -> str:
    """리포트 HTML 파일명 규칙(단일 출처). KR 과 동일하게 index_YYYYMMDD.html.

    시장 구분은 폴더(output/kr·output/us)로 하므로 파일명엔 날짜만 둔다.
    """
    return f"index_{date_str}.html"

TIERS = [
    ("S",   25.0,  999.0),
    ("A",   15.0,   25.0),
    ("B",    5.0,   15.0),
    ("C",    0.0,    5.0),
    ("D",   -5.0,    0.0),
    ("E",  -15.0,   -5.0),
    ("F",  -25.0,  -15.0),
    ("G", -999.0,  -25.0),
]

UP_TIERS = ["S", "A", "B", "C"]
DOWN_TIERS = ["D", "E", "F", "G"]
MAX_PER_TIER = None
MIN_THEME_STOCKS = 2

THEME_MAP_FILE = os.path.join(BASE_DIR, "theme_map.csv")

OUTPUT_DIR = os.path.join("output", "us")
DATA_OUTPUT_DIR = "data"
REPORT_OUTPUT_DIR = "report"
THEME_OUTPUT_DIR = "theme"
