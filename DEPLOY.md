# 배포 가이드 (marketbrief.kr)

리포트를 웹에 올리고 카톡으로 공유하기까지의 전체 구조와 절차를 정리한 문서입니다.

---

## 1. 한눈에 보는 구조

```
[로컬]  python main.py …            → output/kr/report/…html  (작업용, git 무시)
        python scripts/publish_pages.py → docs/…               (배포용, git 커밋)
          │
          └─ git push
                 │
            [GitHub] main 브랜치 /docs 폴더
                 │
            [GitHub Pages] 정적 호스팅
                 │
            [가비아 DNS] marketbrief.kr → GitHub Pages IP
                 │
            https://marketbrief.kr/
```

- **output/** = 로컬 작업물 (`.gitignore`로 git에서 제외)
- **docs/** = 실제 배포되는 정적 사이트 (git에 커밋됨, GitHub Pages가 이 폴더를 서빙)

---

## 2. URL은 어떻게 정해지나 — "경로 = docs 폴더 구조"

GitHub Pages는 **정적 파일 서버**입니다. 동적 서버가 없으므로
**URL 경로는 곧 `docs/` 안의 실제 파일/폴더 구조**입니다. 존재하는 파일만 열리고, 없으면 404입니다.

| URL | 실제 파일 | 결과 |
|-----|-----------|------|
| `marketbrief.kr/` | `docs/index.html` | ✅ `/kr/`로 리다이렉트 |
| `marketbrief.kr/kr/` | `docs/kr/index.html` | ✅ 최신 날짜로 리다이렉트 |
| `marketbrief.kr/kr/20260603/` | `docs/kr/20260603/index.html` | ✅ 리포트 |
| `marketbrief.kr/kr/20260603/thumb.png` | `docs/kr/20260603/thumb.png` | ✅ 썸네일 |
| `marketbrief.kr/kr/99999999/` | (없음) | ❌ 404 |
| `marketbrief.kr/아무거나/` | (없음) | ❌ 404 |

### 자주 하는 오해
- **"URL 뒤에 아무 변수나 붙일 수 있나?"** → 아니요. `docs/`에 **만들어 push한 폴더만큼만** 열립니다.
  우리는 거래일 21일치 폴더를 만들었으니 그 날짜들만 열리고, 없는 날짜는 404입니다.
- **`?d=20260603` 같은 쿼리스트링(`?` 뒤)** → 정적 서버에선 무시됩니다.
  쿼리로 동적 분기를 하려면 백엔드(서버)가 필요합니다 — 계정/구독 단계에서 의미가 생깁니다.
- 끝의 슬래시(`/`)가 있으면 폴더의 `index.html`을 찾습니다. 그래서 날짜 URL은 `…/20260603/`처럼 끝에 `/`를 붙이는 게 안전합니다.

---

## 3. 매일 배포하는 법

```bash
# 1) 리포트 생성 (OG 태그에 박을 도메인을 환경변수로)
export SITE_BASE_URL="https://marketbrief.kr"
python main.py --force                 # 오늘자 (네이버 스냅샷)

# 2) 정적 사이트로 발행 (docs/ 갱신, CNAME·썸네일 포함)
export CUSTOM_DOMAIN="marketbrief.kr"
python scripts/publish_pages.py

# 3) 커밋 & push
git add docs/ ; git commit -m "리포트 갱신 YYYYMMDD" ; git push
```

- `SITE_BASE_URL`이 있어야 OG(카톡 썸네일) 링크가 절대경로가 되어 썸네일이 뜹니다.
- **썸네일 PNG 노이즈 주의**: 헤드리스 Chrome 캡처는 매번 바이너리가 미세하게 달라
  내용이 같아도 git에 변경으로 잡힙니다. 의미 없는 썸네일 변경은
  `git checkout -- 'docs/kr/*/thumb.png'`로 되돌리고 커밋하세요.

### 과거 날짜 일괄 빌드
날짜 이동 화살표는 "직전/직후 날짜 리포트"로 연결되므로, 새 날짜를 추가하면
직전 날짜 리포트도 다시 빌드해야 "다음 ›" 링크가 새 날짜를 가리킵니다.
가용한 모든 `market_*.csv` 날짜를 순회해 빌드하면 안전합니다.

---

## 4. 도메인 연결 (이미 완료된 설정 기록)

- **도메인**: marketbrief.kr (가비아 구매, 루트 도메인)
- **가비아 DNS** — A 레코드 4개 (GitHub Pages 고정 IP):
  ```
  A  @  185.199.108.153
  A  @  185.199.109.153
  A  @  185.199.110.153
  A  @  185.199.111.153
  ```
  (선택) `CNAME  www  eclipse0730.github.io.` 로 www도 연결 가능
- **GitHub**: Settings → Pages → Custom domain = `marketbrief.kr`
- **docs/CNAME**: `marketbrief.kr` (publish가 자동 생성·보존)
- **HTTPS**: GitHub이 자동 발급(무료). 발급되면 Settings → Pages에서 **Enforce HTTPS** 체크.

도메인을 바꾸면: `SITE_BASE_URL`/`CUSTOM_DOMAIN`을 새 값으로 → 전체 재빌드 → 가비아 DNS 변경.

---

## 5. 카톡 공유

공유 URL:
```
https://marketbrief.kr/kr/20260603/
```
→ 제목 + 그날 요약 + 1200×630 썸네일 카드로 표시됩니다.

- **OG 태그·썸네일은 날짜별 페이지에만** 있습니다. 루트(`/`)와 `/kr/`는 리다이렉트라 OG가 없어
  썸네일이 안 뜹니다 → 카톡엔 **날짜가 포함된 URL**을 공유하세요.
  (`marketbrief.kr` 한 줄로도 썸네일이 뜨게 하려면 루트/kr에 최신 OG를 넣는 개선이 필요 — 미구현.)
- 카카오는 OG를 캐싱합니다. 한 번 못생기게 떴으면
  [카카오 OG 디버거](https://developers.kakao.com/tool/clear/og)에서 캐시를 초기화하세요.

---

## 6. 다음 단계 (계정 / 구독)

정적 사이트로는 불가능하고 백엔드가 필요합니다. 리포트는 정적으로 두고
**접근 게이트만 동적**으로 붙이는 게 현실적입니다.
- 호스팅 이전: Cloudflare Pages(+Functions) 또는 Vercel
- 인증: Supabase Auth / Clerk / Firebase Auth
- 결제: 토스페이먼츠(국내) / Stripe(해외)
