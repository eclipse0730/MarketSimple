# Market Brief V1

한국 증시(KOSPI/KOSDAQ)의 **시장 강도·자금 흐름·강한 테마**를 10~30초 안에 파악하기 위한 경량 리포트 생성기.
종목 발굴이 아니라 **시장 전체 분위기 파악**이 목적입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python main.py                    # 기본: 네이버 금융, 로그인 불필요
python main.py --session morning  # 오전장 리포트 (12:00경 실행 → 장중 값)
python main.py --session close     # 마감장 리포트 (15:40~16:00 실행 → 마감 값)
python main.py --date 20260529    # 특정 날짜 리포트
python main.py --source fdr       # 기존 FinanceDataReader 방식으로 실행
python main.py --force            # 기존 CSV가 있어도 재수집
python main.py --mode classic     # 기존 HTML 디자인
python main.py --mode mode1       # 개선된 HTML 디자인 (기본)
python main.py --mode mode2       # 대안 HTML 디자인
python main.py --mode mode3       # 전문가용 다크 테마 HTML 디자인
python main.py --mode mode4       # 모바일 개선형 티어표 디자인
```

세션을 안 주면 실행 시각 기준으로 자동 판별합니다(14시 이전=morning).
기준 날짜/세션의 CSV가 이미 있으면 재수집하지 않고 `output/data/`의 기존 CSV를 사용합니다.
데이터를 다시 받아오려면 `--force`를 지정합니다.
결과물은 `output/` 아래 용도별 폴더에 생성됩니다.

* `output/data/market_YYYYMMDD_SESSION.csv` — 수집한 전 종목 원본 데이터
* `output/report/한국증시 DailyTier [YYYYMMDD]_MODE.html` — 선택한 디자인 모드의 리포트 (브라우저로 열기)
* `output/theme/theme_map_YYYYMMDD.csv` — 수동 테마와 FDR 업종을 합친 최종 테마 매핑

## 데이터 소스

기본 데이터 소스는 네이버 금융입니다. 로그인은 필요 없습니다.

> **네이버 현재 스냅샷 특성**: 오늘 날짜이거나 날짜를 지정하지 않으면 네이버 금융의 현재 시장 페이지를 조회합니다.
> 그래서 12:00에 돌리면 장중 값, 마감 후 돌리면 네이버에 반영된 종가 기준 값이 됩니다.
> 과거 날짜를 `--date 20260529`처럼 지정하면 네이버 일봉 API를 종목별로 조회하므로 현재 스냅샷보다 시간이 오래 걸립니다.

기존 FDR 방식은 `--source fdr`로 실행할 수 있습니다.

## 리포트 구성

1. 시장 요약 (전체 종목 수, 상승/하락/보합 비율)
2. 시장별 요약 (KOSPI / KOSDAQ)
3. 티어표 (S~G, 등락률 기준 정렬)
4. 강한 테마/업종 TOP 10
5. 약한 테마/업종 TOP 10

## 테마 분석

테마 분석은 두 종류의 매핑을 합쳐 계산합니다.

* `theme_map.csv`: 반도체, 2차전지, 방산처럼 직접 관리하는 핵심 테마
* FDR 업종 캐시: 전 종목의 `Industry` 값을 자동 테마로 사용

같은 종목이 수동 테마와 업종 테마에 동시에 포함될 수 있습니다. 예를 들어 삼성전자는 `반도체` 수동 테마와 `반도체 제조업` 업종 테마에 함께 반영됩니다.
업종 정보가 비어 있는 종목은 `미분류`로 보완해 전 종목이 최소 하나의 테마에 포함되게 합니다.

## 파일 구조

```
main.py          실행 진입점 (수집 → 분석 → 리포트)
config.py        티어 기준·설정 (보통 여기만 고치면 됩니다)
collector.py     데이터 수집 (fdr)
collector_naver.py 네이버 금융 데이터 수집
analyzer.py      시장 강도·티어표·테마 분석
report.py        기존 CSV·HTML 리포트 생성
report_mode1.py  개선된 디자인의 CSV·HTML 리포트 생성
report_mode2.py  대안 디자인의 CSV·HTML 리포트 생성
report_mode3.py  전문가용 다크 테마 CSV·HTML 리포트 생성
report_mode4.py  모바일 개선형 티어표 CSV·HTML 리포트 생성
theme_map.csv    테마 매핑 (종목코드,종목명,테마) — 자유롭게 추가/수정
```

## 자동 실행 (매일 12:00 / 15:40)

cron 예시 (Linux/Mac):

```
0 12 * * 1-5  cd /경로/market_brief && python main.py --session morning
40 15 * * 1-5 cd /경로/market_brief && python main.py --session close
```

## 참고 / 주의

* `theme_map.csv`는 핵심 테마를 보강하는 용도입니다.
* 네이버 수집기는 업종 테마 일괄 데이터를 제공하지 않으므로 수동 테마가 없는 종목은 `미분류`로 보완됩니다.
* `--source fdr` 실행 시에는 FDR 업종 캐시를 자동 테마로 함께 사용합니다.
* 시장 관습대로 **상승은 빨강, 하락은 파랑**으로 표기합니다.
* 데이터베이스 없이 CSV 기반으로만 동작하며, 단일 명령으로 실행됩니다.
