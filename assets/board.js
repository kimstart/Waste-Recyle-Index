/* 정보보드 공통 화면 스크립트. 각 페이지는 window.BOARD 설정만 다르게 준다.
   BOARD = { name, minKey, rows:[{cyc, key, dec, why}], extra(items) → HTML 문자열 } */
(function () {
  const B = window.BOARD;
  const kst = new Date(Date.now() + 9 * 3600 * 1000);
  const TODAY = kst.toISOString().slice(0, 10).replace(/-/g, '');
  const dowOf = k => '일월화수목금토'[new Date(Date.UTC(+k.slice(0, 4), +k.slice(4, 6) - 1, +k.slice(6, 8))).getUTCDay()];
  const fmtLong = k => `${k.slice(0, 4)}년 ${+k.slice(4, 6)}월 ${+k.slice(6, 8)}일(${dowOf(k)})`;
  const dash = k => `${k.slice(0, 4)}-${k.slice(4, 6)}-${k.slice(6, 8)}`;
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const getJson = u => fetch(u + (u.includes('?') ? '&' : '?') + 't=' + Date.now()).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
  const fmt = (v, dec) => v == null || isNaN(v) ? '-' : Number(v).toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const $ = id => document.getElementById(id);

  function fmtDate(d) {
    if (!d) return '-';
    if (/^\d{4}-\d{2}$/.test(d)) return `${d.slice(0, 4)}년 ${+d.slice(5, 7)}월`;
    const k = d.replace(/-/g, '');
    return `${+k.slice(4, 6)}.${+k.slice(6, 8)}(${dowOf(k)})` + (k.slice(0, 4) !== TODAY.slice(0, 4) ? `<small>${k.slice(0, 4)}</small>` : '');
  }
  function shortPrev(d) {
    if (!d) return '';
    if (/^\d{4}-\d{2}$/.test(d)) return `${+d.slice(5, 7)}월 대비`;
    const k = d.replace(/-/g, '');
    return `${+k.slice(4, 6)}.${+k.slice(6, 8)} 대비`;
  }
  function spark(arr) {
    if (!arr || arr.length < 3) return '';
    const w = 84, h = 20, mn = Math.min(...arr), mx = Math.max(...arr), r = (mx - mn) || 1;
    const pts = arr.map((v, i) => `${(i / (arr.length - 1) * w).toFixed(1)},${(h - 2 - (v - mn) / r * (h - 4)).toFixed(1)}`).join(' ');
    const up = arr[arr.length - 1] >= arr[0];
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="최근 추이"><polyline fill="none" stroke="${up ? '#d93f3c' : '#005587'}" stroke-width="1.5" points="${pts}"/></svg>`;
  }
  B.fmt = fmt;

  function renderTable(st) {
    const items = (st && st.items) || {};
    B.items = items;
    $('indUpdated').textContent = st && st.updated ? st.updated + ' (KST)' : '-';
    renderRows(B.rows.filter(r => !r.sec), 'indBody', items);
    if ($('refBody')) renderRows(B.rows.filter(r => r.sec === 'ref'), 'refBody', items);
    if (B.extra && $('extra')) $('extra').innerHTML = B.extra(items, fmt) || '';
    document.dispatchEvent(new CustomEvent('board:items', { detail: items }));
  }

  function renderRows(rows, bodyId, items) {
    // grp: 같은 주기라도 묶음을 나눌 때 쓰는 이름(없으면 cyc)
    const span = {}; rows.forEach(r => { const g = r.grp || r.cyc; span[g] = (span[g] || 0) + 1; });
    const seen = {};
    $(bodyId).innerHTML = rows.map(r => {
      const it = items[r.key], g = r.grp || r.cyc;
      const first = !seen[g]; seen[g] = true;
      const cyc = first ? `<td class="cyc" rowspan="${span[g]}">${r.cyc}<span>${B.cycNote[g] || ''}</span></td>` : '';
      let sub = esc([it && it.item, it ? it.unit : r.unit].filter(Boolean).join(' · '));
      if (it && it.url) sub = `<a href="${esc(it.url)}" target="_blank" rel="noopener noreferrer">${sub}</a>`;
      if (it && it.auto) sub += ' · 자동 추출';
      const nm = `<td class="nm">${esc(it ? it.name : r.label)}<small>${sub}</small><span class="note-m">${esc(r.why)}</span></td>`;
      const why = `<td class="why">${esc(r.why)}${it && it.basis ? ` <b>(${esc(it.basis)})</b>` : ''}</td>`;
      const cls = first && Object.keys(seen).length > 1 ? ' class="sep"' : '';
      if (!it) return `<tr${cls}>${cyc}${nm}<td colspan="3" class="fl">${esc(r.empty || '자료 없음')}</td>${why}</tr>`;
      let chg = '<span class="fl">-</span>';
      if (it.prev_value != null && it.prev_value !== 0) {
        const d = it.value - it.prev_value, p = d / it.prev_value * 100, c = d > 0 ? 'up' : d < 0 ? 'dn' : 'fl', ar = d > 0 ? '▲' : d < 0 ? '▼' : '-';
        chg = `<span class="${c}">${ar} ${fmt(Math.abs(d), r.dec)} (${p >= 0 ? '+' : ''}${p.toFixed(1)}%)</span><small>${shortPrev(it.prev_date)}</small>`;
      } else if (r.cyc === '월간') {
        chg = '<span class="fl">-</span><small>다음 달부터 표시</small>';
      }
      if (it.yoy_value != null && it.yoy_value !== 0) {
        const p = (it.value - it.yoy_value) / it.yoy_value * 100, c = p > 0 ? 'up' : p < 0 ? 'dn' : 'fl';
        chg += `<small class="yoy">전년 동월 <span class="${c}">${p >= 0 ? '+' : ''}${p.toFixed(1)}%</span></small>`;
      }
      const krw = it.krw_kg != null ? `<span class="krw">≈ ${fmt(it.krw_kg, 0)} 원/kg</span>`
        : it.krw_m3 != null ? `<span class="krw">≈ ${fmt(it.krw_m3, 0)} 원/㎥</span>` : '';
      return `<tr${cls}>${cyc}${nm}<td class="v">${fmt(it.value, r.dec)}${krw}${spark(it.spark)}</td><td class="d">${fmtDate(it.date)}</td><td class="chg">${chg}</td>${why}</tr>`;
    }).join('');
  }

  function renderNews(nj) {
    const list = (arr, empty) => !arr || !arr.length ? `<li class="fl">${empty}</li>` : arr.map(x => {
      const t = x.pub ? `${+x.pub.slice(5, 7)}.${+x.pub.slice(8, 10)} ${x.pub.slice(11, 16)}` : '';
      const more = x.more > 0 ? ` · 유사 기사 ${x.more}건` : '';
      const sum = x.summary ? `<span class="sum">${esc(x.summary)}</span>` : '';
      return `<li><a href="${esc(x.link)}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a>${sum}<span class="meta">${esc(x.source)}${t ? ' · ' + t : ''}${more}</span></li>`;
    }).join('');
    $('newsUpd').textContent = nj && nj.updated ? '갱신 ' + nj.updated : '';
    $('newsKo').innerHTML = list(nj && nj.domestic, '해당 일자의 국내 뉴스 자료가 없습니다.');
    $('newsEn').innerHTML = list(nj && nj.overseas, '해당 일자의 해외 뉴스 자료가 없습니다.');
  }

  let SEQ = 0;
  async function show(key) {
    const my = ++SEQ;
    $('baseDate').textContent = fmtLong(key);
    $('viewDate').value = dash(key);
    $('btnToday').style.display = key === TODAY ? 'none' : '';
    const pn = $('pastNote');
    if (key === TODAY) pn.style.display = 'none'; else { pn.style.display = 'block'; pn.textContent = `${fmtLong(key)}에 저장된 자료를 보고 있습니다.`; }
    $('indBody').innerHTML = `<tr><td colspan="6" class="fl">불러오는 중...</td></tr>`;
    const isToday = key === TODAY;
    const [st, nj] = await Promise.all([
      getJson(isToday ? `data/${B.name}.json` : `history/${B.name}_${key}.json`).catch(() => null),
      getJson(isToday ? `data/news_${B.name}.json` : `history/news_${B.name}_${key}.json`).catch(() => null)
    ]);
    if (my !== SEQ) return;
    if (!st) { $('indBody').innerHTML = `<tr><td colspan="6" class="fl">${isToday ? '아직 수집된 자료가 없습니다.' : '해당 일자에 저장된 자료가 없습니다.'}</td></tr>`; if ($('extra')) $('extra').innerHTML = ''; }
    else renderTable(st);
    renderNews(nj);
  }

  function renderUpdates(list) {
    const box = $('updBox');
    if (!box) return;
    const mine = (list || []).filter(x => !x.page || x.page === 'all' || x.page === B.name)
      .sort((a, b) => b.date.localeCompare(a.date));
    if (!mine.length) { box.style.display = 'none'; return; }
    const md = d => `${+d.slice(5, 7)}.${+d.slice(8, 10)}`;
    const li = arr => arr.map(x => `<li><span>${md(x.date)}</span>${esc(x.text)}</li>`).join('');
    box.innerHTML = `<b>최근 업데이트</b><ul>${li(mine.slice(0, 3))}</ul>` +
      (mine.length > 3 ? `<details><summary>이전 내용 ${mine.length - 3}건</summary><ul>${li(mine.slice(3, 15))}</ul></details>` : '');
  }
  getJson('data/changelog.json').then(renderUpdates).catch(() => renderUpdates([]));

  const inp = $('viewDate');
  inp.min = dash(B.minKey); inp.max = dash(TODAY);
  inp.addEventListener('change', () => { if (inp.value) show(inp.value.replace(/-/g, '')); });
  $('btnToday').addEventListener('click', () => show(TODAY));
  show(TODAY);
})();
