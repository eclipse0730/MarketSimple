# -*- coding: utf-8 -*-
"""리포트에서 카톡 공유용 요약 이미지 3장을 만든다.

  python -m scripts.make_summary_images            # 최신 빌드 리포트
  python -m scripts.make_summary_images 20260605   # 특정 날짜
  python -m scripts.make_summary_images --out docs/kr/20260605  # 출력 폴더 지정

  python -m scripts.make_summary_images --theme mode2     # 특정 테마만
  python -m scripts.make_summary_images --no-send         # 발송 없이 이미지만

카드 구성(폭 1080px):
  summary-1 : 시장 요약 + 시장 진단 + 거래대금 Top30 + 거래량 급증 Top30  (마스코트: bear)
  summary-2 : 종목 상승률 Tier                                          (마스코트: pengu)
  summary-3 : 섹터 상승률 Tier                                          (마스코트: shiba)

테마: 리포트의 data-theme(mode1 파스텔 / mode2 다크 / mode3 전문가 / mode4 세피아)을
  주입해 테마별로 한 세트씩 만든다. 기본은 4테마 전부 생성(--theme 로 1개만 가능).
  출력은 <out>/<테마> 폴더로 분리한다.

동작: 빌드된 리포트 HTML(output/kr/report/…[날짜].html)에 스타일/스크립트를 주입해
  대상 섹션만 남기고, 헤드리스 Chrome 으로 전체를 캡처한 뒤 배경 여백을 잘라 1080px
  폭으로 저장한다. 좌상단에 카드별 마스코트 + "marketbrief.kr" 말풍선, 상단 중앙에
  "<날짜> 오전장/장마감 요약"(실행 시각으로 자동 판단)을 넣는다.

발송: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수가 있으면, 각 테마 3장을 생성한
  직후 곧바로 텔레그램 앨범(sendMediaGroup)으로 발송한다(테마별 파이프라인). 한 테마
  발송이 실패해도 다음 테마는 계속 진행하고, 끝에 성공/실패 개수를 보고한다.
  --no-send 또는 환경변수 미설정 시 이미지만 생성한다.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2          # device-scale-factor (선명도)
WIDTH = 1080       # 결과 이미지 폭(px)
CAP_H = 5200       # 캡처 윈도우 높이(px) — 가장 긴 카드도 담기게 넉넉히

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# (출력파일명, 남길 섹션 id 들, 카드 부제, 마스코트 이미지파일)
CARDS = [
    ("summary-1", ["sec-market", "sec-diagnosis", "sec-money", "sec-volume"],
     "시장 요약 · 거래대금/거래량 Top30", "bear_clear.png"),
    ("summary-2", ["sec-tiers"], "종목 상승률 Tier", "pengu2_clear.png"),
    ("summary-3", ["sec-sector"], "섹터 상승률 Tier", "siba_01_clear.png"),
]

# 리포트 테마(<html data-theme>) — characters.json/report.css 와 동일한 mode 키.
THEMES = ["mode1", "mode2", "mode3", "mode4"]
THEME_LABELS = {"mode1": "파스텔", "mode2": "다크", "mode3": "전문가", "mode4": "세피아"}

FOOT_TEXT = "marketbrief.kr"


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


def _card_inject(show_ids: list[str], head_title: str, mascot_uri: str) -> tuple[str, str]:
    """대상 섹션만 보이게 하는 <style> 와 카드 헤더/푸터를 붙이는 <script> 를 만든다."""
    show_sel = ", ".join(f"#{i}" for i in show_ids)
    style = f"""
<style id="card-style">
  /* 그라데이션(--body-bg)을 끄고 테마의 단색 --bg 로 채운다(다크 포함).
     모서리색이 균일해야 _trim_and_resize 가 콘텐츠 경계를 정확히 잡는다. */
  html, body {{ background:var(--bg, #eef1f4) !important; background-image:none !important; }}
  .wrap {{ max-width:{WIDTH}px !important; padding:30px 30px 20px !important; }}
  header, footer, .date-nav, .mascot-wrap {{ display:none !important; }}
  section {{ display:none !important; }}
  {show_sel} {{ display:block !important; }}
  .reveal {{ opacity:1 !important; transform:none !important; animation:none !important; }}
  /* 토글(보통주/전종목)은 기본=보통주 노출이 맞으므로 그대로 둔다 */
  /* 헤더 3열: 좌(마스코트+말풍선) | 중앙(제목) | 우(균형용 빈칸).
     좌/우 칼럼 폭을 같게 둬야 제목이 카드 정중앙에 온다. */
  #card-head {{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center;
               margin-bottom:22px; font-family:var(--round,sans-serif); }}
  #card-head .ch-brandwrap {{ display:flex; align-items:center; gap:12px; justify-self:start; }}
  #card-head .ch-brandwrap img {{ width:76px; height:auto; display:block;
                   filter:drop-shadow(0 6px 12px rgba(216,138,168,.4)); }}
  #card-head .cf-bubble {{ position:relative; background:var(--panel); border:1px solid var(--line);
      border-radius:14px; padding:10px 16px; font-family:var(--round,sans-serif);
      font-weight:800; font-size:17px; color:var(--accent); letter-spacing:.01em;
      box-shadow:0 8px 24px rgba(0,0,0,.10); white-space:nowrap; }}
  #card-head .cf-bubble::after {{ content:""; position:absolute; left:-7px; top:50%;
      transform:translateY(-50%) rotate(45deg); width:12px; height:12px; background:var(--panel);
      border-left:1px solid var(--line); border-bottom:1px solid var(--line); }}
  #card-head .ch-title {{ font-weight:800; font-size:23px; color:var(--heading);
               letter-spacing:-.01em; text-align:center; white-space:nowrap; }}
</style>
"""
    script = f"""
<script id="card-script">
(function(){{
  function go(){{
    var wrap = document.querySelector('.wrap'); if(!wrap) return;
    var head = document.createElement('div'); head.id='card-head';
    head.innerHTML = '<span class="ch-brandwrap">'
                   +   '<img src="{mascot_uri}" alt="mascot">'
                   +   '<span class="cf-bubble">{FOOT_TEXT}</span>'
                   + '</span>'
                   + '<span class="ch-title">{head_title}</span>'
                   + '<span></span>';
    wrap.insertBefore(head, wrap.firstChild);
  }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', go); else go();
}})();
</script>
"""
    return style, script


def _apply_theme(report_html: str, theme: str) -> str:
    """<html ... data-theme="modeN"> 의 테마를 교체한다."""
    return re.sub(r'(<html[^>]*\bdata-theme=")[^"]*(")',
                  lambda m: m.group(1) + theme + m.group(2), report_html, count=1)


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
    """아래쪽 배경 여백을 잘라내고 폭 1080px 로 리사이즈.

    배경색은 좌상단 모서리 픽셀에서 읽는다(테마마다 배경이 달라 고정값을 쓸 수 없다)."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[2, 2]   # 모서리 = 카드 바깥 여백색

    def row_has_content(y: int) -> bool:
        for x in range(0, w, 9):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 26:
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


def _send_telegram_album(bot: str, chat: str, pngs: list[Path], caption: str) -> bool:
    """한 테마(3장)를 sendMediaGroup 앨범으로 발송. 실패해도 예외를 던지지 않고 False 반환."""
    import requests

    media, files = [], {}
    for i, p in enumerate(pngs, 1):
        key = f"p{i}"
        item = {"type": "photo", "media": f"attach://{key}"}
        if i == 1:
            item["caption"] = caption
        media.append(item)
        files[key] = (p.name, p.read_bytes(), "image/png")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot}/sendMediaGroup",
            data={"chat_id": chat, "media": json.dumps(media)},
            files=files, timeout=60,
        )
        if r.status_code == 200 and r.json().get("ok"):
            return True
        print(f"  · [발송 실패] HTTP {r.status_code}: {r.text[:160]}")
    except Exception as exc:
        print(f"  · [발송 오류] {str(exc)[:160]}")
    return False


def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="카톡 요약 이미지 생성 (테마별 3장씩)")
    ap.add_argument("date", nargs="?", help="기준일 YYYYMMDD (생략 시 최신 빌드)")
    ap.add_argument("--out", help="출력 폴더 (기본: output/kr/summary/<날짜>)")
    ap.add_argument("--theme", choices=THEMES,
                    help="특정 테마만 생성 (생략 시 4테마 전부)")
    ap.add_argument("--no-send", action="store_true",
                    help="텔레그램 발송 없이 이미지만 생성")
    args = ap.parse_args(argv)

    # 텔레그램 발송: BOT/CHAT 환경변수가 있고 --no-send 가 아니면 테마 생성 직후 발송.
    bot = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    do_send = bool(bot and chat) and not args.no_send
    if args.no_send:
        print("  · --no-send: 발송 생략")
    elif not (bot and chat):
        print("  · TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — 발송 생략(이미지만 생성)")

    chrome = _find_chrome()
    if not chrome:
        raise SystemExit("Chrome 을 찾지 못했습니다. CHROME_PATH 로 지정하세요.")

    report = _report_for_date(args.date) if args.date else _latest_report()
    if not report or not report.exists():
        raise SystemExit("빌드된 리포트를 찾지 못했습니다. 먼저 리포트를 생성하세요.")
    date_str = _date_of(report)
    date_label = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
    # 세션은 실행 시각(KST)으로 판단: 14시 이전=오전장, 이후=장마감.
    # (워크플로에 TZ=Asia/Seoul 이 설정돼 러너 로컬시각이 KST 다)
    session_label = "오전장 요약" if datetime.now().hour < 14 else "장마감 요약"
    head_title = f"{date_label} {session_label}"
    mascot_uris = {
        c[3]: (ROOT / "images" / c[3]).resolve().as_uri() for c in CARDS
    }

    base_dir = Path(args.out) if args.out else (ROOT / "output" / "kr" / "summary" / date_str)
    themes = [args.theme] if args.theme else THEMES
    report_html = report.read_text(encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    print(f"▶ 요약 이미지 생성  |  {date_str}  ←  {report.name}  |  테마 {len(themes)}종"
          f"{' · 발송 ON' if do_send else ''}")

    made = 0
    sent = 0          # 발송 성공한 테마 수
    send_fail = 0     # 발송 시도했으나 실패한 테마 수
    for theme in themes:
        themed_html = _apply_theme(report_html, theme)
        out_dir = base_dir / theme
        out_dir.mkdir(parents=True, exist_ok=True)
        pngs = []     # 이 테마에서 생성에 성공한 이미지(발송 대상)
        for name, ids, sub, mascot in CARDS:
            style, script = _card_inject(ids, head_title, mascot_uris[mascot])
            card_html = _build_card_html(themed_html, style, script)
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
                tf.write(card_html)
                tmp = Path(tf.name)
            out_png = out_dir / f"{name}.png"
            try:
                if _capture(chrome, tmp, out_png):
                    _trim_and_resize(out_png)
                    made += 1
                    pngs.append(out_png)
                    print(f"  ✔ [{theme}] {out_png.relative_to(ROOT)}")
            finally:
                tmp.unlink(missing_ok=True)

        # 이 테마 3장 생성 직후 곧바로 앨범 발송(실패해도 다음 테마로 계속).
        if do_send and len(pngs) == len(CARDS):
            cap = f"📊 Market Brief {head_title} · {THEME_LABELS.get(theme, theme)} · {stamp}"
            if _send_telegram_album(bot, chat, pngs, cap):
                sent += 1
                print(f"  → [{theme}] 텔레그램 발송 완료")
            else:
                send_fail += 1
        elif do_send:
            send_fail += 1
            print(f"  → [{theme}] 이미지 누락으로 발송 스킵")

    print(f"완료: {made}/{len(themes) * len(CARDS)} 장 → {base_dir.relative_to(ROOT)}")
    if do_send:
        print(f"발송: {sent}개 테마 성공" + (f", {send_fail}개 실패" if send_fail else ""))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
