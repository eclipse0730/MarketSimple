# -*- coding: utf-8 -*-
"""고정된 리포트 구조와 데이터 노출 로직을 담당하는 공유 렌더러."""

from . import config
from .report_themes import get_theme

SESSION_LABEL = {"snapshot": "스냅샷"}

TIER_COLLAPSE_LIMIT = 30
TIER_COLLAPSE_LIMITS = {"C": 10, "D": 10, "E": 10}


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
      <div class="sec-head"><span class="num">01</span><h2>시장별 요약</h2></div>
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
      <div class="sec-head"><span class="num">03</span><h2>종목 Tier</h2>{switch}</div>
      {common_block}
      <div class="tiers tiers-all">{all_rows}</div>
    </section>"""


def _tv_chip_grid(rows, grid_cls):
    chips = ""
    for i, r in enumerate(rows.itertuples(), 1):
        code = str(r.종목코드).zfill(6)
        url = config.STOCK_URL_TEMPLATE.format(code=code, code6=code, symbol=code)
        cls = _cls(r.등락률)
        chips += f"""
        <a class="tv-chip {cls}" href="{url}" target="_blank" rel="noopener noreferrer">
          <span class="tv-r mono">{i}</span>
          <span class="tv-body">
            <span class="tv-n">{r.종목명}</span>
            <span class="tv-meta">
              <span class="tv-rate mono {cls}">{_fmt(r.등락률)}%</span>
              <span class="tv-a mono">{_fmt_amount(r.거래대금)}</span>
            </span>
          </span>
        </a>"""
    return f'<div class="tv-chips {grid_cls}">{chips}</div>'


def _section_top_value(top_value, top_value_common=None):
    if top_value is None or not len(top_value):
        return ""

    all_grid = _tv_chip_grid(top_value, "tv-all")
    has_common = top_value_common is not None and len(top_value_common)

    if has_common:
        common_grid = _tv_chip_grid(top_value_common, "tv-common")
        toggle, switch = _rep_switch("tvToggle")
    else:
        common_grid = ""
        toggle = ""
        switch = ""

    return f"""
    <section class="reveal tv-section">
      {toggle}
      <div class="sec-head"><span class="num">02</span><h2>거래대금 Top30</h2>{switch}</div>
      {common_grid}
      {all_grid}
    </section>"""


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
      <div class="sec-head"><span class="num">04</span><h2>섹터 Tier</h2>
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
      <div class="sec-head"><span class="num">02</span><h2>대테마 히트맵</h2>
        <span class="sec-note">평균 등락률 · 강한 → 약한</span></div>
      <div class="heatmap">{cells}</div>
    </section>"""


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top=None, bottom=None, sector_top=None, sector_bottom=None, sector_tiers=None, sector_market_avg=None, big_theme=None, top_value=None, top_value_common=None, tiers_common=None, theme_name="mode1"):
    theme = get_theme(theme_name)
    body = _section_market(by_market)
    #body += _section_heatmap(big_theme)
    body += _section_top_value(top_value, top_value_common)
    body += _section_tiers(tiers, theme, tiers_common)
    if sector_tiers:
        body += _section_sector_tiers(sector_tiers, sector_market_avg, theme)
    html = _PAGE.format(
        date=f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}",
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
  .sec-head {{ display:flex; align-items:center; gap:12px; margin-bottom:22px; }}
  .num {{ font-family:var(--round); font-size:12px; font-weight:700; color:#fff;
          background:linear-gradient(135deg,var(--accent),var(--up));
          border-radius:50%; width:28px; height:28px; display:flex; align-items:center;
          justify-content:center; letter-spacing:0; box-shadow:0 3px 8px rgba(217,138,168,.3); }}
  .sec-head h2 {{ font-family:var(--serif); font-weight:700; font-size:22px; margin:0;
                  letter-spacing:-.01em; color:var(--heading); }}
  .sec-note {{ margin-left:auto; font-family:var(--round); font-size:11.5px;
               color:var(--sub); letter-spacing:.03em; font-weight:600; }}

  /* summary */
  .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:20px; }}
  .metric {{ padding:18px 18px; border-radius:18px; text-align:center;
             background:linear-gradient(180deg,var(--panel2),var(--panel)); border:1px solid var(--line); }}
  .metric.up-card {{ background:linear-gradient(180deg,var(--up-soft),var(--panel)); border-color:var(--up-mid); }}
  .metric.down-card {{ background:linear-gradient(180deg,var(--down-soft),var(--panel)); border-color:var(--down-mid); }}
  .m-label {{ font-size:12px; color:var(--sub); margin-bottom:8px; letter-spacing:.02em; font-weight:700; }}
  .m-value {{ font-size:28px; font-weight:800; line-height:1; display:flex;
              align-items:baseline; gap:7px; justify-content:center; }}
  .m-pct {{ font-size:13px; font-weight:600; opacity:.8; }}
  .bar {{ display:flex; height:14px; border-radius:999px; overflow:hidden;
          background:var(--flat-soft); padding:0; }}
  .seg {{ height:100%; transition:width 1s cubic-bezier(.16,1,.3,1); }}
  .seg.up {{ background:linear-gradient(90deg,var(--up),#f6b0c1); }}
  .seg.down {{ background:linear-gradient(90deg,#b7d0f1,var(--down)); }}
  .seg.flat {{ background:var(--flat); opacity:.48; }}

  /* market cards */
  .mkt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  /* 시장 카드 안 상승/보합/하락 카드 (지수 밑, 컴팩트) */
  .mkt-metrics {{ gap:8px; margin:0; }}
  .mkt-metrics .metric {{ padding:11px 8px; border-radius:14px; }}
  .mkt-metrics .m-label {{ font-size:11px; margin-bottom:5px; }}
  .mkt-metrics .m-value {{ font-size:19px; gap:4px; }}
  .mkt-metrics .m-pct {{ font-size:10.5px; }}
  .mkt-card .bar {{ margin-top:13px; }}
  .mkt-card {{ padding:20px 22px; border-radius:20px;
              background:linear-gradient(180deg,var(--panel2),var(--panel));
              border:1px solid var(--line); }}
  .mkt-head {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:14px; }}
  .mkt-head h3 {{ font-family:var(--round); font-size:16px; font-weight:700; margin:0;
                  letter-spacing:.04em; color:var(--heading); }}
  .mkt-head-idx {{ display:inline-flex; align-items:baseline; gap:8px; }}
  .mkt-index {{ font-size:17px; font-weight:850; color:var(--strong); }}
  .mkt-rate {{ font-size:14px; font-weight:800; }}
  .mkt-change {{ font-size:12px; font-weight:750; }}
  .mkt-flow {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:10px; }}
  .flow-item {{ display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px;
                min-width:0; padding:8px 6px; border:1px solid var(--line); border-radius:12px;
                background:color-mix(in srgb, var(--panel) 78%, transparent); font-family:var(--round);
                font-size:11px; line-height:1.1; font-weight:700; color:var(--sub); text-align:center; }}
  .flow-item b {{ font-size:11.5px; font-weight:850; line-height:1.1; white-space:nowrap; }}

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
  .tv-chips {{ display:grid; grid-template-columns:repeat(6, 1fr); gap:9px; }}
  .tv-chips.tv-all {{ display:none; }}
  .rep-toggle:checked ~ .tv-chips.tv-common {{ display:none; }}
  .rep-toggle:checked ~ .tv-chips.tv-all {{ display:grid; }}

  .tv-chip {{ display:inline-flex; align-items:center; gap:10px; text-decoration:none;
              border-radius:16px; padding:8px 14px; min-width:0;
              background:var(--chip-base); border:1px solid var(--line);
              transition:transform .14s ease, box-shadow .14s ease; }}
  .tv-chip:hover {{ transform:translateY(-2px); box-shadow:0 4px 12px rgba(216,138,168,.16); }}
  .tv-chip.up {{ background:color-mix(in srgb, var(--up) 9%, var(--chip-base)); border-color:var(--up-mid); }}
  .tv-chip.down {{ background:color-mix(in srgb, var(--down) 9%, var(--chip-base)); border-color:var(--down-mid); }}
  .tv-chip .tv-r {{ flex:0 0 auto; font-size:11px; font-weight:800; color:var(--faint);
                    min-width:21px; height:21px; display:inline-flex; align-items:center;
                    justify-content:center; border-radius:50%; background:var(--flat-soft); }}
  .tv-body {{ display:flex; flex-direction:column; gap:3px; min-width:0; flex:1; }}
  .tv-n {{ font-size:13px; font-weight:700; color:var(--chip-name);
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .tv-meta {{ display:flex; justify-content:space-between; align-items:baseline; gap:14px; }}
  .tv-rate {{ font-size:11.5px; font-weight:800; }}
  .tv-a {{ font-size:12px; font-weight:850; color:var(--strong); }}

  footer {{ margin-top:32px; padding-top:20px; text-align:center; font-family:var(--round);
            font-size:11.5px; color:var(--faint); letter-spacing:.02em; font-weight:600; }}

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
    header h1 {{ font-size:33px; }}
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
    .tv-chips {{ grid-template-columns:repeat(3, 1fr); gap:7px; }}
    .tv-chip {{ padding:8px 12px; gap:8px; }}
    .tv-chip .tv-n {{ font-size:12.5px; }}
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
  </header>
  {body}
  <footer>Market Brief V1 — 시장 분위기 파악용 경량 리포트 · 투자 판단의 근거가 아닙니다.</footer>
</div>
</body>
</html>"""
