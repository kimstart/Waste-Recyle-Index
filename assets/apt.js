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

  // 취소된 공고는 숨기고, 같은 단지·같은 공고명이 120일 안에 여러 번 나오면(재공고) 낙찰된 건 또는 가장 최근 건만 남긴다
  const normT = t => String(t || '').replace(/\(?(긴급|재공고|재입찰|\d차)\)?|입찰|공고|선정|\s|[·ㆍ\-_,.()\[\]]/g, '');
  let DROPPED = 0;
  function build(j) {
    const all = (j.items || []).map(x => ({ ...x, date: x.reg || '' }));
    const res = {};
    (j.results || []).forEach(r => { res[(r.apt || '').replace(/\s/g, '')] = r; });   // 엑셀(선택)에서 세대수
    all.forEach(x => { const r = res[(x.apt || '').replace(/\s/g, '')]; if (r && r.households) x.households = r.households; });
    const live = all.filter(x => x.state !== '취소');
    const groups = {};
    live.forEach(x => (groups[(x.apt || '') + '|' + normT(x.title)] ||= []).push(x));
    const out = [];
    Object.values(groups).forEach(g => {
      g.sort((a, b) => (b.reg_dt || '').localeCompare(a.reg_dt || ''));
      const cl = [];
      g.forEach(x => { const c = cl.find(c => Math.abs(dayMs(c[0].date) - dayMs(x.date)) <= 120 * 864e5); c ? c.push(x) : cl.push([x]); });
      cl.forEach(c => { const w = c.filter((x, i) => x.state === '낙찰' && c.findIndex(y => y.state === '낙찰' && y.win_amt === x.win_amt && y.reg_dt === x.reg_dt) === i); w.length ? out.push(...w) : out.push(c[0]); });   // 같은 금액·같은 등록시각 낙찰은 한 번만
    });
    DROPPED = all.length - out.length;
    return out.sort((a, b) => (b.reg_dt || '').localeCompare(a.reg_dt || ''));
  }

  const isLive = r => !['낙찰', '유찰', '취소', '낙찰무효'].includes(r.state) && r.end && dayMs(r.end.slice(0, 10)) >= Date.now() - 864e5;
  function render() {
    const cut = Date.now() - PERIOD * 864e5;
    const rows = ROWS.filter(r => (SCOPE === 'focus' ? r.region === '중점' : true) && r.date && dayMs(r.date) >= cut);
    const live = rows.filter(isLive);
    const done = rows.filter(r => r.state === '낙찰' && r.win_amt);
    const amts = done.map(r => r.win_amt);
    // 낙찰금액은 대개 1년치 총액(세대당 월 단가 × 세대수 × 12) → 세대당 월 단가 = 낙찰금액 ÷ 세대수 ÷ 12
    const perAll = done.filter(r => r.households).map(r => r.win_amt / r.households / 12);
    const mid0 = perAll.length ? median(perAll) : 0;
    const per = perAll.filter(v => v <= mid0 * 3 && v >= mid0 / 3);           // 다년 계약 등 튀는 값 제외
    const perOut = perAll.length - per.length;
    const fail = rows.filter(r => r.state === '유찰' || r.state === '낙찰무효').length;
    $('aptKpi').innerHTML = [
      ['공고', `${rows.length}건`, `진행 중 ${live.length}건 · 유찰 ${fail}건`],
      ['낙찰', `${done.length}건`, rows.length ? `결과 나온 건 중 ${Math.round(done.length / Math.max(1, done.length + fail) * 100)}%` : ''],
      ['낙찰금액 (중앙값)', amts.length ? won(median(amts)) : '-', amts.length ? `${amts.length}건 · ${won(Math.min(...amts))}~${won(Math.max(...amts))}` : ''],
      ['세대당 월 단가 (중앙값)', per.length ? `${n0(median(per))}원` : '-', per.length ? `${per.length}건 · ${n0(Math.min(...per))}~${n0(Math.max(...per))}원${perOut ? ` · 이상치 ${perOut}건 제외` : ''}` : '세대수 자료 준비 중']
    ].map(([a, b, c]) => `<div class="kpi"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
    $('aptBody').innerHTML = (window.Board ? Board.pin(rows.slice(0, 40), ROWS) : rows.slice(0, 40)).map(r => {
      const reg = `<span class="reg${r.region === '중점' ? ' f' : ''}">${esc(r.city || '수도권')}</span>`;
      const hh = r.households ? `<small class="fl" style="display:block">${n0(r.households)}세대</small>` : '';
      let res;
      if (r.state === '낙찰' && r.win_amt) {
        const m = r.households ? r.win_amt / r.households / 12 : null;
        res = r.households ? `<b>월 ${n0(m)}원/세대</b><small class="fl" style="display:block">연 ${won(r.win_amt)}</small>`
          : `<b>${won(r.win_amt)}</b><small class="fl" style="display:block">세대수 미확인</small>`;
      } else if (isLive(r)) {
        res = `<b class="up">진행 중</b><small class="fl" style="display:block">마감 ${esc((r.end || '').slice(5, 10).replace('-', '.'))}</small>`;
      } else res = `<span class="fl">${esc(r.state || '-')}</span>`;
      const sub = [r.cls, r.sys && r.sys !== 'K-APT' ? r.sys : ''].filter(Boolean).join(' · ');
      return `<tr data-id="${esc(r.id)}"><td>${esc((r.date || '').slice(2).replace(/-/g, '.'))}</td><td>${reg}</td><td class="t h-m">${esc(r.apt)}${hh}</td>
        <td class="t"><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>${sub ? `<small class="why-s">${esc(sub)}</small>` : ''}</td>
        <td class="h-m">${esc(r.way || '-')}</td><td class="res">${res}</td></tr>`;
    }).join('') || '<tr><td colspan="6" class="fl">해당 기간·지역의 아파트 재활용품 공고가 없습니다.</td></tr>';
    if ($('aptNote')) $('aptNote').textContent = `${rows.length > 40 ? `최근 40건만 표시(전체 ${rows.length}건). ` : ''}취소·재공고 중복 ${DROPPED}건 제외.`;
  }
  getJson('data/apt_sales.json').then(j => {
    META = j; ROWS = build(j);
    $('aptUpd').textContent = j.updated ? `확인 ${j.updated}${j.bf_done ? '' : ' · 지난 1년치 채우는 중'}` : '';
    render();
  }).catch(() => { $('aptBody').innerHTML = '<tr><td colspan="6" class="fl">자료를 아직 받지 못했습니다.</td></tr>'; });
  const seg = (id, fn) => document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); render();
  }));
  // 결과 공유: 'OO아파트(1,234세대) 재활용품 매각 결과(20261027)\n월 1,050 원/세대 (연 1,555만원)'
  if (window.Board) Board.share('apt', id => {
    const r = ROWS.find(x => String(x.id) === id);
    if (!r || r.state !== '낙찰' || !r.win_amt) return null;
    const hh = r.households;
    return { head: `${r.apt}${hh ? `(${n0(hh)}세대)` : ''} 재활용품 매각 결과(${Board.ymd(r.end || r.date)})`, ids: [r.id],
             lines: [hh ? `월 ${n0(r.win_amt / hh / 12)} 원/세대 (연 ${won(r.win_amt)})` : `낙찰 ${won(r.win_amt)} (세대수 미확인)`, r.title] };
  });
  seg('aptScope', v => SCOPE = v);
  seg('aptPeriod', v => PERIOD = +v);
})();
