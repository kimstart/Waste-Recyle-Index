/* rPET 가격 (기사 기준) 차트·표 — data/rpet.json 을 읽어 그린다.
   x축: 기사 게재일, y축: 기사일 환율로 환산한 원/kg. 색은 지역, 속이 빈 점은 자동 추출. */
(function () {
  const COLORS = { '유럽': '#2a78d6', '아시아': '#eb6834', '북미': '#1baf7a', '국내': '#eda100' };
  const REGIONS = ['유럽', '아시아', '북미', '국내'];
  const GRADES = ['식품용 펠렛', '플레이크', '베일'];
  const SYM = { EUR: '€', USD: '$', GBP: '£', KRW: '', CNY: '' };
  const PER = { t: '톤', kg: 'kg', lb: 'lb' };
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const n0 = v => v == null ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const nv = v => v == null ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: v < 10 ? 4 : v < 100 ? 2 : 0 });
  const day = s => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  const dot = s => `${s.slice(0, 4)}.${+s.slice(5, 7)}.${+s.slice(8, 10)}`;
  let PTS = [], GRADE = '식품용 펠렛';

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(parent, x, y, s, attrs) {
    const t = el('text', Object.assign({ x, y, 'font-size': 11, fill: '#64748b' }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function priceText(p) {
    const u = `${p.cur === 'KRW' ? '원' : p.cur === 'CNY' ? '위안' : ''}/${PER[p.per] || p.per}`;
    const v = p.low === p.high ? nv(p.low) : `${nv(p.low)}~${nv(p.high)}`;
    return `${SYM[p.cur] || ''}${v}${u}`;
  }
  function niceTicks(lo, hi, n) {
    const span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || mag * 10;
    const a = Math.floor(lo / step) * step, out = [];
    for (let v = a; v <= hi + step * 0.001; v += step) out.push(+v.toFixed(6));
    if (out[out.length - 1] < hi) out.push(out[out.length - 1] + step);
    return out;
  }

  /* 공통: 시간축 점 차트. series=[{name,color,pts:[{t,y,lo,hi,p}]}] */
  function drawChart(box, series, opt) {
    box.innerHTML = '';
    const W = Math.max(300, box.clientWidth), H = opt.height, m = { l: 52, r: 54, t: 10, b: 26 };
    const all = series.flatMap(s => s.pts);
    const tip = document.createElement('div'); tip.className = 'rp-tip'; box.appendChild(tip);
    if (!all.length) { box.insertAdjacentHTML('afterbegin', `<div class="note">${opt.empty}</div>`); return; }
    const t0 = day('2023-01-01'), t1 = Date.now();
    let ylo = Math.min(...all.map(d => d.lo != null ? d.lo : d.y)), yhi = Math.max(...all.map(d => d.hi != null ? d.hi : d.y));
    if (opt.zero) { ylo = Math.min(0, ylo); yhi = Math.max(0, yhi); }
    const ticks = niceTicks(ylo, yhi, 4), y0 = ticks[0], y1 = ticks[ticks.length - 1];
    const X = t => m.l + (t - t0) / (t1 - t0) * (W - m.l - m.r), Y = v => m.t + (1 - (v - y0) / (y1 - y0)) * (H - m.t - m.b);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opt.label }, null);
    box.insertBefore(svg, tip);
    ticks.forEach(v => {
      el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: v === 0 && opt.zero ? '#94a3b8' : '#e5e7eb', 'stroke-width': 1 }, svg);
      txt(svg, m.l - 6, Y(v) + 4, n0(v), { 'text-anchor': 'end' });
    });
    for (let y = 2023; y <= new Date().getFullYear(); y++) {
      for (const mo of [1, 7]) {
        const t = Date.UTC(y, mo - 1, 1); if (t > t1) continue;
        el('line', { x1: X(t), x2: X(t), y1: H - m.b, y2: H - m.b + 4, stroke: '#cbd5e1' }, svg);
        txt(svg, X(t), H - 8, mo === 1 ? `${y}` : `${String(y).slice(2)}.7`, { 'text-anchor': 'middle', fill: mo === 1 ? '#334155' : '#94a3b8' });
      }
    }
    const hits = [];
    series.forEach(s => {
      const pts = s.pts.slice().sort((a, b) => a.t - b.t);
      if (pts.length > 1) el('polyline', { points: pts.map(d => `${X(d.t).toFixed(1)},${Y(d.y).toFixed(1)}`).join(' '), fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-opacity': 0.85 }, svg);
      pts.forEach(d => {
        if (d.lo != null && d.hi != null && Y(d.lo) - Y(d.hi) > 3) el('line', { x1: X(d.t), x2: X(d.t), y1: Y(d.lo), y2: Y(d.hi), stroke: s.color, 'stroke-width': 1.5, 'stroke-opacity': 0.45, 'stroke-linecap': 'round' }, svg);
        const auto = d.p && d.p.auto;
        el('circle', { cx: X(d.t), cy: Y(d.y), r: 4, fill: auto ? '#fff' : s.color, stroke: auto ? s.color : '#fff', 'stroke-width': 2 }, svg);
        hits.push({ x: X(d.t), y: Y(d.y), d, s });
      });
      const last = pts[pts.length - 1];
      if (last && opt.endLabel) txt(svg, X(last.t) + 8, Y(last.y) + 4, opt.endLabel(s, last), { fill: '#334155', 'font-weight': 700 });
    });
    const ring = el('circle', { r: 7, fill: 'none', stroke: '#0f172a', 'stroke-width': 1.5, visibility: 'hidden' }, svg);
    let cur = null;
    const pick = ev => {
      const r = svg.getBoundingClientRect(), k = W / r.width, px = (ev.clientX - r.left) * k, py = (ev.clientY - r.top) * k;
      let best = null, bd = 30 * k;
      hits.forEach(h => { const dd = Math.hypot(h.x - px, h.y - py); if (dd < bd) { bd = dd; best = h; } });
      return best;
    };
    svg.addEventListener('pointermove', ev => {
      const h = pick(ev); cur = h;
      if (!h) { tip.style.display = 'none'; ring.setAttribute('visibility', 'hidden'); svg.style.cursor = ''; return; }
      ring.setAttribute('cx', h.x); ring.setAttribute('cy', h.y); ring.setAttribute('visibility', 'visible');
      svg.style.cursor = h.d.p && h.d.p.url ? 'pointer' : '';
      tip.replaceChildren();
      const st = document.createElement('strong'); st.textContent = opt.value(h.d); tip.appendChild(st);
      const l1 = document.createElement('div');
      const key = document.createElement('span'); key.className = 'k'; key.style.background = h.s.color; l1.appendChild(key);
      l1.appendChild(document.createTextNode(opt.line1(h.s, h.d))); tip.appendChild(l1);
      const p = h.d.p;
      if (p) {
        const l2 = document.createElement('div'); l2.textContent = `${dot(p.date)} · ${p.source}${p.auto ? ' · 자동 추출' : ''}`; tip.appendChild(l2);
        if (p.quote) { const q = document.createElement('q'); q.textContent = p.quote.length > 160 ? p.quote.slice(0, 160) + '…' : p.quote; tip.appendChild(q); }
      }
      const br = box.getBoundingClientRect(), k = W / svg.getBoundingClientRect().width;
      const left = Math.min(ev.clientX - br.left + 12, br.width - 296);
      tip.style.left = Math.max(0, left) + 'px'; tip.style.top = (h.y / k + 12) + 'px'; tip.style.display = 'block';
    });
    svg.addEventListener('pointerleave', () => { tip.style.display = 'none'; ring.setAttribute('visibility', 'hidden'); });
    svg.addEventListener('click', ev => { const h = pick(ev); if (h && h.d.p && h.d.p.url) window.open(h.d.p.url, '_blank', 'noopener'); });
  }

  function renderPrice() {
    const pts = PTS.filter(p => p.grade === GRADE && p.krw_kg != null);
    const series = REGIONS.map(r => ({ name: r, color: COLORS[r], pts: pts.filter(p => p.region === r).map(p => ({ t: day(p.date), y: p.krw_kg, lo: p.krw_low, hi: p.krw_high, p })) }))
      .filter(s => s.pts.length);
    $('rpLegend').innerHTML = series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join('') +
      `<span><b style="background:#475569"></b>기사 확인</span><span><b style="border:2px solid #475569;background:#fff"></b>자동 추출</span>`;
    drawChart($('rpChart'), series, {
      height: 260, label: `${GRADE} rPET 가격 추이 (원/kg)`, empty: '이 등급의 기사 가격이 아직 없습니다.',
      value: d => `${n0(d.y)} 원/kg`, line1: (s, d) => `${s.name} · ${GRADE} · ${priceText(d.p)}`,
      endLabel: (s, d) => s.name
    });
    const rows = pts.slice().sort((a, b) => b.date.localeCompare(a.date)).slice(0, 15);
    $('rpBody').innerHTML = rows.map(p => `<tr><td>${dot(p.date)}</td><td>${p.region}</td><td>${priceText(p)}</td><td><b>${n0(p.krw_kg)}</b></td>
      <td>${p.premium != null ? `${p.premium >= 0 ? '+' : '−'}${SYM[p.cur] || ''}${n0(Math.abs(p.premium))}` : '-'}</td>
      <td class="q"></td></tr>`).join('') || '<tr><td colspan="6" class="fl">기사 가격 없음</td></tr>';
    [...$('rpBody').querySelectorAll('td.q')].forEach((td, i) => {
      const p = rows[i], a = document.createElement('a');
      a.href = p.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = p.source;
      td.appendChild(a);
      if (p.auto) { const t = document.createElement('span'); t.className = 'tag-auto'; t.textContent = '자동'; td.appendChild(t); }
      td.appendChild(document.createTextNode(` — ${p.quote || p.title}`));
    });
  }

  function renderPremium() {
    const pts = PTS.filter(p => p.region === '유럽' && p.grade === '식품용 펠렛' && p.premium != null && p.cur === 'EUR' && p.per === 't');
    drawChart($('rpPrem'), [{ name: '유럽', color: COLORS['유럽'], pts: pts.map(p => ({ t: day(p.date), y: p.premium, p })) }], {
      height: 170, zero: true, label: '유럽 식품용 rPET 펠렛의 신재 PET 대비 프리미엄 (€/톤)', empty: '프리미엄을 보도한 기사가 없습니다.',
      value: d => `${d.y >= 0 ? '+' : '−'}€${n0(Math.abs(d.y))}/톤${d.p.premium_krw_kg != null ? ` (≈ ${n0(d.p.premium_krw_kg)}원/kg)` : ''}`,
      line1: (s, d) => `식품용 펠렛 ${priceText(d.p)}${d.p.virgin_low != null ? ` · 신재 €${n0(d.p.virgin_low)}${d.p.virgin_high !== d.p.virgin_low ? '~' + n0(d.p.virgin_high) : ''}/톤` : ''}`,
      endLabel: (s, d) => `€${n0(d.y)}`
    });
  }

  function render() { renderPrice(); renderPremium(); }

  document.querySelectorAll('#rpSeg button').forEach(b => b.addEventListener('click', () => {
    GRADE = b.dataset.g;
    document.querySelectorAll('#rpSeg button').forEach(x => x.classList.toggle('on', x === b));
    renderPrice();
  }));
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => PTS.length && render(), 150); });
  fetch('data/rpet.json?t=' + Date.now()).then(r => r.ok ? r.json() : null).then(j => {
    PTS = (j && j.points) || [];
    $('rpUpd').textContent = j && j.updated ? `갱신 ${j.updated} · 기사 ${PTS.length}건` : '';
    render();
  }).catch(() => { $('rpChart').innerHTML = '<div class="note">rPET 기사 가격 자료를 불러오지 못했습니다.</div>'; });
})();
