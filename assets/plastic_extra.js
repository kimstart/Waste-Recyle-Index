/* 폐플라스틱 페이지 추가 영역
   ① 수도권 재활용 가격 분석(전월·전년 동월·12개월 범위·3개년 동월) + 계절성 차트 — data/recycle_history.json
   ② 수도권 매각입찰 — data/bids.json
   ③ EPR·재생원료 의무 현황과 제도 변경 — data/policy_facts.json, data/policy.json */
(function () {
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const n0 = v => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const n1 = v => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const getJson = u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const ymAdd = (ym, k) => { let y = +ym.slice(0, 4), m = +ym.slice(5, 7) + k; while (m <= 0) { y--; m += 12; } while (m > 12) { y++; m -= 12; } return `${y}-${String(m).padStart(2, '0')}`; };
  const ymK = ym => `${ym.slice(2, 4)}.${+ym.slice(5, 7)}`;
  const pct = (a, b) => a == null || b == null || !b ? null : (a - b) / b * 100;
  const chg = p => p == null ? '<span class="fl">-</span>' : `<span class="${p > 0 ? 'up' : p < 0 ? 'dn' : 'fl'}">${p > 0 ? '▲' : p < 0 ? '▼' : ''} ${Math.abs(p).toFixed(1)}%</span>`;
  function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  function txt(parent, x, y, s, attrs) { const t = el('text', Object.assign({ x, y, 'font-size': 11, fill: '#64748b' }, attrs || {}), parent); t.textContent = s; return t; }
  function niceTicks(lo, hi, n) {
    const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || mag * 10;
    const a = Math.floor(lo / step) * step, out = [];
    for (let v = a; v <= hi + step * 0.001; v += step) out.push(+v.toFixed(6));
    if (out[out.length - 1] < hi) out.push(out[out.length - 1] + step);
    return out;
  }

  /* ---------------------------------------------------------------- ① 가격 분석 */
  let HIST = null;
  const YEAR_COLORS = ['#c3d7ef', '#8cb4e3', '#4a86cf', '#0f2a3d'];   // 오래된 해 → 올해 (같은 색 계열, 진할수록 최근)

  function renderAnalysis() {
    const h = HIST, months = Object.keys(h.months).sort();
    const latest = [...months].reverse().find(ym => Object.values(h.months[ym]).some(v => v != null));
    if (!latest) return;
    const val = (k, ym) => (h.months[ym] || {})[k];
    const y3 = [ymAdd(latest, -36), ymAdd(latest, -24), ymAdd(latest, -12)];
    $('anaHead').innerHTML = `<tr><th>품목</th><th>${latest.slice(0, 4)}년 ${+latest.slice(5, 7)}월<br><small>원/kg</small></th><th>전월 대비</th><th>전년 동월 대비</th><th>최근 12개월 범위에서 위치</th>
      ${y3.map(ym => `<th class="s3">${ym.slice(0, 4)}.${+ym.slice(5, 7)}</th>`).join('')}</tr>`;
    $('anaBody').innerHTML = h.items.map(it => {
      const cur = val(it.key, latest);
      if (cur == null) return '';
      const last12 = Array.from({ length: 12 }, (_, i) => val(it.key, ymAdd(latest, -i))).filter(v => v != null);
      const hi = Math.max(...last12), lo = Math.min(...last12), pos = hi > lo ? (cur - lo) / (hi - lo) * 100 : 50;
      return `<tr><td class="nm">${esc(it.name)}</td><td><b>${n1(cur)}</b></td><td>${chg(pct(cur, val(it.key, ymAdd(latest, -1))))}</td>
        <td>${chg(pct(cur, val(it.key, ymAdd(latest, -12))))}</td>
        <td><div class="rng" title="최저 ${n1(lo)} · 최고 ${n1(hi)}"><i style="left:${pos.toFixed(0)}%"></i></div><div class="rng-l"><span>${n0(lo)}</span><span>${n0(hi)}</span></div></td>
        ${y3.map(ym => `<td class="s3">${n1(val(it.key, ym))}</td>`).join('')}</tr>`;
    }).join('');
    $('anaNote').textContent = `${latest.slice(0, 4)}년 ${+latest.slice(5, 7)}월 기준, 수도권 값. 위치 막대는 최근 12개월 최저(왼쪽)~최고(오른쪽) 사이에서 이번 달 값이 어디쯤인지 보여줍니다. 오른쪽 세 열은 최근 3개년의 같은 달 값입니다.`;
    const sel = $('seasonItem');
    if (!sel.options.length) {
      sel.innerHTML = h.items.map(it => `<option value="${it.key}">${esc(it.name)}</option>`).join('');
      sel.value = 'r_comp_pet';
      sel.addEventListener('change', drawSeason);
    }
    drawSeason();
  }

  function drawSeason() {
    const h = HIST, key = $('seasonItem').value, box = $('seasonChart');
    const years = [...new Set(Object.keys(h.months).map(ym => +ym.slice(0, 4)))].sort().slice(-4);
    const series = years.map((y, i) => ({ y, color: YEAR_COLORS[YEAR_COLORS.length - years.length + i], last: i === years.length - 1,
      vals: Array.from({ length: 12 }, (_, m) => (h.months[`${y}-${String(m + 1).padStart(2, '0')}`] || {})[key]) }));
    const all = series.flatMap(s => s.vals).filter(v => v != null);
    box.innerHTML = '';
    if (!all.length) { box.innerHTML = '<div class="note">자료 없음</div>'; return; }
    const W = Math.max(300, box.clientWidth), H = 240, m = { l: 46, r: 46, t: 10, b: 24 };
    const t = niceTicks(Math.min(...all), Math.max(...all), 4), y0 = t[0], y1 = t[t.length - 1];
    const X = i => m.l + i / 11 * (W - m.l - m.r), Y = v => m.t + (1 - (v - y0) / (y1 - y0)) * (H - m.t - m.b);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': '연도별 월간 가격 비교' }, box);
    t.forEach(v => { el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: '#e5e7eb' }, svg); txt(svg, m.l - 6, Y(v) + 4, n0(v), { 'text-anchor': 'end' }); });
    for (let i = 0; i < 12; i++) txt(svg, X(i), H - 6, `${i + 1}월`, { 'text-anchor': 'middle' });
    series.forEach(s => {
      let d = '';
      s.vals.forEach((v, i) => { if (v == null) return; d += (d && s.vals[i - 1] != null ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1); });
      el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': s.last ? 2.5 : 2, 'stroke-linejoin': 'round' }, svg);
      s.vals.forEach((v, i) => { if (v != null && s.last) el('circle', { cx: X(i), cy: Y(v), r: 3.5, fill: s.color, stroke: '#fff', 'stroke-width': 1.5 }, svg); });
      const li = s.vals.map((v, i) => v == null ? -1 : i).filter(i => i >= 0).pop();
      if (li != null && li >= 0) txt(svg, X(li) + 6, Y(s.vals[li]) + 4, String(s.y), { fill: '#334155', 'font-weight': s.last ? 800 : 600 });
    });
    $('seasonLegend').innerHTML = series.map(s => `<span><i style="background:${s.color};height:${s.last ? 3 : 2}px"></i>${s.y}년</span>`).join('');
    // 십자선 + 툴팁: 해당 월의 모든 해 값을 함께
    const cross = el('line', { y1: m.t, y2: H - m.b, stroke: '#94a3b8', visibility: 'hidden' }, svg);
    const tip = document.createElement('div'); tip.className = 'rp-tip'; box.appendChild(tip);
    svg.addEventListener('pointermove', ev => {
      const r = svg.getBoundingClientRect(), k = W / r.width, px = (ev.clientX - r.left) * k;
      const i = Math.max(0, Math.min(11, Math.round((px - m.l) / (W - m.l - m.r) * 11)));
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
      tip.replaceChildren();
      const hd = document.createElement('strong'); hd.textContent = `${i + 1}월`; tip.appendChild(hd);
      [...series].reverse().forEach(s => { const d = document.createElement('div'); const kk = document.createElement('span'); kk.className = 'k'; kk.style.background = s.color; d.appendChild(kk); d.appendChild(document.createTextNode(`${s.y}년 ${s.vals[i] == null ? '-' : n1(s.vals[i]) + '원/kg'}`)); tip.appendChild(d); });
      tip.style.display = 'block'; tip.style.left = Math.min(X(i) / k + 12, r.width - 180) + 'px'; tip.style.top = '10px';
    });
    svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; cross.setAttribute('visibility', 'hidden'); });
  }

  /* ---------------------------------------------------------------- ② 매각입찰 */
  let BIDS = [], SCOPE = 'focus', PERIOD = 365;
  const CAT_COLORS = { 'PET': '#2a78d6', '폐비닐': '#eb6834', '스티로폼': '#1baf7a' };
  const inScope = b => SCOPE === 'all' ? true : SCOPE === 'cap' ? (b.region === '중점' || b.region === '수도권') : b.region === '중점';
  const dayMs = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;

  function renderBids() {
    const cut = Date.now() - PERIOD * 864e5;
    const rows = BIDS.filter(b => inScope(b) && b.start && dayMs(b.start) >= cut);
    const done = rows.filter(b => /낙찰|유찰/.test(b.status || ''));
    const won = rows.filter(b => b.win_unit_price);
    // 유찰·취소 후 재공고된 같은 물량이 겹치지 않도록 낙찰됐거나 진행 중인 공고만 합산
    const live = rows.filter(b => !/유찰|취소/.test(b.status || ''));
    const tons = live.reduce((s, b) => s + (b.qty_kg || 0), 0) / 1000;
    const pre = rows.map(b => b.pre_unit_price).filter(v => v);
    const ratio = rows.map(b => b.win_ratio).filter(v => v && v < 1000);
    const catAvg = c => { const v = won.filter(b => b.cat === c).map(b => b.win_unit_price); return v.length ? `${n0(mean(v))}원/kg` : '-'; };
    const catN = c => won.filter(b => b.cat === c).length;
    $('bidKpi').innerHTML = [
      ['신규 공고', `${rows.length}건`, `개찰 완료 ${done.length}건 · 유찰 ${done.filter(b => /유찰/.test(b.status)).length}건`],
      ['공고 물량', tons ? `${n0(tons)}톤` : '-', '낙찰·진행 중 공고 합계 (재공고 중복 제외)'],
      ['평균 예정단가', pre.length ? `${n0(mean(pre))}원/kg` : '-', `예정가격 공개 ${pre.length}건`],
      ['낙찰/예정가격', ratio.length ? `${n1(mean(ratio))}%` : '-', `비율 계산 가능 ${ratio.length}건`],
      ['PET 낙찰단가', catAvg('PET'), `${catN('PET')}건 평균`],
      ['폐비닐 낙찰단가', catAvg('폐비닐'), `${catN('폐비닐')}건 평균`],
      ['스티로폼 낙찰단가', catAvg('스티로폼'), `${catN('스티로폼')}건 평균`]
    ].map(([a, b, c]) => `<div class="kpi"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
    drawBidChart(won);
    const list = rows.slice(0, 20);
    $('bidBody').innerHTML = list.map(b => {
      const reg = b.region === '중점' ? `<span class="reg f">${esc(b.city)}</span>` : b.region === '수도권' ? `<span class="reg">${esc(b.city)}</span>` : `<span class="reg">${esc(b.city || '기타')}</span>`;
      const res = b.win_unit_price ? `<b>${n0(b.win_unit_price)}</b>원/kg` : b.win_amt ? `${n0(b.win_amt / 1e4)}만원` : esc(b.status || '-');
      return `<tr><td>${esc((b.start || '').slice(2).replace(/-/g, '.'))}</td><td>${reg}</td><td class="t h-m">${esc(b.org)}</td>
        <td class="t"><a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.title)}</a></td><td class="h-m">${esc(b.cat)}</td>
        <td>${b.qty_kg ? n0(b.qty_kg / 1000) + '톤' : '-'}</td><td class="h-m">${b.pre_unit_price ? n0(b.pre_unit_price) + '원/kg' : b.pre_amt ? '공개' : '비공개'}</td>
        <td>${res}${b.win_ratio && b.win_ratio < 1000 ? `<small class="fl"> (${n1(b.win_ratio)}%)</small>` : ''}</td><td class="h-m">${esc(b.src === '나라장터' ? '나라장터' : '순환자원')}</td></tr>`;
    }).join('') || '<tr><td colspan="9" class="fl">해당 기간·지역의 플라스틱 매각 공고가 없습니다.</td></tr>';
  }

  function drawBidChart(won) {
    const box = $('bidChart'); box.innerHTML = '';
    const pts = won.filter(b => b.open || b.start).map(b => ({ t: dayMs(b.open || b.start), y: b.win_unit_price, b }));
    if (pts.length < 2) { box.innerHTML = '<div class="note">낙찰 단가가 공개된 공고가 아직 적어 추이를 그리지 않았습니다.</div>'; return; }
    const W = Math.max(300, box.clientWidth), H = 200, m = { l: 46, r: 16, t: 10, b: 24 };
    const t0 = Math.min(...pts.map(p => p.t)), t1 = Date.now();
    const tk = niceTicks(0, Math.max(...pts.map(p => p.y)), 4), y1 = tk[tk.length - 1];
    const X = t => m.l + (t - t0) / (t1 - t0 || 1) * (W - m.l - m.r), Y = v => m.t + (1 - v / y1) * (H - m.t - m.b);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': '매각 낙찰 단가 추이' }, box);
    tk.forEach(v => { el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: '#e5e7eb' }, svg); txt(svg, m.l - 6, Y(v) + 4, n0(v), { 'text-anchor': 'end' }); });
    const d0 = new Date(t0); for (let y = d0.getUTCFullYear(); y <= new Date().getFullYear(); y++) for (const mo of [1, 7]) {
      const t = Date.UTC(y, mo - 1, 1); if (t < t0 || t > t1) continue; txt(svg, X(t), H - 6, mo === 1 ? `${y}` : `${String(y).slice(2)}.7`, { 'text-anchor': 'middle' });
    }
    const hits = [];
    pts.forEach(p => { const c = CAT_COLORS[p.b.cat] || '#94a3b8'; el('circle', { cx: X(p.t), cy: Y(p.y), r: 4.5, fill: c, stroke: '#fff', 'stroke-width': 1.5, 'fill-opacity': 0.9 }, svg); hits.push({ x: X(p.t), y: Y(p.y), p, c }); });
    $('bidLegend').innerHTML = Object.entries(CAT_COLORS).map(([k, c]) => `<span><b style="background:${c}"></b>${k}</span>`).join('') + '<span><b style="background:#94a3b8"></b>기타·일괄</span>';
    const tip = document.createElement('div'); tip.className = 'rp-tip'; box.appendChild(tip);
    svg.addEventListener('pointermove', ev => {
      const r = svg.getBoundingClientRect(), k = W / r.width, px = (ev.clientX - r.left) * k, py = (ev.clientY - r.top) * k;
      let best = null, bd = 28 * k; hits.forEach(h => { const dd = Math.hypot(h.x - px, h.y - py); if (dd < bd) { bd = dd; best = h; } });
      if (!best) { tip.style.display = 'none'; return; }
      const b = best.p.b; tip.replaceChildren();
      const s = document.createElement('strong'); s.textContent = `${n0(b.win_unit_price)}원/kg`; tip.appendChild(s);
      const d1 = document.createElement('div'); d1.textContent = `${b.cat} · ${b.city || b.region} · ${(b.open || b.start)}`; tip.appendChild(d1);
      const d2 = document.createElement('div'); d2.textContent = b.title; tip.appendChild(d2);
      tip.style.display = 'block'; tip.style.left = Math.min(best.x / k + 12, r.width - 290) + 'px'; tip.style.top = (best.y / k + 10) + 'px';
    });
    svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
    svg.addEventListener('click', ev => { /* 표에서 원문 확인 */ });
  }

  /* ---------------------------------------------------------------- ③ 제도 */
  function renderPolicy(facts, pol) {
    const badge = s => `<span class="badge ${s === '시행중' ? 'on' : s === '시행예정' ? 'soon' : 'plan'}">${esc(s)}</span>`;
    const recent = (pol && pol.events || []).filter(e => Date.now() - dayMs(e.date) < 14 * 864e5);
    $('polAlert').innerHTML = recent.length ? `<div class="alert"><b>최근 2주 제도 변경 감지 ${recent.length}건</b>${recent.map(e =>
      `<div>· ${esc(e.date.slice(5).replace('-', '.'))} [${esc(e.type)}] <a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a></div>`).join('')}</div>` : '';
    const order = ['재생원료 의무', 'EPR', '부담금·기타'];
    $('polBody').innerHTML = (facts || []).slice().sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group)).map(f =>
      `<tr><td class="h-m">${esc(f.group)}</td><td class="l"><b>${esc(f.item)}</b></td><td class="d">${esc(f.detail)}</td><td>${badge(f.status)}</td>
       <td>${esc(f.effective || '-')}</td><td class="h-m"><a href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">${esc((f.source_date || '').slice(0, 7) || '출처')}</a></td></tr>`).join('');
    const laws = Object.values((pol && pol.laws) || {}).sort((a, b) => (b.promulgated || '').localeCompare(a.promulgated || ''));
    $('polLaws').innerHTML = laws.length ? laws.map(l => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.name)}</a>
      <small> — ${esc(l.kind || '')} ${esc(l.promulgated || '')}${l.effective ? ` · 시행 ${esc(l.effective)}` : ''}</small></li>`).join('') : '<li class="fl">법령 감시 자료를 아직 받지 못했습니다.</li>';
    const posts = ((pol && pol.posts) || []).slice(0, 6);
    $('polPosts').innerHTML = posts.length ? posts.map(p => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a> <small>${esc(p.board)} ${esc(p.date || '')}</small></li>`).join('') : '<li class="fl">관련 게시글 없음</li>';
    $('polUpd').textContent = pol && pol.updated ? `감시 갱신 ${pol.updated}` : '';
  }

  /* ---------------------------------------------------------------- 시작 */

  /* ---------------------------------------------------------------- ②-2 선별·처리 대행 용역 */
  let SVC = [], SVC_SCOPE = 'cap', SVC_PERIOD = 365;
  const eok = v => v == null ? '-' : v >= 1e8 ? `${(v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}억원` : `${n0(v / 1e4)}만원`;
  function renderSvc() {
    const cut = Date.now() - SVC_PERIOD * 864e5;
    const rows = SVC.filter(b => (SVC_SCOPE === 'focus' ? b.region === '중점' : true) && b.start && dayMs(b.start) >= cut);
    const won = rows.filter(b => b.status === '낙찰' && b.win_amt);
    const live = rows.filter(b => b.end && dayMs(b.end) >= Date.now() - 864e5);
    const ests = rows.map(b => b.est).filter(v => v);
    const rates = won.map(b => b.win_rate).filter(v => v);
    $('svcKpi').innerHTML = [
      ['공고', `${rows.length}건`, `진행 중 ${live.length}건 · 낙찰 ${won.length}건`],
      ['추정가격 합계', ests.length ? eok(ests.reduce((a, b) => a + b, 0)) : '-', `추정가격 공개 ${ests.length}건`],
      ['낙찰금액 합계', won.length ? eok(won.reduce((a, b) => a + b.win_amt, 0)) : '-', `낙찰 ${won.length}건`],
      ['평균 낙찰률', rates.length ? `${n1(mean(rates))}%` : '-', '낙찰금액 ÷ 예정가격']
    ].map(([a, b, c]) => `<div class="kpi"><span>${a}</span><b>${b}</b><small>${c}</small></div>`).join('');
    $('svcBody').innerHTML = rows.slice(0, 25).map(b => {
      const reg = `<span class="reg${b.region === '중점' ? ' f' : ''}">${esc(b.city || '수도권')}</span>`;
      const res = b.status === '낙찰' && b.win_amt ? `<b>${eok(b.win_amt)}</b>${b.win_rate ? `<small class="fl"> (${n1(b.win_rate)}%)</small>` : ''}<small class="fl" style="display:block">${esc(b.winner || '')}</small>`
        : live.includes(b) ? `<b class="up">진행 중</b><small class="fl" style="display:block">마감 ${esc((b.end || '').slice(5).replace('-', '.'))}</small>` : esc(b.status || '-');
      return `<tr><td>${esc((b.start || '').slice(2).replace(/-/g, '.'))}</td><td>${reg}</td><td class="t h-m">${esc(b.org)}</td>
        <td class="t"><a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">${esc(b.title)}</a></td><td class="h-m">${esc(b.type)}</td>
        <td>${eok(b.est)}</td><td>${res}</td><td class="h-m">${esc(b.src === '나라장터' ? '나라장터' : '순환자원')}</td></tr>`;
    }).join('') || '<tr><td colspan="8" class="fl">해당 기간·지역의 선별·처리 대행 용역 공고가 없습니다.</td></tr>';
  }
  getJson('data/services.json').then(j => {
    SVC = j.items || [];
    $('svcUpd').textContent = j.updated ? `갱신 ${j.updated}` : '';
    renderSvc();
  }).catch(() => { $('svcBody').innerHTML = '<tr><td colspan="8" class="fl">용역 자료를 아직 받지 못했습니다.</td></tr>'; });
  const segSvc = (id, fn) => document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(`#${id} button`).forEach(x => x.classList.toggle('on', x === b)); fn(b.dataset.v); renderSvc();
  }));
  segSvc('svcScope', v => SVC_SCOPE = v);
  segSvc('svcPeriod', v => SVC_PERIOD = +v);

  getJson('data/recycle_history.json').then(h => { HIST = h; renderAnalysis(); }).catch(() => { $('anaBody').innerHTML = '<tr><td colspan="8" class="fl">자료 없음</td></tr>'; });
  getJson('data/bids.json').then(j => {
    BIDS = (j.bids || []).filter(b => b.start);
    $('bidUpd').textContent = j.updated ? `갱신 ${j.updated} · 누적 ${BIDS.length}건` : '';
    renderBids();
  }).catch(() => { $('bidBody').innerHTML = '<tr><td colspan="9" class="fl">입찰 자료를 아직 받지 못했습니다.</td></tr>'; });
  Promise.all([getJson('data/policy_facts.json').catch(() => []), getJson('data/policy.json').catch(() => null)]).then(([f, p]) => renderPolicy(f, p));
  document.querySelectorAll('#bidScope button').forEach(b => b.addEventListener('click', () => {
    SCOPE = b.dataset.v; document.querySelectorAll('#bidScope button').forEach(x => x.classList.toggle('on', x === b)); renderBids();
  }));
  document.querySelectorAll('#bidPeriod button').forEach(b => b.addEventListener('click', () => {
    PERIOD = +b.dataset.v; document.querySelectorAll('#bidPeriod button').forEach(x => x.classList.toggle('on', x === b)); renderBids();
  }));
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (HIST) drawSeason(); if (BIDS.length) renderBids(); }, 150); });
})();
