# -*- coding: utf-8 -*-
"""
Market Brief 리포트 디자인 모드 1.

report.py를 보존하기 위해 동일한 공개 함수 이름을 유지합니다.
- write_csv
- write_theme_map
- write_html
"""

from html import escape

import config

SESSION_LABEL = {"morning": "오전장", "close": "장마감"}


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def write_theme_map(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def _cls(rate):
    return "up" if rate > 0 else "down" if rate < 0 else "flat"


def _fmt(rate, suffix=""):
    value = f"+{rate:.2f}" if rate > 0 else f"{rate:.2f}"
    return f"{value}{suffix}"


def _safe_width(value):
    return max(0.0, min(100.0, float(value)))


def _market_tone(overall):
    if overall["up_pct"] >= 55:
        return "상승 우위", "up"
    if overall["down_pct"] >= 55:
        return "하락 우위", "down"
    return "혼조", "flat"


def _stacked_bar(c):
    return (
        '<div class="stacked" aria-label="시장 강도">'
        f'<span class="seg up" style="width:{_safe_width(c["up_pct"])}%"></span>'
        f'<span class="seg flat" style="width:{_safe_width(c["flat_pct"])}%"></span>'
        f'<span class="seg down" style="width:{_safe_width(c["down_pct"])}%"></span>'
        '</div>'
    )


def _stat(label, value, cls=""):
    return f"""
      <div class="stat {cls}">
        <span>{escape(label)}</span>
        <strong>{escape(str(value))}</strong>
      </div>"""


def _hero(date, session_label, generated_at, overall):
    tone, tone_cls = _market_tone(overall)
    return f"""
    <section class="hero">
      <div>
        <div class="eyebrow">Market Brief V1</div>
        <h1>한국 증시 리포트</h1>
        <p>{date} · {escape(session_label)} · 생성 {escape(generated_at)}</p>
      </div>
      <div class="hero-panel">
        <span class="tone {tone_cls}">{tone}</span>
        <strong>{overall['total']:,}</strong>
        <small>KOSPI / KOSDAQ 전체 종목</small>
      </div>
    </section>"""


def _section_summary(overall):
    return f"""
    <section class="section">
      <div class="section-head">
        <span>01</span>
        <h2>시장 요약</h2>
      </div>
      <div class="summary-grid">
        {_stat("상승", f"{overall['up']:,} ({overall['up_pct']}%)", "up")}
        {_stat("보합", f"{overall['flat']:,} ({overall['flat_pct']}%)", "flat")}
        {_stat("하락", f"{overall['down']:,} ({overall['down_pct']}%)", "down")}
      </div>
      {_stacked_bar(overall)}
    </section>"""


def _section_market(by_market):
    cards = []
    for market in ("KOSPI", "KOSDAQ"):
        c = by_market[market]
        cards.append(f"""
        <article class="market-card">
          <div class="market-title">
            <h3>{market}</h3>
            <span>{c['total']:,} 종목</span>
          </div>
          {_stacked_bar(c)}
          <div class="market-counts">
            <span class="up">상승 {c['up']:,}</span>
            <span class="flat">보합 {c['flat']:,}</span>
            <span class="down">하락 {c['down']:,}</span>
          </div>
        </article>""")
    return f"""
    <section class="section">
      <div class="section-head">
        <span>02</span>
        <h2>시장별 강도</h2>
      </div>
      <div class="market-grid">{''.join(cards)}</div>
    </section>"""


def _tier_chip(row):
    name = escape(str(row.종목명))
    rate = float(row.등락률)
    return f'<span class="stock-chip {_cls(rate)}"><b>{name}</b><i>{_fmt(rate, "%")}</i></span>'


def _section_tiers(tiers):
    rows = []
    for name, lo, hi in config.TIERS:
        sub = tiers[name]
        side = "up" if name in config.UP_TIERS else "down"
        range_label = f"{lo:g}% 이상" if hi >= 999 else f"{lo:g}% ~ {hi:g}%"
        chips = "".join(_tier_chip(r) for r in sub.itertuples())
        if not chips:
            chips = '<span class="empty">해당 종목 없음</span>'
        rows.append(f"""
        <div class="tier-line">
          <div class="tier-label {side}">
            <strong>{name}</strong>
            <span>{escape(range_label)}</span>
          </div>
          <div class="tier-list">{chips}</div>
        </div>""")
    return f"""
    <section class="section">
      <div class="section-head">
        <span>03</span>
        <h2>등락률 티어</h2>
      </div>
      <div class="tier-board">{''.join(rows)}</div>
    </section>"""


def _theme_table(rows):
    if not len(rows):
        return '<div class="empty">데이터 없음</div>'

    trs = []
    for rank, row in enumerate(rows.itertuples(index=False), 1):
        theme = escape(str(row.테마))
        rate = float(row.평균등락률)
        trs.append(f"""
        <tr>
          <td class="rank">{rank}</td>
          <td class="theme-name">{theme}</td>
          <td class="theme-rate {_cls(rate)}">{_fmt(rate, "%")}</td>
          <td class="theme-count">{int(row.종목수):,}</td>
        </tr>""")
    return f"""
    <table class="theme-table">
      <thead>
        <tr><th>#</th><th>테마/업종</th><th>평균 등락률</th><th>종목수</th></tr>
      </thead>
      <tbody>{''.join(trs)}</tbody>
    </table>"""


def _section_themes(top, bottom):
    return f"""
    <section class="theme-grid">
      <article class="section">
        <div class="section-head">
          <span>04</span>
          <h2>강한 테마/업종</h2>
        </div>
        {_theme_table(top)}
      </article>
      <article class="section">
        <div class="section-head">
          <span>05</span>
          <h2>약한 테마/업종</h2>
        </div>
        {_theme_table(bottom)}
      </article>
    </section>"""


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top, bottom):
    date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    session_label = SESSION_LABEL.get(session, session)
    body = (
        _hero(date, session_label, generated_at, overall)
        + _section_summary(overall)
        + _section_market(by_market)
        + _section_tiers(tiers)
        + _section_themes(top, bottom)
    )
    html = _PAGE.format(
        date=date,
        session_label=escape(session_label),
        body=body,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Brief - {date} {session_label}</title>
<style>
  :root {{
    --up:#d92d20;
    --up-bg:#fff1f0;
    --down:#1971c2;
    --down-bg:#eef6ff;
    --flat:#6b7280;
    --flat-bg:#f3f4f6;
    --ink:#111827;
    --muted:#6b7280;
    --line:#e5e7eb;
    --soft:#f7f8fa;
    --paper:#ffffff;
  }}
  * {{ box-sizing:border-box; }}
  html {{ background:var(--soft); }}
  body {{
    margin:0;
    color:var(--ink);
    background:var(--soft);
    font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
    line-height:1.5;
  }}
  .wrap {{
    width:min(1120px, calc(100% - 32px));
    margin:0 auto;
    padding:28px 0 56px;
  }}
  .hero {{
    display:grid;
    grid-template-columns:minmax(0,1fr) 260px;
    gap:18px;
    align-items:stretch;
    margin-bottom:16px;
    padding:26px;
    border:1px solid var(--line);
    border-radius:8px;
    background:var(--paper);
  }}
  .eyebrow {{
    margin-bottom:8px;
    color:var(--muted);
    font-size:12px;
    font-weight:800;
    text-transform:uppercase;
  }}
  h1 {{
    margin:0 0 10px;
    font-size:34px;
    line-height:1.15;
  }}
  .hero p {{
    margin:0;
    color:var(--muted);
    font-size:14px;
  }}
  .hero-panel {{
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:flex-start;
    gap:5px;
    padding:18px;
    border:1px solid var(--line);
    border-radius:8px;
    background:#fafafa;
  }}
  .hero-panel strong {{ font-size:34px; line-height:1; }}
  .hero-panel small {{ color:var(--muted); }}
  .tone {{
    display:inline-flex;
    align-items:center;
    height:26px;
    padding:0 9px;
    border-radius:999px;
    font-size:12px;
    font-weight:800;
  }}
  .tone.up {{ color:var(--up); background:var(--up-bg); }}
  .tone.down {{ color:var(--down); background:var(--down-bg); }}
  .tone.flat {{ color:var(--flat); background:var(--flat-bg); }}
  .section {{
    margin-bottom:16px;
    padding:20px;
    border:1px solid var(--line);
    border-radius:8px;
    background:var(--paper);
  }}
  .section-head {{
    display:flex;
    align-items:center;
    gap:10px;
    margin-bottom:15px;
  }}
  .section-head span {{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-width:34px;
    height:24px;
    border-radius:6px;
    background:var(--ink);
    color:white;
    font-size:12px;
    font-weight:800;
  }}
  h2, h3 {{ margin:0; }}
  h2 {{ font-size:18px; }}
  h3 {{ font-size:16px; }}
  .up {{ color:var(--up); }}
  .down {{ color:var(--down); }}
  .flat {{ color:var(--flat); }}
  .summary-grid {{
    display:grid;
    grid-template-columns:repeat(3, minmax(0,1fr));
    gap:10px;
    margin-bottom:14px;
  }}
  .stat {{
    padding:14px;
    border:1px solid var(--line);
    border-radius:8px;
    background:#fafafa;
  }}
  .stat span {{
    display:block;
    margin-bottom:5px;
    color:var(--muted);
    font-size:12px;
    font-weight:800;
  }}
  .stat strong {{ font-size:22px; }}
  .stat.up {{ background:var(--up-bg); }}
  .stat.down {{ background:var(--down-bg); }}
  .stat.flat {{ background:var(--flat-bg); }}
  .stacked {{
    display:flex;
    width:100%;
    height:12px;
    overflow:hidden;
    border-radius:999px;
    background:#edf0f2;
  }}
  .seg.up {{ background:var(--up); }}
  .seg.down {{ background:var(--down); }}
  .seg.flat {{ background:#9ca3af; }}
  .market-grid {{
    display:grid;
    grid-template-columns:repeat(2, minmax(0,1fr));
    gap:12px;
  }}
  .market-card {{
    padding:16px;
    border:1px solid var(--line);
    border-radius:8px;
    background:#fafafa;
  }}
  .market-title {{
    display:flex;
    justify-content:space-between;
    gap:12px;
    margin-bottom:12px;
  }}
  .market-title span,
  .market-counts {{
    color:var(--muted);
    font-size:13px;
    font-weight:700;
  }}
  .market-counts {{
    display:flex;
    flex-wrap:wrap;
    gap:12px;
    margin-top:10px;
  }}
  .tier-board {{
    display:grid;
    gap:9px;
  }}
  .tier-line {{
    display:grid;
    grid-template-columns:112px minmax(0,1fr);
    gap:12px;
    align-items:start;
  }}
  .tier-label {{
    min-height:42px;
    padding:8px 10px;
    border-radius:8px;
    background:#f5f5f5;
    border:1px solid var(--line);
  }}
  .tier-label strong {{
    display:block;
    font-size:18px;
    line-height:1;
  }}
  .tier-label span {{
    display:block;
    margin-top:4px;
    color:var(--muted);
    font-size:11px;
  }}
  .tier-label.up {{ border-color:#ffd6d1; background:var(--up-bg); }}
  .tier-label.down {{ border-color:#cfe5ff; background:var(--down-bg); }}
  .tier-list {{
    display:flex;
    flex-wrap:wrap;
    gap:6px;
    min-width:0;
  }}
  .stock-chip {{
    display:inline-flex;
    align-items:center;
    gap:6px;
    max-width:100%;
    padding:5px 8px;
    border:1px solid var(--line);
    border-radius:999px;
    background:#fff;
    font-size:12px;
    white-space:nowrap;
  }}
  .stock-chip b {{
    overflow:hidden;
    text-overflow:ellipsis;
    font-weight:700;
  }}
  .stock-chip i {{
    font-style:normal;
    font-weight:800;
  }}
  .stock-chip.up {{ background:var(--up-bg); border-color:#ffd6d1; }}
  .stock-chip.down {{ background:var(--down-bg); border-color:#cfe5ff; }}
  .theme-grid {{
    display:grid;
    grid-template-columns:repeat(2, minmax(0,1fr));
    gap:16px;
  }}
  .theme-table {{
    width:100%;
    border-collapse:collapse;
    table-layout:fixed;
    font-size:13px;
  }}
  .theme-table th,
  .theme-table td {{
    padding:9px 8px;
    border-bottom:1px solid var(--line);
    text-align:left;
    vertical-align:middle;
  }}
  .theme-table th {{
    color:var(--muted);
    font-size:12px;
    font-weight:800;
  }}
  .rank {{ width:36px; color:var(--muted); }}
  .theme-name {{
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
  }}
  .theme-rate {{
    width:96px;
    text-align:right !important;
    font-weight:800;
  }}
  .theme-count {{
    width:66px;
    color:var(--muted);
    text-align:right !important;
    font-weight:700;
  }}
  .empty {{
    color:var(--muted);
    font-size:13px;
  }}
  footer {{
    margin-top:22px;
    color:var(--muted);
    text-align:center;
    font-size:12px;
  }}
  @media (max-width:760px) {{
    .wrap {{ width:min(100% - 20px, 1120px); padding-top:12px; }}
    .hero,
    .market-grid,
    .theme-grid,
    .summary-grid {{
      grid-template-columns:1fr;
    }}
    .hero {{ padding:20px; }}
    h1 {{ font-size:28px; }}
    .tier-line {{ grid-template-columns:1fr; }}
    .theme-table {{ table-layout:auto; }}
  }}
</style>
</head>
<body>
<main class="wrap">
  {body}
  <footer>Market Brief V1 - 시장 분위기 파악용 경량 리포트이며 투자 판단의 근거가 아닙니다.</footer>
</main>
</body>
</html>"""
