/* 바이오가스 페이지: 수도권 유기성폐자원 입찰·용역·공사 — data/bio_bids.json
   필요한 요소: #bioKpi #bioBody #bioUpd, 필터 #bioScope #bioPeriod #bioType */
(function () {
  const $ = id => document.getElementById(id);
  if (!$('bioBody')) return;
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const n0 = v => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const n1 = v => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
  const dayMs = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  const eok = v => v == null ? '-' : v >= 1e8 ? `${(v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억원` : `${n0(v / 1e4)}만원`;
  const getJson = u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

  let ALL = [], SCOPE = 'cap', PERIOD = 365, TYPE = '';
  // 단가계약: 추정가격이 톤당 단가로 올라왔거나(300만원 미만 + '단가'), 낙찰금액이 추정가격의 1/500 미만
  const estUnit = b => b.est && b.est < 3e6 && /단가/.test(b.title || '');
  const isUnit = b => b.win_amt && ((b.est && b.win_amt < b.est / 500) || estUnit(b));

  function render() {
    const cut = Date.now() - PERIOD * 864e5;
    const rows = ALL.filter(b => (SCOPE === 'focus' ? b.region === '중점' : true) && (!TYPE || b.type === TYPE) && b.start && dayMs(b.start) >= cut);
    const live = rows.filter(b => b.end && dayMs(b.end) >= Date.now() - 864e5 && !/낙찰|유찰|취소/.test(b.status || ''));
    const won = rows.filter(b => b.status === '낙찰');
    const ests = rows.filter(b => !estUnit(b)).map(b => b.est).filter(v => v);
    const wonTot = won.filter(b => b.win_amt && !isUnit(b));
    const epc = rows.filter(b => b.type === 'EPC·공사' && b.est).map(b => b.est);
    const rates = won.map(b => b.win_rate).filter(v => v);
    $('bioKpi').innerHTML = [
      ['공고', `${rows.length}건`, `진행 중 ${live.length}건 · 낙찰 ${won.length}건`],
      ['추정가격 합계', ests.length ? eok(ests.reduce((a, b) => a + b, 0)) : '-', `추정가격 공개 ${ests.length}건 (재공고 포함)`],
      ['낙찰금액 합계 (총액계약)', wonTot.length ? eok(wonTot.reduce((a, b) => a + b.win_amt, 0)) : '-', `총액 낙찰 ${wonTot.length}건`],
      ['EPC·공사 추정가격', epc.length ? eok(epc.reduce((a, b) => a + b, 0)) : '-', `공사·설계 ${epc.length}건`],
      ['평균 낙찰률', rates.length ? `${n1(mean(rates))}%` : '-', '낙찰금액 ÷ 예정가격']
    ].map(([a, b, c]) => `<div class="kpi"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
    $('bioBody').innerHTML = rows.slice(0, 30).map(b => {
      const reg = `<span class="reg${b.region === '중점' ? ' f' : ''}">${esc(b.city || '수도권')}</span>`;
      const g2b = b.src === '나라장터';
      const est = g2b ? (estUnit(b) ? n1(b.est) + '원<small class="fl" style="display:block">단가</small>' : eok(b.est)) : esc(b.pre_raw || '-');
      let res;
      if (b.status === '낙찰' && (b.win_amt || b.win_raw)) {
        res = g2b ? `<b>${isUnit(b) ? n1(b.win_amt) + '원' : eok(b.win_amt)}</b>${isUnit(b) ? '<small class="fl" style="display:block">단가계약</small>' : ''}${b.win_rate ? `<small class="fl"> (${n1(b.win_rate)}%)</small>` : ''}<small class="fl" style="display:block">${esc(b.winner || '')}</small>`
          : `<b>${esc(b.win_raw)}</b>`;
      } else if (live.includes(b)) {
        res = `<b class="up">진행 중</b><small class="fl" style="display:block">마감 ${esc((b.end || '').slice(5).replace('-', '.'))}</small>`;
      } else res = esc(b.status === '공고' ? '결과 대기' : b.status || '-');
      return `<tr><td>${esc((b.start || '').slice(2).replace(/-/g, '.'))}</td><td>${reg}</td><td class="t h-m">${esc(b.org)}</td>
        <td class="t"><a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.title)}</a><small class="why-s">${esc(b.waste || '')}${b.kind ? ' · ' + esc(b.kind) : ''}</small></td>
        <td class="h-m">${esc(b.type)}</td><td>${est}</td><td>${res}</td><td class="h-m">${esc(g2b ? '나라장터' : '순환자원')}</td></tr>`;
    }).join('') || '<tr><td colspan="8" class="fl">해당 기간·지역의 유기성폐자원 공고가 없습니다.</td></tr>';
    $('bioMore').textContent = rows.length > 30 ? `최근 30건만 표시 (전체 ${rows.length}건)` : '';
  }
  getJson('data/bio_bids.json').then(j => {
    ALL = j.items || [];
    $('bioUpd').textContent = j.updated ? `갱신 ${j.updated}` : '';
    render();
  }).catch(() => { $('bioBody').innerHTML = '<tr><td colspan="8" class="fl">입찰 자료를 아직 받지 못했습니다. 다음 수집(07:05·13:05·18:05) 후 표시됩니다.</td></tr>'; });
  const seg = (id, fn) => document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); render();
  }));
  seg('bioScope', v => SCOPE = v);
  seg('bioPeriod', v => PERIOD = +v);
  seg('bioType', v => TYPE = v);
})();
