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
  /* 태평양(BKL) 월간 환경 정책 동향 — data-page(plastic|biogas) 관련 항목 */
  const PAGE = me.dataset.page, BKL = me.dataset.bkl;
  const SEC_ORDER = ['법령·고시 개정', '입법·행정예고', '의원 발의'];
  const dot = d => d ? d.slice(2).replace(/-/g, '.') : '';
  const today = new Date(Date.now() + 9 * 36e5).toISOString().slice(0, 10);
  function bklTable(iss) {
    const its = (iss.items || []).filter(i => (i.pages || []).includes(PAGE))
      .sort((a, b) => SEC_ORDER.indexOf(a.sec) - SEC_ORDER.indexOf(b.sec) || (b.date || '').localeCompare(a.date || ''));
    const head = `<div class="bkl-iss"><b>${esc(iss.title)}</b> · 관련 ${its.length}건 / 전체 ${iss.n_total || '-'}건 ·
      <a href="${esc(iss.pdf)}" target="_blank" rel="noopener noreferrer">원문 PDF</a> · <a href="${esc(iss.url)}" target="_blank" rel="noopener noreferrer">소개 페이지</a></div>`;
    if (!its.length) return head + '<p class="fl">이 페이지와 관련된 항목이 없습니다.</p>';
    const kind = s => s === '법령·고시 개정' ? '<span class="badge on">개정</span>' : s === '입법·행정예고' ? '<span class="badge soon">예고</span>' : '<span class="badge plan">발의</span>';
    const rows = its.map(i => {
      const when = i.sec === '입법·행정예고' ? `${dot(i.date)}~${dot(i.until)}` : dot(i.date);
      const note = i.sec === '법령·고시 개정' ? (i.effective ? `시행 ${dot(i.effective)}` : '')
        : i.sec === '입법·행정예고' ? (i.until && i.until >= today ? '<b class="up">의견 제출 가능</b>' : '예고 종료')
        : esc(i.by || '');
      return `<tr><td>${kind(i.sec)}</td><td>${esc(when)}</td><td class="l"><b>${esc(i.name)}</b></td><td class="h-m">${esc(i.field)}</td><td>${note}</td></tr>`;
    }).join('');
    return head + `<table class="cmp pol bkl"><thead><tr><th>구분</th><th>날짜</th><th>법령·고시명</th><th class="h-m">분야</th><th>비고</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  if (BKL && $('polBkl')) getJson(BKL).then(j => {
    const iss = j.issues || [];
    $('polBkl').innerHTML = iss.length ? bklTable(iss[0]) + (iss.length > 1 ? `<details class="bkl-old"><summary>지난 호 보기 (${iss.slice(1).map(i => esc(i.month)).join(', ')})</summary>${iss.slice(1).map(bklTable).join('')}</details>` : '')
      : '<p class="fl">아직 받은 호가 없습니다.</p>';
    if ($('bklUpd')) $('bklUpd').textContent = j.updated ? `확인 ${j.updated}` : '';
  }).catch(() => { $('polBkl').innerHTML = '<p class="fl">월간 동향 자료를 아직 받지 못했습니다.</p>'; });

  Promise.all([getJson(FACTS).catch(() => []), getJson(STATE).catch(() => null)]).then(([f, p]) => render(f, p));
})();
