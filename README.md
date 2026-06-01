# Market Brief V1

한국 증시(KOSPI/KOSDAQ)의 **시장 강도·자금 흐름·강한 테마**를 10~30초 안에 파악하기 위한 경량 리포트 생성기.
종목 발굴이 아니라 **시장 전체 분위기 파악**이 목적입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python main.py                    # 기본: FinanceDataReader(fdr), 로그인 불필요
python main.py --session morning  # 오전장 리포트 (12:00경 실행 → 장중 값)
python main.py --session close     # 마감장 리포트 (15:40~16:00 실행 → 마감 값)
python main.py --date 20260529    # 특정 날짜 리포트 (기본: fdr)
```

세션을 안 주면 실행 시각 기준으로 자동 판별합니다(14시 이전=morning).
결과물은 `output/` 폴더에 생성됩니다.

* `report_YYYYMMDD_SESSION.html` — 리포트 (브라우저로 열기)
* `market_YYYYMMDD_SESSION.csv` — 수집한 전 종목 원본 데이터
* `theme_map_YYYYMMDD.csv` — 수동 테마와 FDR 업종을 합친 최종 테마 매핑

## 데이터 소스

FinanceDataReader(FDR)를 사용합니다. 로그인은 필요 없습니다.

> **fdr 의 현재 스냅샷 특성**: 날짜를 지정하지 않으면 `fdr`은 "지금" 값을 가져옵니다.
> 그래서 12:00에 돌리면 오전장 값, 마감 후 돌리면 종가가 됩니다 — 즉 *실행 시각이 곧 세션*입니다.
> 특정 날짜를 `--date 20260529`처럼 지정하면 `fdr`의 KRX 날짜별 캐시 데이터를 조회합니다.

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
analyzer.py      시장 강도·티어표·테마 분석
report.py        CSV·HTML 생성
theme_map.csv    테마 매핑 (종목코드,종목명,테마) — 자유롭게 추가/수정
```

## 자동 실행 (매일 12:00 / 15:40)

cron 예시 (Linux/Mac):

```
0 12 * * 1-5  cd /경로/market_brief && python main.py --session morning
40 15 * * 1-5 cd /경로/market_brief && python main.py --session close
```

## 참고 / 주의

* `theme_map.csv`는 핵심 테마를 보강하는 용도입니다. 전 종목 업종 테마는 FDR에서 자동으로 가져옵니다.
* 시장 관습대로 **상승은 빨강, 하락은 파랑**으로 표기합니다.
* 데이터베이스 없이 CSV 기반으로만 동작하며, 단일 명령으로 실행됩니다.
