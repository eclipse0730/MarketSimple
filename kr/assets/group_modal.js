(function(){
  var dataEl = document.getElementById('mb-group-data');
  var modal = document.getElementById('gmModal');
  if(!dataEl || !modal) return;

  var DATA = {};
  try { DATA = JSON.parse(dataEl.textContent) || {}; } catch(e) { return; }

  var titleEl = document.getElementById('gmTitle');
  var subEl = document.getElementById('gmSub');
  var listEl = document.getElementById('gmList');
  var lastFocus = null;

  function esc(s){
    return String(s).replace(/[&<>"']/g, function(ch){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch];
    });
  }
  function rateClass(v){ return v > 0 ? 'up' : (v < 0 ? 'down' : 'flat'); }
  function fmtRate(v){ return (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%'; }
  function stockUrl(code){ return 'https://finance.naver.com/item/main.naver?code=' + encodeURIComponent(code); }

  function openGroup(kind, key){
    var members = (DATA[kind] || {})[key];
    if(!members) return;

    titleEl.textContent = key;
    subEl.textContent = members.length.toLocaleString() + '종목 · 등락률순';
    var html = '';
    for(var i = 0; i < members.length; i++){
      var m = members[i];
      html += '<a class="gm-row" href="' + stockUrl(m.code) + '" target="_blank" rel="noopener noreferrer">'
            + '<span class="gm-nm">' + esc(m.name) + '</span>'
            + '<span class="gm-rt mono ' + rateClass(m.rate) + '">' + fmtRate(m.rate) + '</span></a>';
    }
    listEl.innerHTML = html;
    listEl.scrollTop = 0;
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeGroup(){
    modal.hidden = true;
    document.body.style.overflow = '';
    if(lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener('click', function(e){
    var opener = e.target.closest && e.target.closest('.gm-open');
    if(opener){
      openGroup(opener.getAttribute('data-gkind'), opener.getAttribute('data-gkey'));
      return;
    }
    if(e.target.closest && e.target.closest('[data-close]')) closeGroup();
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && !modal.hidden) closeGroup();
    if(e.key === 'Enter' || e.key === ' '){
      var opener = e.target.closest && e.target.closest('.gm-open');
      if(opener){
        e.preventDefault();
        openGroup(opener.getAttribute('data-gkind'), opener.getAttribute('data-gkey'));
      }
    }
  });
})();
