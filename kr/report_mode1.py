# -*- coding: utf-8 -*-
"""Mode 1 테마 래퍼."""

from .report_shared import write_csv
from .report_shared import write_html as _write_shared_html


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top=None, bottom=None, sector_top=None, sector_bottom=None, sector_tiers=None, sector_market_avg=None, big_theme=None, top_value=None, top_value_common=None, tiers_common=None):
    _write_shared_html(
        path,
        date_str=date_str,
        session=session,
        generated_at=generated_at,
        overall=overall,
        by_market=by_market,
        tiers=tiers,
        tiers_common=tiers_common,
        top=top,
        bottom=bottom,
        sector_top=sector_top,
        sector_bottom=sector_bottom,
        sector_tiers=sector_tiers,
        sector_market_avg=sector_market_avg,
        big_theme=big_theme,
        top_value=top_value,
        top_value_common=top_value_common,
        theme_name="mode1",
    )
