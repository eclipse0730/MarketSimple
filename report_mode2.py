# -*- coding: utf-8 -*-
"""Mode 2 테마 래퍼."""

from report_shared import write_csv
from report_shared import write_html as _write_shared_html


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top, bottom):
    _write_shared_html(
        path,
        date_str=date_str,
        session=session,
        generated_at=generated_at,
        overall=overall,
        by_market=by_market,
        tiers=tiers,
        top=top,
        bottom=bottom,
        theme_name="mode2",
    )
