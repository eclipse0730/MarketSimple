/* MarketBrief 마스코트 — characters.json 으로 구동되는 범용 렌더러.
 *
 * 캐릭터/대사는 모두 characters.json 에 선언적으로 둔다(코드 수정·리빌드 불필요).
 * 리포트 페이지는 아래 전역만 심고 이 파일을 <script defer> 로 불러온다:
 *   window.__MB_MASCOT = { url:"/characters.json", base:"<SITE_BASE_URL>", key:"<WEB3FORMS_KEY>" }
 *
 * 캐릭터 타입:
 *   - notice  : 말풍선 공지(클릭마다 messages 순환)
 *   - feedback: 인사말 ↔ 피드백 폼 토글, Web3Forms 비동기 제출(키 없으면 미표시)
 */
(function () {
  "use strict";

  var CFG = window.__MB_MASCOT || {};
  var BASE = CFG.base || "";

  // "/..." 로 시작하는 경로에 배포 기준 URL(BASE)을 붙인다(서브경로 배포 대응).
  function asset(p) {
    return (BASE && p && p.charAt(0) === "/") ? BASE + p : p;
  }

  // ── 공통 런타임: 드래그 이동 + 눌림 효과 + 위치 기억 + 클릭 토글 ──
  function runtime(o) {
    var wrap = o.wrap, btn = o.btn, bubble = o.bubble || null;
    if (!wrap || !btn) return null;
    var moved = false, dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;

    function bubbleOpen() { return bubble && !bubble.hidden; }
    function showBubble(v) {
      if (!bubble) return;
      bubble.hidden = !v;
      btn.classList.toggle("is-active", !!v);
    }
    function press() {
      btn.classList.add("is-pressed");
      setTimeout(function () { btn.classList.remove("is-pressed"); }, 160);
    }

    btn.addEventListener("click", function () {
      if (moved) { moved = false; return; }   // 드래그였으면 클릭 무시
      press();
      if (o.onToggle) o.onToggle({ showBubble: showBubble, isOpen: bubbleOpen() });
    });

    // 위치 복원
    if (o.posKey) {
      try {
        var p = JSON.parse(localStorage.getItem(o.posKey) || "null");
        if (p) {
          wrap.style.left = p.x + "px"; wrap.style.top = p.y + "px";
          wrap.style.right = "auto"; wrap.style.bottom = "auto";
        }
      } catch (e) {}
    }

    btn.addEventListener("pointerdown", function (e) {
      dragging = true; moved = false; btn.setPointerCapture(e.pointerId);
      sx = e.clientX; sy = e.clientY;
      var r = wrap.getBoundingClientRect(); ox = r.left; oy = r.top;
      wrap.style.left = ox + "px"; wrap.style.top = oy + "px";
      wrap.style.right = "auto"; wrap.style.bottom = "auto";
    });
    btn.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      var nx = Math.max(8, Math.min(window.innerWidth - wrap.offsetWidth - 8, ox + dx));
      var ny = Math.max(8, Math.min(window.innerHeight - wrap.offsetHeight - 8, oy + dy));
      wrap.style.left = nx + "px"; wrap.style.top = ny + "px";
    });
    btn.addEventListener("pointerup", function (e) {
      dragging = false;
      try { btn.releasePointerCapture(e.pointerId); } catch (_) {}
      if (moved && o.posKey) {
        try {
          var r = wrap.getBoundingClientRect();
          localStorage.setItem(o.posKey, JSON.stringify({ x: r.left, y: r.top }));
        } catch (_) {}
      }
    });

    // 숨김(×) 버튼 — 이 세션 동안만 숨김(새로고침하면 복원)
    if (o.hideBtn) {
      o.hideBtn.addEventListener("click", function (e) {
        e.stopPropagation(); wrap.style.display = "none";
      });
    }

    return { showBubble: showBubble, isOpen: bubbleOpen };
  }

  // ── DOM 헬퍼 ──
  function el(tag, cls, attrs) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // 캐릭터 그림: 이미지 우선, 없으면 기본 말풍선 SVG.
  var FALLBACK_SVG =
    '<svg viewBox="0 0 24 24" aria-hidden="true" style="color:var(--accent)">' +
    '<path d="M4 5h16v11H7l-3 3z" fill="currentColor"/></svg>';
  // 이미지가 없을 때의 대체 그림. placeholder 문구가 있으면 임시 텍스트 카드,
  // 없으면 기본 말풍선 SVG. (테마에 맞춰 색이 바뀌도록 CSS 변수 사용)
  function fallbackFigure(c) {
    if (c && c.placeholder) {
      var card = el("div", "mascot-ph");
      card.style.cssText = [
        "width:100%", "min-height:64px", "box-sizing:border-box",
        "display:flex", "flex-direction:column", "align-items:center",
        "justify-content:center", "gap:1px", "padding:14px 8px",
        "border-radius:20px", "color:#fff",
        "background:linear-gradient(135deg,var(--accent),var(--up))",
        "font-family:var(--round,sans-serif)", "font-weight:800",
        "font-size:14px", "line-height:1.18", "text-align:center",
        "box-shadow:0 6px 14px rgba(0,0,0,.18)"
      ].join(";");
      String(c.placeholder).split("\n").forEach(function (line) {
        var s = el("span"); s.textContent = line; card.appendChild(s);
      });
      return card;
    }
    var span = el("span");
    span.innerHTML = FALLBACK_SVG;
    return span.firstChild;
  }
  function figure(c) {
    if (c.image) {
      var img = el("img", null, { src: asset(c.image), alt: c.ariaButton || c.id, draggable: "false" });
      // 이미지가 아직 없으면(404 등) placeholder/SVG 로 대체 — 나중에 파일만 넣으면 그대로 표시.
      img.addEventListener("error", function () {
        if (img.parentNode) img.parentNode.replaceChild(fallbackFigure(c), img);
      });
      return img;
    }
    return fallbackFigure(c);
  }

  function px(v) { return typeof v === "number" ? v + "px" : v; }

  // 공통 골격: wrap > [bubble] + btn + hide  → body 에 부착하고 참조 반환.
  function shell(c, bubble) {
    var right = c.position === "right";
    var wrap = el("div", "mascot-wrap" + (right ? " mascot-right" : ""));

    // 캐릭터 크기(버튼 폭). 미지정 시 CSS 기본값(데스크톱 108 / 모바일 84) 유지.
    if (c.size != null) wrap.style.setProperty("--mb-size", px(c.size));
    if (c.sizeMobile != null) wrap.style.setProperty("--mb-size-sm", px(c.sizeMobile));
    // 생성 위치(화면 모서리로부터의 간격). x 는 좌/우(position 따라), y 는 하단 기준.
    if (c.offset) {
      if (c.offset.x != null) wrap.style[right ? "right" : "left"] = px(c.offset.x);
      if (c.offset.y != null) wrap.style.bottom = px(c.offset.y);
    }

    if (bubble) wrap.appendChild(bubble);
    var btn = el("button", "mascot-btn", {
      type: "button", "aria-label": c.ariaButton || "마스코트", title: c.ariaButton || ""
    });
    btn.appendChild(figure(c));
    wrap.appendChild(btn);
    var hide = el("button", "mascot-hide", { type: "button", "aria-label": "마스코트 숨기기", title: "숨기기" });
    hide.innerHTML = "&times;";
    wrap.appendChild(hide);
    document.body.appendChild(wrap);
    return { wrap: wrap, btn: btn, hide: hide };
  }

  function closeBtn() {
    var x = el("button", "mascot-x", { type: "button", "aria-label": "닫기" });
    x.innerHTML = "&times;";
    return x;
  }

  // ── 타입: notice (공지 말풍선 + 문구 순환) ──
  function mountNotice(c) {
    var bubble = el("div", "mascot-bubble", { role: "status", hidden: "" });
    var x = closeBtn();
    var title = el("div", "mascot-bubble-title");
    var msg = el("div", "mascot-bubble-msg");
    bubble.appendChild(x); bubble.appendChild(title); bubble.appendChild(msg);

    var parts = shell(c, bubble);
    var msgs = Array.isArray(c.messages) ? c.messages : null;
    var idx = 0;

    function setText(t, m) {
      title.textContent = t || c.title || "안녕하세요!";
      msg.textContent = m || c.defaultMessage || "";
    }
    function render() {
      if (msgs && msgs.length) {
        var m = msgs[idx % msgs.length];
        setText(c.title, typeof m === "string" ? m : (m && m.message));
      } else {
        setText(c.title, c.message || c.defaultMessage);
      }
    }
    render();

    var dismissed = false;
    var api = runtime({
      wrap: parts.wrap, btn: parts.btn, bubble: bubble,
      posKey: "mb_" + c.id + "_pos", hideBtn: parts.hide,
      onToggle: function (ctx) {
        if (!ctx.isOpen) { render(); ctx.showBubble(true); }
        else if (msgs && msgs.length > 1) { idx++; render(); }
        else ctx.showBubble(false);
      }
    });
    x.addEventListener("click", function (e) {
      e.stopPropagation(); dismissed = true; if (api) api.showBubble(false);
    });
    if (api && c.autoOpen !== false && !dismissed) api.showBubble(true);
  }

  // ── 타입: feedback (인사 ↔ 폼 토글 + Web3Forms 제출) ──
  function mountFeedback(c) {
    if (!CFG.key) return;   // Web3Forms 키 없으면 미표시

    var bubble = el("div", "mascot-bubble fb-bubble", { role: "dialog", "aria-label": "피드백", hidden: "" });
    var x = closeBtn();

    var greet = el("div", "fb-greet");
    var gT = el("div", "mascot-bubble-title"); gT.textContent = c.greetTitle || "반가워요!";
    var gM = el("div", "mascot-bubble-msg"); gM.textContent = c.greetMsg || "";
    greet.appendChild(gT); greet.appendChild(gM);

    var form = el("form", null, { hidden: "" });
    var fT = el("div", "mascot-bubble-title"); fT.textContent = c.formTitle || "";
    var ta = el("textarea", null, { name: "message", rows: "3", required: "", placeholder: "여기에 내용을 적어주세요" });
    var send = el("button", "fb-send", { type: "submit" }); send.textContent = "보내기";
    var fmsg = el("p", "fb-msg", { hidden: "" });

    function hidden(name, val) { return el("input", null, { type: "hidden", name: name, value: val }); }
    form.appendChild(fT);
    form.appendChild(hidden("access_key", CFG.key));
    form.appendChild(hidden("subject", c.subject || "[MarketBrief] 피드백"));
    form.appendChild(hidden("from_name", c.fromName || "MarketBrief 방문자"));
    form.appendChild(ta); form.appendChild(send); form.appendChild(fmsg);

    bubble.appendChild(x); bubble.appendChild(greet); bubble.appendChild(form);

    var parts = shell(c, bubble);

    function setMode(m) {
      var f = (m === "form");
      form.hidden = !f; greet.hidden = f;
      bubble.classList.toggle("mode-form", f);
    }
    setMode("greet");

    var api = runtime({
      wrap: parts.wrap, btn: parts.btn, bubble: bubble,
      posKey: "mb_" + c.id + "_pos", hideBtn: parts.hide,
      onToggle: function (ctx) {
        if (!ctx.isOpen) { setMode("greet"); ctx.showBubble(true); }
        else { setMode(form.hidden ? "form" : "greet"); }
      }
    });
    x.addEventListener("click", function (e) {
      e.stopPropagation(); if (api) api.showBubble(false);
    });
    if (api && c.autoOpen !== false) { setMode("greet"); api.showBubble(true); }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = new FormData(form);
      fmsg.hidden = false; fmsg.textContent = "보내는 중…";
      fetch("https://api.web3forms.com/submit", { method: "POST", body: data })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.success) {
            fmsg.textContent = "보내주셔서 감사합니다! 🙏"; form.reset();
            setTimeout(function () { fmsg.hidden = true; setMode("greet"); }, 1500);
          } else {
            fmsg.textContent = "전송 실패 — 잠시 후 다시 시도해주세요.";
          }
        })
        .catch(function () { fmsg.textContent = "전송 실패 — 네트워크를 확인해주세요."; });
    });
  }

  // ── 타입: theme (카멜레온 — 클릭마다 화면 테마 순환) ──
  // <html data-theme> 만 바꾸면 페이지에 함께 심긴 모든 테마 중 하나가 즉시 적용된다.
  // 선택값은 localStorage("mb_theme") 에 저장돼 날짜를 넘겨도 유지된다.
  function mountTheme(c) {
    var cfg = window.__MB_THEMES || {};
    // 라벨은 characters.json(themes)이 우선, 없으면 페이지가 심은 목록을 사용.
    var themes = (Array.isArray(c.themes) && c.themes.length)
      ? c.themes
      : (cfg.list || []).map(function (id) { return { id: id, label: id }; });
    if (!themes.length) return;
    var ids = themes.map(function (t) { return t.id; });

    function labelOf(id) {
      for (var i = 0; i < themes.length; i++) if (themes[i].id === id) return themes[i].label || id;
      return id;
    }
    function curId() {
      var t = document.documentElement.getAttribute("data-theme");
      return ids.indexOf(t) >= 0 ? t : (cfg.def || ids[0]);
    }
    function apply(id) {
      document.documentElement.setAttribute("data-theme", id);
      try { localStorage.setItem("mb_theme", id); } catch (e) {}
    }

    var bubble = el("div", "mascot-bubble", { role: "status", hidden: "" });
    var x = closeBtn();
    var title = el("div", "mascot-bubble-title");
    var msg = el("div", "mascot-bubble-msg");
    bubble.appendChild(x); bubble.appendChild(title); bubble.appendChild(msg);

    var parts = shell(c, bubble);

    function render() {
      title.textContent = c.title || "테마 변경";
      msg.textContent = "현재 «" + labelOf(curId()) + "» · 누르면 다음 테마로 바뀌어요";
    }
    render();

    var api = runtime({
      wrap: parts.wrap, btn: parts.btn, bubble: bubble,
      posKey: "mb_" + c.id + "_pos", hideBtn: parts.hide,
      onToggle: function (ctx) {
        if (!ctx.isOpen) { render(); ctx.showBubble(true); return; }
        // 이미 열려 있으면 다음 테마로 순환
        var i = ids.indexOf(curId());
        apply(ids[(i + 1) % ids.length]);
        render();
      }
    });
    x.addEventListener("click", function (e) {
      e.stopPropagation(); if (api) api.showBubble(false);
    });
    if (api && c.autoOpen) { render(); api.showBubble(true); }
  }

  var TYPES = { notice: mountNotice, feedback: mountFeedback, theme: mountTheme };

  function start(data) {
    var list = (data && data.characters) || [];
    list.forEach(function (c) {
      if (!c || c.active === false) return;
      var fn = TYPES[c.type];
      if (fn) fn(c);
    });
  }

  function init() {
    fetch(asset(CFG.url || "/characters.json"), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) start(d); })
      .catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
