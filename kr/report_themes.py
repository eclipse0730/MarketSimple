# -*- coding: utf-8 -*-
"""공유 리포트 렌더러의 시각 테마.

각 테마는 CSS 변수 묶음(vars)으로만 정의된다. 페이지에는 모든 테마가
`html[data-theme="modeX"]` 선택자로 함께 심기고, 기본 테마는 `:root` 에도
한 번 더 깔려 폴백이 된다. 마스코트(카멜레온) 클릭이나 localStorage 에
저장된 값으로 <html data-theme> 만 바꾸면 리빌드 없이 즉시 전환된다.

새 테마 추가법:
  1) THEMES 에 {"label": 한글이름, "vars": "변수선언…"} 항목 추가
  2) THEME_ORDER 에 모드 id 를 넣어 순환 위치 지정
  3) (선택) characters.json 의 테마 캐릭터 themes 목록에 {id,label} 추가
"""

THEMES = {
    "mode1": {
        "label": "파스텔",
        "vars": """
    --up:#e8688a; --up-soft:#fbe4ea; --up-mid:#f7c9d6;
    --down:#7fa8e0; --down-soft:#e6eefb; --down-mid:#cbddf6;
    --flat:#b8a9c9; --flat-soft:#f0eaf5;
    --bg:#fdf7f4; --bg2:#fbf1ee; --panel:#ffffff; --panel2:#fffafa;
    --ink:#5a4a52; --sub:#9b8a92; --faint:#c4b4bc;
    --line:#f3e6e6; --line2:#ecd9dc;
    --accent:#d98aa8; --accent-soft:#f8e6ee;
    --heading:#6b5560; --strong:#4f4148;
    --chip-text:#6b5560; --chip-name:#5f4e56;
    --chip-base:#ffffff; --chip-rate-base:#6b5560;
    --body-bg:
      radial-gradient(800px 500px at 82% -6%, #fce4ee, transparent 60%),
      radial-gradient(700px 600px at -5% 100%, #e6eefb, transparent 55%),
      radial-gradient(600px 400px at 50% 50%, #fdf0f5, transparent 70%),
      var(--bg);
    --section-shadow:0 8px 30px rgba(216,138,168,.07), 0 2px 8px rgba(216,138,168,.04);
    --tier-S-1:#ff719c; --tier-S-2:#e83f73; --tier-S-text:#fff;
    --tier-A-1:#f8a6bb; --tier-A-2:#f48aa0; --tier-A-text:#fff;
    --tier-B-1:#fbc0a8; --tier-B-2:#f7a98e; --tier-B-text:#fff;
    --tier-C-1:#fadca6; --tier-C-2:#f5c98a; --tier-C-text:#8a6a3a;
    --tier-D-1:#c3d9f5; --tier-D-2:#a9c7ef; --tier-D-text:#4a6a98;
    --tier-E-1:#a9c6f0; --tier-E-2:#8fb4ea; --tier-E-text:#fff;
    --tier-F-1:#b3b1ee; --tier-F-2:#9d9ce6; --tier-F-text:#fff;
    --tier-G-1:#9288ef; --tier-G-2:#7466dc; --tier-G-text:#fff;
    --round:"Quicksand","Nunito",sans-serif;
    --serif:"Gowun Batang",serif;
    --sans:"Nunito","Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  """,
    },
    "mode2": {
        "label": "다크",
        "vars": """
    --up:#ff4d4f; --up-soft:#2d1518; --up-mid:#5c2428;
    --down:#4c8dff; --down-soft:#111d34; --down-mid:#20365f;
    --flat:#8992a3; --flat-soft:#222936;
    --bg:#0b0f14; --bg2:#111821; --panel:#101721; --panel2:#151e2b;
    --ink:#e6edf5; --sub:#9aa8bc; --faint:#637083;
    --line:#263344; --line2:#334255;
    --accent:#f0b35a; --accent-soft:#241c12;
    --heading:#f4f7fb; --strong:#ffffff;
    --chip-text:#dbe5f2; --chip-name:#f2f6fb;
    --chip-base:#101721; --chip-rate-base:#dbe5f2;
    --body-bg:
      radial-gradient(900px 600px at 78% -8%, rgba(240,179,90,.15), transparent 60%),
      radial-gradient(800px 560px at -10% 100%, rgba(76,141,255,.16), transparent 55%),
      var(--bg);
    --section-shadow:0 12px 34px rgba(0,0,0,.28);
    --tier-S-1:#ff6868; --tier-S-2:#e01919; --tier-S-text:#fff;
    --tier-A-1:#ff7a50; --tier-A-2:#f0401f; --tier-A-text:#fff;
    --tier-B-1:#ffad4a; --tier-B-2:#f07a1f; --tier-B-text:#111821;
    --tier-C-1:#f0c15a; --tier-C-2:#d99a1f; --tier-C-text:#111821;
    --tier-D-1:#78aef5; --tier-D-2:#5a93e8; --tier-D-text:#07111f;
    --tier-E-1:#5d8df0; --tier-E-2:#3570d8; --tier-E-text:#fff;
    --tier-F-1:#476ad8; --tier-F-2:#2351c0; --tier-F-text:#fff;
    --tier-G-1:#354fad; --tier-G-2:#1b3aa0; --tier-G-text:#fff;
    --round:"Quicksand","Nunito",sans-serif;
    --serif:"Gowun Batang",serif;
    --sans:"Nunito","Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  """,
    },
    # 전문가 모드 — 중립 고대비 라이트. 장식 최소화, 헤딩까지 산세리프로 통일해
    # 데이터 가독성에 집중. (Inter 미로드 시 Pretendard/시스템 산세리프로 폴백)
    "mode3": {
        "label": "전문가",
        "vars": """
    --up:#d92d20; --up-soft:#fef3f2; --up-mid:#fcd2cd;
    --down:#1d4ed8; --down-soft:#eff4ff; --down-mid:#cdddfb;
    --flat:#667085; --flat-soft:#f2f4f7;
    --bg:#f4f6f8; --bg2:#eceff3; --panel:#ffffff; --panel2:#fafbfc;
    --ink:#1d2433; --sub:#5b6472; --faint:#98a2b3;
    --line:#e3e7ec; --line2:#d3d9e0;
    --accent:#0f62fe; --accent-soft:#eaf1ff;
    --heading:#101828; --strong:#0b1220;
    --chip-text:#344054; --chip-name:#1d2433;
    --chip-base:#ffffff; --chip-rate-base:#344054;
    --body-bg:
      radial-gradient(900px 480px at 82% -10%, rgba(15,98,254,.05), transparent 60%),
      linear-gradient(180deg,#f7f9fb,var(--bg));
    --section-shadow:0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10);
    --tier-S-1:#f97066; --tier-S-2:#d92d20; --tier-S-text:#fff;
    --tier-A-1:#fd8a64; --tier-A-2:#ef5a3a; --tier-A-text:#fff;
    --tier-B-1:#fcb44d; --tier-B-2:#f79009; --tier-B-text:#3a2400;
    --tier-C-1:#f3cf5a; --tier-C-2:#dca40a; --tier-C-text:#3a2e00;
    --tier-D-1:#8fb4f5; --tier-D-2:#5a8dee; --tier-D-text:#0a1c44;
    --tier-E-1:#5e8cf0; --tier-E-2:#2f6fed; --tier-E-text:#fff;
    --tier-F-1:#4a6fe0; --tier-F-2:#1d4ed8; --tier-F-text:#fff;
    --tier-G-1:#3550c0; --tier-G-2:#1530a8; --tier-G-text:#fff;
    --round:"Inter","Pretendard","Apple SD Gothic Neo",ui-sans-serif,sans-serif;
    --serif:"Inter","Pretendard","Apple SD Gothic Neo",sans-serif;
    --sans:"Inter","Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  """,
    },
    # 세피아 — 따뜻한 종이/신문 톤. 헤딩 명조(Gowun Batang) 유지로 클래식한 분위기.
    "mode4": {
        "label": "세피아",
        "vars": """
    --up:#b3402b; --up-soft:#f7ece4; --up-mid:#eccdbb;
    --down:#3f6b8c; --down-soft:#e9eef2; --down-mid:#c6d6e2;
    --flat:#8a7d6b; --flat-soft:#efe7d8;
    --bg:#f3ead8; --bg2:#ece0c9; --panel:#fbf5e9; --panel2:#f6eede;
    --ink:#3b3228; --sub:#7a6f5d; --faint:#a99e88;
    --line:#e4d7bf; --line2:#d8c8a9;
    --accent:#9a6a3a; --accent-soft:#efe2cb;
    --heading:#2c241a; --strong:#1f1810;
    --chip-text:#4a4030; --chip-name:#352c20;
    --chip-base:#fbf5e9; --chip-rate-base:#4a4030;
    --body-bg:
      radial-gradient(800px 500px at 80% -8%, rgba(154,106,58,.10), transparent 60%),
      radial-gradient(700px 600px at -5% 100%, rgba(63,107,140,.08), transparent 55%),
      var(--bg);
    --section-shadow:0 8px 24px rgba(90,66,30,.08), 0 2px 6px rgba(90,66,30,.05);
    --tier-S-1:#cf6a4a; --tier-S-2:#b3402b; --tier-S-text:#fff;
    --tier-A-1:#d98a5a; --tier-A-2:#bf6a34; --tier-A-text:#fff;
    --tier-B-1:#dba85c; --tier-B-2:#c08a3a; --tier-B-text:#3a2a12;
    --tier-C-1:#d8c074; --tier-C-2:#b89a48; --tier-C-text:#352a10;
    --tier-D-1:#85a6bf; --tier-D-2:#5a829e; --tier-D-text:#fff;
    --tier-E-1:#6a90ad; --tier-E-2:#436b8c; --tier-E-text:#fff;
    --tier-F-1:#4f7390; --tier-F-2:#34566f; --tier-F-text:#fff;
    --tier-G-1:#3d5b73; --tier-G-2:#284156; --tier-G-text:#fff;
    --round:"Quicksand","Nunito",sans-serif;
    --serif:"Gowun Batang",serif;
    --sans:"Nunito","Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  """,
    },
}

# 카멜레온 순환 순서 & 기본 테마(생성 시 <html data-theme> 초기값)
THEME_ORDER = ["mode1", "mode2", "mode3", "mode4"]
DEFAULT_THEME = "mode1"


def get_theme(name: str) -> dict:
    try:
        return THEMES[name]
    except KeyError as exc:
        raise ValueError(f"알 수 없는 리포트 테마입니다: {name}") from exc


def theme_ids() -> list:
    """순환 순서대로의 테마 id 목록."""
    return list(THEME_ORDER)


def theme_labels() -> list:
    """캐릭터/스위처용 [{id, label}, …] (순환 순서)."""
    return [{"id": m, "label": THEMES[m]["label"]} for m in THEME_ORDER]


def all_themes_css(default: str = DEFAULT_THEME) -> str:
    """모든 테마 CSS 를 한 번에 출력.

    - `:root { … }` 에 기본 테마를 깔아 data-theme 미지정/오타 시 폴백.
    - `html[data-theme="modeX"] { … }` 각 테마. 매칭되는 하나만 적용된다.
    """
    if default not in THEMES:
        default = DEFAULT_THEME
    blocks = [f":root {{{THEMES[default]['vars']}}}"]
    for mode in THEME_ORDER:
        blocks.append(f'html[data-theme="{mode}"] {{{THEMES[mode]["vars"]}}}')
    return "\n".join(blocks)
