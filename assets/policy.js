/* 제도·규제 영역 (폐플라스틱·바이오가스 공통)
   script 태그의 data-facts(제도 현황 목록), data-state(법령·게시글 감시 결과), data-order(구분 표시 순서)를 읽어 그린다.
   필요한 요소: #polAlert #polBody #polUpd #bklNote (제도·규제), #polLaws #polPosts (맨 아래 참고 영역)
   data-page·data-bkl 이 있으면 태평양 월간 동향 중 빠진 항목을 '최근 동향' 행으로 표 맨 위에 더한다 */
(function () {
  const me = document.currentScript;
  const FACTS = me.dataset.facts, STATE = me.dataset.state;
  const ORDER = (me.dataset.order || '').split(',').filter(Boolean);
  const $ = id => document.getElementById(id);
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const getJson = u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const dayMs = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));

  /* 태평양(BKL) 월간 환경 정책 동향 중 '제도 현황'과 '법령 감시'에 아직 없는 항목만 골라 제도·규제 표의 '최근 동향' 행으로 넣는다 */
  const PAGE = me.dataset.page, BKL = me.dataset.bkl;
  const today = new Date(Date.now() + 9 * 36e5).toISOString().slice(0, 10);
  const dot = d => d ? d.slice(2).replace(/-/g, '.') : '';
  const nz = t => String(t || '').replace(/[\s「」()（）ㆍ·‧∙“”"']/g, '');
  // 2026.9.18 재생에너지법 분법으로 '신·재생에너지', '신에너지 및 재생에너지' → '재생에너지'로 이름이 바뀐 법령·지침을 같은 것으로 본다
  const key = t => nz(t).replace(/^신에너지및재생에너지|^신재생에너지/, '재생에너지');
  const dTok = d => { if (!d) return null; const [y, m, dd] = d.split('-').map(Number); return new RegExp(`(?:${y}\\.\\s?${m}|(?<![\\d.])${m})\\.\\s?${dd}(?![\\d])`); };
  const near = (a, b, days) => a && b && Math.abs(dayMs(a) - dayMs(b)) <= days * 864e5;
  function bklRows(bkl, facts, pol) {
    const iss = (bkl && bkl.issues) || [];
    if (!iss.length || !PAGE) return { rows: [], dropped: 0, total: 0, latest: null };
    const latest = iss[0], cut = iss[0].month;
    // 최근 호 전부 + 지난 호 중 아직 의견 제출 중인 예고·시행 전인 개정
    let its = [];
    iss.forEach((s, k) => (s.items || []).filter(i => (i.pages || []).includes(PAGE))
      .filter(i => k === 0 || (i.sec === '입법·행정예고' && i.until >= today) || (i.sec === '법령·고시 개정' && i.effective > today))
      .forEach(i => its.push({ ...i, iss: s })));
    const total = its.length;
    const laws = Object.values((pol && pol.laws) || {}), posts = (pol && pol.posts) || [];
    const why = {};
    // ① 같은 법령의 이전 단계(예고 뒤 개정, 같은 지침의 앞선 개정)는 최신 것만 남긴다
    its = its.filter(i => i.sec === '의원 발의' || !its.some(j => j !== i && j.sec !== '의원 발의' && key(j.name) === key(i.name) &&
      ((j.date || '') > (i.date || '') || (j.date === i.date && j.sec === '법령·고시 개정' && i.sec !== j.sec))) || (why.old = (why.old || 0) + 1, false));
    its = its.filter(i => {
      const n = key(i.name), tok = dTok(i.date);
      // ② 법령 감시: 같은 법령의 같은 날짜 또는 더 나중 개정이 이미 잡혀 있음
      if (i.sec !== '의원 발의' && laws.some(l => (key(l.name) === n || key(l.name).includes(n) || n.includes(key(l.name))) &&
          l.promulgated && dayMs(l.promulgated) >= dayMs(i.date) - 3 * 864e5)) { why.watch = (why.watch || 0) + 1; return false; }
      // ③ 부처 게시판: 같은 이름의 입법·행정예고 글
      if (i.sec === '입법·행정예고' && posts.some(p => key(p.title).includes(n) && near(p.date, i.date, 5))) { why.watch = (why.watch || 0) + 1; return false; }
      // ④ 제도 현황: 근거·내용에 같은 법령명과 같은 날짜가 이미 적혀 있음
      if (tok && (facts || []).some(f => key(`${f.basis || ''}${f.detail || ''}${f.item || ''}`).includes(n) && tok.test(f.detail || ''))) { why.facts = (why.facts || 0) + 1; return false; }
      return true;
    });
    const secRank = { '입법·행정예고': 0, '법령·고시 개정': 1, '의원 발의': 2 };
    its.sort((a, b) => secRank[a.sec] - secRank[b.sec] || (b.date || '').localeCompare(a.date || ''));
    const rows = its.map(i => {
      let detail, status, eff;
      if (i.sec === '법령·고시 개정') {
        detail = `${dot(i.date)} ${/^「/.test(i.name) ? '발령' : '공포'}${i.effective ? `, ${dot(i.effective)} 시행` : ''}.`;
        status = i.effective && i.effective > today ? '시행예정' : '시행중'; eff = i.effective || i.date;
      } else if (i.sec === '입법·행정예고') {
        const open = i.until && i.until >= today;
        detail = `${/^「/.test(i.name) ? '행정예고' : '입법예고'} ${dot(i.date)}~${dot(i.until)}${open ? ' — 지금 의견 제출 가능' : ' — 예고 종료, 확정 여부는 원문 확인'}.`;
        status = open ? '의견 제출 중' : '예고 종료'; eff = '-';
      } else {
        detail = `${dot(i.date)} ${i.by || ''} 발의, 국회 계류 중.`;
        status = '발의'; eff = '-';
      }
      return { group: '최근 동향', item: i.name, sub: `${i.sec} · ${i.field || ''}`, detail, status, effective: eff,
               source_url: i.iss.pdf, source_label: `BKL ${+i.iss.month.slice(5)}월호`, live: status === '의견 제출 중' };
    });
    return { rows, dropped: total - rows.length, why, total, latest };
  }

  function render(facts, pol, bkl) {
    const badge = s => `<span class="badge ${s === '시행중' ? 'on' : (s === '시행예정' || s === '의견 제출 중') ? 'soon' : 'plan'}">${esc(s)}</span>`;
    const recent = ((pol && pol.events) || []).filter(e => e.date && Date.now() - dayMs(e.date) < 14 * 864e5);
    if ($('polAlert')) $('polAlert').innerHTML = recent.length ? `<div class="alert"><b>최근 2주 제도 변경 감지 ${recent.length}건</b>${recent.map(e =>
      `<div>· ${esc(e.date.slice(5).replace('-', '.'))} [${esc(e.type)}] <a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a></div>`).join('')}</div>` : '';
    const rank = g => { if (g === '최근 동향') return -1; const i = ORDER.indexOf(g); return i < 0 ? 99 : i; };
    const B = bklRows(bkl, facts, pol);
    const all = B.rows.concat((facts || []).slice().sort((a, b) => rank(a.group) - rank(b.group)));
    if ($('polBody')) $('polBody').innerHTML = all.map(f =>
      `<tr${f.group === '최근 동향' ? ' class="trend"' : ''}><td class="h-m">${esc(f.group)}</td><td class="l"><b>${esc(f.item)}</b>${f.sub ? `<small class="why-s">${esc(f.sub)}</small>` : ''}</td><td class="d">${esc(f.detail)}</td><td>${badge(f.status)}</td>
       <td>${esc(f.effective || '-')}</td><td class="h-m"><a href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">${esc(f.source_label || (f.source_date || '').slice(0, 7) || '출처')}</a></td></tr>`).join('')
      || '<tr><td colspan="6" class="fl">제도 현황 자료가 없습니다.</td></tr>';
    if ($('bklNote')) $('bklNote').innerHTML = B.latest ? `'최근 동향' 행은 법무법인 태평양의 월간 「환경 주요 정책 동향」(<a href="${esc(B.latest.pdf)}" target="_blank" rel="noopener noreferrer">${esc(B.latest.title)}</a>)에서 이 페이지와 관련된 ${B.total}건 중,
      아래 현황 표나 실시간 법령·게시판 감시(맨 아래 참고)에 이미 있는 ${(B.why.watch || 0) + (B.why.facts || 0)}건${B.why.old ? `과 같은 법령의 이전 단계 ${B.why.old}건` : ''}을 뺀 ${B.rows.length}건입니다(날짜·법령명만 옮기고 내용은 원문 PDF 참고).` : '';
    const laws = Object.values((pol && pol.laws) || {}).sort((a, b) => (b.promulgated || '').localeCompare(a.promulgated || ''));
    if ($('polLaws')) $('polLaws').innerHTML = laws.length ? laws.map(l => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.name)}</a>
      <small> — ${esc(l.kind || '')} ${esc(l.promulgated || '')}${l.effective ? ` · 시행 ${esc(l.effective)}` : ''}</small></li>`).join('') : '<li class="fl">법령 감시 자료를 아직 받지 못했습니다.</li>';
    const posts = ((pol && pol.posts) || []).slice(0, 8);
    if ($('polPosts')) $('polPosts').innerHTML = posts.length ? posts.map(p => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a> <small>${esc(p.board)} ${esc(p.date || '')}</small></li>`).join('') : '<li class="fl">최근 관련 게시글 없음</li>';
    if ($('polUpd')) $('polUpd').textContent = pol && pol.updated ? `감시 갱신 ${pol.updated}` : '';
  }
  Promise.all([getJson(FACTS).catch(() => []), getJson(STATE).catch(() => null), BKL ? getJson(BKL).catch(() => null) : null]).then(([f, p, k]) => render(f, p, k));
})();
