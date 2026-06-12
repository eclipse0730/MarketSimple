(function(){
  var dataEl = document.getElementById('mb-news-data');
  var modal = document.getElementById('newsModal');
  if(!dataEl || !modal) return;

  var DATA = {};
  try { DATA = JSON.parse(dataEl.textContent) || {}; } catch(e) { return; }

  var titleEl = document.getElementById('newsTitle');
  var subEl = document.getElementById('newsSub');
  var bodyEl = document.getElementById('newsBody');
  var lastFocus = null;

  function esc(s){
    return String(s).replace(/[&<>"']/g, function(ch){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch];
    });
  }
  function stockUrl(code){ return 'https://finance.naver.com/item/main.naver?code=' + encodeURIComponent(code); }

  // "YYYYMMDDHHMM" → 상대 시간(방금 / N분 전 / N시간 전 / M.D).
  function relTime(dt){
    if(!dt || dt.length < 12) return '';
    var y=+dt.slice(0,4), mo=+dt.slice(4,6)-1, d=+dt.slice(6,8), h=+dt.slice(8,10), mi=+dt.slice(10,12);
    var then = new Date(y, mo, d, h, mi);
    var diff = (Date.now() - then.getTime()) / 60000; // 분
    if(diff < 1) return '방금';
    if(diff < 60) return Math.floor(diff) + '분 전';
    if(diff < 60*24) return Math.floor(diff/60) + '시간 전';
    return (mo+1) + '.' + d;
  }

  function openNews(code){
    var entry = DATA[code];
    if(!entry) return;
    var items = entry.items || [];

    titleEl.textContent = entry.name || code;
    subEl.innerHTML = '<a class="news-stock-link" href="' + stockUrl(code)
      + '" target="_blank" rel="noopener noreferrer">네이버 종목 페이지 ↗</a>';

    var html = '';
    for(var i = 0; i < items.length; i++){
      var it = items[i];
      html += '<a class="news-row" href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">'
            + '<span class="news-title">' + esc(it.title) + '</span>'
            + '<span class="news-meta"><span class="news-office">' + esc(it.office) + '</span>'
            + '<span class="news-time">' + esc(relTime(it.datetime)) + '</span></span></a>';
    }
    bodyEl.innerHTML = html || '<p class="news-empty">최근 뉴스가 없습니다.</p>';
    bodyEl.scrollTop = 0;
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeNews(){
    modal.hidden = true;
    document.body.style.overflow = '';
    if(lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener('click', function(e){
    var opener = e.target.closest && e.target.closest('.tv-has-news, .chip-has-news');
    if(opener){
      openNews(opener.getAttribute('data-news-code'));
      return;
    }
    if(e.target.closest && e.target.closest('[data-nclose]')) closeNews();
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && !modal.hidden) closeNews();
  });
})();
