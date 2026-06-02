# -*- coding: utf-8 -*-
"""GitHub Pages용 정적 파일을 docs/에 갱신한다."""

from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _latest_report(market: str, mode: str = "mode1") -> Path | None:
    report_dir = ROOT / "output" / market / "report"
    if not report_dir.exists():
        return None
    reports = sorted(
        report_dir.glob(f"*_{mode}.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def publish_market(market: str, title: str) -> bool:
    report = _latest_report(market)
    out_dir = DOCS / market
    out_dir.mkdir(parents=True, exist_ok=True)

    if report is None:
        _write_text(
            out_dir / "index.html",
            f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<title>{title}</title>
<body>
  <h1>{title}</h1>
  <p>아직 게시된 리포트가 없습니다.</p>
  <p><a href="../index.html">홈으로</a></p>
</body>
</html>
""",
        )
        return False

    shutil.copy2(report, out_dir / "latest.html")
    _write_text(
        out_dir / "index.html",
        f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=latest.html">
<title>{title}</title>
<p><a href="latest.html">{title} 최신 리포트 열기</a></p>
</html>
""",
    )
    return True


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    _write_text(DOCS / ".nojekyll", "")

    kr_ready = publish_market("kr", "KR Market Brief")
    us_ready = publish_market("us", "US Market Brief")
    _write_text(
        DOCS / "index.html",
        f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Brief</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
      background: #f7f8fa;
      color: #17202a;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 56px 24px;
    }}
    h1 {{ margin: 0 0 12px; font-size: 32px; }}
    p {{ color: #667085; line-height: 1.6; }}
    .links {{ display: grid; gap: 12px; margin-top: 28px; }}
    a {{
      display: block;
      padding: 18px 20px;
      border: 1px solid #d9dee7;
      border-radius: 12px;
      background: white;
      color: #17202a;
      text-decoration: none;
      font-weight: 700;
    }}
    small {{ display: block; margin-top: 5px; color: #98a2b3; font-weight: 500; }}
  </style>
</head>
<body>
  <main>
    <h1>Market Brief</h1>
    <p>GitHub Pages에서 보는 시장 리포트입니다.</p>
    <div class="links">
      <a href="kr/latest.html">KR 최신 리포트<small>{'게시됨' if kr_ready else '아직 없음'}</small></a>
      <a href="us/latest.html">US 최신 리포트<small>{'게시됨' if us_ready else '아직 없음'}</small></a>
    </div>
  </main>
</body>
</html>
""",
    )


if __name__ == "__main__":
    main()
