(function(){
  var dataEl = document.getElementById('mb-flow-data');
  var modal = document.getElementById('flowModal');
  if(!dataEl || !modal) return;

  var DATA = {};
  try { DATA = JSON.parse(dataEl.textContent) || {}; } catch(e) { return; }

  var titleEl = document.getElementById('fmTitle');
  var subEl = document.getElementById('fmSub');
  var bodyEl = document.getElementById('fmBody');
  var lastFocus = null;

  // 카드 라벨 순서와 동일(기관·외인·개인). key 는 데이터 필드명.
  var COLS = [
    { label: '기관', key: 'institution' },
    { label: '외인', key: 'foreign' },
    { label: '개인', key: 'personal' }
  ];

  function rateClass(v){ return v > 0 ? 'up' : (v < 0 ? 'down' : 'flat'); }
  function fmtFlow(v){
    var n = Math.round(Number(v) || 0);
    return (n > 0 ? '+' : (n < 0 ? '-' : '')) + Math.abs(n).toLocaleString() + '억';
  }
  function fmtDate(s){
    // YYYYMMDD → MM.DD
    s = String(s);
    return s.length === 8 ? s.slice(4, 6) + '.' + s.slice(6, 8) : s;
  }

  function openFlow(market, investor){
    var rows = DATA[market];
    if(!rows || !rows.length) return;

    titleEl.textContent = market + ' 투자자별 수급';
    subEl.textContent = '최근 ' + rows.length + '거래일 · 순매수(억원)';

    var head = '<tr><th class="fm-d">날짜</th>';
    for(var c = 0; c < COLS.length; c++){
      var hl = COLS[c].key === investor ? ' fm-hl' : '';
      head += '<th class="' + COLS[c].key + hl + '">' + COLS[c].label + '</th>';
    }
    head += '</tr>';

    var tbody = '';
    for(var i = 0; i < rows.length; i++){
      var r = rows[i];
      tbody += '<tr><td class="fm-d mono">' + fmtDate(r.date) + '</td>';
      for(var k = 0; k < COLS.length; k++){
        var key = COLS[k].key;
        var v = r[key];
        var cell = (v == null) ? 'N/A' : fmtFlow(v);
        var cls = 'mono ' + rateClass(v) + (key === investor ? ' fm-hl' : '');
        tbody += '<td class="' + cls + '">' + cell + '</td>';
      }
      tbody += '</tr>';
    }

    bodyEl.innerHTML = '<table class="fm-table"><thead>' + head + '</thead><tbody>' + tbody + '</tbody></table>';
    bodyEl.scrollTop = 0;
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeFlow(){
    modal.hidden = true;
    document.body.style.overflow = '';
    if(lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener('click', function(e){
    var opener = e.target.closest && e.target.closest('.flow-open');
    if(opener){
      openFlow(opener.getAttribute('data-fmkt'), opener.getAttribute('data-finv'));
      return;
    }
    if(e.target.closest && e.target.closest('[data-fclose]')) closeFlow();
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && !modal.hidden) closeFlow();
  });
})();
