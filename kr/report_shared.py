# -*- coding: utf-8 -*-
"""고정된 리포트 구조와 데이터 노출 로직을 담당하는 공유 렌더러."""

import json
from html import escape
from pathlib import Path
from urllib.parse import quote

from . import config
from .report_themes import DEFAULT_THEME, all_themes_css, get_theme, theme_ids

SESSION_LABEL = {"snapshot": "Snapshot"}

# 날짜 이동 화살표 (좌/우 chevron)
ARROWS = {
    "prev": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>',
    "next": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
}

TIER_COLLAPSE_LIMIT = 30
TIER_COLLAPSE_LIMITS = {"B": 10, "C": 10, "D": 10, "E": 10}

_REPORT_DIR = Path(__file__).resolve().parent


def _read_text(path):
    return path.read_text(encoding="utf-8")


def _script_tag(js):
    return f"<script>\n{js.rstrip()}\n</script>"


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지


def write_theme_map(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


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


def _market_flow_row(market, c):
    flows = [
        ("기관", "institution", c.get("flow_institution")),
        ("외인", "foreign", c.get("flow_foreign")),
        ("개인", "personal", c.get("flow_personal")),
    ]
    if all(value is None for _, _, value in flows):
        return ""
    # 7일치 히스토리가 있으면 카드를 버튼화해 클릭 시 모달을 연다.
    has_hist = bool(c.get("flow_history"))
    items = ""
    for label, key, value in flows:
        inner = (f'<span>{label}</span>'
                 f'<b class="mono {_cls(value or 0)}">{_fmt_flow(value)}</b>')
        if has_hist:
            items += (f'<button type="button" class="flow-item flow-open" '
                      f'data-fmkt="{market}" data-finv="{key}" '
                      f'aria-label="{market} {label} 최근 수급 추이 보기">{inner}</button>')
        else:
            items += f'<span class="flow-item">{inner}</span>'
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
          {_market_flow_row(m, c)}
        </div>"""
    return f"""
    <section class="reveal" id="sec-market">
      <div class="sec-head">{_section_icon("market", "시장별 요약")}<h2>시장별 요약</h2></div>
      <div class="mkt-grid">{cards}</div>
    </section>"""


def _delta(value, *, unit="", digits=0):
    """전일 대비 변화량을 ▲/▼ 칩으로. 증가=▲, 감소=▼, 0=– (중립 회색).
    숫자 부호만 표시하므로 의미(좋다/나쁘다)는 맥락에 맡긴다."""
    if value is None:
        return ""
    v = round(float(value), digits) if digits else int(value)
    if v > 0:
        arrow, cls, num = "▲", "delta-up", v
    elif v < 0:
        arrow, cls, num = "▼", "delta-down", -v
    else:
        arrow, cls, num = "–", "delta-flat", 0
    fmt = f"{num:,.{digits}f}" if digits else f"{num:,}"
    text = arrow if v == 0 else f"{arrow}{fmt}{unit}"
    return f'<span class="dg-delta {cls}">{text}</span>'


def _info(text):
    """ⓘ 아이콘 + 툴팁. 데스크톱은 hover, 모바일은 탭(focus)으로 뜬다.
    tabindex 로 모바일에서도 focus 가능, role=button + aria-label 로 접근성 확보."""
    safe = escape(text)
    return (f'<span class="dg-info" tabindex="0" role="button" aria-label="{safe}">ⓘ'
            f'<span class="dg-tip" role="tooltip">{safe}</span></span>')


def _diagnosis_block(market, d):
    """한 시장(코스피/코스닥)의 진단 블록: 시총 카드 3개 + 과열 신호 칩."""
    cap_cards = ""
    for c in d.get("caps", []):
        cls = _cls(c["avg_rate"])
        key = escape(f"{market} {c['label']}", quote=True)
        cap_cards += f"""
          <div class="dg-cap gm-open" role="button" tabindex="0" data-gkind="diagnosis" data-gkey="{key}">
            <div class="dg-cap-label">{c['label']}</div>
            <div class="dg-cap-rate mono {cls}">{_fmt(c['avg_rate'])}%</div>
            <div class="dg-cap-sub">{c['count']:,}종목 · 상승 {c['up_pct']}%</div>
          </div>"""

    chips = []
    if d.get("limit_up") is not None:
        key = escape(f"{market} 상한가 근접", quote=True)
        chips.append(f'<span class="dg-chip gm-open" role="button" tabindex="0" data-gkind="diagnosis" data-gkey="{key}"><span>상한가 근접</span>'
                     f'<b class="mono up">{d["limit_up"]}</b></span>')
    if d.get("limit_down") is not None:
        key = escape(f"{market} 하한가 근접", quote=True)
        chips.append(f'<span class="dg-chip gm-open" role="button" tabindex="0" data-gkind="diagnosis" data-gkey="{key}"><span>하한가 근접</span>'
                     f'<b class="mono down">{d["limit_down"]}</b></span>')
    if d.get("turnover") is not None:
        tip = "거래대금 ÷ 시가총액. 그날 시총의 몇 %가 거래됐는지 — 높을수록 거래가 활발(과열·패닉), 낮을수록 한산(관망)."
        delta = _delta(d.get("turnover_delta"), unit="%p", digits=2)
        chips.append(f'<span class="dg-chip"><span>회전율 {_info(tip)}</span>'
                     f'<b class="mono">{d["turnover"]}%</b>{delta}</span>')
    signal_row = f'<div class="dg-signals">{"".join(chips)}</div>' if chips else ""

    return f"""
      <div class="dg-block">
        <div class="dg-block-head">{market}</div>
        <div class="dg-caps">{cap_cards}</div>
        {signal_row}
      </div>"""


def _section_diagnosis(diag):
    """시장 진단: 코스피/코스닥별 시총 구간 강도 + 과열 신호(상한가·하한가·회전율)."""
    if not diag:
        return ""
    # 시총 카드가 하나라도 있는 시장만 렌더(데이터 없으면 섹션 자체 생략)
    blocks = "".join(
        _diagnosis_block(m, diag[m])
        for m in config.MARKETS
        if diag.get(m) and diag[m].get("caps")
    )
    if not blocks:
        return ""

    return f"""
    <section class="reveal" id="sec-diagnosis">
      <div class="sec-head">{_section_icon("market", "시장 진단")}<h2>시장 진단</h2>
        <span class="sec-note">시가총액 구간별 평균 등락률 · 보통주 기준</span></div>
      <div class="dg-markets">{blocks}</div>
    </section>"""


def _tier_rows(tiers, theme):
    rows = ""
    for name, lo, hi in config.TIERS:
        sub = tiers[name]
        # 티어 강조색은 테마 변수(--tier-X-2)를 참조 → data-theme 변경 시 실시간 반영
        color = f"var(--tier-{name}-2, #888)"
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
    <section class="reveal" id="sec-tiers">
      {toggle}
      <div class="sec-head">{_section_icon("tier", "종목 상승률 Tier")}<h2>종목 상승률 Tier</h2>{switch}</div>
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
    <section class="reveal tv-section" id="sec-{icon}">
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
    """섹터 티어 칩 — 클릭하면 해당 섹터 종목 리스트 모달을 연다."""
    name = escape(str(row.섹터))
    return (
        f'<span class="chip gm-open {_cls(row.초과)}" role="button" tabindex="0" '
        f'data-gkind="sector" data-gkey="{name}">'
        f'<span class="c-name">{row.섹터}</span>'
        f'<span class="c-rate mono">{_fmt(row.초과)}p</span></span>'
    )


def _sector_tier_rows(sector_tiers, theme):
    rows = ""
    for name, lo, hi in config.SECTOR_TIERS:
        sub = sector_tiers[name]
        color = f"var(--tier-{name}-2, #888)"
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
    <section class="reveal" id="sec-sector">
      <div class="sec-head">{_section_icon("sector", "섹터 상승률 Tier")}<h2>섹터 상승률 Tier</h2>
        <span class="sec-note">시장평균 {_fmt(market_avg)}% 기준 · 값은 초과수익(%p)</span></div>
      <div class="tiers">{rows}</div>
    </section>"""


_HEAT_RANGE = 4.5  # ±4.5% 에서 색 포화


def _heat_style(rate):
    """평균 등락률 → 테마 변수 기반의 히트맵 강조 강도."""
    ratio = min(abs(rate) / _HEAT_RANGE, 1.0)
    if rate > 0:
        color, soft, mid = "--up", "--up-soft", "--up-mid"
    elif rate < 0:
        color, soft, mid = "--down", "--down-soft", "--down-mid"
    else:
        color, soft, mid = "--flat", "--flat-soft", "--flat"
    strength = round(7 + ratio * 20)
    edge = round(32 + ratio * 48)
    glow = round(4 + ratio * 11)
    hover_glow = glow + 5
    stripe = round(3 + ratio * 3)
    return (
        f"--heat-color:var({color});--heat-soft:var({soft});--heat-mid:var({mid});"
        f"--heat-strength:{strength}%;--heat-edge:{edge}%;"
        f"--heat-glow:{glow}%;--heat-hover-glow:{hover_glow}%;"
        f"--heat-stripe:{stripe}px;"
    )


def _heat_card(r, group_kind="big"):
    name = escape(str(r.대테마))
    return f"""
        <div class="heat-cell gm-open {_cls(r.평균등락률)}" role="button" tabindex="0"
             data-gkind="{group_kind}" data-gkey="{name}" style="{_heat_style(r.평균등락률)}">
          <span class="h-name">{r.대테마}</span>
          <span class="h-val mono">{_fmt(r.평균등락률)}%</span>
          <span class="h-sub">{r.종목수}종목 · ▲{r.상승} ▼{r.하락}</span>
        </div>"""


def _section_heatmap(big_theme, big_theme_common=None):
    if big_theme is None or not len(big_theme):
        return ""
    all_cells = "".join(_heat_card(r, "big") for r in big_theme.itertuples())

    if big_theme_common is not None and len(big_theme_common):
        common_cells = "".join(_heat_card(r, "big_common") for r in big_theme_common.itertuples())
        toggle, switch = _rep_switch("bigThemeToggle")
        common_block = f'<div class="heatmap heatmap-common">{common_cells}</div>'
        all_class = "heatmap heatmap-all"
    else:
        toggle = switch = common_block = ""
        all_class = "heatmap"

    return f"""
    <section class="reveal" id="sec-big-theme">
      {toggle}
      <div class="sec-head">{_section_icon("heat", "대테마 히트맵")}<h2>대테마 히트맵</h2>{switch}</div>
      {common_block}
      <div class="{all_class}">{all_cells}</div>
    </section>"""


def _group_modal_html(group_members):
    data = group_members or {"diagnosis": {}, "sector": {}, "big": {}, "big_common": {}}
    payload = json.dumps(data, ensure_ascii=False)
    return f"""
    <script id="mb-group-data" type="application/json">{payload}</script>
    <div class="gm-modal" id="gmModal" hidden>
      <div class="gm-backdrop" data-close></div>
      <div class="gm-panel" role="dialog" aria-modal="true" aria-labelledby="gmTitle">
        <div class="gm-head">
          <h3 id="gmTitle" class="gm-title"></h3>
          <button class="gm-x" type="button" aria-label="닫기" data-close>&times;</button>
        </div>
        <div class="gm-sub" id="gmSub"></div>
        <div class="gm-list" id="gmList"></div>
      </div>
    </div>"""


def _flow_modal_html(by_market):
    """수급 카드 클릭 시 뜨는 '최근 7거래일 투자자별 순매수' 모달.

    데이터는 by_market[*]['flow_history'](최신순 행 리스트)를 그대로 주입하고,
    표 렌더링은 flow_modal.js 가 맡는다. 히스토리가 한 시장도 없으면 비활성.
    """
    data = {
        m: by_market[m]["flow_history"]
        for m in config.MARKETS
        if by_market.get(m, {}).get("flow_history")
    }
    if not data:
        return ""
    payload = json.dumps(data, ensure_ascii=False)
    return f"""
    <script id="mb-flow-data" type="application/json">{payload}</script>
    <div class="gm-modal" id="flowModal" hidden>
      <div class="gm-backdrop" data-fclose></div>
      <div class="gm-panel fm-panel" role="dialog" aria-modal="true" aria-labelledby="fmTitle">
        <div class="gm-head">
          <h3 id="fmTitle" class="gm-title"></h3>
          <button class="gm-x" type="button" aria-label="닫기" data-fclose>&times;</button>
        </div>
        <div class="gm-sub" id="fmSub"></div>
        <div class="fm-body" id="fmBody"></div>
      </div>
    </div>"""


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
        "function gtag(){dataLayer.push(arguments);}"
        "gtag('js',new Date());"
        f"gtag('config','{gid}');</script>"
    )


def _market_ctx(date_str, session, overall):
    """마스코트가 그날 시장 분위기로 대사를 고를 수 있도록 페이지에 주입할 컨텍스트.

    추세(trend)는 그 날짜 데이터 기준이라 페이지마다 baked 된다. 대사 '텍스트'는
    characters.json 에 두므로, 문구만 바꿀 땐 재빌드가 필요 없다(플래그만 baked).
    """
    if not overall:
        return {"date": date_str, "session": session}
    up, down = overall.get("up", 0), overall.get("down", 0)
    trend = "up" if up > down else "down" if down > up else "flat"
    return {
        "date": date_str,
        "session": session,
        "trend": trend,
        "upPct": overall.get("up_pct"),
        "downPct": overall.get("down_pct"),
    }


# 마스코트(곰·펭귄 등) 부트스트랩. 캐릭터·대사는 characters.json, 동작은 mascots.js
# 가 담당한다(리포트 페이지엔 설정 전역 + <script> 만 심는다). 갱신 시 두 파일만
# 고치면 되고 리포트 재생성은 불필요하다. __MB_CTX(시장 추세)만 페이지에 baked.
def _mascots_html(ctx=None):
    if not config.MASCOT_ENABLED:
        return ""
    try:
        # 마스코트 소스 겸 배포본은 docs/mascot 하나로 관리한다(중복 제거).
        mascot_version = int((_REPORT_DIR.parent / "docs" / "mascot" / "mascots.js").stat().st_mtime)
        js_url = f"/mascot/mascots.js?v={mascot_version}"
    except OSError:
        js_url = "/mascot/mascots.js"
    cfg = {
        "url": config.CHARACTERS_JSON_PATH,
        "base": "",
        "key": config.WEB3FORMS_KEY,
    }
    cfg_json = json.dumps(cfg, ensure_ascii=False)
    ctx_script = ""
    if ctx:
        ctx_json = json.dumps(ctx, ensure_ascii=False)
        ctx_script = f"\n  <script>window.__MB_CTX={ctx_json};</script>"
    return (
        f"{ctx_script}"
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
                f"보합 {overall.get('flat', 0):,}  |  거래대금·거래량 Top30, 종목 상승률 Tier")
    else:
        desc = f"{config.MARKET_SUBTITLE} 시장 분위기 요약 — 거래대금·거래량 Top30, 종목 상승률 Tier"

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


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, diagnosis=None, top=None, bottom=None, sector_top=None, sector_bottom=None, sector_tiers=None, sector_market_avg=None, big_theme=None, big_theme_common=None, group_members=None, top_value=None, top_value_common=None, top_volume=None, top_volume_common=None, tiers_common=None, date_nav=None, theme_name=DEFAULT_THEME):
    theme = get_theme(theme_name)
    body = _section_market(by_market)
    body += _section_diagnosis(diagnosis)
    body += _section_top_value(top_value, top_value_common)
    body += _section_top_volume(top_volume, top_volume_common)
    body += _section_tiers(tiers, theme, tiers_common)
    if sector_tiers:
        body += _section_sector_tiers(sector_tiers, sector_market_avg, theme)
    body += _section_heatmap(big_theme, big_theme_common)
    body += _group_modal_html(group_members)
    body += _flow_modal_html(by_market)
    html = _PAGE.format(
        date=_date_label(date_str),
        og_tags=_og_tags_html(date_str, overall),
        ga=_ga_html(),
        mascots=_mascots_html(_market_ctx(date_str, session, overall)),
        date_nav=_date_nav_html(date_str, date_nav),
        session_label=SESSION_LABEL.get(session, session),
        generated_at=generated_at,
        report_title=config.MARKET_NAME,
        market_subtitle=config.MARKET_SUBTITLE,
        year=date_str[:4],
        themes_css=all_themes_css(theme_name),
        report_css=_REPORT_CSS,
        default_theme=theme_name,
        theme_ids_json=json.dumps(theme_ids(), ensure_ascii=False),
        group_modal_js=_GROUP_MODAL_JS,
        flow_modal_js=_FLOW_MODAL_JS,
        body=body,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


_TEMPLATE_DIR = _REPORT_DIR / "templates"
_ASSET_DIR = _REPORT_DIR / "assets"
_PAGE = _read_text(_TEMPLATE_DIR / "report.html")
_REPORT_CSS = _read_text(_ASSET_DIR / "report.css")
_GROUP_MODAL_JS = _script_tag(_read_text(_ASSET_DIR / "group_modal.js"))
_FLOW_MODAL_JS = _script_tag(_read_text(_ASSET_DIR / "flow_modal.js"))
