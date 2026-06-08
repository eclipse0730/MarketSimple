# -*- coding: utf-8 -*-
"""로컬 프리뷰 서버 — 폰/PC 브라우저로 최신 리포트를 바로 확인.

  python -m scripts.serve_local            # 오늘자 리포트
  python -m scripts.serve_local 20260602   # 특정 날짜
  python -m scripts.serve_local --port 9000

동작:
  1) SITE_BASE_URL 을 비워서 빌드 → 이미지/마스코트 경로가 상대(/images, /mascot/…)가 됨
     (로컬 서버 루트에서 이미지가 깨지지 않도록)
  2) 최신 리포트를 _localtest/index.html 로, docs/images·docs/mascot 을 루트에 배치
  3) http 서버 기동 → 같은 와이파이의 폰에서 http://<PC IP>:<port>/ 로 접속

배포(marketbrief.kr)는 publish_pages.py 가 담당한다. 이건 로컬 확인 전용이다.
"""

from __future__ import annotations

import argparse
import glob
import http.server
import os
import shutil
import socket
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_localtest"


def _lan_ip() -> str:
    """LAN IP 추정 (외부로 안 나가는 UDP 소켓 트릭)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def build_and_stage(date: str | None) -> None:
    # 로컬용: 절대 URL 대신 상대경로가 되도록 SITE_BASE_URL 비움
    os.environ["SITE_BASE_URL"] = ""
    sys.path.insert(0, str(ROOT))
    from kr.main import main as kr_main

    argv = []   # kr.main 은 --market 을 모른다(상위 main.py 가 처리). 모드는 mode1 단일.
    if date:
        argv += ["--date", date]
    kr_main(argv)

    SITE.mkdir(parents=True, exist_ok=True)
    reports = sorted((ROOT / "output" / "kr" / "report").glob("index_*.html"))
    if not reports:
        raise SystemExit("리포트가 없습니다. 먼저 데이터를 수집하세요.")
    shutil.copy2(reports[-1], SITE / "index.html")

    # 이미지·마스코트는 docs/ 안에서 단일 소스로 관리한다(중복 제거).
    images = ROOT / "docs" / "images"
    if images.is_dir():
        shutil.copytree(images, SITE / "images", dirs_exist_ok=True)
    mascot = ROOT / "docs" / "mascot"
    if mascot.is_dir():
        shutil.copytree(mascot, SITE / "mascot", dirs_exist_ok=True)


def serve(port: int) -> None:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(SITE), **k)

        def end_headers(self):
            # 로컬 테스트는 캐시 끄기 (폰에서 옛 버전 안 보이게)
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a):
            pass

    ip = _lan_ip()
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        print("로컬 프리뷰 서버 실행 중")
        print(f"  PC:  http://127.0.0.1:{port}/")
        print(f"  폰:  http://{ip}:{port}/   (같은 와이파이, 진짜 브라우저로)")
        print("  Ctrl+C 로 종료")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n종료")


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="로컬 프리뷰 서버")
    ap.add_argument("date", nargs="?", help="기준일 YYYYMMDD (생략 시 오늘)")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    build_and_stage(args.date)
    serve(args.port)


if __name__ == "__main__":
    main()
