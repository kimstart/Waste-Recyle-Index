/* 제도·규제 영역 (폐플라스틱·바이오가스 공통)
   script 태그의 data-facts(제도 현황 목록), data-state(법령·게시글 감시 결과), data-order(구분 표시 순서)를 읽어 그린다.
   필요한 요소: #polAlert #polBody #polUpd (제도·규제), #polLaws #polPosts (맨 아래 참고 영역) */
(function () {
  const me = document.currentScript;
  const FACTS = me.dataset.facts, STATE = me.dataset.state;
  const ORDER = (me.dataset.order || '').split(',').filter(Boolean);
  const $ = id => document.getElementById(id);
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const getJson = u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const dayMs = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));

  function render(facts, pol) {
    const badge = s => `<span class="badge ${s === '시행중' ? 'on' : s === '시행예정' ? 'soon' : 'plan'}">${esc(s)}</span>`;
    const recent = ((pol && pol.events) || []).filter(e => e.date && Date.now() - dayMs(e.date) < 14 * 864e5);
    if ($('polAlert')) $('polAlert').innerHTML = recent.length ? `<div class="alert"><b>최근 2주 제도 변경 감지 ${recent.length}건</b>${recent.map(e =>
      `<div>· ${esc(e.date.slice(5).replace('-', '.'))} [${esc(e.type)}] <a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a></div>`).join('')}</div>` : '';
    const rank = g => { const i = ORDER.indexOf(g); return i < 0 ? 99 : i; };
    if ($('polBody')) $('polBody').innerHTML = (facts || []).slice().sort((a, b) => rank(a.group) - rank(b.group)).map(f =>
      `<tr><td class="h-m">${esc(f.group)}</td><td class="l"><b>${esc(f.item)}</b></td><td class="d">${esc(f.detail)}</td><td>${badge(f.status)}</td>
       <td>${esc(f.effective || '-')}</td><td class="h-m"><a href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">${esc((f.source_date || '').slice(0, 7) || '출처')}</a></td></tr>`).join('')
      || '<tr><td colspan="6" class="fl">제도 현황 자료가 없습니다.</td></tr>';
    const laws = Object.values((pol && pol.laws) || {}).sort((a, b) => (b.promulgated || '').localeCompare(a.promulgated || ''));
    if ($('polLaws')) $('polLaws').innerHTML = laws.length ? laws.map(l => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.name)}</a>
      <small> — ${esc(l.kind || '')} ${esc(l.promulgated || '')}${l.effective ? ` · 시행 ${esc(l.effective)}` : ''}</small></li>`).join('') : '<li class="fl">법령 감시 자료를 아직 받지 못했습니다.</li>';
    const posts = ((pol && pol.posts) || []).slice(0, 8);
    if ($('polPosts')) $('polPosts').innerHTML = posts.length ? posts.map(p => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a> <small>${esc(p.board)} ${esc(p.date || '')}</small></li>`).join('') : '<li class="fl">최근 관련 게시글 없음</li>';
    if ($('polUpd')) $('polUpd').textContent = pol && pol.updated ? `감시 갱신 ${pol.updated}` : '';
  }
  Promise.all([getJson(FACTS).catch(() => []), getJson(STATE).catch(() => null)]).then(([f, p]) => render(f, p));
})();
