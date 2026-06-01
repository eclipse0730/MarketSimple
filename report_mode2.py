# -*- coding: utf-8 -*-
"""
리포트 생성 모듈 (Mode 2 — 세련된 디자인 개편판)

report.py 와 동일한 공개 API 를 제공하므로 그대로 교체해 쓸 수 있습니다.
  - write_csv       : 수집한 전 종목 데이터를 CSV 로 저장
  - write_theme_map : 테마 매핑을 CSV 로 저장
  - write_html      : 5개 섹션으로 구성된 HTML 리포트 저장

기존과 달라진 점은 시각 디자인뿐입니다.
  · 다크 히어로 헤더 + 핵심 지표 대시보드
  · 등락 강도 막대에 비율 인라인 표기
  · 테마 테이블에 미니 게이지 바
  · 정제된 타이포그래피 / 여백 / 카드 그림자

한국 관습대로 상승은 빨강, 하락은 파랑으로 표기합니다.
"""

import config

SESSION_LABEL = {"morning": "오전장 (11:59 기준)", "close": "장마감"}


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지


def write_theme_map(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────
def _cls(rate):
    return "up" if rate > 0 else "down" if rate < 0 else "flat"


def _fmt(rate):
    return f"+{rate:.2f}" if rate > 0 else f"{rate:.2f}"


def _strength_bar(c, *, labels=False):
    """상승/하락/보합 비율을 한 줄 막대로. labels=True 면 칸 안에 % 표기."""
    def seg(kind, pct):
        txt = f"{pct:.0f}%" if labels and pct >= 8 else ""
        return f'<span class="seg {kind}" style="width:{pct}%">{txt}</span>'

    return (
        '<div class="bar">'
        + seg("up", c["up_pct"])
        + seg("flat", c["flat_pct"])
        + seg("down", c["down_pct"])
        + "</div>"
    )


def _sentiment(c):
    """전체 분위기를 한 단어로 요약 (히어로 배지용)."""
    diff = c["up_pct"] - c["down_pct"]
    if diff >= 30:
        return "강세", "up"
    if diff >= 8:
        return "상승 우위", "up"
    if diff <= -30:
        return "약세", "down"
    if diff <= -8:
        return "하락 우위", "down"
    return "혼조", "flat"


# ──────────────────────────────────────────────
# 섹션
# ──────────────────────────────────────────────
def _hero(overall, by_market):
    c = overall
    mood, mood_cls = _sentiment(c)
    ks, kq = by_market["KOSPI"], by_market["KOSDAQ"]
    return f"""
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="hero-label">시장 분위기</div>
          <div class="hero-mood {mood_cls}">{mood}</div>
        </div>
        <div class="hero-ratio">
          <span class="up">{c['up_pct']}%</span>
          <span class="hero-vs">vs</span>
          <span class="down">{c['down_pct']}%</span>
        </div>
      </div>
      {_strength_bar(c, labels=True)}
      <div class="hero-stats">
        <div class="stat"><div class="stat-k">전체 종목</div><div class="stat-v">{c['total']:,}</div></div>
        <div class="stat"><div class="stat-k up">상승</div><div class="stat-v">{c['up']:,}</div></div>
        <div class="stat"><div class="stat-k flat">보합</div><div class="stat-v">{c['flat']:,}</div></div>
        <div class="stat"><div class="stat-k down">하락</div><div class="stat-v">{c['down']:,}</div></div>
        <div class="stat"><div class="stat-k">KOSPI</div><div class="stat-v">{ks['total']:,}</div></div>
        <div class="stat"><div class="stat-k">KOSDAQ</div><div class="stat-v">{kq['total']:,}</div></div>
      </div>
    </section>"""


def _section_market(by_market):
    cards = ""
    for m in ("KOSPI", "KOSDAQ"):
        c = by_market[m]
        mood, mood_cls = _sentiment(c)
        cards += f"""
        <div class="mkt-card">
          <div class="mkt-head">
            <h3>{m}</h3>
            <span class="pill {mood_cls}">{mood}</span>
          </div>
          <div class="mkt-total">{c['total']:,} 종목</div>
          {_strength_bar(c, labels=True)}
          <div class="mkt-row">
            <span class="up">▲ {c['up']:,}</span>
            <span class="flat">― {c['flat']:,}</span>
            <span class="down">▼ {c['down']:,}</span>
          </div>
        </div>"""
    return f"""
    <section>
      <h2><span class="num">01</span> 시장별 요약</h2>
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
          <div class="tier-badge {side}">{name}<span class="tier-cnt">{len(sub)}</span></div>
          <div class="tier-stocks">{chips}</div>
        </div>"""
    return f"""
    <section>
      <h2><span class="num">02</span> 티어표 <small>(강한 순 · 좌→우)</small></h2>
      <div class="tiers">{rows}</div>
    </section>"""


def _theme_table(rows, *, side):
    if not len(rows):
        return '<div class="empty">데이터 없음</div>'
    # 게이지 정규화 기준 (해당 표 내 최대 절대값)
    peak = max((abs(r.평균등락률) for r in rows.itertuples()), default=1) or 1
    trs = ""
    for i, r in enumerate(rows.itertuples(), 1):
        w = min(abs(r.평균등락률) / peak * 100, 100)
        cls = _cls(r.평균등락률)
        trs += (
            f'<tr><td class="rank">{i}</td>'
            f'<td class="theme-name">{r.테마}</td>'
            f'<td class="gauge-cell"><span class="gauge {cls}" style="width:{w:.0f}%"></span></td>'
            f'<td class="{cls} val">{_fmt(r.평균등락률)}%</td>'
            f'<td class="cnt">{r.종목수}</td></tr>'
        )
    return f"""<table class="theme {side}">
      <thead><tr><th>#</th><th>테마</th><th></th><th>평균</th><th>종목</th></tr></thead>
      <tbody>{trs}</tbody></table>"""


def _section_themes(top, bottom):
    return f"""
    <section>
      <h2><span class="num">03</span> 강한 테마/업종 <small>TOP 10</small></h2>
      {_theme_table(top, side="up")}
    </section>
    <section>
      <h2><span class="num">04</span> 약한 테마/업종 <small>TOP 10</small></h2>
      {_theme_table(bottom, side="down")}
    </section>"""


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top, bottom):
    body = (
        _hero(overall, by_market)
        + _section_market(by_market)
        + _section_tiers(tiers)
        + _section_themes(top, bottom)
    )
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
    --up:#e8384f; --up-soft:#fce8eb;
    --down:#2563eb; --down-soft:#e7eefc;
    --flat:#9aa3af; --flat-soft:#f0f1f3;
    --ink:#0e1117; --sub:#646b76; --line:#e9eaee;
    --card:#ffffff; --bg:#eef0f3;
    --hero-1:#0e1117; --hero-2:#1d2433;
    --shadow:0 1px 2px rgba(16,22,30,.04), 0 8px 24px rgba(16,22,30,.06);
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",-apple-system,sans-serif;
    line-height:1.5; -webkit-font-smoothing:antialiased; letter-spacing:-.01em;
  }}
  .wrap {{ max-width:960px; margin:0 auto; padding:36px 20px 72px; }}

  /* 헤더 */
  header.page {{ display:flex; justify-content:space-between; align-items:flex-end;
                 margin-bottom:22px; flex-wrap:wrap; gap:12px; }}
  header.page .kicker {{ font-size:11px; letter-spacing:.26em; color:var(--sub);
                         text-transform:uppercase; font-weight:600; }}
  header.page h1 {{ font-size:32px; margin:8px 0 0; font-weight:800; letter-spacing:-.03em; }}
  header.page .meta {{ font-size:12.5px; color:var(--sub); text-align:right; line-height:1.7; }}
  header.page .meta b {{ color:var(--ink); font-weight:600; }}

  /* 섹션 공통 */
  section {{ background:var(--card); border:1px solid var(--line); border-radius:18px;
            padding:22px 24px; margin-bottom:16px; box-shadow:var(--shadow); }}
  h2 {{ font-size:16px; margin:0 0 18px; display:flex; align-items:center; gap:10px; font-weight:700; }}
  h2 small {{ font-weight:500; color:var(--sub); font-size:12px; letter-spacing:0; }}
  .num {{ font-size:11px; font-weight:800; color:var(--ink); background:#f1f2f5;
         border-radius:7px; padding:4px 8px; letter-spacing:.04em; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }} .flat {{ color:var(--flat); }}

  /* 강도 막대 */
  .bar {{ display:flex; height:24px; border-radius:9px; overflow:hidden;
          background:var(--flat-soft); font-size:11px; font-weight:700; }}
  .seg {{ display:flex; align-items:center; justify-content:center; color:#fff;
          min-width:0; transition:width .3s; }}
  .seg.up {{ background:var(--up); }}
  .seg.down {{ background:var(--down); }}
  .seg.flat {{ background:var(--flat); }}

  /* 히어로 */
  .hero {{ background:linear-gradient(135deg,var(--hero-1),var(--hero-2)); border:0; color:#fff; }}
  .hero-top {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }}
  .hero-label {{ font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:#9aa3b2; font-weight:600; }}
  .hero-mood {{ font-size:34px; font-weight:800; margin-top:4px; letter-spacing:-.02em; }}
  .hero-mood.up {{ color:#ff7a8a; }} .hero-mood.down {{ color:#7aa7ff; }} .hero-mood.flat {{ color:#cfd5df; }}
  .hero-ratio {{ font-size:26px; font-weight:800; display:flex; align-items:center; gap:10px; }}
  .hero-ratio .up {{ color:#ff7a8a; }} .hero-ratio .down {{ color:#7aa7ff; }}
  .hero-vs {{ font-size:12px; color:#7a8294; font-weight:600; }}
  .hero .bar {{ height:26px; background:rgba(255,255,255,.1); }}
  .hero-stats {{ display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-top:18px; }}
  .stat {{ background:rgba(255,255,255,.06); border-radius:11px; padding:10px 12px; }}
  .stat-k {{ font-size:11px; color:#9aa3b2; font-weight:600; }}
  .stat-k.up {{ color:#ff7a8a; }} .stat-k.down {{ color:#7aa7ff; }} .stat-k.flat {{ color:#cfd5df; }}
  .stat-v {{ font-size:19px; font-weight:800; margin-top:2px; }}

  /* 시장별 카드 */
  .mkt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  .mkt-card {{ border:1px solid var(--line); border-radius:14px; padding:16px 18px; background:#fcfcfd; }}
  .mkt-head {{ display:flex; align-items:center; justify-content:space-between; }}
  .mkt-head h3 {{ margin:0; font-size:16px; font-weight:800; letter-spacing:-.02em; }}
  .pill {{ font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; }}
  .pill.up {{ background:var(--up-soft); color:var(--up); }}
  .pill.down {{ background:var(--down-soft); color:var(--down); }}
  .pill.flat {{ background:var(--flat-soft); color:var(--flat); }}
  .mkt-total {{ font-size:12.5px; color:var(--sub); margin:4px 0 10px; }}
  .mkt-row {{ display:flex; gap:16px; margin-top:10px; font-size:13px; font-weight:700; }}

  /* 티어표 */
  .tier-row {{ display:flex; align-items:flex-start; gap:14px; padding:11px 0; border-bottom:1px solid var(--line); }}
  .tier-row:last-child {{ border-bottom:0; }}
  .tier-badge {{ flex:0 0 40px; height:40px; border-radius:11px; color:#fff; font-weight:800;
                display:flex; flex-direction:column; align-items:center; justify-content:center;
                font-size:17px; line-height:1; position:relative; }}
  .tier-badge.up {{ background:linear-gradient(160deg,#f04d63,var(--up)); }}
  .tier-badge.down {{ background:linear-gradient(160deg,#4a82f5,var(--down)); }}
  .tier-cnt {{ font-size:9px; font-weight:700; opacity:.85; margin-top:2px; }}
  .tier-stocks {{ display:flex; flex-wrap:wrap; gap:6px; padding-top:3px; }}
  .chip {{ font-size:12.5px; background:#f7f7f9; border:1px solid var(--line);
          border-radius:9px; padding:4px 9px; white-space:nowrap; font-weight:500; }}
  .chip.up {{ background:var(--up-soft); border-color:#f6d4da; }}
  .chip.down {{ background:var(--down-soft); border-color:#d3e0fb; }}
  .chip i {{ font-style:normal; font-weight:800; margin-left:6px; }}
  .empty {{ color:var(--sub); font-size:13px; padding:4px 0; }}

  /* 테마 테이블 */
  table.theme {{ width:100%; border-collapse:collapse; font-size:14px; }}
  table.theme th, table.theme td {{ padding:9px 8px; border-bottom:1px solid var(--line); text-align:left; }}
  table.theme tr:last-child td {{ border-bottom:0; }}
  table.theme th {{ font-size:11px; color:var(--sub); font-weight:600; text-transform:uppercase; letter-spacing:.04em; }}
  table.theme .rank {{ color:var(--sub); width:30px; font-variant-numeric:tabular-nums; font-weight:700; }}
  table.theme .theme-name {{ font-weight:600; }}
  table.theme .gauge-cell {{ width:34%; }}
  .gauge {{ display:block; height:8px; border-radius:5px; min-width:3px; }}
  .gauge.up {{ background:linear-gradient(90deg,#f6a6b1,var(--up)); }}
  .gauge.down {{ background:linear-gradient(90deg,#9cbcfa,var(--down)); }}
  table.theme .val {{ font-weight:800; text-align:right; width:74px; font-variant-numeric:tabular-nums; }}
  table.theme .cnt {{ text-align:right; color:var(--sub); width:50px; font-variant-numeric:tabular-nums; }}

  footer {{ text-align:center; color:var(--sub); font-size:12px; margin-top:28px; line-height:1.7; }}
  footer b {{ color:var(--ink); font-weight:700; letter-spacing:.04em; }}

  @media (max-width:640px) {{
    .mkt-grid {{ grid-template-columns:1fr; }}
    .hero-stats {{ grid-template-columns:repeat(3,1fr); }}
    .hero-mood {{ font-size:28px; }}
    header.page h1 {{ font-size:26px; }}
    header.page .meta {{ text-align:left; }}
    table.theme .gauge-cell {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="page">
    <div>
      <div class="kicker">Market Brief · KOSPI / KOSDAQ</div>
      <h1>한국 증시 리포트</h1>
    </div>
    <div class="meta"><b>{date}</b><br>{session_label}<br>생성 {generated_at}</div>
  </header>
  {body}
  <footer>
    <b>MARKET BRIEF</b><br>
    시장 분위기 파악용 경량 리포트 · 투자 판단의 근거가 아닙니다.
  </footer>
</div>
</body>
</html>"""
