/* 폐플라스틱 페이지: 아파트 단지 재활용품 매각·수거업체 선정 — data/apt_sales.json
   공고는 K-APT 공개 목록(하루 1회), 낙찰 결과는 사용자가 올린 K-APT 입찰결과 엑셀에서 온다.
   필요한 요소: #aptKpi #aptBody #aptUpd #aptNote, 필터 #aptScope #aptPeriod */
(function () {
  const $ = id => document.getElementById(id);
  if (!$('aptBody')) return;
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const n0 = v => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const dayMs = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  const won = v => v == null ? '-' : v >= 1e8 ? `${(v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}억원` : v >= 1e4 ? `${n0(v / 1e4)}만원` : `${n0(v)}원`;
  const median = a => { const s = a.slice().sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const getJson = u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  let ROWS = [], META = {}, SCOPE = 'cap', PERIOD = 365;

  function build(j) {
    const items = (j.items || []).map(x => ({ ...x, date: x.reg || '', kind: 'notice' }));
    // 목록에 없는(1년 넘은 등) 결과도 표에 넣는다
    const extra = (j.results || []).filter(r => !r.matched).map(r => ({
      id: 'r:' + r.key, date: r.end || '', end: r.end || '', apt: r.apt, title: r.title, way: '', households: r.households,
      win_amt: r.amount, winner: r.winner, region: /수원|화성|평택|오산/.test(r.area || '') ? '중점' : '수도권', city: r.area || '',
      src: 'K-APT 입찰결과', url: 'https://www.k-apt.go.kr/bid/bidResultList.do', kind: 'result'
    }));
    return items.concat(extra).sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }

  function render() {
    const cut = Date.now() - PERIOD * 864e5;
    const rows = ROWS.filter(r => (SCOPE === 'focus' ? r.region === '중점' : true) && r.date && dayMs(r.date) >= cut);
    const live = rows.filter(r => r.kind === 'notice' && r.end && dayMs(r.end.slice(0, 10)) >= Date.now() - 864e5 && !r.win_amt);
    const done = rows.filter(r => r.win_amt);
    const per = done.filter(r => r.households).map(r => r.win_amt / r.households);
    $('aptKpi').innerHTML = [
      ['공고', `${rows.filter(r => r.kind === 'notice').length}건`, `진행 중 ${live.length}건`],
      ['낙찰 결과', `${done.length}건`, META.results_updated ? `엑셀 반영 ${META.results_updated.slice(0, 10)}` : '입찰결과 엑셀을 올리면 표시'],
      ['세대당 낙찰금액 (중앙값)', per.length ? `${n0(median(per))}원` : '-', per.length ? `${per.length}건 · 낙찰금액 ÷ 세대수` : '세대수 있는 결과 없음'],
      ['평균 세대수', done.filter(r => r.households).length ? `${n0(done.filter(r => r.households).reduce((a, r) => a + r.households, 0) / done.filter(r => r.households).length)}세대` : '-', '결과 반영 단지']
    ].map(([a, b, c]) => `<div class="kpi"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
    $('aptBody').innerHTML = rows.slice(0, 30).map(r => {
      const reg = `<span class="reg${r.region === '중점' ? ' f' : ''}">${esc(r.city || '수도권')}</span>`;
      const hh = r.households ? `<small class="fl" style="display:block">${n0(r.households)}세대</small>` : '';
      let res;
      if (r.win_amt) {
        res = `<b>${won(r.win_amt)}</b>${r.households ? `<small class="fl" style="display:block">세대당 ${n0(r.win_amt / r.households)}원</small>` : ''}<small class="fl" style="display:block">${esc(r.winner || '')}</small>`;
      } else if (live.includes(r)) {
        res = `<b class="up">진행 중</b><small class="fl" style="display:block">마감 ${esc((r.end || '').slice(5, 10).replace('-', '.'))}</small>`;
      } else res = `<span class="fl">${esc(r.state === '입찰마감' ? '마감 · 결과 미반영' : r.state || '-')}</span>`;
      const sub = [r.cls, r.sys && r.sys !== 'K-APT' ? r.sys : ''].filter(Boolean).join(' · ');
      return `<tr><td>${esc((r.date || '').slice(2).replace(/-/g, '.'))}</td><td>${reg}</td><td class="t h-m">${esc(r.apt)}${hh}</td>
        <td class="t"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>${sub ? `<small class="why-s">${esc(sub)}</small>` : ''}</td>
        <td class="h-m">${esc(r.way || '-')}</td><td>${res}</td></tr>`;
    }).join('') || '<tr><td colspan="6" class="fl">해당 기간·지역의 아파트 재활용품 공고가 없습니다.</td></tr>';
  }
  getJson('data/apt_sales.json').then(j => {
    META = j; ROWS = build(j);
    $('aptUpd').textContent = j.updated ? `공고 확인 ${j.updated}` : '';
    render();
  }).catch(() => { $('aptBody').innerHTML = '<tr><td colspan="6" class="fl">자료를 아직 받지 못했습니다.</td></tr>'; });
  const seg = (id, fn) => document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); render();
  }));
  seg('aptScope', v => SCOPE = v);
  seg('aptPeriod', v => PERIOD = +v);
})();
