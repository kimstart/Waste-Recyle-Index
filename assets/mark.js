/* 표 행 강조·공유 (폐플라스틱·바이오가스 공통) — 표를 그리는 스크립트보다 먼저 불러온다.
   ① 오늘(KST) '최근 업데이트'(data/data_updates.json) 소식에 담긴 공고 id → 신규 공고는 행 전체, 새 결과는 결과 칸을 붉게.
   ② 결과 칸에 마우스를 올리면 공유 버튼 → 결과 문구 + 인포보드 해당 행 링크(?hl=id#섹션)를 공유하거나 복사.
   ③ ?hl= 로 들어오면 그 행으로 내려가 잠시 깜빡인다.
   표 스크립트가 할 일: <tr data-id="공고 id">, 결과 칸 <td class="res">, 공유 문구는 Board.share(섹션 id, id => {head, lines, ids}) 로 등록,
   목록을 자를 때 Board.pin(잘린 목록, 전체 목록) 으로 ?hl= 행을 끼워 넣는다. */
(function () {
  const me = document.currentScript, PAGE = me && me.dataset.page;
  const q = new URLSearchParams(location.search);
  const HL = new Set((q.get('hl') || '').split(',').map(s => s.trim()).filter(Boolean));
  const NEW = new Set(), RES = new Set(), SHARE = {};
  const Board = window.Board = {
    hl: id => HL.has(String(id)),
    pin: (list, all) => {
      if (!HL.size) return list;
      const have = new Set(list.map(b => String(b.id)));
      return list.concat(all.filter(b => HL.has(String(b.id)) && !have.has(String(b.id))));
    },
    share: (sec, fn) => { SHARE[sec] = fn; schedule(); }
  };

  // 숫자: 소수점이 있으면 한 자리까지
  Board.num = v => Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 1 });
  // 기관명 줄이기: '경기도 수원시' → '수원시', '서울특별시 양천구' → '서울 양천구'
  Board.org = o => {
    o = String(o || '').trim();
    let m = o.match(/^(서울|부산|대구|인천|광주|대전|울산)(?:특별시|광역시)\s+(\S+[구군])$/);
    if (m) return `${m[1]} ${m[2]}`;
    m = o.match(/^\S+도\s+(\S+[시군])(?:\s+(\S+구))?$/);
    if (m) return m[1] + (m[2] ? ' ' + m[2] : '');
    return o;
  };
  Board.ymd = d => String(d || '').slice(0, 10).replace(/-/g, '');

  // 오늘 소식의 id
  const today = new Date(Date.now() + 9 * 36e5).toISOString().slice(0, 10);
  fetch('data/data_updates.json?t=' + Date.now()).then(r => r.ok ? r.json() : null).then(j => {
    ((j && j.events) || []).filter(e => e.date === today && (!PAGE || e.page === PAGE) && e.ids).forEach(e =>
      e.ids.forEach(id => (e.mark === 'res' ? RES : NEW).add(String(id))));
    schedule();
  }).catch(() => {});

  // 표가 다시 그려질 때마다(필터 변경 등) 강조·공유 버튼을 다시 붙인다
  let pend = false, flashed = false;
  function schedule() { if (!pend) { pend = true; requestAnimationFrame(() => { pend = false; apply(); }); } }
  function secOf(tr) {
    const navs = [...document.querySelectorAll('[data-nav][id]')];
    let id = null;
    for (const n of navs) if (n.compareDocumentPosition(tr) & Node.DOCUMENT_POSITION_FOLLOWING || n.contains(tr)) id = n.id;
    return id;
  }
  function apply() {
    document.querySelectorAll('tr[data-id]').forEach(tr => {
      const id = tr.dataset.id, res = tr.querySelector('td.res');
      tr.classList.toggle('mk-new', NEW.has(id));
      if (NEW.has(id) && !tr.querySelector('.mk-badge')) {
        const t = tr.querySelector('td.t:not(.h-m)') || tr.querySelector('td.t');
        if (t) t.insertAdjacentHTML('afterbegin', '<span class="mk-badge" title="오늘 새로 올라온 공고">NEW</span>');
      }
      if (res) {
        res.classList.toggle('mk-res', RES.has(id));
        if (RES.has(id)) res.title = '오늘 나온 결과';
        const sec = tr.dataset.sec || (tr.dataset.sec = secOf(tr) || '');
        const fn = SHARE[sec];
        if (fn && !res.querySelector('.shr')) {
          let ok = null;
          try { ok = fn(id); } catch (e) { ok = null; }
          if (ok) res.insertAdjacentHTML('beforeend', '<button type="button" class="shr" title="결과 공유·복사" aria-label="결과 공유"><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v13"/></svg></button>');
        }
      }
    });
    if (HL.size && !flashed) {
      const rows = [...document.querySelectorAll('tr[data-id]')].filter(tr => HL.has(tr.dataset.id));
      if (rows.length) {
        flashed = true;
        const navOff = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--navOff')) || 120;
        const go = () => window.scrollTo({ top: rows[0].getBoundingClientRect().top + window.scrollY - navOff - 40, behavior: 'auto' });
        go(); setTimeout(go, 600); setTimeout(go, 1600);
        rows.forEach(tr => { tr.classList.add('mk-flash'); setTimeout(() => tr.classList.remove('mk-flash'), 6000); });
      }
    }
  }
  new MutationObserver(muts => { if (muts.some(m => [...m.addedNodes].some(n => n.nodeType === 1 && (n.matches('tr') || n.querySelector && n.querySelector('tr[data-id]'))))) schedule(); })
    .observe(document.body, { childList: true, subtree: true });

  // 점이 찍힌 탭을 누르면 그 섹션의 첫 강조 행으로
  document.addEventListener('click', ev => {
    const a = ev.target.closest('.secnav a');
    if (!a || a.querySelector('.dot[hidden]')) return;
    const r = [...document.querySelectorAll('tr.mk-new, td.mk-res')].map(x => x.closest('tr')).find(tr => (tr.dataset.sec || secOf(tr)) === a.dataset.id);
    if (!r) return;
    const navOff = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--navOff')) || 120;
    setTimeout(() => window.scrollTo({ top: r.getBoundingClientRect().top + window.scrollY - navOff - 40, behavior: 'smooth' }), 0);
  });

  // 공유
  let toastT;
  function toast(t) {
    let el = document.querySelector('.mk-toast');
    if (!el) { el = document.createElement('div'); el.className = 'mk-toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
    el.textContent = t; el.classList.add('on');
    clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('on'), 2200);
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise((ok, no) => {
      const ta = document.createElement('textarea'); ta.value = text; ta.style.cssText = 'position:fixed;opacity:0;top:0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy') ? ok() : no(); } catch (e) { no(e); } finally { ta.remove(); }
    });
  }
  document.addEventListener('click', ev => {
    const btn = ev.target.closest('.shr');
    if (!btn) return;
    ev.preventDefault(); ev.stopPropagation();
    const tr = btn.closest('tr[data-id]'), fn = SHARE[tr.dataset.sec];
    const s = fn && fn(tr.dataset.id);
    if (!s) return;
    const url = `${location.origin}${location.pathname}?hl=${(s.ids || [tr.dataset.id]).map(i => encodeURIComponent(i).replace(/%3A/gi, ':')).join(',')}#${tr.dataset.sec}`;
    const text = [s.head, ...s.lines].join('\n');
    const mobile = window.matchMedia('(pointer:coarse)').matches;
    if (mobile && navigator.share) {
      navigator.share({ text: text + '\n' + url }).catch(() => {});
    } else {
      copy(text + '\n' + url).then(() => toast('결과를 복사했습니다 — 메신저·메일에 붙여넣으세요')).catch(() => toast('복사하지 못했습니다'));
    }
  });
})();
