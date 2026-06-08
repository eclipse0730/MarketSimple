# Cloud Scheduler + Cloud Run 으로 GitHub 워크플로 트리거

GitHub Actions 의 `schedule:` cron 은 혼잡 시간대에 **지연·드롭**되거나 60일
비활성 시 자동 중단된다. 이 문서는 그 트리거만 **Cloud Scheduler(정확한 cron)**
→ **Cloud Run(얇은 트리거 서비스)** → **GitHub `workflow_dispatch`** 로 대체하는
절차다. 수집·빌드·Chrome 캡처·push·텔레그램 발송은 **여전히 GitHub Actions**
워크플로(`update.yml`, `summary-telegram.yml`)에서 그대로 실행된다.

```
[Cloud Scheduler] ──cron──▶ [Cloud Run /trigger] ──POST dispatch──▶ [GitHub Actions]
   (정확한 시각)              (PAT 보관, 화이트리스트)               update.yml / summary-telegram.yml
```

서비스 코드는 `cloud/trigger/`(main.py · Dockerfile · requirements.txt)에 있다.

---

## 0. 사전 준비

- GCP 계정 + 결제 계정 연결(이 규모는 무료 한도 내라 사실상 $0, 단 결제 계정은 필요)
- `gcloud` CLI 설치 및 로그인: `gcloud auth login`
- 아래 변수는 본인 값으로 바꿔서 쓴다. (PowerShell 기준 예시)

```powershell
$PROJECT = "marketsimple-trigger"      # 새로 만들거나 기존 프로젝트 ID
$REGION  = "asia-northeast3"           # 서울 리전
$SERVICE = "ms-trigger"                # Cloud Run 서비스 이름
$REPO    = "eclipse0730/MarketSimple"  # owner/repo
```

---

## 1. GitHub PAT(Personal Access Token) 발급

Cloud Run 이 GitHub API 로 워크플로를 트리거하려면 토큰이 필요하다.

**Fine-grained token (권장)**
1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token
2. **Repository access**: Only select repositories → `MarketSimple` 선택
3. **Permissions** → Repository permissions:
   - **Actions**: Read and write  ← workflow_dispatch 에 필수
   - **Contents**: Read-only (워크플로가 git push 는 자기 GITHUB_TOKEN 으로 하므로 PAT 엔 불필요. Read 면 충분)
4. 만료일 설정(예: 1년) → 토큰 문자열 복사 (`github_pat_...`). **이 화면을 벗어나면 다시 못 본다.**

> classic token 이면 `repo` + `workflow` 스코프. fine-grained 가 권한 최소화에 낫다.

토큰과 별개로 Scheduler↔Cloud Run 인증용 **공유 비밀**을 하나 만든다(아무 랜덤 문자열):
```powershell
$TRIGGER_TOKEN = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})
$GITHUB_TOKEN  = "github_pat_여기에붙여넣기"
```

---

## 2. GCP 프로젝트 · API 활성화

```powershell
gcloud projects create $PROJECT          # 기존 프로젝트 쓰면 생략
gcloud config set project $PROJECT
# 결제 계정 연결(콘솔에서 해도 됨): https://console.cloud.google.com/billing

gcloud services enable run.googleapis.com cloudscheduler.googleapis.com `
  artifactregistry.googleapis.com cloudbuild.googleapis.com
```

---

## 3. Cloud Run 서비스 배포

`cloud/trigger/` 폴더에서 소스 기반으로 배포한다(Cloud Build 가 Dockerfile 로 빌드).

```powershell
cd cloud/trigger

gcloud run deploy $SERVICE `
  --source . `
  --region $REGION `
  --no-allow-unauthenticated `
  --set-env-vars "GITHUB_REPO=$REPO,DEFAULT_REF=main,ALLOWED_WORKFLOWS=update.yml,summary-telegram.yml" `
  --set-env-vars "GITHUB_TOKEN=$GITHUB_TOKEN,TRIGGER_TOKEN=$TRIGGER_TOKEN"
```

- `--no-allow-unauthenticated`: 아무나 호출 못 하게. Scheduler 는 서비스 계정 +
  `TRIGGER_TOKEN` 두 겹으로 인증한다.
- 배포가 끝나면 서비스 URL 이 출력된다. 저장:
  ```powershell
  $URL = gcloud run services describe $SERVICE --region $REGION --format "value(status.url)"
  $URL
  ```

> 토큰을 환경변수 대신 **Secret Manager** 로 관리하려면 4-B 참고(권장이지만 선택).

---

## 4. Scheduler 가 Cloud Run 을 호출할 서비스 계정

`--no-allow-unauthenticated` 라 Scheduler 가 OIDC 토큰으로 인증해야 한다.

```powershell
$SA = "ms-scheduler"
gcloud iam service-accounts create $SA --display-name "MarketSimple scheduler"
$SA_EMAIL = "$SA@$PROJECT.iam.gserviceaccount.com"

# 이 서비스 계정에 해당 Cloud Run 호출 권한 부여
gcloud run services add-iam-policy-binding $SERVICE `
  --region $REGION `
  --member "serviceAccount:$SA_EMAIL" `
  --role "roles/run.invoker"
```

---

## 5. Cloud Scheduler 잡 생성

기존 GitHub cron 을 그대로 옮긴다. **Cloud Scheduler 의 timezone 을 직접 지정**할 수
있어 UTC 변환이 불필요하다(`Asia/Seoul` 그대로).

기존 스케줄:
- `update.yml`        — 평일 09:07~15:37 KST, 30분 간격(수집·빌드·배포)
- `summary-telegram.yml` — 평일 11:58, 15:33 KST(요약 발송)

```powershell
# 공통 호출 옵션 함수처럼 쓸 본문/헤더
$HDR = "Content-Type=application/json,X-Trigger-Token=$TRIGGER_TOKEN"

# (1) update-report : 평일 09~15시 매 7,37분 (기존 cron 과 동일 간격)
gcloud scheduler jobs create http ms-update `
  --location $REGION `
  --schedule "7,37 9-15 * * 1-5" `
  --time-zone "Asia/Seoul" `
  --uri "$URL/trigger" `
  --http-method POST `
  --headers $HDR `
  --message-body '{\"workflow\":\"update.yml\",\"ref\":\"main\"}' `
  --oidc-service-account-email $SA_EMAIL `
  --oidc-token-audience $URL

# (2) summary 오전장 : 평일 11:58 KST
gcloud scheduler jobs create http ms-summary-am `
  --location $REGION `
  --schedule "58 11 * * 1-5" `
  --time-zone "Asia/Seoul" `
  --uri "$URL/trigger" `
  --http-method POST `
  --headers $HDR `
  --message-body '{\"workflow\":\"summary-telegram.yml\",\"ref\":\"main\"}' `
  --oidc-service-account-email $SA_EMAIL `
  --oidc-token-audience $URL

# (3) summary 장마감 : 평일 15:33 KST
gcloud scheduler jobs create http ms-summary-pm `
  --location $REGION `
  --schedule "33 15 * * 1-5" `
  --time-zone "Asia/Seoul" `
  --uri "$URL/trigger" `
  --http-method POST `
  --headers $HDR `
  --message-body '{\"workflow\":\"summary-telegram.yml\",\"ref\":\"main\"}' `
  --oidc-service-account-email $SA_EMAIL `
  --oidc-token-audience $URL
```

> `--schedule` 시각 표기는 GitHub 보다 자유롭다. 더 촘촘히 하려면
> `"7,22,37,52 9-15 * * 1-5"` 처럼 늘려도 워크플로가 멱등(같은 날짜는 재수집 skip)
> 이라 안전하다.

---

## 6. 동작 확인

```powershell
# (a) Cloud Run 헬스체크 — 설정값만 검사(GitHub 호출 안 함). 인증 토큰으로 호출.
$ID = gcloud auth print-identity-token
curl -H "Authorization: Bearer $ID" "$URL/healthz"
#   → {"ok":true,"repo_set":true,"token_set":true,"auth_required":true,...}

# (b) Scheduler 잡 즉시 1회 실행 → GitHub Actions 탭에 update-report 가 떠야 한다.
gcloud scheduler jobs run ms-update --location $REGION

# (c) Cloud Run 로그에서 트리거 결과 확인
gcloud run services logs read $SERVICE --region $REGION --limit 20
```

GitHub → 레포 → **Actions** 탭에서 `update-report` 실행이 "manually triggered"로
뜨면 성공이다.

---

## 7. 기존 GitHub schedule cron 정리(선택)

Cloud Scheduler 로 옮긴 뒤에는 GitHub 워크플로의 `schedule:` 을 **지우거나 주석**
처리해 중복 실행을 막는다. `workflow_dispatch:` 는 **반드시 남겨둔다**(트리거 통로).

`.github/workflows/update.yml`, `summary-telegram.yml` 의 `on:` 에서:
```yaml
on:
  # schedule:                     # ← Cloud Scheduler 로 이관, 제거/주석
  #   - cron: "7,37 0-6 * * 1-5"
  workflow_dispatch:              # ← 유지 (Cloud Run 이 이걸로 트리거)
```

> 둘 다 켜두면 GitHub cron 이 (가끔) 돌 때 하루 두 번 실행될 수 있다. 중복이 싫으면
> GitHub schedule 을 끄고 Cloud Scheduler 만 신뢰원으로 삼는다.

---

## 비용·운영 메모

- **Cloud Run**: 요청이 있을 때만 인스턴스가 뜨고(min-instances=0), 트리거는 하루
  10여 회 · 각 1초 미만이라 무료 한도(월 200만 요청·충분한 CPU·초)에 한참 못 미친다.
- **Cloud Scheduler**: 잡 3개 → 무료 한도(월 3잡 무료) 경계. 더 늘리면 잡당 월
  $0.10 수준.
- **토큰 만료**: PAT 만료일이 오면 트리거가 401/403 으로 실패한다. 만료 전 갱신 후
  `gcloud run services update $SERVICE --region $REGION --update-env-vars GITHUB_TOKEN=새토큰`.

### 4-B. (선택) 토큰을 Secret Manager 로

환경변수에 평문 토큰을 두는 대신:
```powershell
gcloud services enable secretmanager.googleapis.com
echo $GITHUB_TOKEN | gcloud secrets create github-token --data-file=-
# Cloud Run 서비스 계정에 secret 접근 권한 부여 후
gcloud run services update $SERVICE --region $REGION `
  --update-secrets "GITHUB_TOKEN=github-token:latest"
```

---

## 8. 운영 (일상 관리)

실제 배포된 환경 값:

| 항목 | 값 |
|---|---|
| 프로젝트 | `marketsimple-trigger` |
| 리전 | `asia-northeast3` (서울) |
| Cloud Run 서비스 | `ms-trigger` |
| 서비스 URL | `https://ms-trigger-sxbozghs5q-du.a.run.app` |
| Scheduler 잡 | `ms-update`(평일 09~15시 7,37분) · `ms-summary-am`(11:58) · `ms-summary-pm`(15:33), 모두 KST |
| Scheduler 서비스계정 | `ms-scheduler@marketsimple-trigger.iam.gserviceaccount.com` |

> **중요**: GitHub schedule cron 은 비활성화돼 있다(update.yml·summary-telegram.yml).
> 따라서 **Cloud Scheduler 가 유일한 자동 실행원**이다. 잡을 pause/삭제하면 리포트
> 자동 갱신이 멈춘다.

### 콘솔(브라우저)에서 보기

| 무엇 | URL |
|---|---|
| Cloud Run 서비스 | https://console.cloud.google.com/run?project=marketsimple-trigger |
| Cloud Scheduler 잡 | https://console.cloud.google.com/cloudscheduler?project=marketsimple-trigger |
| 로그 | Run → `ms-trigger` 클릭 → 상단 **로그** 탭 |
| 비용/예산 | https://console.cloud.google.com/billing |

Cloud Run 서비스 클릭 시 탭: **측정항목**(요청·에러율) · **로그** · **수정 및 새 버전
배포**(환경변수·메모리) · **버전**(revision 이력) · **트리거**.

### CLI 빠른 참조

> PATH 미반영 시: `$gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"`
> 로 잡고 `& $gcloud ...` 로 호출. 아래는 PATH 반영된 새 터미널 기준.

```powershell
$P = "marketsimple-trigger"; $R = "asia-northeast3"

# (A) 상태 확인 — 잡 목록 + 마지막 실행 시각
gcloud scheduler jobs list --location $R --project $P

# (B) 로그 보기 (문제 추적 1순위)
gcloud run services logs read ms-trigger --region $R --project $P --limit 30

# (C) 수동 테스트 — 직후 GitHub Actions 탭에 workflow_dispatch 로 떠야 정상
gcloud scheduler jobs run ms-update --location $R --project $P

# (D) 스케줄 멈춤 / 재개 (휴장·점검 시)
gcloud scheduler jobs pause  ms-update --location $R --project $P
gcloud scheduler jobs resume ms-update --location $R --project $P

# (E) 실행 시각 변경
gcloud scheduler jobs update http ms-update --schedule "0,30 9-15 * * 1-5" --location $R --project $P
```

### 코드/환경변수 변경

```powershell
# 트리거 서비스 코드(cloud/trigger/main.py)를 고쳤을 때 → 재배포(환경변수 유지)
cd cloud/trigger
gcloud run deploy ms-trigger --source . --region $R --project $P --no-allow-unauthenticated

# 환경변수 개별 수정(기존 유지). 예: PAT 갱신
gcloud run services update ms-trigger --region $R --project $P --update-env-vars "GITHUB_TOKEN=새토큰"
```

### ⚠️ 자주 밟는 함정 (PowerShell)

- **`--env-vars-file` 은 환경변수를 전체 교체**한다. 일부만 든 파일을 주면 나머지가
  날아간다. 개별 변경은 `--update-env-vars` 를 쓴다.
- **콤마 든 값**(`ALLOWED_WORKFLOWS=a.yml,b.yml`)이나 **JSON body** 는 PowerShell
  에서 따옴표가 깨진다 → YAML 파일(`--env-vars-file`) / `--message-body-from-file`
  / 콘솔 UI 로 넣는다. (Scheduler body 가 `{workflow:...}` 처럼 따옴표 없이 저장되면
  Cloud Run 이 422 를 낸다.)
- **Scheduler 가 Content-Type 을 octet-stream 으로 강제**하므로 서버는 raw body 를
  직접 json.loads 한다(main.py). Content-Type 헤더를 못 바꿔도 정상이다.

### 점검 주기

- **PAT 만료**: 발급 시 정한 만료일 도래 시 트리거가 401/403. 미리 갱신(위 명령).
- **비용 알림**: billing → 예산 및 알림에서 월 $1 등 임계 알림을 걸어 과금 조기 감지.
- 실질 비용은 이 규모에서 거의 $0(Cloud Run 무료 한도 한참 아래, Scheduler 3잡 무료).
