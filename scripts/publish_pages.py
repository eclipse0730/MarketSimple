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
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REPORT_RE = re.compile(r"index_(\d{8})\.html$")
# 리포트 내 날짜 이동 버튼: href="<url인코딩된 index_YYYYMMDD.html>"
NAV_HREF_RE = re.compile(r'(class="date-nav-btn (?:prev|next)" href=")([^"]+)(")')

# 게시할 시장 목록 — 시장 추가/제거는 여기 한 줄. landing=True 인 시장이 루트(/) 기본.
# 게시·링크교정·홈페이지가 모두 이 목록을 돌므로 kr/us 가 코드상 완전 대칭이다.
MARKETS = [
    {"key": "kr", "title": "KR Market Brief", "landing": True},
    {"key": "us", "title": "US Market Brief"},
]

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
    for p in report_dir.glob("index_*.html"):   # REPORT_RE 로 날짜만 추출(다른 잔존물 제외)
        m = REPORT_RE.search(p.name)
        if m:
            dates.append(m.group(1))
    return sorted(set(dates))


def _rewrite_nav_links(html: str) -> str:
    """날짜 이동 링크(로컬 파일명) → 배포 경로(../YYYYMMDD/)로 치환."""
    def repl(m):
        target = unquote(m.group(2))
        dm = re.search(r"index_(\d{8})\.html$", target)
        if not dm:
            return m.group(0)
        return f"{m.group(1)}../{dm.group(1)}/{m.group(3)}"
    return NAV_HREF_RE.sub(repl, html)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# 라이브로 열어둔 페이지(모바일/웹)가 배치 재발행을 감지해 '새로고침' 배너를 띄우는
# 스니펫. GitHub Pages 는 정적 파일마다 ETag/Last-Modified 를 주므로, 자기 URL 의 그
# 값이 처음 본 값과 달라지면 콘텐츠가 새로 발행된 것 → 배너. 옛 날짜 페이지는 내용이
# 안 바뀌어 ETag 도 그대로라 배너가 뜨지 않는다(페이지별로 정확히 동작). 캐시 우회
# 쿼리(?_mb=)로 엣지 캐시(max-age=600)를 건너뛰어 발행 직후 빠르게 감지한다.
_LIVE_REFRESH = """<!--mb-live-refresh-->
<style>
#mb-refresh{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom));
  transform:translate(-50%,160%);z-index:300;display:flex;align-items:center;gap:9px;
  padding:11px 18px;border:none;border-radius:999px;cursor:pointer;font-family:inherit;
  font-size:14px;color:#fff;background:linear-gradient(120deg,var(--up,#ff8aab),var(--accent,#d88aa8));
  box-shadow:0 10px 30px rgba(0,0,0,.28);opacity:0;
  transition:transform .35s cubic-bezier(.16,1,.3,1),opacity .35s ease;}
#mb-refresh.on{transform:translate(-50%,0);opacity:1;}
#mb-refresh span{font-weight:600;opacity:.95;}
#mb-refresh b{font-weight:800;}
@media (prefers-reduced-motion:reduce){#mb-refresh{transition:opacity .2s ease;}}
</style>
<script>
(function(){
  if(location.protocol==='file:') return;          /* 로컬 미리보기 제외 */
  var POLL_MS=90000, base=null, shown=false, timer=null;
  function sig(r){ return r.headers.get('etag')||r.headers.get('last-modified')||''; }
  function check(){
    fetch(location.pathname+'?_mb='+Date.now(),{method:'HEAD',cache:'no-store'})
      .then(function(r){
        if(!r.ok) return;
        var s=sig(r); if(!s) return;
        if(base===null){ base=s; return; }          /* 첫 응답을 기준으로 */
        if(s!==base && !shown) banner();
      }).catch(function(){});
  }
  function banner(){
    shown=true; if(timer){ clearInterval(timer); timer=null; }
    var b=document.createElement('button');
    b.type='button'; b.id='mb-refresh'; b.setAttribute('aria-live','polite');
    b.innerHTML='<span>새 데이터가 도착했어요</span><b>새로고침 ↻</b>';
    b.addEventListener('click',function(){ location.reload(); });
    document.body.appendChild(b);
    requestAnimationFrame(function(){ b.classList.add('on'); });
  }
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible' && !shown) check();
  });
  check();
  timer=setInterval(function(){
    if(document.visibilityState==='visible' && !shown) check();
  },POLL_MS);
})();
</script>
"""


def _inject_live_refresh(html: str) -> str:
    """발행 콘텐츠 페이지에 라이브 새로고침 배너 스니펫을 1회 주입한다(멱등)."""
    if "mb-live-refresh" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", _LIVE_REFRESH + "</body>", 1)
    return html + _LIVE_REFRESH


# date-nav 전체 블록(<nav class="date-nav">…</nav>). 페이지마다 하나뿐이다.
NAV_BLOCK_RE = re.compile(r'<nav class="date-nav"[\s\S]*?</nav>')
# 리포트와 동일한 화살표 SVG (report_shared.ARROWS 와 일치시켜야 모양이 같다)
NAV_ARROWS = {
    "prev": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>',
    "next": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
}


def _date_label(date_str: str) -> str:
    return f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"


def _nav_btn(neighbor: str | None, kind: str, title: str, prefix: str = "../") -> str:
    if neighbor:
        return (f'<a class="date-nav-btn {kind}" href="{prefix}{neighbor}/" '
                f'aria-label="{title}" title="{title} ({_date_label(neighbor)})">'
                f'{NAV_ARROWS[kind]}</a>')
    return (f'<span class="date-nav-btn {kind} is-disabled" aria-hidden="true">'
            f'{NAV_ARROWS[kind]}</span>')


def _nav_block(cur: str, prev: str | None, nxt: str | None, prefix: str = "../") -> str:
    return (
        '<nav class="date-nav" aria-label="날짜 이동">'
        f'{_nav_btn(prev, "prev", "이전 거래일", prefix)}'
        f'<span class="date-nav-cur mono">{_date_label(cur)}</span>'
        f'{_nav_btn(nxt, "next", "다음 거래일", prefix)}'
        '</nav>'
    )


def _rebuild_nav_links(market_root: Path) -> int:
    """배포된 모든 날짜 페이지의 date-nav 를 실제 폴더 집합으로부터 통째로 재생성한다.

    날짜 이동 링크는 리포트 빌드 시점에 구워지는데, 페이지는 '그 날이 최신'일 때만
    빌드되므로 그 시점엔 next 가 비활성으로 굳는다. 다음 거래일이 생겨도 직전 페이지는
    재빌드되지 않아 next 가 영구히 막힌다(돌아갈 수 없음). publish 는 매번 전체 날짜
    폴더를 알고 있으니, 여기서 각 페이지의 prev/next 를 이웃 날짜로 다시 써서
    활성/비활성·끊긴 링크를 한 번에 바로잡는다.
    """
    if not market_root.is_dir():
        return 0
    dates = sorted(d.name for d in market_root.iterdir()
                   if d.is_dir() and d.name.isdigit() and len(d.name) == 8)
    if not dates:
        return 0

    fixed = 0
    for i, cur in enumerate(dates):
        idx_file = market_root / cur / "index.html"
        if not idx_file.exists():
            continue
        html = idx_file.read_text(encoding="utf-8")
        prev = dates[i - 1] if i > 0 else None
        nxt = dates[i + 1] if i < len(dates) - 1 else None
        new_html, n = NAV_BLOCK_RE.subn(lambda _m: _nav_block(cur, prev, nxt), html, count=1)
        if n and new_html != html:
            idx_file.write_text(new_html, encoding="utf-8")
            fixed += 1
    if fixed:
        print(f"  · {market_root.name}: 날짜 네비 {fixed}건 갱신")
    return fixed


def _write_root_latest(landing: str) -> bool:
    """루트(/)에 landing 시장 최신 리포트를 직접 배치한다.

    meta-refresh 리다이렉트(/, /kr/ → /kr/날짜/) 대신 루트에 리포트 본문을 바로
    두어, marketbrief.kr 로 들어와도 주소창이 /kr/날짜/ 로 바뀌지 않게 한다(공유 시
    날짜 박힌 URL 이 복사되던 문제 해결). 날짜 nav 는 루트 기준(kr/날짜/)으로,
    og:url 은 루트로 재작성한다. 마스코트·이미지 경로는 절대경로(/mascot, /images)라
    루트에서도 그대로 동작한다.
    """
    market_root = DOCS / landing
    dates = sorted(d.name for d in market_root.iterdir()
                   if d.is_dir() and d.name.isdigit() and len(d.name) == 8) if market_root.is_dir() else []
    if not dates:
        return False
    latest = dates[-1]
    src = market_root / latest / "index.html"
    if not src.exists():
        return False

    html = src.read_text(encoding="utf-8")
    # 1) 날짜 nav 를 루트 기준(kr/날짜/)으로 재생성 — 루트는 /kr/ 보다 한 단계 위라 prefix 다름
    prev = dates[-2] if len(dates) >= 2 else None
    html, _ = NAV_BLOCK_RE.subn(
        lambda _m: _nav_block(latest, prev, None, prefix=f"{landing}/"), html, count=1)
    # 2) og:url / twitter url 의 /kr/날짜/ 를 루트(/)로 — 루트 페이지의 정식 주소는 도메인 루트
    base = os.environ.get("SITE_BASE_URL", "").rstrip("/")
    if base:
        html = html.replace(f'content="{base}/{landing}/{latest}/"', f'content="{base}/"')
    _write_text(DOCS / "index.html", html)
    print(f"  · 루트(/): {landing} 최신({latest}) 리포트 직접 배치")
    return True


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


def publish_market(market: str, title: str, only_latest: bool = False,
                   skip_thumb: bool = False) -> bool:
    all_dates = _report_dates(market)
    out_root = DOCS / market
    out_root.mkdir(parents=True, exist_ok=True)

    if not all_dates:
        _write_text(out_root / "index.html", _empty_page(title))
        return False

    latest = all_dates[-1]
    # 장중 모드: 최신 날짜 페이지만 갱신한다. 썸네일은 새 날짜에 없을 때만 만든다.
    dates = [latest] if only_latest else all_dates

    chrome = None if skip_thumb else _find_chrome()
    if chrome is None and not skip_thumb:
        print("  · [안내] Chrome 미발견 — 썸네일 생략 (CHROME_PATH 로 지정 가능)")

    report_dir = ROOT / "output" / market / "report"
    for date_str in dates:
        src = report_dir / _report_filename(market, date_str)
        if not src.exists():
            continue
        day_dir = out_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        html = _inject_live_refresh(_rewrite_nav_links(src.read_text(encoding="utf-8")))
        _write_text(day_dir / "index.html", html)
        # 최신 날짜(=오늘)는 장중 데이터가 계속 바뀌므로 매 발행마다 다시 캡처한다.
        # (안 하면 그날 첫 실행 — 장 시작 전 0% 스냅샷 — 썸네일이 종일 박제된다)
        # 과거 날짜는 확정본이라 썸네일이 있으면 재캡처를 건너뛴다(캡처 비용 절감).
        # 실패/Chrome 부재 시엔 OG 404 방지를 위해 직전 날짜 썸네일을 복사한다.
        thumb = day_dir / "thumb.png"
        if chrome and (date_str == latest or not thumb.exists()):
            _make_thumbnail(chrome, src, thumb)
        if not thumb.exists():
            _copy_fallback_thumb(out_root, day_dir, date_str)

    # 최신으로 리다이렉트 (카톡 공유는 항상 /<market>/ 한 줄만). OG 로 최신 썸네일 노출.
    _write_text(out_root / "index.html",
                _redirect_page(title, f"{latest}/", _redirect_og(market, latest)))
    print(f"  · {market}: {len(dates)}일 게시 (최신 {latest})")
    return True


def _report_filename(market: str, date_str: str) -> str:
    """시장별 리포트 원본 파일명(단일 출처는 각 시장 config.report_filename)."""
    if market == "kr":
        from kr import config
    else:
        from us import config  # type: ignore
    return config.report_filename(date_str)


def _copy_fallback_thumb(out_root: Path, day_dir: Path, date_str: str) -> bool:
    """현재 날짜 썸네일이 없으면 가장 가까운 이전 썸네일을 복사한다."""
    candidates = []
    for p in out_root.glob("*/thumb.png"):
        if not p.parent.name.isdigit() or p.parent == day_dir:
            continue
        if p.parent.name <= date_str:
            candidates.append(p)
    if not candidates:
        return False
    src = sorted(candidates, key=lambda p: p.parent.name)[-1]
    shutil.copy2(src, day_dir / "thumb.png")
    print(f"  · [안내] {day_dir.name} 썸네일 대체: {src.parent.name}/thumb.png 복사")
    return True


OG_DESC = "거래대금·거래량 Top30, 종목·섹터 Tier — 시장 분위기 요약(매일 갱신)"


def _og_meta(page_url: str, img_url: str, title: str, desc: str = OG_DESC) -> str:
    """리다이렉트 페이지용 Open Graph/트위터 카드 메타.

    카톡·SNS 는 meta-refresh 를 따라가지 않고 이 HTML 만 긁으므로, 여기에 og:image 가
    없으면 루트(marketbrief.kr) 공유 시 썸네일이 안 뜬다(날짜 URL 만 떴던 이유).
    """
    return "\n".join([
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{page_url}">',
        f'<meta property="og:image" content="{img_url}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:image" content="{img_url}">',
    ])


def _redirect_og(market: str, latest: str, *, root: bool = False) -> str:
    """배포 기준 URL(SITE_BASE_URL)이 있으면 최신 날짜 썸네일로 OG 메타를 만든다."""
    base = os.environ.get("SITE_BASE_URL", "").rstrip("/")
    if not base or not latest:
        return ""
    page_url = f"{base}/" if root else f"{base}/{market}/"
    img_url = f"{base}/{market}/{latest}/thumb.png"
    title = "Market Brief · 데일리 브리프" if root else f"{market.upper()} Market Brief · 데일리 브리프"
    return _og_meta(page_url, img_url, title)


def _redirect_page(title: str, target: str, og: str = "") -> str:
    return f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}">
<title>{title}</title>
{og}
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


def _custom_domain() -> str:
    """커스텀 도메인 결정. CUSTOM_DOMAIN 환경변수 우선, 없으면 SITE_BASE_URL 호스트.

    단, *.github.io 는 커스텀 도메인이 아니므로 CNAME 을 만들지 않는다.
    """
    domain = os.environ.get("CUSTOM_DOMAIN", "").strip()
    if not domain:
        # 도메인은 사이트(전체) 소유 — 특정 시장 패키지에 의존하지 않게 환경변수로 직접 읽는다.
        domain = urlparse(os.environ.get("SITE_BASE_URL", "")).netloc
    if not domain or domain.endswith(".github.io"):
        return ""
    return domain


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="GitHub Pages 발행")
    ap.add_argument("--intraday", action="store_true",
                    help="장중 모드: 최신 날짜만 갱신 + 새 날짜 썸네일만 생성")
    ap.add_argument("--skip-thumb", action="store_true",
                    help="썸네일 캡처 생략. 없으면 직전 썸네일로 대체")
    args = ap.parse_args(argv)
    only_latest = args.intraday
    skip_thumb = args.skip_thumb

    DOCS.mkdir(parents=True, exist_ok=True)
    _write_text(DOCS / ".nojekyll", "")

    # GitHub Pages 커스텀 도메인 (publish 마다 보존). 없으면 CNAME 제거.
    domain = _custom_domain()
    cname_file = DOCS / "CNAME"
    if domain:
        _write_text(cname_file, domain + "\n")
        print(f"  · CNAME: {domain}")
    elif cname_file.exists():
        cname_file.unlink()

    # 마스코트(docs/mascot)·정적 이미지(docs/images)는 docs/ 안에서 소스 겸 배포본으로
    # 직접 관리한다(과거엔 루트 mascot/·images/ 를 여기로 복사했으나 중복이라 통합).
    # 갱신 시 docs/mascot·docs/images 파일만 고치면 되고 재빌드는 불필요하다.

    ready = {}
    for m in MARKETS:
        ready[m["key"]] = publish_market(m["key"], m["title"], only_latest, skip_thumb)
        # 배포 후 전체 페이지의 date-nav 를 실제 날짜 집합으로 재생성
        # (장중 모드에서 직전 날짜의 next 가 막히는 문제 + 끊긴 링크 동시 교정)
        _rebuild_nav_links(DOCS / m["key"])

    # 루트(/) 에는 landing 시장 최신 리포트를 '직접' 배치한다(리다이렉트 X).
    # → marketbrief.kr 로 들어와도 주소창이 /kr/날짜/ 로 바뀌지 않아, 공유 URL 이 깔끔하다.
    # 리포트가 아직 없으면 시장 선택 메뉴로 폴백.
    landing = next((m["key"] for m in MARKETS if m.get("landing")), None)
    if not (landing and ready.get(landing) and _write_root_latest(landing)):
        _write_text(DOCS / "index.html", _home_page(ready))
    print("✔ docs/ 갱신 완료")


def _home_page(ready: dict) -> str:
    links = "\n".join(
        f'    <a href="{m["key"]}/">{m["key"].upper()} 최신 리포트'
        f'<small>{"게시됨" if ready.get(m["key"]) else "아직 없음"}</small></a>'
        for m in MARKETS
    )
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
{links}
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
