# -*- coding: utf-8 -*-
"""고정된 리포트 구조와 데이터 노출 로직을 담당하는 공유 렌더러."""

import json
from html import escape
from urllib.parse import quote

from . import config
from .report_themes import get_theme

SESSION_LABEL = {"snapshot": "Snapshot"}

# 날짜 이동 화살표 (좌/우 chevron)
ARROWS = {
    "prev": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>',
    "next": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
}

TIER_COLLAPSE_LIMIT = 30
TIER_COLLAPSE_LIMITS = {"B": 10, "C": 10, "D": 10, "E": 10}


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────
def _cls(rate):
    return "up" if rate > 0 else "down" if rate < 0 else "flat"


def _fmt(rate):
    return f"+{rate:.2f}" if rate > 0 else f"{rate:.2f}"


def _fmt_index(value):
    return f"{value:,.2f}" if value is not None else "N/A"


def _fmt_flow(value):
    if value is None:
        return "N/A"
    return f"{value:+,.0f}억"


def _fmt_amount(value):
    """거래대금(원) → 조/억원 단위 컴팩트 표기."""
    if value is None:
        return "N/A"
    v = float(value)
    if v >= 1e12:
        return f"{v / 1e12:.1f}조"
    return f"{round(v / 1e8):,}억"


def _strength_bar(c):
    return (
        f'<div class="bar" role="img" aria-label="상승 {c["up_pct"]}% 하락 {c["down_pct"]}%">'
        f'<span class="seg up"   style="width:{c["up_pct"]}%"></span>'
        f'<span class="seg flat" style="width:{c["flat_pct"]}%"></span>'
        f'<span class="seg down" style="width:{c["down_pct"]}%"></span>'
        f'</div>'
    )


def _market_flow_row(c):
    flows = [
        ("기관", c.get("flow_institution")),
        ("외인", c.get("flow_foreign")),
        ("개인", c.get("flow_personal")),
    ]
    if all(value is None for _, value in flows):
        return ""
    items = "".join(
        f'<span class="flow-item"><span>{label}</span>'
        f'<b class="mono {_cls(value or 0)}">{_fmt_flow(value)}</b></span>'
        for label, value in flows
    )
    return f'<div class="mkt-flow">{items}</div>'


def _stock_chip(row):
    code = str(row.종목코드).zfill(6)
    url = config.STOCK_URL_TEMPLATE.format(code=code, code6=code, symbol=code)
    return (
        f'<a class="chip {_cls(row.등락률)}" href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<span class="c-name">{row.종목명}</span>'
        f'<span class="c-rate mono">{_fmt(row.등락률)}</span></a>'
    )


def _section_icon(name, label):
    icons = {
        "market": (
            '<path d="M4.5 16.5h15"/>'
            '<path d="M6.5 14.5l3.2-3.6 3.1 2.2 4.7-6.1"/>'
            '<path d="M16.5 7h3v3"/>'
        ),
        "money": (
            '<circle cx="12" cy="12" r="7.5"/>'
            '<path d="M7.7 9.2l1.5 5.6 2.8-5.6 2.8 5.6 1.5-5.6"/>'
            '<path d="M7.3 12h9.4"/>'
        ),
        "volume": (
            '<path d="M5 19.5V11"/>'
            '<path d="M10 19.5V5"/>'
            '<path d="M15 19.5v-6"/>'
            '<path d="M20 19.5V8"/>'
            '<path d="M3.5 19.5h17"/>'
        ),
        "tier": (
            '<path d="M12 4.7l2.1 4.2 4.6.7-3.3 3.2.8 4.6-4.2-2.2-4.2 2.2.8-4.6-3.3-3.2 4.6-.7z"/>'
        ),
        "sector": (
            '<rect x="5" y="5" width="5.5" height="5.5" rx="1.4"/>'
            '<rect x="13.5" y="5" width="5.5" height="5.5" rx="1.4"/>'
            '<rect x="5" y="13.5" width="5.5" height="5.5" rx="1.4"/>'
            '<rect x="13.5" y="13.5" width="5.5" height="5.5" rx="1.4"/>'
        ),
        "heat": (
            '<path d="M12 20c3.1 0 5.5-2.2 5.5-5.4 0-2.6-1.6-4.2-3.2-5.7-.9-.9-1.8-1.7-2.1-3.1-2.2 1.5-3.3 3.3-3.1 5.2-.8-.5-1.4-1.2-1.7-2.1-.8 1.2-1.1 2.4-1.1 3.8C6.3 16.8 8.7 20 12 20z"/>'
            '<path d="M12 17.6c1.4 0 2.4-1 2.4-2.3 0-1-.5-1.7-1.2-2.3-.5-.5-.9-.9-1-1.6-1.2.9-1.8 1.9-1.6 3-.5-.3-.8-.7-1-1.2-.3.6-.5 1.2-.5 1.8 0 1.5 1.1 2.6 2.9 2.6z"/>'
        ),
    }
    svg = icons[name]
    return (
        f'<span class="num icon-{name}" role="img" aria-label="{label}">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true">{svg}</svg></span>'
    )


# ──────────────────────────────────────────────
# sections
# ──────────────────────────────────────────────
def _metric_cards(c):
    """시장별 상승/보합/하락 카드."""
    return f"""
          <div class="metrics mkt-metrics">
            <div class="metric up-card">
              <div class="m-label up">상승</div>
              <div class="m-value mono up">{c['up']:,}<span class="m-pct">{c['up_pct']}%</span></div>
            </div>
            <div class="metric flat-card">
              <div class="m-label flat">보합</div>
              <div class="m-value mono flat">{c['flat']:,}<span class="m-pct">{c['flat_pct']}%</span></div>
            </div>
            <div class="metric down-card">
              <div class="m-label down">하락</div>
              <div class="m-value mono down">{c['down']:,}<span class="m-pct">{c['down_pct']}%</span></div>
            </div>
          </div>"""


def _section_market(by_market):
    cards = ""
    for m in config.MARKETS:
        c = by_market[m]
        index_rate = c.get("index_rate")
        index_change = c.get("index_change")
        rate_cls = _cls(index_rate or 0)
        index_rate_label = f"{_fmt(index_rate)}%" if index_rate is not None else "N/A"
        index_change_label = _fmt(index_change) if index_change is not None else "N/A"
        cards += f"""
        <div class="mkt-card">
          <div class="mkt-head">
            <h3>{m}</h3>
            <span class="mkt-head-idx">
              <span class="mkt-index mono">{_fmt_index(c.get('index_value'))}</span>
              <span class="mkt-rate mono {rate_cls}">{index_rate_label}</span>
              <span class="mkt-change mono {rate_cls}">{index_change_label}</span>
            </span>
          </div>
          {_metric_cards(c)}
          {_strength_bar(c)}
          {_market_flow_row(c)}
        </div>"""
    return f"""
    <section class="reveal">
      <div class="sec-head">{_section_icon("market", "시장별 요약")}<h2>시장별 요약</h2></div>
      <div class="mkt-grid">{cards}</div>
    </section>"""


def _tier_rows(tiers, theme):
    rows = ""
    tier_colors = theme["tier_colors"]
    for name, lo, hi in config.TIERS:
        sub = tiers[name]
        color = tier_colors.get(name, "#888")
        # 티어 범위 라벨
        if hi >= 999:
            rng = f"+{lo:.0f}% 이상"
        elif lo <= -999:
            rng = f"{hi:.0f}% 이하"
        elif name in config.UP_TIERS:
            rng = f"+{lo:.0f} ~ +{hi:.0f}%"
        elif name in config.DOWN_TIERS:
            if min(lo, hi) <= -999:
                rng = f"{max(lo, hi):.0f}% 이하"
            else:
                rng = f"{max(lo, hi):.0f} ~ {min(lo, hi):.0f}%"
        else:
            rng = f"{lo:.0f} ~ {hi:.0f}%"

        total = len(sub)
        if total:
            collapse_limit = TIER_COLLAPSE_LIMITS.get(name, TIER_COLLAPSE_LIMIT)
            tier_rows = list(sub.itertuples())
            visible = tier_rows[:collapse_limit]
            hidden = tier_rows[collapse_limit:]
            chips = "".join(_stock_chip(r) for r in visible)
            if hidden:
                hidden_chips = "".join(_stock_chip(r) for r in hidden)
                chips += f"""
                <details class="tier-more">
                  <summary class="mono">+{len(hidden)}개 더 보기</summary>
                  <div class="tier-more-list">{hidden_chips}</div>
                </details>"""
            count = f'<span class="tier-count mono">{len(sub)}</span>'
        else:
            chips = '<span class="empty">—</span>'
            count = ""

        rows += f"""
        <div class="tier-row" style="--tc:{color}">
          <div class="tier-side">
            <div class="tier-badge t-{name}">{name}</div>
            <div class="tier-range mono">{rng}</div>
            {count}
          </div>
          <div class="tier-stocks">{chips}</div>
        </div>"""
    return rows


def _rep_switch(toggle_id):
    """보통주(기본) ↔ 전종목 토글 스위치 + 숨김 체크박스."""
    toggle = f'<input type="checkbox" class="rep-toggle" id="{toggle_id}">'
    switch = f"""
        <label class="rep-switch" for="{toggle_id}">
          <span class="seg seg-l">보통주</span>
          <span class="seg seg-r">전종목</span>
        </label>"""
    return toggle, switch


def _section_tiers(tiers, theme, tiers_common=None):
    all_rows = _tier_rows(tiers, theme)
    has_common = tiers_common is not None

    if has_common:
        common_rows = _tier_rows(tiers_common, theme)
        toggle, switch = _rep_switch("tierToggle")
        common_block = f'<div class="tiers tiers-common">{common_rows}</div>'
    else:
        toggle = switch = common_block = ""

    return f"""
    <section class="reveal">
      {toggle}
      <div class="sec-head">{_section_icon("tier", "종목 Tier")}<h2>종목 Tier</h2>{switch}</div>
      {common_block}
      <div class="tiers tiers-all">{all_rows}</div>
    </section>"""


TV_COLLAPSE_LIMIT = 10


def _tv_value_meta(r):
    """거래대금 섹션 메타: 등락률 + 거래대금."""
    cls = _cls(r.등락률)
    return (
        f'<span class="tv-rate mono {cls}">{_fmt(r.등락률)}%</span>'
        f'<span class="tv-a mono">{_fmt_amount(r.거래대금)}</span>'
    )


def _tv_volume_meta(r):
    """거래량 급증 섹션 메타: 배율(x) 강조 + 등락률."""
    cls = _cls(r.등락률)
    return (
        f'<span class="tv-mult mono">{r.거래량배율:.1f}x</span>'
        f'<span class="tv-rate mono {cls}">{_fmt(r.등락률)}%</span>'
    )


def _tv_chip(i, r, meta_fn):
    code = str(r.종목코드).zfill(6)
    url = config.STOCK_URL_TEMPLATE.format(code=code, code6=code, symbol=code)
    cls = _cls(r.등락률)
    name = str(r.종목명)
    name_attr = escape(name, quote=True)
    return (
        f'<a class="tv-chip {cls}" href="{url}" target="_blank" rel="noopener noreferrer"'
        f' title="{name_attr}" aria-label="{name_attr}">'
        f'<span class="tv-top">'
        f'<span class="tv-r mono">{i}</span>'
        f'<span class="tv-n">{r.종목명}</span>'
        f'</span>'
        f'<span class="tv-meta">{meta_fn(r)}</span></a>'
    )


def _tv_chip_grid(rows, grid_cls, meta_fn):
    all_rows = list(rows.itertuples())
    visible = all_rows[:TV_COLLAPSE_LIMIT]
    hidden = all_rows[TV_COLLAPSE_LIMIT:]
    chips = "".join(_tv_chip(i + 1, r, meta_fn) for i, r in enumerate(visible))
    if hidden:
        hidden_chips = "".join(
            _tv_chip(i + TV_COLLAPSE_LIMIT + 1, r, meta_fn) for i, r in enumerate(hidden)
        )
        chips += f"""
        <details class="tv-more">
          <summary class="mono">+{len(hidden)}개 더 보기</summary>
          <div class="tv-more-grid">{hidden_chips}</div>
        </details>"""
    return f'<div class="tv-chips {grid_cls}">{chips}</div>'


def _tv_section(*, icon, title, all_rows, common_rows, toggle_id, meta_fn):
    """거래대금/거래량 등 '순위 칩 그리드 + 보통주 토글' 공용 섹션."""
    if all_rows is None or not len(all_rows):
        return ""

    all_grid = _tv_chip_grid(all_rows, "tv-all", meta_fn)
    has_common = common_rows is not None and len(common_rows)

    if has_common:
        common_grid = _tv_chip_grid(common_rows, "tv-common", meta_fn)
        toggle, switch = _rep_switch(toggle_id)
    else:
        common_grid = toggle = switch = ""

    return f"""
    <section class="reveal tv-section">
      {toggle}
      <div class="sec-head">{_section_icon(icon, title)}<h2>{title}</h2>{switch}</div>
      {common_grid}
      {all_grid}
    </section>"""


def _section_top_value(top_value, top_value_common=None):
    return _tv_section(
        icon="money", title="거래대금 Top30",
        all_rows=top_value, common_rows=top_value_common,
        toggle_id="tvToggle", meta_fn=_tv_value_meta,
    )


def _section_top_volume(top_volume, top_volume_common=None):
    return _tv_section(
        icon="volume", title="거래량 급증 Top30",
        all_rows=top_volume, common_rows=top_volume_common,
        toggle_id="tvolToggle", meta_fn=_tv_volume_meta,
    )


def _sector_chip(row):
    """섹터 티어 칩 — 값은 시장 대비 초과수익(%p), 색은 초과수익 부호."""
    return (
        f'<span class="chip {_cls(row.초과)}">'
        f'<span class="c-name">{row.섹터}</span>'
        f'<span class="c-rate mono">{_fmt(row.초과)}p</span></span>'
    )


def _sector_tier_rows(sector_tiers, theme):
    rows = ""
    tier_colors = theme["tier_colors"]
    for name, lo, hi in config.SECTOR_TIERS:
        sub = sector_tiers[name]
        color = tier_colors.get(name, "#888")
        if hi >= 999:
            rng = f"+{lo:.1f}%p 이상"
        elif lo <= -999:
            rng = f"{hi:.1f}%p 이하"
        elif name in config.UP_TIERS:
            rng = f"+{lo:.1f} ~ +{hi:.1f}%p"
        elif name in config.DOWN_TIERS:
            rng = f"{max(lo, hi):.1f} ~ {min(lo, hi):.1f}%p"
        else:
            rng = f"{lo:.1f} ~ {hi:.1f}%p"

        if len(sub):
            chips = "".join(_sector_chip(r) for r in sub.itertuples())
            count = f'<span class="tier-count mono">{len(sub)}</span>'
        else:
            chips = '<span class="empty">—</span>'
            count = ""

        rows += f"""
        <div class="tier-row" style="--tc:{color}">
          <div class="tier-side">
            <div class="tier-head">
              <div class="tier-badge t-{name}">{name}</div>
              <!--{count}-->
            </div>
            <div class="tier-range mono">{rng}</div>
          </div>
          <div class="tier-stocks">{chips}</div>
        </div>"""
    return rows


def _section_sector_tiers(sector_tiers, market_avg, theme):
    if not sector_tiers:
        return ""
    rows = _sector_tier_rows(sector_tiers, theme)
    return f"""
    <section class="reveal">
      <div class="sec-head">{_section_icon("sector", "섹터 Tier")}<h2>섹터 Tier</h2>
        <span class="sec-note">시장평균 {_fmt(market_avg)}% 기준 · 값은 초과수익(%p)</span></div>
      <div class="tiers">{rows}</div>
    </section>"""


_HEAT_RANGE = 3.0  # ±3% 에서 색 포화


def _lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def _heat_style(rate):
    """평균 등락률 → 카드 배경/글자색 (한국식: 상승 빨강, 하락 파랑)."""
    white, up, down = (255, 255, 255), (224, 49, 49), (28, 126, 214)
    ratio = min(abs(rate) / _HEAT_RANGE, 1.0)
    t = 0.12 + 0.88 * ratio
    if rate > 0:
        bg = _lerp(white, up, t)
    elif rate < 0:
        bg = _lerp(white, down, t)
    else:
        bg, t = (241, 243, 245), 0.2
    fg = "#ffffff" if t >= 0.55 else "#212529"
    return f"background:rgb({bg[0]},{bg[1]},{bg[2]});color:{fg}"


def _heat_card(r):
    return f"""
        <div class="heat-cell" style="{_heat_style(r.평균등락률)}">
          <span class="h-name">{r.대테마}</span>
          <span class="h-val mono">{_fmt(r.평균등락률)}%</span>
          <span class="h-sub">{r.종목수}종목 · ▲{r.상승} ▼{r.하락}</span>
        </div>"""


def _section_heatmap(big_theme):
    if big_theme is None or not len(big_theme):
        return ""
    cells = "".join(_heat_card(r) for r in big_theme.itertuples())
    return f"""
    <section class="reveal">
      <div class="sec-head">{_section_icon("heat", "대테마 히트맵")}<h2>대테마 히트맵</h2>
        <span class="sec-note">평균 등락률 · 강한 → 약한</span></div>
      <div class="heatmap">{cells}</div>
    </section>"""


def _date_label(date_str):
    return f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"


def _ga_html():
    """Google Analytics 4 스크립트. 측정 ID 없으면 빈 문자열."""
    gid = config.GA_MEASUREMENT_ID
    if not gid:
        return ""
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
        "<script>window.dataLayer=window.dataLayer||[];"
        "function gtag(){{dataLayer.push(arguments);}}"
        "gtag('js',new Date());"
        f"gtag('config','{gid}');</script>"
    ).replace("{{", "{").replace("}}", "}")


# 마스코트(곰·펭귄 등) 부트스트랩. 캐릭터·대사는 characters.json, 동작은 mascots.js
# 가 담당한다(리포트 페이지엔 설정 전역 + <script> 만 심는다). 갱신 시 두 파일만
# 고치면 되고 리포트 재생성은 불필요하다.
def _mascots_html():
    if not config.MASCOT_ENABLED:
        return ""
    js_url = "/mascots.js"
    base = config.SITE_BASE_URL
    if base and js_url.startswith("/"):
        js_url = base + js_url
    cfg = {
        "url": config.CHARACTERS_JSON_PATH,
        "base": base,
        "key": config.WEB3FORMS_KEY,
    }
    cfg_json = json.dumps(cfg, ensure_ascii=False)
    return (
        f"\n  <script>window.__MB_MASCOT={cfg_json};</script>"
        f'\n  <script src="{js_url}" defer></script>'
    )


def _og_tags_html(date_str, overall):
    """카톡/SNS 공유용 Open Graph 메타태그.

    og:url / og:image 는 배포 기준 URL(config.SITE_BASE_URL)이 있어야 절대경로가
    되어 카톡 썸네일이 뜬다. 없으면 제목·설명만 넣는다(이미지 카드 없음).
    """
    label = _date_label(date_str)
    title = f"{config.MARKET_NAME} 데일리 브리프 · {label}"
    if overall:
        desc = (f"상승 {overall.get('up', 0):,} · 하락 {overall.get('down', 0):,} · "
                f"보합 {overall.get('flat', 0):,}  |  거래대금·거래량 Top30, 종목 Tier")
    else:
        desc = f"{config.MARKET_SUBTITLE} 시장 분위기 요약 — 거래대금·거래량 Top30, 종목 Tier"

    tags = [
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{escape(title, quote=True)}">',
        f'<meta property="og:description" content="{escape(desc, quote=True)}">',
        f'<meta property="og:site_name" content="{escape(config.MARKET_NAME, quote=True)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(title, quote=True)}">',
        f'<meta name="twitter:description" content="{escape(desc, quote=True)}">',
    ]
    base = config.SITE_BASE_URL
    if base:
        page_url = f"{base}/{config.MARKET_KEY}/{date_str}/"
        img_url = f"{page_url}thumb.png"
        tags += [
            f'<meta property="og:url" content="{page_url}">',
            f'<meta property="og:image" content="{img_url}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            f'<meta name="twitter:image" content="{img_url}">',
        ]
    return "\n".join(tags)


def _date_nav_html(date_str, date_nav):
    """상단 날짜 이동 바: ‹ 이전  현재날짜  다음 › . 링크 없으면 비활성."""
    if not date_nav:
        return ""

    def arrow(link, label, cls, title):
        if link:
            href = quote(link)   # 파일명에 공백·대괄호가 있어 URL 인코딩
            return (f'<a class="date-nav-btn {cls}" href="{href}" '
                    f'aria-label="{title}" title="{title} ({_date_label(label)})">{ARROWS[cls]}</a>')
        return f'<span class="date-nav-btn {cls} is-disabled" aria-hidden="true">{ARROWS[cls]}</span>'

    prev_btn = arrow(date_nav.get("prev_link"), date_nav.get("prev_date"), "prev", "이전 거래일")
    next_btn = arrow(date_nav.get("next_link"), date_nav.get("next_date"), "next", "다음 거래일")
    return (
        '<nav class="date-nav" aria-label="날짜 이동">'
        f'{prev_btn}'
        f'<span class="date-nav-cur mono">{_date_label(date_str)}</span>'
        f'{next_btn}'
        '</nav>'
    )


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top=None, bottom=None, sector_top=None, sector_bottom=None, sector_tiers=None, sector_market_avg=None, big_theme=None, top_value=None, top_value_common=None, top_volume=None, top_volume_common=None, tiers_common=None, date_nav=None, theme_name="mode1"):
    theme = get_theme(theme_name)
    body = _section_market(by_market)
    #body += _section_heatmap(big_theme)
    body += _section_top_value(top_value, top_value_common)
    body += _section_top_volume(top_volume, top_volume_common)
    body += _section_tiers(tiers, theme, tiers_common)
    if sector_tiers:
        body += _section_sector_tiers(sector_tiers, sector_market_avg, theme)
    html = _PAGE.format(
        date=_date_label(date_str),
        og_tags=_og_tags_html(date_str, overall),
        ga=_ga_html(),
        mascots=_mascots_html(),
        date_nav=_date_nav_html(date_str, date_nav),
        session_label=SESSION_LABEL.get(session, session),
        generated_at=generated_at,
        report_title=config.MARKET_NAME,
        market_subtitle=config.MARKET_SUBTITLE,
        theme_css=theme["css"],
        body=body,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Brief — {date} {session_label}</title>
{og_tags}
{ga}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Quicksand:wght@400;500;600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
{theme_css}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; color:var(--ink);
    background:var(--body-bg);
    font-family:var(--sans); line-height:1.6; -webkit-font-smoothing:antialiased;
    letter-spacing:.005em;
  }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:44px 24px 80px; }}
  .mono {{ font-family:var(--round); font-weight:600; font-variant-numeric:tabular-nums; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }} .flat {{ color:var(--flat); }}

  /* 날짜 이동 바 */
  .date-nav {{ display:flex; align-items:center; justify-content:center; gap:10px;
               margin-top:18px; }}
  .date-nav-cur {{ min-width:118px; text-align:center; font-size:14.5px; font-weight:800;
                   color:var(--heading); letter-spacing:.02em;
                   padding:7px 16px; border-radius:999px;
                   background:var(--accent-soft); }}
  .date-nav-btn {{ display:inline-flex; align-items:center; justify-content:center;
                   width:34px; height:34px; border-radius:50%;
                   border:1px solid var(--line); background:var(--panel);
                   color:var(--sub); text-decoration:none;
                   transition:background .15s ease, color .15s ease, transform .12s ease;
                   box-shadow:var(--section-shadow); }}
  .date-nav-btn svg {{ width:18px; height:18px; fill:none; stroke:currentColor;
                       stroke-width:2.2; stroke-linecap:round; stroke-linejoin:round; }}
  .date-nav-btn:hover {{ background:var(--accent); color:#fff; transform:translateY(-1px); }}
  .date-nav-btn.is-disabled {{ opacity:.32; pointer-events:none; box-shadow:none; }}

  /* header */
  header {{ position:relative; margin-bottom:34px; padding-bottom:24px; text-align:center; }}
  header::after {{ content:""; position:absolute; left:50%; bottom:0; transform:translateX(-50%);
                   width:80px; height:3px; border-radius:3px;
                   background:linear-gradient(90deg,var(--up),var(--accent),var(--down)); }}
  .brand {{ display:inline-flex; align-items:center; gap:9px; margin-bottom:16px;
            padding:6px 16px; background:var(--accent-soft); border-radius:999px; }}
  .brand .dot {{ width:7px; height:7px; border-radius:50%; background:var(--accent);
                 animation:pulse 2.6s ease-in-out infinite; }}
  .brand .kicker {{ font-family:var(--round); font-size:11px; letter-spacing:.24em;
                    color:var(--accent); text-transform:uppercase; font-weight:700; }}
  header h1 {{ font-family:var(--serif); font-weight:700; font-size:44px; line-height:1.1;
               margin:0 0 16px; letter-spacing:-.01em; color:var(--heading); }}
  header h1 em {{ font-style:normal; color:var(--accent);
                  background:linear-gradient(120deg,var(--up),var(--accent));
                  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }}
  .meta-row {{ display:inline-flex; flex-wrap:wrap; justify-content:center; gap:8px 18px;
               font-family:var(--round); font-size:12.5px; color:var(--sub); font-weight:600; }}
  .meta-row b {{ color:var(--ink); }}
  .meta-row .sep {{ color:var(--faint); }}

  /* sections */
  section {{ background:var(--panel); border:1px solid var(--line);
             border-radius:24px; padding:26px 28px; margin-bottom:20px; position:relative;
             box-shadow:var(--section-shadow); }}
  .sec-head {{ display:flex; align-items:center; gap:12px; margin-bottom:22px; min-width:0; }}
  .num {{ font-family:var(--round); font-size:12px; font-weight:700; color:#fff;
          background:linear-gradient(135deg,var(--accent),var(--up));
          border-radius:50%; width:28px; height:28px; display:flex; align-items:center;
          justify-content:center; letter-spacing:0; box-shadow:0 3px 8px rgba(217,138,168,.3); }}
  .num svg {{ width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:2.05;
              stroke-linecap:round; stroke-linejoin:round; }}
  .sec-head h2 {{ font-family:var(--serif); font-weight:700; font-size:22px; margin:0;
                  letter-spacing:-.01em; color:var(--heading); }}
  .sec-note {{ margin-left:auto; font-family:var(--round); font-size:11.5px;
               color:var(--sub); letter-spacing:.03em; font-weight:600; }}

  /* summary */
  .metrics {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-bottom:20px; }}
  .metric {{ padding:18px 18px; border-radius:18px; text-align:center;
             min-width:0; overflow:hidden;
             background:linear-gradient(180deg,var(--panel2),var(--panel)); border:1px solid var(--line); }}
  .metric.up-card {{ background:linear-gradient(180deg,var(--up-soft),var(--panel)); border-color:var(--up-mid); }}
  .metric.down-card {{ background:linear-gradient(180deg,var(--down-soft),var(--panel)); border-color:var(--down-mid); }}
  .m-label {{ font-size:12px; color:var(--sub); margin-bottom:8px; letter-spacing:.02em; font-weight:700; }}
  .m-value {{ font-size:28px; font-weight:800; line-height:1; display:flex;
              align-items:baseline; gap:7px; justify-content:center; min-width:0; flex-wrap:wrap; }}
  .m-pct {{ font-size:13px; font-weight:600; opacity:.8; white-space:nowrap; }}
  .bar {{ display:flex; height:14px; border-radius:999px; overflow:hidden;
          background:var(--flat-soft); padding:0; }}
  .seg {{ height:100%; transition:width 1s cubic-bezier(.16,1,.3,1); }}
  .seg.up {{ background:linear-gradient(90deg,var(--up),#f6b0c1); }}
  .seg.down {{ background:linear-gradient(90deg,#b7d0f1,var(--down)); }}
  .seg.flat {{ background:var(--flat); opacity:.48; }}

  /* market cards */
  .mkt-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
  /* 시장 카드 안 상승/보합/하락 카드 (지수 밑, 컴팩트) */
  .mkt-metrics {{ gap:8px; margin:0; }}
  .mkt-metrics .metric {{ padding:11px 8px; border-radius:14px; }}
  .mkt-metrics .m-label {{ font-size:11px; margin-bottom:5px; }}
  .mkt-metrics .m-value {{ font-size:19px; gap:4px; }}
  .mkt-metrics .m-pct {{ font-size:10.5px; }}
  .mkt-card .bar {{ margin-top:13px; }}
  .mkt-card {{ padding:20px 22px; border-radius:20px;
              min-width:0; overflow:hidden;
              background:linear-gradient(180deg,var(--panel2),var(--panel));
              border:1px solid var(--line); }}
  .mkt-head {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px 14px; margin-bottom:14px; min-width:0; }}
  .mkt-head h3 {{ font-family:var(--round); font-size:16px; font-weight:700; margin:0;
                  letter-spacing:.04em; color:var(--heading); }}
  .mkt-head-idx {{ display:inline-flex; align-items:baseline; justify-content:flex-end; gap:8px; min-width:0; }}
  .mkt-index {{ font-size:17px; font-weight:850; color:var(--strong); }}
  .mkt-index, .mkt-rate, .mkt-change {{ max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .mkt-rate {{ font-size:14px; font-weight:800; }}
  .mkt-change {{ font-size:12px; font-weight:750; }}
  .mkt-flow {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:10px; }}
  .flow-item {{ display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px;
                min-width:0; padding:8px 6px; border:1px solid var(--line); border-radius:12px;
                background:color-mix(in srgb, var(--panel) 78%, transparent); font-family:var(--round);
                font-size:11px; line-height:1.1; font-weight:700; color:var(--sub); text-align:center; }}
  .flow-item b {{ max-width:100%; overflow:hidden; text-overflow:ellipsis;
                  font-size:11.5px; font-weight:850; line-height:1.1; white-space:nowrap; }}

  /* tiers */
  .tier-row {{ display:flex; gap:16px; padding:15px 0 15px 18px; position:relative;
               border-bottom:1px solid var(--line); }}
  .tier-row:last-child {{ border-bottom:0; }}
  .tier-row::before {{ content:""; position:absolute; left:0; top:15px; bottom:15px;
                       width:4px; border-radius:4px; background:var(--tc); opacity:.9; }}
  .tier-side {{ flex:0 0 92px; display:flex; flex-direction:column; align-items:flex-start; gap:6px; }}
  .tier-badge {{ width:40px; height:40px; border-radius:14px; font-family:var(--serif);
                 font-weight:700; font-size:20px; display:flex; align-items:center;
                 justify-content:center; color:#fff; }}
  .tier-badge.t-S {{ background:linear-gradient(145deg,var(--tier-S-1),var(--tier-S-2)); color:var(--tier-S-text); }}
  .tier-badge.t-A {{ background:linear-gradient(145deg,var(--tier-A-1),var(--tier-A-2)); color:var(--tier-A-text); }}
  .tier-badge.t-B {{ background:linear-gradient(145deg,var(--tier-B-1),var(--tier-B-2)); color:var(--tier-B-text); }}
  .tier-badge.t-C {{ background:linear-gradient(145deg,var(--tier-C-1),var(--tier-C-2)); color:var(--tier-C-text); }}
  .tier-badge.t-D {{ background:linear-gradient(145deg,var(--tier-D-1),var(--tier-D-2)); color:var(--tier-D-text); }}
  .tier-badge.t-E {{ background:linear-gradient(145deg,var(--tier-E-1),var(--tier-E-2)); color:var(--tier-E-text); }}
  .tier-badge.t-F {{ background:linear-gradient(145deg,var(--tier-F-1),var(--tier-F-2)); color:var(--tier-F-text); }}
  .tier-badge.t-G {{ background:linear-gradient(145deg,var(--tier-G-1),var(--tier-G-2)); color:var(--tier-G-text); }}
  .tier-head {{ display:flex; align-items:center; gap:8px; }}  /* 섹터 티어: 뱃지 + 카운트 한 줄 */
  .tier-range {{ font-size:10.5px; color:var(--faint); letter-spacing:.01em; font-weight:600; }}
  .tier-count {{ font-size:11px; color:var(--sub); background:var(--flat-soft);
                 padding:2px 8px; border-radius:999px; font-weight:700; }}
  .tier-stocks {{ display:flex; flex-wrap:wrap; gap:7px; align-content:flex-start; padding-top:3px; }}
  .tier-more {{
    flex-basis:100%;
    margin-top:5px;
  }}
  .tier-more summary {{
    display:inline-flex;
    align-items:center;
    height:28px;
    cursor:pointer;
    color:var(--chip-text);
    border:1px solid color-mix(in srgb, var(--tc) 52%, var(--chip-base));
    background:color-mix(in srgb, var(--tc) 18%, var(--chip-base));
    border-radius:999px;
    padding:0 12px;
    font-size:11.5px;
    list-style:none;
    user-select:none;
    box-shadow:0 4px 12px rgba(216,138,168,.10);
  }}
  .tier-more summary::-webkit-details-marker {{ display:none; }}
  .tier-more summary::after {{
    content:"펼치기";
    margin-left:8px;
    color:var(--sub);
    font-family:var(--sans);
    font-size:11px;
    font-weight:700;
  }}
  .tier-more[open] summary::after {{ content:"접기"; }}
  .tier-more-list {{
    display:flex;
    flex-wrap:wrap;
    gap:7px;
    margin-top:9px;
    max-height:176px;
    overflow:auto;
    padding:2px 4px 5px 0;
  }}
  .tier-more-list::-webkit-scrollbar {{ width:8px; height:8px; }}
  .tier-more-list::-webkit-scrollbar-thumb {{
    background:color-mix(in srgb, var(--tc) 35%, var(--chip-base));
    border-radius:999px;
  }}
  .chip {{ display:inline-flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600;
           background:color-mix(in srgb, var(--tc) 14%, var(--chip-base));
           border:1px solid color-mix(in srgb, var(--tc) 50%, var(--chip-base));
           color:var(--chip-text);
           text-decoration:none;
           border-radius:999px; padding:5px 13px; white-space:nowrap;
           transition:transform .14s ease, box-shadow .14s ease; }}
  .chip:hover {{
    transform:translateY(-2px);
    box-shadow:0 4px 12px color-mix(in srgb, var(--tc) 24%, transparent);
  }}
  .chip .c-name {{ color:var(--chip-name); }}
  .chip .c-rate {{ color:color-mix(in srgb, var(--tc) 82%, var(--chip-rate-base)); font-size:12px; font-weight:800; }}
  .empty {{ color:var(--faint); font-size:13px; }}

  /* big-theme heatmap */
  .heatmap {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(152px,1fr)); gap:9px; }}
  .heat-cell {{ border-radius:14px; padding:14px 15px 13px; min-height:88px;
               display:flex; flex-direction:column; justify-content:center; gap:3px;
               box-shadow:0 2px 8px rgba(0,0,0,.06); transition:transform .15s ease; }}
  .heat-cell:hover {{ transform:translateY(-2px); }}
  .heat-cell .h-name {{ font-size:14px; font-weight:800; letter-spacing:-.01em; }}
  .heat-cell .h-val {{ font-size:23px; font-weight:800; letter-spacing:-.03em; line-height:1.1; }}
  .heat-cell .h-sub {{ font-size:11px; font-weight:600; opacity:.82; }}

  /* themes */
  .theme-list {{ display:flex; flex-direction:column; gap:3px; }}
  .theme-item {{ display:grid; grid-template-columns:30px 1fr 150px 74px 44px;
                 align-items:center; gap:14px; padding:11px 6px;
                 border-bottom:1px solid var(--line); border-radius:12px;
                 transition:background .15s ease; }}
  .theme-item:hover {{ background:var(--bg2); }}
  .theme-item:last-child {{ border-bottom:0; }}
  .t-rank {{ font-size:12px; color:var(--faint); font-weight:700; }}
  .t-name {{ font-size:14px; font-weight:700; color:var(--heading); }}
  .t-gauge {{ height:9px; background:var(--flat-soft); border-radius:999px; overflow:hidden; }}
  .t-fill {{ display:block; height:100%; border-radius:999px;
             transition:width 1.1s cubic-bezier(.16,1,.3,1); }}
  .t-fill.up {{ background:linear-gradient(90deg,#f59ab3,var(--up)); }}
  .t-fill.down {{ background:linear-gradient(90deg,var(--down),#a5c4ee); }}
  .t-fill.flat {{ background:var(--flat); }}
  .t-val {{ font-size:13.5px; font-weight:800; text-align:right; }}
  .t-cnt {{ font-size:12px; color:var(--faint); text-align:right; font-weight:600; }}

  /* 보통주(기본) ↔ 전종목 공용 토글 스위치 */
  .rep-toggle {{ position:absolute; width:0; height:0; opacity:0; pointer-events:none; }}
  .rep-switch {{ margin-left:auto; display:inline-flex; gap:2px; cursor:pointer;
                 background:var(--flat-soft); border-radius:999px; padding:3px;
                 font-family:var(--round); user-select:none; }}
  .rep-switch .seg {{ padding:4px 13px; border-radius:999px; font-size:11.5px; font-weight:700;
                      color:var(--sub); transition:color .18s ease, background .18s ease; }}
  .rep-switch .seg-l {{ background:linear-gradient(135deg,var(--accent),var(--up)); color:#fff; }}
  .rep-toggle:checked ~ .sec-head .rep-switch .seg-l {{ background:transparent; color:var(--sub); }}
  .rep-toggle:checked ~ .sec-head .rep-switch .seg-r {{
      background:linear-gradient(135deg,var(--accent),var(--up)); color:#fff; }}

  /* 토글 콘텐츠 전환 (기본=보통주 노출, 체크=전종목 노출) */
  .tiers.tiers-all {{ display:none; }}
  .rep-toggle:checked ~ .tiers.tiers-common {{ display:none; }}
  .rep-toggle:checked ~ .tiers.tiers-all {{ display:block; }}

  /* trading value top — 2줄 캐주얼 칩 */
  .tv-chips {{ display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:9px;
               grid-auto-rows:auto; align-items:start; }}
  .tv-chips > .tv-chip {{ height:64px; }}
  /* 펼치기 블록: 그리드 전체 폭을 차지하되 높이는 내용에 따라 자유롭게 */
  .tv-more {{ grid-column:1 / -1; align-self:start; margin-top:4px; }}
  .tv-more summary {{
    display:inline-flex; align-items:center; height:30px; cursor:pointer;
    color:var(--chip-text); border:1px solid var(--line);
    background:var(--flat-soft); border-radius:999px;
    padding:0 14px; font-size:11.5px; list-style:none; user-select:none;
  }}
  .tv-more summary::-webkit-details-marker {{ display:none; }}
  .tv-more summary::after {{ content:"펼치기"; margin-left:8px; color:var(--sub);
    font-family:var(--sans); font-size:11px; font-weight:700; }}
  .tv-more[open] summary::after {{ content:"접기"; }}
  .tv-more-grid {{ display:grid; grid-template-columns:repeat(5, minmax(0, 1fr));
                   gap:9px; grid-auto-rows:auto; align-items:start; margin-top:9px; }}
  .tv-more-grid > .tv-chip {{ height:64px; }}
  .tv-chips.tv-all {{ display:none; }}
  .rep-toggle:checked ~ .tv-chips.tv-common {{ display:none; }}
  .rep-toggle:checked ~ .tv-chips.tv-all {{ display:grid; }}

  .tv-chip {{ position:relative; display:flex; flex-direction:column; justify-content:center; gap:7px; text-decoration:none;
              border-radius:16px; padding:10px 12px 10px 14px; min-width:0; width:100%; overflow:hidden;
              background:linear-gradient(180deg,var(--panel2),var(--chip-base)); border:1px solid var(--line);
              transition:transform .14s ease, box-shadow .14s ease; }}
  .tv-chip:hover {{ transform:translateY(-2px); box-shadow:0 5px 14px rgba(79,65,72,.12); }}
  .tv-top {{ display:flex; align-items:center; gap:8px; min-width:0; width:100%; }}
  .tv-chip .tv-r {{ flex:0 0 auto; font-size:12px; font-weight:900; color:#fff;
                    min-width:22px; height:22px; display:inline-flex; align-items:center;
                    justify-content:center; border-radius:50%;
                    background:var(--flat-soft); color:var(--sub);
                    border:1px solid color-mix(in srgb, var(--faint) 28%, var(--chip-base));
                    box-shadow:none; }}
  .tv-chips > .tv-chip:nth-child(1) .tv-r {{ background:linear-gradient(135deg,#ffe18a,#f4b83f); color:#6b4a00; }}
  .tv-chips > .tv-chip:nth-child(2) .tv-r {{ background:linear-gradient(135deg,#f3f4f6,#b8c0cc); color:#4f5968; }}
  .tv-chips > .tv-chip:nth-child(3) .tv-r {{ background:linear-gradient(135deg,#f3bf8d,#b87333); color:#fff8f0; }}
  .tv-n {{ flex:1 1 auto; min-width:0; font-size:13px; font-weight:800; color:var(--chip-name);
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .tv-meta {{ display:flex; justify-content:space-between; align-items:center; gap:8px; min-width:0; width:100%; }}
  .tv-rate {{ flex:0 1 auto; min-width:0; max-width:100%; overflow:hidden; text-overflow:ellipsis;
              font-size:12px; line-height:1; font-weight:900; white-space:nowrap;
              padding:0; border-radius:0; background:transparent; }}
  .tv-a {{ flex:0 1 auto; min-width:0; max-width:100%; overflow:hidden; text-overflow:ellipsis;
           margin-left:auto; font-size:12.5px; line-height:1; font-weight:950; color:var(--strong);
           white-space:nowrap; padding:3px 0; letter-spacing:.01em; }}
  /* 거래량 급증: 배율 강조 알약 (좌) + 등락률 (우) */
  .tv-mult {{ flex:0 0 auto; font-size:11.5px; line-height:1; font-weight:900; white-space:nowrap;
              color:#fff; padding:3px 8px; border-radius:999px; letter-spacing:.01em;
              background:linear-gradient(135deg,var(--accent),var(--up)); }}
  .tv-meta .tv-mult ~ .tv-rate {{ margin-left:auto; }}

  footer {{ margin-top:32px; padding-top:20px; text-align:center; font-family:var(--round);
            font-size:11.5px; color:var(--faint); letter-spacing:.02em; font-weight:600; }}

  @keyframes fbrise {{ from{{opacity:0;transform:translateY(12px);}} to{{opacity:1;transform:none;}} }}
  /* 피드백 말풍선(펭귄) 내부 폼 */
  /* 카드 전체 폭(박스+입력란+보내기 모두 이 폭을 따른다) */
  .mascot-bubble.fb-bubble {{ width:200px; max-width:88vw; }}
  /* 피드백 폼 상태일 때만 넓게 (인사 상태는 260px) */
  .mascot-bubble.fb-bubble.mode-form {{ width:260px; }}
  .fb-bubble form .mascot-bubble-title {{ white-space:nowrap; }}
  .fb-bubble form {{ margin-top:6px; }}
  .fb-bubble textarea {{ width:100%; box-sizing:border-box; border:1px solid var(--line);
           border-radius:12px; padding:9px 11px; margin-bottom:8px;
           font-family:var(--sans); font-size:13px; background:var(--panel2); color:var(--ink);
           resize:vertical; }}
  .fb-bubble textarea:focus {{ outline:none; border-color:var(--accent); }}
  .fb-send {{ width:100%; border:none; cursor:pointer; border-radius:11px; padding:10px;
              font-family:var(--round); font-size:13px; font-weight:800; color:#fff;
              background:linear-gradient(135deg,var(--accent),var(--up)); }}
  .fb-msg {{ margin:9px 0 0; font-size:12px; font-weight:700; color:var(--sub); text-align:center; }}

  /* 마스코트 + 공지 말풍선 (좌하단) */
  .mascot-wrap {{ position:fixed; left:16px; bottom:16px; z-index:50;
                  display:flex; flex-direction:column; align-items:flex-start; gap:10px; }}
  .mascot-wrap.mascot-right {{ left:auto; right:16px; align-items:flex-end; }}
  .mascot-right .mascot-bubble::after {{ left:auto; right:40px; }}
  .mascot-btn {{ width:108px; height:auto; padding:0; border:none; cursor:grab;
                 touch-action:none; background:none; color:var(--accent); line-height:0;
                 filter:drop-shadow(0 6px 12px rgba(216,138,168,.4));
                 transition:transform .18s ease; animation:mascotBob 3.4s ease-in-out infinite; }}
  .mascot-btn:active {{ cursor:grabbing; }}
  /* 클릭 눌림 효과 (꾹 눌렀다 통통) */
  .mascot-btn.is-pressed {{ animation:none; transform:translateY(5px) scale(.9); }}
  .mascot-btn img {{ width:100%; height:auto; display:block; pointer-events:none; }}
  .mascot-btn:hover {{ transform:scale(1.06) rotate(-3deg); }}
  .mascot-btn.is-active {{ transform:scale(1.03); }}
  .mascot-btn svg {{ width:100%; height:auto; display:block; }}
  /* 캐릭터 숨김(×) 버튼 — 말풍선이 펼쳐지는 반대쪽 상단에 둬서 안 가리게.
     곰(좌하단,말풍선 오른쪽): 좌상단 / 펭귄(우하단,말풍선 왼쪽): 우상단 */
  .mascot-hide {{ position:absolute; top:-2px; left:-2px; right:auto; z-index:55;
                  width:24px; height:24px; border-radius:50%; cursor:pointer;
                  border:1px solid var(--line); background:var(--panel); color:var(--sub);
                  font-size:15px; line-height:1; display:flex; align-items:center;
                  justify-content:center; padding:0; box-shadow:0 2px 6px rgba(0,0,0,.12);
                  opacity:.6; transition:opacity .15s ease, transform .15s ease; }}
  .mascot-right .mascot-hide {{ left:auto; right:-2px; }}
  .mascot-hide:hover {{ opacity:1; transform:scale(1.1); }}
  @keyframes mascotBob {{ 0%,100%{{transform:translateY(0);}} 50%{{transform:translateY(-5px);}} }}
  /* 말풍선: 마스코트 버튼 위에 절대 배치 → 버튼은 제자리 고정, 말풍선만 위로 뜸.
     wrap 이 버튼폭(좁음)이라 shrink-to-fit 으로 눌리지 않게 width 를 명시한다. */
  .mascot-bubble {{ position:absolute; bottom:100%; left:0; margin-bottom:12px;
                    width:220px; max-width:80vw; background:var(--panel);
                    border:1px solid var(--line); border-radius:16px; padding:13px 30px 13px 15px;
                    box-shadow:0 10px 30px rgba(0,0,0,.16);
                    animation:fbrise .22s cubic-bezier(.16,1,.3,1); }}
  .mascot-right .mascot-bubble {{ left:auto; right:0; }}
  .mascot-bubble[hidden] {{ display:none; }}
  .mascot-bubble::after {{ content:""; position:absolute; left:24px; bottom:-7px;
                           width:14px; height:14px; background:var(--panel);
                           border-right:1px solid var(--line); border-bottom:1px solid var(--line);
                           transform:rotate(45deg); }}
  .mascot-bubble-title {{ font-family:var(--round); font-size:13.5px; font-weight:800;
                          color:var(--heading); margin-bottom:3px; }}
  .mascot-bubble-msg {{ font-size:12.5px; line-height:1.5; color:var(--sub); }}
  .mascot-x {{ position:absolute; top:6px; right:8px; border:none; background:none; cursor:pointer;
               font-size:18px; line-height:1; color:var(--faint); }}
  @media (max-width:430px) {{
    .mascot-btn {{ width:84px; height:auto; }}
    .mascot-bubble {{ max-width:190px; }}
  }}
  @media (prefers-reduced-motion:reduce) {{ .mascot-btn {{ animation:none; }} }}

  @keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:.4;}} }}
  .reveal {{ opacity:0; transform:translateY(16px); animation:rise .8s cubic-bezier(.16,1,.3,1) forwards; }}
  .reveal:nth-child(1){{animation-delay:.05s;}} .reveal:nth-child(2){{animation-delay:.14s;}}
  .reveal:nth-child(3){{animation-delay:.23s;}} .reveal:nth-child(4){{animation-delay:.32s;}}
  .reveal:nth-child(5){{animation-delay:.41s;}}
  @keyframes rise {{ to {{ opacity:1; transform:none; }} }}
  @media (prefers-reduced-motion:reduce) {{
    .reveal{{animation:none;opacity:1;transform:none;}} .seg,.t-fill{{transition:none;}}
    .brand .dot{{animation:none;}}
  }}

  @media (max-width:680px) {{
    .wrap {{ padding:32px 14px 64px; }}
    section {{ border-radius:18px; padding:20px 16px; }}
    header h1 {{ font-size:33px; }}
    .sec-head {{ flex-wrap:wrap; gap:10px; margin-bottom:18px; }}
    .sec-head h2 {{ font-size:20px; flex:1 1 auto; }}
    .sec-note {{ flex-basis:100%; margin-left:40px; }}
    .rep-switch {{ margin-left:0; flex:0 0 auto; }}
    .metrics {{ grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
    .metric {{ padding:13px 8px; border-radius:14px; }}
    .m-label {{ font-size:10.5px; margin-bottom:6px; }}
    .m-value {{ font-size:20px; gap:4px; }}
    .m-pct {{ font-size:10.5px; }}
    .mkt-grid {{ grid-template-columns:1fr; }}
    .heatmap {{ grid-template-columns:repeat(2,1fr); gap:7px; }}
    .heat-cell {{ min-height:78px; padding:12px 12px 11px; }}
    .heat-cell .h-val {{ font-size:20px; }}
    .theme-item {{ grid-template-columns:26px 1fr 60px 38px; }}
    .theme-item .t-gauge {{ display:none; }}
    .tv-chips {{ grid-template-columns:repeat(2, minmax(0, 1fr)); gap:7px; grid-auto-rows:auto; }}
    .tv-more-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); gap:7px; grid-auto-rows:auto; }}
    .tv-chips > .tv-chip, .tv-more-grid > .tv-chip {{ height:58px; }}
    .mkt-head {{ flex-wrap:wrap; }}
    .mkt-head-idx {{ width:100%; justify-content:flex-start; flex-wrap:wrap; }}
    .tv-chip {{ padding:9px 10px; gap:7px; }}
    .tv-chip .tv-n {{ font-size:12.5px; }}
    .tv-top {{ gap:7px; }}
    .tv-meta {{ gap:7px; }}
    .tv-rate {{ font-size:11.5px; padding:3px 5px; }}
    .tv-a {{ font-size:12px; }}
    .tier-row {{
      display:block;
      padding-left:14px;
    }}
    .tier-side {{
      width:100%;
      flex-direction:row;
      align-items:center;
      gap:8px;
      margin-bottom:10px;
    }}
    .tier-badge {{
      width:34px;
      height:34px;
      border-radius:12px;
      font-size:17px;
    }}
    .tier-range {{
      flex:1;
      font-size:11px;
    }}
    .tier-stocks {{
      display:flex;
      flex-wrap:wrap;
      align-items:flex-start;
      gap:7px;
      width:100%;
    }}
    .tier-more-list {{
      display:flex;
      flex-wrap:wrap;
      gap:7px;
      width:100%;
    }}
    .tier-more {{
      grid-column:1 / -1;
      width:100%;
    }}
    .tier-more-list {{
      margin-top:9px;
      max-height:220px;
    }}
    .chip {{
      min-width:0;
      width:auto;
      max-width:100%;
      justify-content:flex-start;
      gap:6px;
      padding:6px 9px;
    }}
    .chip .c-name {{
      min-width:0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }}
    .chip .c-rate {{
      flex:0 0 auto;
      font-size:11.5px;
    }}
  }}
  @media (max-width:380px) {{
    .tier-stocks,
    .tier-more-list {{
      display:flex;
      flex-wrap:wrap;
    }}
  }}
  @media (max-width:430px) {{
    .tv-chips {{ grid-template-columns:1fr; grid-auto-rows:auto; }}
    .tv-more-grid {{ grid-template-columns:1fr; grid-auto-rows:auto; }}
    .tv-chips > .tv-chip, .tv-more-grid > .tv-chip {{ height:auto; }}
    .tv-chip {{ min-height:44px; flex-direction:row; align-items:center; gap:8px; padding:8px 10px; }}
    .tv-chip .tv-top {{ flex:1 1 auto; min-width:0; overflow:hidden; }}
    .tv-chip .tv-meta {{ flex:0 0 120px; flex-direction:row; gap:6px; justify-content:flex-end; }}
    .tv-chip .tv-n {{ font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }}
    .tv-chip .tv-rate {{ font-size:12px; white-space:nowrap; }}
    .tv-chip .tv-a {{ font-size:12px; margin-left:0; }}
    .mkt-metrics .m-value {{
      flex-direction:column;
      align-items:center;
      gap:3px;
      font-size:17px;
      line-height:1.05;
    }}
    .mkt-metrics .m-pct {{ font-size:10px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand"><span class="dot"></span><span class="kicker">Market Brief · Daily</span></div>
    <h1>{report_title} <em>데일리 브리프</em></h1>
    <div class="meta-row">
      <span><b>{date}</b></span><span class="sep">·</span>
      <span><b>{session_label}</b></span><span class="sep">·</span>
      <span>{market_subtitle}</span><span class="sep">·</span>
      <span>기준 {generated_at}</span>
    </div>
    {date_nav}
  </header>
  {body}
  <footer>Market Brief V1 — 시장 분위기 파악용 경량 리포트 · 투자 판단의 근거가 아닙니다.</footer>
</div>
{mascots}
</body>
</html>"""
