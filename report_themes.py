# -*- coding: utf-8 -*-
"""공유 리포트 렌더러에서 사용하는 시각 테마."""

THEMES = {
    "mode1": {
        "tier_colors": {
            "S": "#e83f73", "A": "#f48aa0", "B": "#f7a98e", "C": "#f5c98a",
            "D": "#a9c7ef", "E": "#8fb4ea", "F": "#9d9ce6", "G": "#7466dc",
        },
        "css": """
  :root {
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
  }
""",
    },
    "mode2": {
        "tier_colors": {
            "S": "#e01919", "A": "#f0401f", "B": "#f07a1f", "C": "#d99a1f",
            "D": "#5a93e8", "E": "#3570d8", "F": "#2351c0", "G": "#1b3aa0",
        },
        "css": """
  :root {
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
  }
""",
    },
}


def get_theme(name: str) -> dict:
    try:
        return THEMES[name]
    except KeyError as exc:
        raise ValueError(f"알 수 없는 리포트 테마입니다: {name}") from exc
