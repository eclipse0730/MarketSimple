# -*- coding: utf-8 -*-
"""
리포트 생성 모듈 (Mode 3 — 전문가용 다크 테마)

report.py 와 '보이는 정보'는 동일합니다. 디자인만 다릅니다.
write_csv / write_html 시그니처가 report.py 와 같으므로 main.py 에서
import 만 바꿔 끼우면 그대로 동작합니다.

  import report_mode3 as report   # main.py 상단에서 이렇게 교체

디자인 컨셉: 블룸버그/리피니티브 류의 금융 터미널.
짙은 차콜 배경 + 셰리프 디스플레이 헤드라인 + 모노스페이스 수치,
얇은 구분선과 절제된 모션. 상승=레드, 하락=블루(국장 관습).
"""

import config

SESSION_LABEL = {"morning": "오전장 (11:59 기준)", "close": "장 마감"}

# 티어별 대표색 (행 왼쪽 액센트 막대용). 배지 그라데이션은 CSS .t-S ~ .t-G 와 짝을 이룸.
# 상승(S~C)은 진한 빨강→앰버, 하락(D~G)은 옅은 파랑→진한 남색으로 강도 표현.
TIER_COLORS = {
    "S": "#e01919", "A": "#f0401f", "B": "#f07a1f", "C": "#d99a1f",
    "D": "#5a93e8", "E": "#3570d8", "F": "#2351c0", "G": "#1b3aa0",
}
TIER_COLLAPSE_LIMIT = 30


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")  # 엑셀 한글 깨짐 방지


# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────
def _cls(rate):
    return "up" if rate > 0 else "down" if rate < 0 else "flat"


def _fmt(rate):
    return f"+{rate:.2f}" if rate > 0 else f"{rate:.2f}"


def _strength_bar(c):
    return (
        f'<div class="bar" role="img" aria-label="상승 {c["up_pct"]}% 하락 {c["down_pct"]}%">'
        f'<span class="seg up"   style="width:{c["up_pct"]}%"></span>'
        f'<span class="seg flat" style="width:{c["flat_pct"]}%"></span>'
        f'<span class="seg down" style="width:{c["down_pct"]}%"></span>'
        f'</div>'
    )


def _stock_chip(row):
    return (
        f'<span class="chip {_cls(row.등락률)}">'
        f'<span class="c-name">{row.종목명}</span>'
        f'<span class="c-rate mono">{_fmt(row.등락률)}</span></span>'
    )


# ──────────────────────────────────────────────
# sections
# ──────────────────────────────────────────────
def _section_summary(overall):
    c = overall
    # 시장 강도 한줄 판정 (상승 비율 기준)
    up = c["up_pct"]
    if up >= 65:
        verdict, vclass = "강세 우위", "up"
    elif up >= 55:
        verdict, vclass = "매수 우위", "up"
    elif up >= 45:
        verdict, vclass = "중립 / 혼조", "flat"
    elif up >= 35:
        verdict, vclass = "매도 우위", "down"
    else:
        verdict, vclass = "약세 우위", "down"

    return f"""
    <section class="reveal">
      <div class="sec-head">
        <span class="num">01</span><h2>시장 요약</h2>
        <span class="verdict {vclass}">{verdict}</span>
      </div>
      <div class="summary">
        <div class="metrics">
          <div class="metric">
            <div class="m-label">전체 종목</div>
            <div class="m-value mono">{c['total']:,}</div>
          </div>
          <div class="metric">
            <div class="m-label up">상승</div>
            <div class="m-value mono up">{c['up']:,}<span class="m-pct">{c['up_pct']}%</span></div>
          </div>
          <div class="metric">
            <div class="m-label down">하락</div>
            <div class="m-value mono down">{c['down']:,}<span class="m-pct">{c['down_pct']}%</span></div>
          </div>
          <div class="metric">
            <div class="m-label flat">보합</div>
            <div class="m-value mono flat">{c['flat']:,}<span class="m-pct">{c['flat_pct']}%</span></div>
          </div>
        </div>
        {_strength_bar(c)}
      </div>
    </section>"""


def _section_market(by_market):
    cards = ""
    for m in ("KOSPI", "KOSDAQ"):
        c = by_market[m]
        cards += f"""
        <div class="mkt-card">
          <div class="mkt-head"><h3>{m}</h3><span class="mkt-total mono">{c['total']:,}</span></div>
          {_strength_bar(c)}
          <div class="mkt-row">
            <span class="up">▲ {c['up']:,}</span>
            <span class="flat">— {c['flat']:,}</span>
            <span class="down">▼ {c['down']:,}</span>
          </div>
        </div>"""
    return f"""
    <section class="reveal">
      <div class="sec-head"><span class="num">02</span><h2>시장별 요약</h2></div>
      <div class="mkt-grid">{cards}</div>
    </section>"""


def _section_tiers(tiers):
    rows = ""
    for name, lo, hi in config.TIERS:
        sub = tiers[name]
        color = TIER_COLORS.get(name, "#888")
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
            rows_iter = list(sub.itertuples())
            visible = rows_iter[:TIER_COLLAPSE_LIMIT]
            hidden = rows_iter[TIER_COLLAPSE_LIMIT:]
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
    return f"""
    <section class="reveal">
      <div class="sec-head"><span class="num">03</span><h2>티어 분포</h2>
        <span class="sec-note">강한 순 · 좌 → 우</span></div>
      <div class="tiers">{rows}</div>
    </section>"""


def _theme_block(rows, kind):
    """kind: 'top' or 'bottom' — 막대 게이지 포함 테마 리스트."""
    if not len(rows):
        return '<div class="empty">데이터 없음</div>'
    # 게이지 폭 정규화용 최대 절대값
    mx = max((abs(r.평균등락률) for r in rows.itertuples()), default=1) or 1
    items = ""
    for i, r in enumerate(rows.itertuples(), 1):
        cls = _cls(r.평균등락률)
        w = min(100, abs(r.평균등락률) / mx * 100)
        items += f"""
        <div class="theme-item">
          <span class="t-rank mono">{i:02d}</span>
          <span class="t-name">{r.테마}</span>
          <div class="t-gauge"><span class="t-fill {cls}" style="width:{w:.1f}%"></span></div>
          <span class="t-val mono {cls}">{_fmt(r.평균등락률)}%</span>
          <span class="t-cnt mono">{r.종목수}</span>
        </div>"""
    return f'<div class="theme-list">{items}</div>'


def _section_themes(top, bottom):
    return f"""
    <section class="reveal">
      <div class="sec-head"><span class="num">04</span><h2>주도 테마</h2>
        <span class="sec-note up">강한 테마 TOP 10</span></div>
      {_theme_block(top, 'top')}
    </section>
    <section class="reveal">
      <div class="sec-head"><span class="num">05</span><h2>소외 테마</h2>
        <span class="sec-note down">약한 테마 TOP 10</span></div>
      {_theme_block(bottom, 'bottom')}
    </section>"""


def write_html(path, *, date_str, session, generated_at, overall, by_market, tiers, top, bottom):
    body = (
        _section_summary(overall)
        + _section_market(by_market)
        + _section_tiers(tiers)
        + _section_themes(top, bottom)
    )
    html = _PAGE.format(
        date=f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}",
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --up:#ff4d4d; --up-dim:rgba(255,77,77,.14);
    --down:#3b9dff; --down-dim:rgba(59,157,255,.14);
    --flat:#8a8f99; --flat-dim:rgba(138,143,153,.16);
    --bg:#0c0e12; --bg2:#13161c; --panel:#161a21; --panel2:#1b202a;
    --ink:#eef1f6; --sub:#9aa3b2; --faint:#5c636f;
    --line:rgba(255,255,255,.07); --line2:rgba(255,255,255,.12);
    --gold:#d8b773;
    --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
    --serif:"Fraunces",Georgia,serif;
    --sans:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; color:var(--ink);
    background:
      radial-gradient(900px 500px at 78% -8%, rgba(216,183,115,.06), transparent 60%),
      radial-gradient(800px 600px at 0% 100%, rgba(59,157,255,.05), transparent 55%),
      var(--bg);
    font-family:var(--sans); line-height:1.55; -webkit-font-smoothing:antialiased;
    letter-spacing:.01em;
  }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:40px 24px 80px; }}
  .mono {{ font-family:var(--mono); font-feature-settings:"tnum" 1; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }} .flat {{ color:var(--flat); }}

  /* ── header ── */
  header {{ position:relative; margin-bottom:34px; padding-bottom:22px;
            border-bottom:1px solid var(--line2); }}
  .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:18px; }}
  .brand .dot {{ width:8px; height:8px; border-radius:50%; background:var(--gold);
                 box-shadow:0 0 12px var(--gold); animation:pulse 2.4s ease-in-out infinite; }}
  .brand .kicker {{ font-family:var(--mono); font-size:11px; letter-spacing:.34em;
                    color:var(--gold); text-transform:uppercase; }}
  header h1 {{ font-family:var(--serif); font-weight:600; font-size:46px; line-height:1.02;
               margin:0 0 14px; letter-spacing:-.015em; }}
  header h1 em {{ font-style:italic; color:var(--gold); }}
  .meta-row {{ display:flex; flex-wrap:wrap; gap:8px 22px; font-family:var(--mono);
               font-size:12.5px; color:var(--sub); }}
  .meta-row b {{ color:var(--ink); font-weight:500; }}
  .meta-row .sep {{ color:var(--faint); }}

  /* ── sections ── */
  section {{ background:linear-gradient(180deg,var(--panel),var(--bg2));
             border:1px solid var(--line); border-radius:16px;
             padding:24px 26px; margin-bottom:18px; position:relative; overflow:hidden; }}
  section::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px;
                     background:linear-gradient(90deg,transparent,var(--line2),transparent); }}
  .sec-head {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; }}
  .num {{ font-family:var(--mono); font-size:11px; font-weight:700; color:var(--bg);
          background:var(--gold); border-radius:5px; padding:3px 7px; letter-spacing:.06em; }}
  .sec-head h2 {{ font-family:var(--serif); font-weight:600; font-size:21px; margin:0;
                  letter-spacing:-.01em; }}
  .sec-note {{ margin-left:auto; font-family:var(--mono); font-size:11.5px;
               color:var(--sub); letter-spacing:.04em; }}
  .verdict {{ margin-left:auto; font-family:var(--mono); font-size:12px; font-weight:700;
              padding:5px 12px; border-radius:999px; letter-spacing:.04em;
              border:1px solid currentColor; }}
  .verdict.up {{ background:var(--up-dim); }} .verdict.down {{ background:var(--down-dim); }}
  .verdict.flat {{ background:var(--flat-dim); color:var(--sub); }}

  /* ── summary ── */
  .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }}
  .metric {{ padding:14px 16px; background:rgba(255,255,255,.02);
             border:1px solid var(--line); border-radius:11px; }}
  .m-label {{ font-size:12px; color:var(--sub); margin-bottom:7px; letter-spacing:.03em;
              font-weight:600; }}
  .m-value {{ font-size:27px; font-weight:700; line-height:1; display:flex;
              align-items:baseline; gap:8px; }}
  .m-pct {{ font-size:13px; font-weight:500; opacity:.85; }}
  .bar {{ display:flex; height:10px; border-radius:6px; overflow:hidden;
          background:rgba(255,255,255,.05); border:1px solid var(--line); }}
  .seg {{ height:100%; transition:width .9s cubic-bezier(.16,1,.3,1); }}
  .seg.up {{ background:linear-gradient(90deg,#ff6b6b,var(--up)); }}
  .seg.down {{ background:linear-gradient(90deg,var(--down),#5fb0ff); }}
  .seg.flat {{ background:var(--flat); }}

  /* ── market cards ── */
  .mkt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .mkt-card {{ padding:18px 20px; background:rgba(255,255,255,.02);
              border:1px solid var(--line); border-radius:13px; }}
  .mkt-head {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px; }}
  .mkt-head h3 {{ font-family:var(--mono); font-size:15px; font-weight:700; margin:0;
                  letter-spacing:.06em; }}
  .mkt-total {{ font-size:14px; color:var(--sub); }}
  .mkt-row {{ display:flex; gap:18px; margin-top:11px; font-family:var(--mono);
              font-size:13px; font-weight:500; }}

  /* ── tiers ── */
  .tier-row {{ display:flex; gap:16px; padding:13px 0 13px 16px; position:relative;
               border-bottom:1px solid var(--line); }}
  .tier-row:last-child {{ border-bottom:0; }}
  .tier-row::before {{ content:""; position:absolute; left:0; top:13px; bottom:13px;
                       width:3px; border-radius:3px; background:var(--tc); opacity:.85;
                       box-shadow:0 0 10px var(--tc); }}
  .tier-side {{ flex:0 0 92px; display:flex; flex-direction:column; align-items:flex-start; gap:5px; }}
  .tier-badge {{ width:38px; height:38px; border-radius:9px; font-family:var(--serif);
                 font-weight:700; font-size:19px; display:flex; align-items:center;
                 justify-content:center; color:#fff; }}
  .tier-badge.t-S {{ background:linear-gradient(145deg,#ff5a4d,#d11414); box-shadow:0 4px 16px rgba(224,25,25,.45); }}
  .tier-badge.t-A {{ background:linear-gradient(145deg,#ff7a4d,#e63a1a); box-shadow:0 4px 14px rgba(240,64,31,.38); }}
  .tier-badge.t-B {{ background:linear-gradient(145deg,#ff9d52,#e0741a); box-shadow:0 4px 14px rgba(240,122,31,.34); }}
  .tier-badge.t-C {{ background:linear-gradient(145deg,#f2c14e,#ca900f); box-shadow:0 4px 14px rgba(217,154,31,.30); color:#2a1d00; }}
  .tier-badge.t-D {{ background:linear-gradient(145deg,#9fc6ff,#5a8fe0); box-shadow:0 4px 14px rgba(90,147,232,.30); }}
  .tier-badge.t-E {{ background:linear-gradient(145deg,#6fa8f5,#3570d8); box-shadow:0 4px 14px rgba(53,112,216,.34); }}
  .tier-badge.t-F {{ background:linear-gradient(145deg,#4d86e8,#2148b8); box-shadow:0 4px 14px rgba(35,81,192,.40); }}
  .tier-badge.t-G {{ background:linear-gradient(145deg,#3f63d6,#162f8c); box-shadow:0 4px 16px rgba(27,58,160,.46); }}
  .tier-range {{ font-size:10.5px; color:var(--faint); letter-spacing:.02em; }}
  .tier-count {{ font-size:11px; color:var(--sub); background:rgba(255,255,255,.05);
                 padding:1px 7px; border-radius:5px; }}
  .tier-stocks {{ display:flex; flex-wrap:wrap; gap:7px; align-content:flex-start; padding-top:2px; }}
  .tier-more {{
    flex-basis:100%;
    margin-top:4px;
  }}
  .tier-more summary {{
    display:inline-flex;
    align-items:center;
    height:26px;
    cursor:pointer;
    color:var(--gold);
    border:1px solid rgba(216,183,115,.35);
    background:rgba(216,183,115,.08);
    border-radius:8px;
    padding:0 10px;
    font-size:11.5px;
    list-style:none;
    user-select:none;
  }}
  .tier-more summary::-webkit-details-marker {{ display:none; }}
  .tier-more summary::after {{
    content:"펼치기";
    margin-left:8px;
    color:var(--sub);
    font-family:var(--sans);
    font-size:11px;
  }}
  .tier-more[open] summary::after {{ content:"접기"; }}
  .tier-more-list {{
    display:flex;
    flex-wrap:wrap;
    gap:7px;
    margin-top:8px;
    max-height:168px;
    overflow:auto;
    padding:2px 4px 4px 0;
  }}
  .tier-more-list::-webkit-scrollbar {{ width:8px; height:8px; }}
  .tier-more-list::-webkit-scrollbar-thumb {{
    background:rgba(255,255,255,.16);
    border-radius:999px;
  }}
  .chip {{ display:inline-flex; align-items:center; gap:8px; font-size:12.5px;
           background:rgba(255,255,255,.03); border:1px solid var(--line2);
           border-radius:8px; padding:4px 10px; white-space:nowrap;
           transition:transform .12s ease, border-color .12s ease; }}
  .chip:hover {{ transform:translateY(-1px); border-color:var(--faint); }}
  .chip .c-name {{ color:var(--ink); }}
  .chip .c-rate {{ font-size:12px; font-weight:700; }}
  .chip.up {{ background:var(--up-dim); }} .chip.up .c-rate {{ color:var(--up); }}
  .chip.down {{ background:var(--down-dim); }} .chip.down .c-rate {{ color:var(--down); }}
  .chip.flat .c-rate {{ color:var(--flat); }}
  .empty {{ color:var(--faint); font-size:13px; }}

  /* ── themes ── */
  .theme-list {{ display:flex; flex-direction:column; gap:2px; }}
  .theme-item {{ display:grid; grid-template-columns:30px 1fr 150px 74px 44px;
                 align-items:center; gap:14px; padding:9px 4px;
                 border-bottom:1px solid var(--line); }}
  .theme-item:last-child {{ border-bottom:0; }}
  .t-rank {{ font-size:12px; color:var(--faint); }}
  .t-name {{ font-size:14px; font-weight:600; }}
  .t-gauge {{ height:7px; background:rgba(255,255,255,.05); border-radius:4px; overflow:hidden; }}
  .t-fill {{ display:block; height:100%; border-radius:4px;
             transition:width 1s cubic-bezier(.16,1,.3,1); }}
  .t-fill.up {{ background:linear-gradient(90deg,#ff6b6b,var(--up)); }}
  .t-fill.down {{ background:linear-gradient(90deg,var(--down),#5fb0ff); }}
  .t-fill.flat {{ background:var(--flat); }}
  .t-val {{ font-size:13.5px; font-weight:700; text-align:right; }}
  .t-cnt {{ font-size:12px; color:var(--faint); text-align:right; }}

  footer {{ margin-top:30px; padding-top:18px; border-top:1px solid var(--line);
            text-align:center; font-family:var(--mono); font-size:11px;
            color:var(--faint); letter-spacing:.03em; }}

  /* ── motion ── */
  @keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:.35;}} }}
  .reveal {{ opacity:0; transform:translateY(14px); animation:rise .7s cubic-bezier(.16,1,.3,1) forwards; }}
  .reveal:nth-child(1){{animation-delay:.05s;}} .reveal:nth-child(2){{animation-delay:.13s;}}
  .reveal:nth-child(3){{animation-delay:.21s;}} .reveal:nth-child(4){{animation-delay:.29s;}}
  .reveal:nth-child(5){{animation-delay:.37s;}}
  @keyframes rise {{ to {{ opacity:1; transform:none; }} }}
  @media (prefers-reduced-motion:reduce) {{
    .reveal{{animation:none;opacity:1;transform:none;}} .seg,.t-fill{{transition:none;}}
    .brand .dot{{animation:none;}}
  }}

  @media (max-width:680px) {{
    header h1 {{ font-size:34px; }}
    .metrics {{ grid-template-columns:repeat(2,1fr); }}
    .mkt-grid {{ grid-template-columns:1fr; }}
    .theme-item {{ grid-template-columns:26px 1fr 60px 38px; }}
    .theme-item .t-gauge {{ display:none; }}
    .tier-side {{ flex-basis:74px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="brand"><span class="dot"></span><span class="kicker">Market Brief · Terminal</span></div>
    <h1>한국 증시 <em>데일리 브리프</em></h1>
    <div class="meta-row">
      <span><b>{date}</b></span><span class="sep">/</span>
      <span><b>{session_label}</b></span><span class="sep">/</span>
      <span>KOSPI · KOSDAQ</span><span class="sep">/</span>
      <span>생성 {generated_at}</span>
    </div>
  </header>
  {body}
  <footer>MARKET BRIEF V1 — 시장 분위기 파악용 경량 리포트. 투자 판단의 근거가 아닙니다.</footer>
</div>
</body>
</html>"""
