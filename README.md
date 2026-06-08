# Market Brief V1

한국 증시(KOSPI/KOSDAQ)의 **시장 강도·자금 흐름·강한 테마**를 10~30초 안에 파악하기 위한 경량 리포트 생성기.
종목 발굴이 아니라 **시장 전체 분위기 파악**이 목적입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

`main.py`는 `--market`(kr/us, 기본 kr)으로 시장을 고른 뒤 나머지 인자를 각 시장 구현으로 넘깁니다.

```bash
python main.py                              # 기본: KR, 네이버 금융, 로그인 불필요
python main.py --market kr                  # 한국 시장 명시 실행
python main.py --date 20260529              # 특정 날짜 리포트
python main.py --force                      # 같은 날짜 CSV/리포트를 현재 스냅샷으로 갱신
python main.py --collector                  # CSV 수집/저장까지만 실행(리포트 생략)
python main.py --refresh-sector             # 섹터(업종) 매핑을 네이버에서 재수집해 sector_map.csv 갱신
python main.py --market us --date 20260529  # 미국 시장 EOD 리포트
```

공통 플래그(`--date`, `--force`, `--collector`)는 KR/US 모두 동작합니다.
`--refresh-sector`는 KR 전용, `--mode {classic,mode1,mode2}`는 US 전용입니다(KR 리포트는 단일 레이아웃).

기준 날짜의 CSV가 이미 있으면 재수집하지 않고 `output/kr/data/`의 기존 CSV를 사용합니다.
현재 스냅샷으로 같은 날짜 파일을 갱신하려면 `--force`를 지정합니다.
결과물은 `output/` 아래 용도별 폴더에 생성됩니다.

* `output/kr/data/market_YYYYMMDD.csv` — 수집한 전 종목 원본 데이터
* `output/kr/report/한국증시 DailyTier [YYYYMMDD].html` — 리포트 (브라우저로 열기)
* `output/kr/theme/theme_map_YYYYMMDD.csv` — 수동 테마와 미분류 보완을 합친 최종 테마 매핑

## 데이터 소스

KR 기본 데이터 소스는 네이버 금융입니다. 로그인은 필요 없습니다.

> **네이버 현재 스냅샷 특성**: 오늘 날짜이거나 날짜를 지정하지 않으면 네이버 금융의 현재 시장 페이지를 조회합니다.
> 그래서 12:00에 돌리면 장중 값, 마감 후 돌리면 네이버에 반영된 종가 기준 값이 됩니다.
> 과거 날짜를 `--date 20260529`처럼 지정하면 네이버 일봉 API를 종목별로 조회하므로 현재 스냅샷보다 시간이 오래 걸립니다.

US 데이터 소스는 Polygon grouped daily입니다. 실행 전에 API key를 환경변수로 지정해야 합니다.

```bash
export POLYGON_API_KEY=...
python main.py --market us --date 20260529
```

날짜를 생략하면 최근 사용 가능한 미국장 EOD 날짜를 역순으로 찾습니다.

## 리포트 구성

1. 시장 요약 (전체 종목 수, 상승/하락/보합 비율)
2. 종목 Tier표 (S~G, 등락률 기준 정렬)
3. 거래대금 / 거래량 급증 Top30
4. 섹터 Tier (시장 대비 초과수익 %p 기준)
5. 대테마 히트맵 (섹터를 17개 대분류로 묶은 전수 분류)
6. 강한 / 약한 테마 분석

## 분류 체계 (테마 · 섹터 · 대테마)

종목 분류는 세 층으로 나뉘며, 각각 별도의 매핑 파일로 관리합니다.

* `kr/theme_map.csv` — 반도체·2차전지·방산처럼 직접 관리하는 **핵심 테마**(수기, 한 종목이 여러 테마 중복 가능)
* `kr/sector_map.csv` — 네이버 업종을 자동 수집한 **섹터** 캐시(한 종목 1섹터, `--refresh-sector`로 갱신)
* `kr/big_theme_map.csv` — 섹터를 17개로 묶은 **대테마** 전수 분류

수동 테마가 없는 종목은 `미분류`로 보완해 전 종목이 최소 하나의 테마에 포함되게 합니다.

## 파일 구조

```
main.py              시장 선택 진입점 (--market kr/us, 기본 kr)
kr/                  한국 시장 구현
  main.py            KR 실행 로직 (수집 → 분석 → 리포트)
  config.py          KR 티어 기준·설정
  collector.py       네이버 금융 데이터 수집
  analyzer.py        시장 강도·티어표·테마/섹터 분석
  report_shared.py   리포트 구조·HTML/CSS·데이터 노출 로직
  report_themes.py   data-theme 별 색 팔레트(파스텔/다크/전문가/세피아)
  import_krx_csv.py  KRX 수동 다운로드 CSV → market_*.csv 변환(과거 데이터 적재)
  theme_map.csv      핵심 테마 매핑(수기)
  sector_map.csv     섹터(업종) 매핑 캐시(자동 수집)
  big_theme_map.csv  대테마(17개 대분류) 매핑
us/                  미국 시장 구현
  main.py            US 실행 로직 (--mode classic/mode1/mode2)
  collector.py       Polygon EOD 데이터 수집
  config.py          US 티어 기준·설정
  analyzer.py        US 시장 분석
  report_shared.py   US 리포트 공용 구조
  report_themes.py   US 시각 테마 정의
  report.py          classic HTML 리포트
  report_mode1.py    mode1 테마 래퍼
  report_mode2.py    mode2 테마 래퍼
scripts/             보조 스크립트
  publish_pages.py   리포트·마스코트·이미지를 docs/ 로 발행(GitHub Pages)
  make_summary_images.py  카톡 공유용 요약 이미지 3장 생성
  serve_local.py     로컬 미리보기 서버
mascot/              마스코트 위젯 (재빌드 불필요, 두 파일만 고치면 갱신)
  mascots.js         동작·렌더러
  mascots.css        스타일
  characters.json    캐릭터·대사·말풍선 설정
```

## 자동 실행 (GitHub Actions)

`.github/workflows/update.yml`이 한국 장중(평일 09:07~15:37 KST) **30분마다** 자동으로
수집·빌드·발행·커밋합니다. 워크플로는 매 실행마다 아래를 수행합니다.

```bash
python main.py --market kr --force          # 오늘(KST) 스냅샷 수집 + 리포트 빌드
python scripts/publish_pages.py --intraday  # 최신 날짜만 갱신(장중 경량 발행)
```

`Actions` 탭에서 수동 실행(`workflow_dispatch`)도 가능합니다.

### 맥북 launchd 백업 트리거 (cron 드롭 보완)

GitHub Actions의 `schedule`(cron)은 best-effort라 혼잡 시간대에 자주 지연·드롭됩니다.
그래서 맥북 launchd 가 평일 **09:07~15:37 30분 간격(KST)** 으로 `update.yml` 을
`workflow_dispatch` 로 직접 트리거하는 백업을 둡니다.

```
[맥북 launchd] ──(정시에 신호만 발사)──▶ [GitHub Actions] ──▶ 수집·빌드·발행·커밋
   알람 역할(curl 한 번)                      실제 작업은 전부 클라우드에서 실행
```

맥북은 "지금 돌려라" 신호만 보내고, 무거운 작업은 모두 GitHub 클라우드에서 돕니다.
GitHub cron 도 그대로 두며(워크플로 `concurrency: cancel-in-progress` 라 겹쳐도 중복 실행 없음),
맥북이 꺼져 있을 때의 백업이 됩니다.

**구성 파일 (저장소 밖, 맥북 로컬)**

| 항목 | 경로 |
| --- | --- |
| 트리거 스크립트 | `~/.marketsimple/dispatch.sh` |
| launchd 정의 | `~/Library/LaunchAgents/com.marketsimple.dispatch.plist` |
| 실행 로그 | `~/.marketsimple/dispatch.log` |

`dispatch.sh` 는 PAT 를 1) macOS 키체인(`marketsimple-gh-pat`), 2) 프로젝트 `.env` 의
`GH_DISPATCH_TOKEN` 순으로 읽어 GitHub API 를 호출합니다. PAT 는 fine-grained 토큰으로
대상 저장소에 **Actions: Read and write** 권한이 필요합니다. (`.env` 는 `.gitignore` 에 있어 커밋되지 않음)

**관리 명령 (터미널)**

```bash
launchctl load   ~/Library/LaunchAgents/com.marketsimple.dispatch.plist   # 켜기
launchctl unload ~/Library/LaunchAgents/com.marketsimple.dispatch.plist   # 끄기
launchctl list | grep marketsimple                                        # 동작 확인(한 줄 = ON)
~/.marketsimple/dispatch.sh && tail -1 ~/.marketsimple/dispatch.log       # 즉시 1회 실행 테스트
```

launchd 정의는 운영체제 스케줄러라 재부팅·로그아웃에도 유지됩니다. 단, **맥북이 깨어 있을 때만**
트리거되며 잠자기로 놓친 작업은 깨어난 직후 1회만 보충됩니다. 토큰이 만료되면 `.env` 의
`GH_DISPATCH_TOKEN` 값만 갱신하면 됩니다.

## 요약 이미지 + 텔레그램 발송

리포트에서 공유용 요약 이미지 3장(1080px)을 만듭니다.

```bash
python -m scripts.make_summary_images            # 최신 빌드 리포트
python -m scripts.make_summary_images 20260605   # 특정 날짜
```

* `summary-1` 시장 요약 + 거래대금/거래량 Top30
* `summary-2` 종목 Tier
* `summary-3` 섹터 Tier
* 출력: `output/kr/summary/<날짜>/` (헤드리스 Chrome 필요, `CHROME_PATH`로 경로 지정 가능)

`.github/workflows/summary-telegram.yml`이 평일 **12:33 / 15:33 KST**에 위 이미지를
만들어 텔레그램으로 보냅니다. 발송에는 아래 두 Secret이 필요합니다.

* `TELEGRAM_BOT_TOKEN` — @BotFather 로 만든 봇 토큰
* `TELEGRAM_CHAT_ID` — 받을 채팅 ID

## GitHub Pages 게시

리포트·마스코트·이미지를 `docs/`로 복사해 GitHub Pages에서 볼 수 있게 발행합니다.

```bash
python scripts/publish_pages.py              # 전체 발행(모든 날짜 + 썸네일 생성)
python scripts/publish_pages.py --intraday   # 최신 날짜만(장중용, 빠름)
python scripts/publish_pages.py --skip-thumb # 썸네일 생성 생략
```

GitHub 저장소 설정:

* `Settings > Pages`
* Source: `Deploy from a branch`
* Branch: `main`
* Folder: `/docs`

게시 후 주소:

```text
https://marketbrief.kr/            (커스텀 도메인, 가비아)
```

배포 구조·URL 동작 원리·도메인 연결·카톡 공유는 [DEPLOY.md](DEPLOY.md)에 정리되어 있습니다.

## 참고 / 주의

* `kr/theme_map.csv`는 핵심 테마를 보강하는 수기 매핑이며, 섹터는 `--refresh-sector`로 네이버에서 자동 수집합니다.
* 핵심 테마가 없는 종목은 `미분류`로 보완해 전 종목이 최소 하나의 테마에 포함됩니다.
* 시장 관습대로 **상승은 빨강, 하락은 파랑**으로 표기합니다.
* 데이터베이스 없이 CSV 기반으로만 동작하며, 단일 명령으로 실행됩니다.
* 과거 데이터는 네이버 일봉 API(`--date`)로도 적재할 수 있고, KRX 수동 다운로드 CSV는 `kr/import_krx_csv.py`로 변환합니다.
