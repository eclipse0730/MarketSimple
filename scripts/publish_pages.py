# -*- coding: utf-8 -*-
"""GitHub Pages용 정적 사이트를 docs/ 에 생성한다.

배포 URL 구조 (카톡 공유·날짜 이동 친화적):
  docs/<market>/                 → 최신 리포트로 리다이렉트
  docs/<market>/YYYYMMDD/index.html  → 날짜별 리포트 (깔끔한 경로)
  docs/<market>/YYYYMMDD/thumb.png   → 카톡 OG 썸네일

리포트 내부의 날짜 이동 링크(로컬 파일명)는 배포 경로(../YYYYMMDD/)로 재작성한다.
썸네일은 헤드리스 Chrome 으로 리포트 상단을 1200×630 으로 캡처한다.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REPORT_RE = re.compile(r"\[(\d{8})\]_mode1\.html$")
# 리포트 내 날짜 이동 버튼: href="<url인코딩된 …[YYYYMMDD]_mode1.html>"
NAV_HREF_RE = re.compile(r'(class="date-nav-btn (?:prev|next)" href=")([^"]+)(")')

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def _find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def _report_dates(market: str) -> list[str]:
    report_dir = ROOT / "output" / market / "report"
    if not report_dir.exists():
        return []
    dates = []
    for p in report_dir.glob("*_mode1.html"):
        m = REPORT_RE.search(p.name)
        if m:
            dates.append(m.group(1))
    return sorted(set(dates))


def _rewrite_nav_links(html: str) -> str:
    """날짜 이동 링크(로컬 파일명) → 배포 경로(../YYYYMMDD/)로 치환."""
    def repl(m):
        target = unquote(m.group(2))
        dm = re.search(r"\[(\d{8})\]_mode1\.html$", target)
        if not dm:
            return m.group(0)
        return f"{m.group(1)}../{dm.group(1)}/{m.group(3)}"
    return NAV_HREF_RE.sub(repl, html)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_thumbnail(chrome: str, html_path: Path, out_png: Path) -> bool:
    """리포트 상단을 1200×630 OG 썸네일로 캡처한다. 실패해도 배포는 진행."""
    try:
        from PIL import Image
    except ImportError:
        print("  · [안내] Pillow 미설치 — 썸네일 생략 (pip install pillow)")
        return False

    tmp = out_png.with_suffix(".full.png")
    # reveal 애니메이션이 캡처를 흐리지 않도록 강제 해제한 임시 HTML
    html = html_path.read_text(encoding="utf-8")
    html = html.replace(
        "</head>",
        "<style>.reveal{opacity:1!important;transform:none!important;}"
        ".date-nav{display:none!important;}</style></head>",
    )
    tmp_html = out_png.with_suffix(".cap.html")
    tmp_html.write_text(html, encoding="utf-8")

    try:
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2", "--window-size=1200,900",
             f"--screenshot={tmp}", tmp_html.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        im = Image.open(tmp)
        # 상단 1200×630 비율로 크롭 (device-scale 2 → 2400×1800 캡처)
        w, h = im.size
        crop_h = int(w * 630 / 1200)
        im.crop((0, 0, w, min(crop_h, h))).resize((1200, 630)).save(out_png)
        return True
    except Exception as exc:
        print(f"  · [안내] 썸네일 생성 실패({html_path.name}): {str(exc)[:100]}")
        return False
    finally:
        for f in (tmp, tmp_html):
            try:
                f.unlink()
            except OSError:
                pass


def publish_market(market: str, title: str) -> bool:
    dates = _report_dates(market)
    out_root = DOCS / market
    out_root.mkdir(parents=True, exist_ok=True)

    if not dates:
        _write_text(out_root / "index.html", _empty_page(title))
        return False

    chrome = _find_chrome()
    if chrome is None:
        print("  · [안내] Chrome 미발견 — 썸네일 생략 (CHROME_PATH 로 지정 가능)")

    report_dir = ROOT / "output" / market / "report"
    for date_str in dates:
        src = report_dir / f"{_prefix(market)} [{date_str}]_mode1.html"
        if not src.exists():
            continue
        day_dir = out_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        html = _rewrite_nav_links(src.read_text(encoding="utf-8"))
        _write_text(day_dir / "index.html", html)
        if chrome:
            _make_thumbnail(chrome, src, day_dir / "thumb.png")

    latest = dates[-1]
    # 최신으로 리다이렉트 (카톡 공유는 항상 /<market>/ 한 줄만)
    _write_text(out_root / "index.html", _redirect_page(title, f"{latest}/"))
    print(f"  · {market}: {len(dates)}일 게시 (최신 {latest})")
    return True


def _prefix(market: str) -> str:
    if market == "kr":
        from kr import config
        return config.REPORT_FILENAME_PREFIX
    from us import config  # type: ignore
    return getattr(config, "REPORT_FILENAME_PREFIX", "Report")


def _redirect_page(title: str, target: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}">
<title>{title}</title>
<p><a href="{target}">{title} 최신 리포트 열기</a></p>
</html>
"""


def _empty_page(title: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<title>{title}</title>
<body><h1>{title}</h1><p>아직 게시된 리포트가 없습니다.</p>
<p><a href="../index.html">홈으로</a></p></body>
</html>
"""


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    _write_text(DOCS / ".nojekyll", "")

    kr_ready = publish_market("kr", "KR Market Brief")
    us_ready = publish_market("us", "US Market Brief")
    _write_text(DOCS / "index.html", _home_page(kr_ready, us_ready))
    print("✔ docs/ 갱신 완료")


def _home_page(kr_ready: bool, us_ready: bool) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Brief</title>
  <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
            background:#f7f8fa; color:#17202a; }}
    main {{ max-width:720px; margin:0 auto; padding:56px 24px; }}
    h1 {{ margin:0 0 12px; font-size:32px; }}
    p {{ color:#667085; line-height:1.6; }}
    .links {{ display:grid; gap:12px; margin-top:28px; }}
    a {{ display:block; padding:18px 20px; border:1px solid #d9dee7; border-radius:12px;
         background:white; color:#17202a; text-decoration:none; font-weight:700; }}
    small {{ display:block; margin-top:5px; color:#98a2b3; font-weight:500; }}
  </style>
</head>
<body><main>
  <h1>Market Brief</h1>
  <p>시장 분위기 파악용 경량 리포트입니다.</p>
  <div class="links">
    <a href="kr/">KR 최신 리포트<small>{'게시됨' if kr_ready else '아직 없음'}</small></a>
    <a href="us/">US 최신 리포트<small>{'게시됨' if us_ready else '아직 없음'}</small></a>
  </div>
</main></body>
</html>
"""


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
