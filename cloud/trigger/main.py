# -*- coding: utf-8 -*-
"""GitHub 워크플로를 트리거하는 얇은 Cloud Run 서비스.

Cloud Scheduler 가 정확한 시각에 이 서비스를 POST 로 호출하면, 지정한 GitHub
워크플로를 workflow_dispatch 로 실행시킨다. GitHub Actions 의 schedule cron 이
드롭·지연되는 문제를 우회하기 위한 용도 — 수집·빌드·배포·발송 자체는 여전히
GitHub Actions 워크플로(update.yml / summary-telegram.yml)에서 실행된다.

요청:
  POST /trigger
  Header: X-Trigger-Token: <TRIGGER_TOKEN>      (Scheduler 와 공유하는 보안 토큰)
  Body : {"workflow": "update.yml", "ref": "main"}   # ref 생략 시 DEFAULT_REF

환경변수:
  GITHUB_TOKEN   GitHub PAT (repo + workflow 권한). 필수.
  GITHUB_REPO    "owner/repo" 형식. 예: eclipse0730/MarketSimple. 필수.
  TRIGGER_TOKEN  Scheduler 호출을 인증할 공유 비밀. 비우면 인증 생략(권장 X).
  DEFAULT_REF    워크플로를 실행할 기본 브랜치. 기본 "main".
  ALLOWED_WORKFLOWS  허용할 워크플로 파일명 콤마 목록. 비우면 전부 허용.
"""

from __future__ import annotations

import os

import json

import requests
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="MarketSimple workflow trigger")

GITHUB_API = "https://api.github.com"
DEFAULT_REF = os.environ.get("DEFAULT_REF", "main")


def _allowed_workflows() -> set[str]:
    raw = os.environ.get("ALLOWED_WORKFLOWS", "").strip()
    return {w.strip() for w in raw.split(",") if w.strip()}


@app.get("/healthz")
def healthz():
    """배포 직후 동작 확인용 — GitHub 호출 없이 설정만 검사한다."""
    return {
        "ok": True,
        "repo_set": bool(os.environ.get("GITHUB_REPO")),
        "token_set": bool(os.environ.get("GITHUB_TOKEN")),
        "auth_required": bool(os.environ.get("TRIGGER_TOKEN")),
        "default_ref": DEFAULT_REF,
    }


@app.post("/trigger")
async def trigger(request: Request, x_trigger_token: str | None = Header(default=None)):
    # 1) 공유 토큰 인증 (TRIGGER_TOKEN 이 설정돼 있을 때만)
    expected = os.environ.get("TRIGGER_TOKEN", "")
    if expected and x_trigger_token != expected:
        raise HTTPException(status_code=401, detail="invalid trigger token")

    # body 파싱: Cloud Scheduler 는 Content-Type 을 application/octet-stream 으로
    # 강제하므로 FastAPI 의 자동 JSON 파싱(application/json 필요)에 의존하지 않고
    # raw body 를 직접 json.loads 한다.
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="body must be valid JSON")
    workflow = payload.get("workflow")
    if not workflow:
        raise HTTPException(status_code=422, detail="missing 'workflow'")
    ref = payload.get("ref") or DEFAULT_REF

    # 2) 허용 워크플로 화이트리스트 (설정된 경우)
    allowed = _allowed_workflows()
    if allowed and workflow not in allowed:
        raise HTTPException(status_code=403, detail=f"workflow not allowed: {workflow}")

    repo = os.environ.get("GITHUB_REPO", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo or not token:
        raise HTTPException(status_code=500, detail="GITHUB_REPO / GITHUB_TOKEN not configured")

    url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/dispatches"
    resp = requests.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": ref},
        timeout=20,
    )

    # GitHub 는 성공 시 204 No Content 를 준다. 그 외는 본문을 그대로 전달해 디버깅.
    if resp.status_code == 204:
        return {"ok": True, "workflow": workflow, "ref": ref}
    raise HTTPException(
        status_code=502,
        detail={"github_status": resp.status_code, "github_body": resp.text[:500]},
    )
