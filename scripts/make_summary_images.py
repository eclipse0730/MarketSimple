# -*- coding: utf-8 -*-
"""리포트에서 카톡 공유용 요약 이미지 3장을 만든다.

  python -m scripts.make_summary_images            # 최신 빌드 리포트
  python -m scripts.make_summary_images 20260605   # 특정 날짜
  python -m scripts.make_summary_images --out docs/kr/20260605  # 출력 폴더 지정

카드 구성(폭 1080px):
  summary-1 : 시장 요약 + 거래대금 Top30 + 거래량 급증 Top30
  summary-2 : 종목 Tier
  summary-3 : 섹터 Tier

동작: 빌드된 리포트 HTML(output/kr/report/…[날짜].html)에 스타일/스크립트를 주입해
  대상 섹션만 남기고, 헤드리스 Chrome 으로 전체를 캡처한 뒤 배경 여백을 잘라 1080px
  폭으로 저장한다. 하단 여백에 bear 마스코트 + "marketbrief.kr" 말풍선을 넣는다.
  리포트 섹션의 실제 스타일을 그대로 재사용하므로 별도 CSS 중복이 없다.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2          # device-scale-factor (선명도)
WIDTH = 1080       # 결과 이미지 폭(px)
CAP_H = 5200       # 캡처 윈도우 높이(px) — 가장 긴 카드도 담기게 넉넉히
BG = (238, 241, 244)   # 카드 바깥 여백색(트리밍 기준). CSS 와 일치시켜야 함

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# (출력파일명, 남길 섹션 id 들, 카드 부제)
CARDS = [
    ("summary-1", ["sec-market", "sec-diagnosis", "sec-money", "sec-volume"], "시장 요약 · 거래대금/거래량 Top30"),
    ("summary-2", ["sec-tiers"], "종목 Tier"),
    ("summary-3", ["sec-sector"], "섹터 Tier"),
]


def _find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def _latest_report() -> Path | None:
    files = sorted(Path(ROOT / "output" / "kr" / "report").glob("*].html"))
    return files[-1] if files else None


def _report_for_date(date_str: str) -> Path | None:
    hits = list(Path(ROOT / "output" / "kr" / "report").glob(f"*[[]{date_str}].html"))
    return hits[0] if hits else None


def _date_of(path: Path) -> str:
    m = re.search(r"\[(\d{8})\]\.html$", path.name)
    return m.group(1) if m else ""


def _card_inject(show_ids: list[str], date_label: str, bear_uri: str) -> tuple[str, str]:
    """대상 섹션만 보이게 하는 <style> 와 카드 헤더/푸터를 붙이는 <script> 를 만든다."""
    show_sel = ", ".join(f"#{i}" for i in show_ids)
    style = f"""
<style id="card-style">
  html, body {{ background:#eef1f4 !important; }}
  body {{ background-image:none !important; }}
  .wrap {{ max-width:{WIDTH}px !important; padding:30px 30px 20px !important; }}
  header, footer, .date-nav, .mascot-wrap {{ display:none !important; }}
  section {{ display:none !important; }}
  {show_sel} {{ display:block !important; }}
  .reveal {{ opacity:1 !important; transform:none !important; animation:none !important; }}
  /* 토글(보통주/전종목)은 기본=보통주 노출이 맞으므로 그대로 둔다 */
  #card-head {{ display:flex; align-items:center; justify-content:space-between;
               gap:14px; margin-bottom:20px; font-family:var(--round,sans-serif); }}
  #card-head .ch-brand {{ font-weight:800; font-size:21px; color:var(--heading); letter-spacing:-.01em; }}
  #card-head .ch-date {{ font-size:14.5px; font-weight:700; color:var(--sub); }}
  #card-foot {{ display:flex; align-items:center; justify-content:flex-end; gap:14px;
               margin-top:20px; }}
  #card-foot img {{ width:88px; height:auto; display:block;
                   filter:drop-shadow(0 6px 12px rgba(216,138,168,.4)); }}
  #card-foot .cf-bubble {{ position:relative; background:var(--panel); border:1px solid var(--line);
      border-radius:14px; padding:11px 18px; font-family:var(--round,sans-serif);
      font-weight:800; font-size:18px; color:var(--accent); letter-spacing:.01em;
      box-shadow:0 8px 24px rgba(0,0,0,.10); }}
  #card-foot .cf-bubble::after {{ content:""; position:absolute; right:-7px; top:50%;
      transform:translateY(-50%) rotate(45deg); width:12px; height:12px; background:var(--panel);
      border-right:1px solid var(--line); border-top:1px solid var(--line); }}
</style>
"""
    script = f"""
<script id="card-script">
(function(){{
  function go(){{
    var wrap = document.querySelector('.wrap'); if(!wrap) return;
    var head = document.createElement('div'); head.id='card-head';
    head.innerHTML = '<span class="ch-brand">\\uD83D\\uDCCA Market Brief</span>'
                   + '<span class="ch-date">{date_label} · KOSPI·KOSDAQ</span>';
    wrap.insertBefore(head, wrap.firstChild);
    var foot = document.createElement('div'); foot.id='card-foot';
    foot.innerHTML = '<span class="cf-bubble">marketbrief.kr</span>'
                   + '<img src="{bear_uri}" alt="bear">';
    wrap.appendChild(foot);
  }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', go); else go();
}})();
</script>
"""
    return style, script


def _build_card_html(report_html: str, style: str, script: str) -> str:
    html = report_html.replace("</head>", style + "</head>", 1)
    html = html.replace("</body>", script + "</body>", 1)
    return html


def _capture(chrome: str, html_path: Path, out_png: Path) -> bool:
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        f"--force-device-scale-factor={SCALE}", f"--window-size={WIDTH},{CAP_H}",
        "--virtual-time-budget=3000", f"--screenshot={out_png}", html_path.as_uri(),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        return out_png.exists()
    except Exception as exc:
        print(f"  · [오류] 캡처 실패: {str(exc)[:120]}")
        return False


def _trim_and_resize(png: Path) -> None:
    """아래쪽 배경 여백을 잘라내고 폭 1080px 로 리사이즈."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    w, h = im.size
    px = im.load()

    def row_has_content(y: int) -> bool:
        for x in range(0, w, 9):
            r, g, b = px[x, y]
            if abs(r - BG[0]) + abs(g - BG[1]) + abs(b - BG[2]) > 26:
                return True
        return False

    last = h - 1
    for y in range(h - 1, -1, -1):
        if row_has_content(y):
            last = y
            break
    bottom = min(h, last + 30 * SCALE)   # 콘텐츠 아래 여백 30px
    im = im.crop((0, 0, w, bottom))
    if im.width != WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    im.save(png)


def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="카톡 요약 이미지 3장 생성")
    ap.add_argument("date", nargs="?", help="기준일 YYYYMMDD (생략 시 최신 빌드)")
    ap.add_argument("--out", help="출력 폴더 (기본: output/kr/summary/<날짜>)")
    args = ap.parse_args(argv)

    chrome = _find_chrome()
    if not chrome:
        raise SystemExit("Chrome 을 찾지 못했습니다. CHROME_PATH 로 지정하세요.")

    report = _report_for_date(args.date) if args.date else _latest_report()
    if not report or not report.exists():
        raise SystemExit("빌드된 리포트를 찾지 못했습니다. 먼저 리포트를 생성하세요.")
    date_str = _date_of(report)
    date_label = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
    bear_uri = (ROOT / "images" / "bear_clear.png").resolve().as_uri()

    out_dir = Path(args.out) if args.out else (ROOT / "output" / "kr" / "summary" / date_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_html = report.read_text(encoding="utf-8")
    print(f"▶ 요약 이미지 생성  |  {date_str}  ←  {report.name}")
    made = []
    for name, ids, sub in CARDS:
        style, script = _card_inject(ids, date_label, bear_uri)
        card_html = _build_card_html(report_html, style, script)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
            tf.write(card_html)
            tmp = Path(tf.name)
        out_png = out_dir / f"{name}.png"
        try:
            if _capture(chrome, tmp, out_png):
                _trim_and_resize(out_png)
                made.append(out_png)
                print(f"  ✔ {out_png.relative_to(ROOT)}")
        finally:
            tmp.unlink(missing_ok=True)

    print(f"완료: {len(made)}/3 장 → {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
