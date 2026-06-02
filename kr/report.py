# -*- coding: utf-8 -*-
"""
리포트 생성 모듈
- write_csv  : 수집한 전 종목 데이터를 CSV 로 저장
- write_html : 5개 섹션으로 구성된 HTML 리포트 저장
  섹션1 시장요약 / 섹션2 시장별요약 / 섹션3 티어표 / 섹션4 강한테마 / 섹션5 약한테마

한국 관습대로 상승은 빨강, 하락은 파랑으로 표기합니다.
"""

from . import config

SESSION_LABEL = {"snapshot": "스냅샷"}


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지


def write_theme_map(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ──────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────
def _cls(rate):
    return "up" if rate > 0 else "down" if rate < 0 else "flat"


def _fmt(rate):
    return f"+{rate:.2f}" if rate > 0 else f"{rate:.2f}"


def _strength_bar(c):
    """상승/하락/보합 비율을 한 줄 막대로."""
    return (
        f'<div class="bar">'
        f'<span class="seg up"   style="width:{c["up_pct"]}%"></span>'
        f'<span class="seg flat" style="width:{c["flat_pct"]}%"></span>'
        f'<span class="seg down" style="width:{c["down_pct"]}%"></span>'
        f'</div>'
    )


def _section_summary(overall):
    c = overall
    return f"""
    <section>
      <h2><span class="num">01</span> 시장 요약</h2>
      <div class="summary">
        <div class="big">전체 <b>{c['total']:,}</b> 종목</div>
        {_strength_bar(c)}
        <div class="legend">
          <span class="up">▲ 상승 {c['up']:,} ({c['up_pct']}%)</span>
          <span class="flat">― 보합 {c['flat']:,} ({c['flat_pct']}%)</span>
          <span class="down">▼ 하락 {c['down']:,} ({c['down_pct']}%)</span>
        </div>
      </div>
    </section>"""


def _section_market(by_market):
    cards = ""
    for m in ("KOSPI", "KOSDAQ"):
        c = by_market[m]
        cards += f"""
        <div class="mkt-card">
          <h3>{m}</h3>
          <div class="mkt-total">{c['total']:,} 종목</div>
          {_strength_bar(c)}
          <div class="mkt-row"><span class="up">상승 {c['up']:,}</span>
            <span class="flat">보합 {c['flat']:,}</span>
            <span class="down">하락 {c['down']:,}</span></div>
        </div>"""
    return f"""
    <section>
      <h2><span class="num">02</span> 시장별 요약</h2>
      <div class="mkt-grid">{cards}</div>
    </section>"""


def _section_tiers(tiers):
    rows = ""
    for name, _lo, _hi in config.TIERS:
        sub = tiers[name]
        side = "up" if name in config.UP_TIERS else "down"
        if len(sub):
            chips = "".join(
                f'<span class="chip {_cls(r.등락률)}">{r.종목명}'
                f'<i>{_fmt(r.등락률)}</i></span>'
                for r in sub.itertuples()
            )
        else:
            chips = '<span class="empty">해당 종목 없음</span>'
        rows += f"""
        <div class="tier-row">
          <div class="tier-badge {side}">{name}</div>
          <div class="tier-stocks">{chips}</div>
        </div>"""
    return f"""
    <section>
      <h2><span class="num">04</span> 티어표 <small>(좌→우, 강한 순)</small></h2>
      <div class="tiers">{rows}</div>
    </section>"""


def _section_sector_tiers(sector_tiers, market_avg):
    if not sector_tiers:
        return ""
    rows = ""
    for name, _lo, _hi in config.SECTOR_TIERS:
        sub = sector_tiers[name]
        side = "up" if name in config.UP_TIERS else "down"
        if len(sub):
            chips = "".join(
                f'<span class="chip {_cls(r.초과)}">{r.섹터}<i>{_fmt(r.초과)}p</i></span>'
                for r in sub.itertuples()
            )
        else:
            chips = '<span class="empty">해당 없음</span>'
        rows += f"""
        <div class="tier-row">
          <div class="tier-badge {side}">{name}</div>
          <div class="tier-stocks">{chips}</div>
        </div>"""
    return f"""
    <section>
      <h2><span class="num">05</span> 섹터 티어 <small>(시장평균 {_fmt(market_avg)}% 대비, 값=초과수익 %p)</small></h2>
      <div class="tiers">{rows}</div>
    </section>"""


def _heat_style(rate):
    white, up, down = (255, 255, 255), (224, 49, 49), (28, 126, 214)
    ratio = min(abs(rate) / 3.0, 1.0)
    t = 0.12 + 0.88 * ratio
    bg = white if rate == 0 else (_lerp(white, up, t) if rate > 0 else _lerp(white, down, t))
    fg = "#fff" if (rate != 0 and t >= 0.55) else "#212529"
    return f"background:rgb({bg[0]},{bg[1]},{bg[2]});color:{fg}"


def _lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def _section_heatmap(big_theme):
    if big_theme is None or not len(big_theme):
        return ""
    cells = "".join(
        f'<div class="heat-cell" style="{_heat_style(r.평균등락률)}">'
        f'<b>{r.대테마}</b><span class="hv">{_fmt(r.평균등락률)}%</span>'
        f'<small>{r.종목수}종목</small></div>'
        for r in big_theme.itertuples()
    )
    return f"""
    <section>
      <h2><span class="num">03</span> 대테마 히트맵</h2>
      <div class="heatmap">{cells}</div>
    </section>"""


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top=None, bottom=None, sector_top=None, sector_bottom=None, sector_tiers=None, sector_market_avg=None, big_theme=None, top_value=None, top_value_common=None, top_volume=None, top_volume_common=None, tiers_common=None, date_nav=None):
    body = _section_summary(overall) + _section_market(by_market)
    body += _section_heatmap(big_theme)
    body += _section_tiers(tiers)
    if sector_tiers:
        body += _section_sector_tiers(sector_tiers, sector_market_avg)
    html = _PAGE.format(
        date=f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
        session_label=SESSION_LABEL.get(session, session),
        generated_at=generated_at,
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
<style>
  :root {{
    --up:#e03131; --down:#1c7ed6; --flat:#868e96;
    --ink:#1a1a1a; --sub:#6b7280; --line:#e7e7e9; --card:#fff; --bg:#f4f4f2;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
    line-height:1.5; -webkit-font-smoothing:antialiased;
  }}
  .wrap {{ max-width:980px; margin:0 auto; padding:32px 20px 64px; }}
  header {{ border-bottom:2px solid var(--ink); padding-bottom:14px; margin-bottom:28px; }}
  header .kicker {{ font-size:12px; letter-spacing:.22em; color:var(--sub); text-transform:uppercase; }}
  header h1 {{ font-size:30px; margin:6px 0 4px; font-weight:800; letter-spacing:-.02em; }}
  header .meta {{ font-size:13px; color:var(--sub); }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
            padding:20px 22px; margin-bottom:18px; }}
  h2 {{ font-size:18px; margin:0 0 16px; display:flex; align-items:center; gap:10px; font-weight:700; }}
  h2 small {{ font-weight:400; color:var(--sub); font-size:12px; }}
  .num {{ font-size:12px; font-weight:700; color:#fff; background:var(--ink);
         border-radius:6px; padding:3px 7px; letter-spacing:.05em; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }} .flat {{ color:var(--flat); }}

  .summary .big {{ font-size:15px; color:var(--sub); margin-bottom:10px; }}
  .summary .big b {{ font-size:22px; color:var(--ink); }}
  .bar {{ display:flex; height:14px; border-radius:8px; overflow:hidden; background:#eee; }}
  .seg.up {{ background:var(--up); }} .seg.down {{ background:var(--down); }} .seg.flat {{ background:var(--flat); }}
  .legend {{ display:flex; gap:18px; margin-top:10px; font-size:14px; font-weight:600; flex-wrap:wrap; }}

  .mkt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .mkt-card {{ border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .mkt-card h3 {{ margin:0 0 4px; font-size:15px; }}
  .mkt-total {{ font-size:13px; color:var(--sub); margin-bottom:8px; }}
  .mkt-row {{ display:flex; gap:14px; margin-top:8px; font-size:13px; font-weight:600; }}

  .tier-row {{ display:flex; align-items:flex-start; gap:12px; padding:9px 0; border-bottom:1px solid var(--line); }}
  .tier-row:last-child {{ border-bottom:0; }}
  .tier-badge {{ flex:0 0 34px; height:34px; border-radius:8px; color:#fff; font-weight:800;
                display:flex; align-items:center; justify-content:center; font-size:16px; }}
  .tier-badge.up {{ background:var(--up); }} .tier-badge.down {{ background:var(--down); }}
  .tier-stocks {{ display:flex; flex-wrap:wrap; gap:6px; padding-top:2px; }}
  .chip {{ font-size:12.5px; background:#f3f3f1; border:1px solid var(--line);
          border-radius:7px; padding:3px 8px; white-space:nowrap; }}
  .chip i {{ font-style:normal; font-weight:700; margin-left:5px; }}
  .empty {{ color:var(--sub); font-size:13px; padding:4px 0; }}

  table.theme {{ width:100%; border-collapse:collapse; font-size:14px; }}
  table.theme th, table.theme td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; }}
  table.theme th {{ font-size:12px; color:var(--sub); font-weight:600; }}
  table.theme .rank {{ color:var(--sub); width:34px; }}
  table.theme .val {{ font-weight:700; text-align:right; }}
  table.theme .cnt {{ text-align:right; color:var(--sub); width:60px; }}

  .heatmap {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:8px; }}
  .heat-cell {{ border-radius:12px; padding:13px 14px; display:flex; flex-direction:column; gap:2px; min-height:80px; justify-content:center; }}
  .heat-cell b {{ font-size:14px; }}
  .heat-cell .hv {{ font-size:21px; font-weight:800; }}
  .heat-cell small {{ font-size:11px; opacity:.8; }}

  footer {{ text-align:center; color:var(--sub); font-size:12px; margin-top:24px; }}
  @media (max-width:640px) {{ .mkt-grid {{ grid-template-columns:1fr; }} header h1 {{ font-size:24px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">Market Brief V1 · KOSPI / KOSDAQ</div>
    <h1>한국 증시 리포트</h1>
    <div class="meta">{date} · {session_label} · 생성 {generated_at}</div>
  </header>
  {body}
  <footer>Market Brief V1 — 시장 분위기 파악용 경량 리포트 · 투자 판단의 근거가 아닙니다.</footer>
</div>
</body>
</html>"""
