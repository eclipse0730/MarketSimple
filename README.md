# Market Brief V1

한국 증시(KOSPI/KOSDAQ)의 **시장 강도·자금 흐름·강한 테마**를 10~30초 안에 파악하기 위한 경량 리포트 생성기.
종목 발굴이 아니라 **시장 전체 분위기 파악**이 목적입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python main.py                    # 기본: KR, 네이버 금융, 로그인 불필요
python main.py --market kr        # 한국 시장 명시 실행
python main.py --date 20260529    # 특정 날짜 리포트
python main.py --force            # 같은 날짜 CSV/리포트를 현재 스냅샷으로 갱신
python main.py --mode classic     # 기존 HTML 디자인
python main.py --mode mode1       # 공유 레이아웃 + 소프트 테마 (기본)
python main.py --mode mode2       # 공유 레이아웃 + 다크 테마
```

기준 날짜의 CSV가 이미 있으면 재수집하지 않고 `output/kr/data/`의 기존 CSV를 사용합니다.
현재 스냅샷으로 같은 날짜 파일을 갱신하려면 `--force`를 지정합니다.
결과물은 `output/` 아래 용도별 폴더에 생성됩니다.

* `output/kr/data/market_YYYYMMDD.csv` — 수집한 전 종목 원본 데이터
* `output/kr/report/한국증시 DailyTier [YYYYMMDD]_MODE.html` — 선택한 디자인 모드의 리포트 (브라우저로 열기)
* `output/kr/theme/theme_map_YYYYMMDD.csv` — 수동 테마와 미분류 보완을 합친 최종 테마 매핑

## 데이터 소스

기본 데이터 소스는 네이버 금융입니다. 로그인은 필요 없습니다.

> **네이버 현재 스냅샷 특성**: 오늘 날짜이거나 날짜를 지정하지 않으면 네이버 금융의 현재 시장 페이지를 조회합니다.
> 그래서 12:00에 돌리면 장중 값, 마감 후 돌리면 네이버에 반영된 종가 기준 값이 됩니다.
> 과거 날짜를 `--date 20260529`처럼 지정하면 네이버 일봉 API를 종목별로 조회하므로 현재 스냅샷보다 시간이 오래 걸립니다.

## 리포트 구성

1. 시장 요약 (전체 종목 수, 상승/하락/보합 비율)
2. 시장별 요약 (KOSPI / KOSDAQ)
3. 티어표 (S~G, 등락률 기준 정렬)
4. 강한 테마/업종 TOP 10
5. 약한 테마/업종 TOP 10

## 테마 분석

테마 분석은 수동 매핑을 기준으로 계산합니다.

* `kr/theme_map.csv`: 반도체, 2차전지, 방산처럼 직접 관리하는 핵심 테마
* 수동 테마가 없는 종목은 `미분류`로 자동 보완

수동 테마가 없는 종목은 `미분류`로 보완해 전 종목이 최소 하나의 테마에 포함되게 합니다.

## 파일 구조

```
main.py              시장 선택 진입점 (기본 kr)
kr/                  한국 시장 구현
  main.py            KR 실행 로직 (수집 → 분석 → 리포트)
  config.py          KR 티어 기준·설정
  collector.py       네이버 금융 데이터 수집
  analyzer.py        시장 강도·티어표·테마 분석
  report.py          기존 CSV·HTML 리포트 생성
  report_shared.py   고정 리포트 구조·데이터 노출 로직
  report_themes.py   mode1/mode2 시각 테마 정의
  report_mode1.py    mode1 테마 래퍼
  report_mode2.py    mode2 테마 래퍼
  theme_map.csv      KR 테마 매핑
us/                  미국 시장 구현 예정
```

## 자동 실행 (매일 12:00 / 15:40)

cron 예시 (Linux/Mac):

```
0 12 * * 1-5  cd /경로/market_brief && python main.py --force
40 15 * * 1-5 cd /경로/market_brief && python main.py --force
```

## 참고 / 주의

* `kr/theme_map.csv`는 핵심 테마를 보강하는 용도입니다.
* 네이버 수집기는 업종 테마 일괄 데이터를 제공하지 않으므로 수동 테마가 없는 종목은 `미분류`로 보완됩니다.
* 시장 관습대로 **상승은 빨강, 하락은 파랑**으로 표기합니다.
* 데이터베이스 없이 CSV 기반으로만 동작하며, 단일 명령으로 실행됩니다.
