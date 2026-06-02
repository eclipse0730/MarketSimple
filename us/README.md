# US Market Brief

미국 시장 EOD 리포트 구현입니다.

Polygon API key가 필요합니다.

```bash
export POLYGON_API_KEY=...
python main.py --market us --date 20260529
```

날짜를 생략하면 최근 사용 가능한 미국장 EOD 날짜를 찾습니다.

구조:

```text
collector.py
analyzer.py
config.py
report_*.py
theme_map.csv
```
