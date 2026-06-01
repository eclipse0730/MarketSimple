# -*- coding: utf-8 -*-
"""
리포트 생성 모듈 (Mode 4 — 파스텔 / 소프트 테마)

report.py 와 '보이는 정보'는 동일합니다. 디자인만 다릅니다.
write_csv / write_html 시그니처가 report.py 와 같으므로 main.py 에서
import 만 바꿔 끼우면 그대로 동작합니다.

  import report_mode4 as report   # main.py 상단에서 이렇게 교체

디자인 컨셉: 부드러운 파스텔 무드의 에디토리얼 스타일.
크림빛 배경 + 둥근 형태 + 라운드한 셰리프 헤드라인,
은은한 그림자와 파스텔 그라데이션. 상승=코랄/로즈, 하락=소프트 블루.
"""

import config

SESSION_LABEL = {"morning": "오전장 (11:59 기준)", "close": "장 마감"}

# 티어별 대표색 (파스텔). 상승(S~C)은 진한 로즈→피치, 하락(D~G)은 라일락→소프트 블루.
TIER_COLORS = {
    "S": "#e83f73", "A": "#f48aa0", "B": "#f7a98e", "C": "#f5c98a",
    "D": "#a9c7ef", "E": "#8fb4ea", "F": "#9d9ce6", "G": "#7466dc",
}
TIER_COLLAPSE_LIMIT = 30
TIER_COLLAPSE_LIMITS = {"B": 20, "C": 20, "D": 20, "E": 20}


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
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    return (
        f'<a class="chip {_cls(row.등락률)}" href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<span class="c-name">{row.종목명}</span>'
        f'<span class="c-rate mono">{_fmt(row.등락률)}</span></a>'
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
          <!--
          <div class="metric">
            <div class="m-label">전체 종목</div>
            <div class="m-value mono">{c['total']:,}</div>
          </div>
          -->
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
        </div>
        {_strength_bar(c)}
      </div>
    </section>"""


def _section_market(by_market):
    cards = ""
    for m in ("KOSPI", "KOSDAQ"):
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
            <span class="mkt-total mono">{c['total']:,}</span>
          </div>
          <div class="mkt-index-row">
            <span class="mkt-index mono">{_fmt_index(c.get('index_value'))}</span>
            <span class="mkt-rate mono {rate_cls}">{index_rate_label}</span>
            <span class="mkt-change mono {rate_cls}">{index_change_label}</span>
          </div>
          {_strength_bar(c)}
          <div class="mkt-row">
            <span class="up">▲ {c['up']:,}</span>
            <span class="flat">— {c['flat']:,}</span>
            <span class="down">▼ {c['down']:,}</span>
          </div>
          {_market_flow_row(c)}
        </div>"""
    return f"""
    <section class="reveal">
      <div class="sec-head"><span class="num">02</span><h2>시장별 요약</h2></div>
        <!--<span class="sec-note">지수 등락률 · 카운트는<br> 보통주 기준</span></div>-->
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
    return f"""
    <section class="reveal">
      <div class="sec-head"><span class="num">03</span><h2>티어 분포</h2></div>
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
    #    + _section_themes(top, bottom)
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
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Quicksand:wght@400;500;600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --up:#e8688a; --up-soft:#fbe4ea; --up-mid:#f7c9d6;
    --down:#7fa8e0; --down-soft:#e6eefb; --down-mid:#cbddf6;
    --flat:#b8a9c9; --flat-soft:#f0eaf5;
    --bg:#fdf7f4; --bg2:#fbf1ee; --panel:#ffffff; --panel2:#fffafa;
    --ink:#5a4a52; --sub:#9b8a92; --faint:#c4b4bc;
    --line:#f3e6e6; --line2:#ecd9dc;
    --accent:#d98aa8; --accent-soft:#f8e6ee;
    --round:"Quicksand","Nunito",sans-serif;
    --serif:"Gowun Batang",serif;
    --sans:"Nunito","Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; color:var(--ink);
    background:
      radial-gradient(800px 500px at 82% -6%, #fce4ee, transparent 60%),
      radial-gradient(700px 600px at -5% 100%, #e6eefb, transparent 55%),
      radial-gradient(600px 400px at 50% 50%, #fdf0f5, transparent 70%),
      var(--bg);
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
               margin:0 0 16px; letter-spacing:-.01em; color:#6b5560; }}
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
             box-shadow:0 8px 30px rgba(216,138,168,.07), 0 2px 8px rgba(216,138,168,.04); }}
  .sec-head {{ display:flex; align-items:center; gap:12px; margin-bottom:22px; }}
  .num {{ font-family:var(--round); font-size:12px; font-weight:700; color:#fff;
          background:linear-gradient(135deg,var(--accent),var(--up));
          border-radius:50%; width:28px; height:28px; display:flex; align-items:center;
          justify-content:center; letter-spacing:0; box-shadow:0 3px 8px rgba(217,138,168,.3); }}
  .sec-head h2 {{ font-family:var(--serif); font-weight:700; font-size:22px; margin:0;
                  letter-spacing:-.01em; color:#6b5560; }}
  .sec-note {{ margin-left:auto; font-family:var(--round); font-size:11.5px;
               color:var(--sub); letter-spacing:.03em; font-weight:600; }}
  .verdict {{ margin-left:auto; font-family:var(--round); font-size:12px; font-weight:700;
              padding:6px 16px; border-radius:999px; letter-spacing:.02em; }}
  .verdict.up {{ background:var(--up-soft); color:var(--up); }}
  .verdict.down {{ background:var(--down-soft); color:var(--down); }}
  .verdict.flat {{ background:var(--flat-soft); color:var(--flat); }}

  /* summary */
  .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:20px; }}
  .metric {{ padding:18px 18px; border-radius:18px; text-align:center;
             background:linear-gradient(180deg,var(--panel2),#fff); border:1px solid var(--line); }}
  .metric.up-card {{ background:linear-gradient(180deg,var(--up-soft),#fff); border-color:var(--up-mid); }}
  .metric.down-card {{ background:linear-gradient(180deg,var(--down-soft),#fff); border-color:var(--down-mid); }}
  .m-label {{ font-size:12px; color:var(--sub); margin-bottom:8px; letter-spacing:.02em; font-weight:700; }}
  .m-value {{ font-size:28px; font-weight:800; line-height:1; display:flex;
              align-items:baseline; gap:7px; justify-content:center; }}
  .m-pct {{ font-size:13px; font-weight:600; opacity:.8; }}
  .bar {{ display:flex; height:14px; border-radius:999px; overflow:hidden;
          background:var(--flat-soft); padding:0; }}
  .seg {{ height:100%; transition:width 1s cubic-bezier(.16,1,.3,1); }}
  .seg.up {{ background:linear-gradient(90deg,var(--up),#f6b0c1); }}
  .seg.down {{ background:linear-gradient(90deg,#b7d0f1,var(--down)); }}
  .seg.flat {{ background:linear-gradient(90deg,#fffafc,#f7f1f5,#fffafc); }}

  /* market cards */
  .mkt-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .mkt-card {{ padding:20px 22px; border-radius:20px;
              background:linear-gradient(180deg,var(--panel2),#fff);
              border:1px solid var(--line); }}
  .mkt-head {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:14px; }}
  .mkt-head h3 {{ font-family:var(--round); font-size:16px; font-weight:700; margin:0;
                  letter-spacing:.04em; color:#6b5560; }}
  .mkt-index-row {{ display:flex; align-items:baseline; gap:10px; justify-content:flex-start;
                    margin:-5px 0 12px; }}
  .mkt-index {{ font-size:19px; font-weight:850; color:#4f4148; }}
  .mkt-rate {{ font-size:14px; font-weight:800; }}
  .mkt-change {{ font-size:12px; font-weight:750; }}
  .mkt-total {{ font-size:14px; color:var(--sub); font-weight:600; }}
  .mkt-flow {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:10px; }}
  .flow-item {{ display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px;
                min-width:0; padding:8px 6px; border:1px solid var(--line); border-radius:12px;
                background:rgba(255,255,255,.68); font-family:var(--round);
                font-size:11px; line-height:1.1; font-weight:700; color:var(--sub); text-align:center; }}
  .flow-item b {{ font-size:11.5px; font-weight:850; line-height:1.1; white-space:nowrap; }}
  .mkt-row {{ display:flex; gap:18px; margin-top:13px; font-family:var(--round);
              font-size:13.5px; font-weight:700; }}

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
  .tier-badge.t-S {{ background:linear-gradient(145deg,#ff719c,#e83f73); box-shadow:0 5px 16px rgba(232,63,115,.38); }}
  .tier-badge.t-A {{ background:linear-gradient(145deg,#f8a6bb,#f48aa0); box-shadow:0 5px 14px rgba(244,138,160,.28); }}
  .tier-badge.t-B {{ background:linear-gradient(145deg,#fbc0a8,#f7a98e); box-shadow:0 5px 14px rgba(247,169,142,.26); }}
  .tier-badge.t-C {{ background:linear-gradient(145deg,#fadca6,#f5c98a); box-shadow:0 5px 14px rgba(245,201,138,.26); color:#8a6a3a; }}
  .tier-badge.t-D {{ background:linear-gradient(145deg,#c3d9f5,#a9c7ef); box-shadow:0 5px 14px rgba(169,199,239,.28); color:#4a6a98; }}
  .tier-badge.t-E {{ background:linear-gradient(145deg,#a9c6f0,#8fb4ea); box-shadow:0 5px 14px rgba(143,180,234,.30); }}
  .tier-badge.t-F {{ background:linear-gradient(145deg,#b3b1ee,#9d9ce6); box-shadow:0 5px 14px rgba(157,156,230,.30); }}
  .tier-badge.t-G {{ background:linear-gradient(145deg,#9288ef,#7466dc); box-shadow:0 5px 16px rgba(116,102,220,.38); }}
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
    color:#8b6574;
    border:1px solid color-mix(in srgb, var(--tc) 52%, white);
    background:color-mix(in srgb, var(--tc) 18%, white);
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
    background:color-mix(in srgb, var(--tc) 35%, white);
    border-radius:999px;
  }}
  .chip {{ display:inline-flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600;
           background:color-mix(in srgb, var(--tc) 14%, white);
           border:1px solid color-mix(in srgb, var(--tc) 50%, white);
           color:#6b5560;
           text-decoration:none;
           border-radius:999px; padding:5px 13px; white-space:nowrap;
           transition:transform .14s ease, box-shadow .14s ease; }}
  .chip:hover {{
    transform:translateY(-2px);
    box-shadow:0 4px 12px color-mix(in srgb, var(--tc) 24%, transparent);
  }}
  .chip .c-name {{ color:#5f4e56; }}
  .chip .c-rate {{ color:color-mix(in srgb, var(--tc) 82%, #6b5560); font-size:12px; font-weight:800; }}
  .empty {{ color:var(--faint); font-size:13px; }}

  /* themes */
  .theme-list {{ display:flex; flex-direction:column; gap:3px; }}
  .theme-item {{ display:grid; grid-template-columns:30px 1fr 150px 74px 44px;
                 align-items:center; gap:14px; padding:11px 6px;
                 border-bottom:1px solid var(--line); border-radius:12px;
                 transition:background .15s ease; }}
  .theme-item:hover {{ background:var(--bg2); }}
  .theme-item:last-child {{ border-bottom:0; }}
  .t-rank {{ font-size:12px; color:var(--faint); font-weight:700; }}
  .t-name {{ font-size:14px; font-weight:700; color:#6b5560; }}
  .t-gauge {{ height:9px; background:var(--flat-soft); border-radius:999px; overflow:hidden; }}
  .t-fill {{ display:block; height:100%; border-radius:999px;
             transition:width 1.1s cubic-bezier(.16,1,.3,1); }}
  .t-fill.up {{ background:linear-gradient(90deg,#f59ab3,var(--up)); }}
  .t-fill.down {{ background:linear-gradient(90deg,var(--down),#a5c4ee); }}
  .t-fill.flat {{ background:var(--flat); }}
  .t-val {{ font-size:13.5px; font-weight:800; text-align:right; }}
  .t-cnt {{ font-size:12px; color:var(--faint); text-align:right; font-weight:600; }}

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
    .theme-item {{ grid-template-columns:26px 1fr 60px 38px; }}
    .theme-item .t-gauge {{ display:none; }}
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
    <h1>한국 증시 <em>데일리 브리프</em></h1>
    <div class="meta-row">
      <span><b>{date}</b></span><span class="sep">·</span>
      <span><b>{session_label}</b></span><span class="sep">·</span>
      <span>KOSPI · KOSDAQ</span><span class="sep">·</span>
      <!--<span>생성 {generated_at}</span>-->
    </div>
  </header>
  {body}
  <footer>Market Brief V1 — 시장 분위기 파악용 경량 리포트 · 투자 판단의 근거가 아닙니다.</footer>
</div>
</body>
</html>"""
