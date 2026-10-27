/* 섹션 바로가기 탭 (폐플라스틱·바이오가스 공통)
   data-nav="탭 이름" 이 붙은 요소(id 필수)를 순서대로 모아 헤더 아래 고정 탭을 만든다.
   data-dot="정규식" 이 있으면 오늘 '최근 업데이트'(data/data_updates.json) 소식 중 이 화면·이 정규식에 맞는 것이 있을 때 탭에 점을 찍는다.
   script 태그의 data-page(plastic|biogas)로 화면을 구분한다. */
(function () {
  const me = document.currentScript, PAGE = me.dataset.page;
  const secs = [...document.querySelectorAll('[data-nav][id]')];
  const header = document.querySelector('.site-header');
  if (!secs.length || !header) return;
  const nav = document.createElement('nav');
  nav.className = 'secnav';
  nav.setAttribute('aria-label', '섹션 바로가기');
  nav.innerHTML = `<div class="in">${secs.map(s => `<a href="#${s.id}" data-id="${s.id}">${s.dataset.nav}<i class="dot" hidden></i></a>`).join('')}</div>`;
  header.insertAdjacentElement('afterend', nav);
  const links = [...nav.querySelectorAll('a')];

  // 고정 위치: PC는 헤더(고정) 아래, 모바일은 헤더가 고정이 아니므로 맨 위
  function layout() {
    const sticky = getComputedStyle(header).position === 'sticky';
    const top = sticky ? header.offsetHeight : 0;
    document.documentElement.style.setProperty('--navTop', top + 'px');
    document.documentElement.style.setProperty('--navOff', (top + nav.offsetHeight + 10) + 'px');
  }
  layout();
  window.addEventListener('resize', layout);

  // 현재 보고 있는 섹션 표시
  let cur = null;
  function mark() {
    const off = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--navOff')) || 120;
    let id = secs[0].id;
    for (const s of secs) if (s.getBoundingClientRect().top - off <= 4) id = s.id;
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) id = secs[secs.length - 1].id;
    if (id === cur) return;
    cur = id;
    links.forEach(a => a.classList.toggle('on', a.dataset.id === id));
    const a = links.find(a => a.dataset.id === id), box = nav.querySelector('.in');
    if (a && box.scrollWidth > box.clientWidth) box.scrollTo({ left: a.offsetLeft - box.clientWidth / 2 + a.offsetWidth / 2, behavior: 'smooth' });
  }
  let tick = false;
  window.addEventListener('scroll', () => { if (!tick) { tick = true; requestAnimationFrame(() => { mark(); tick = false; }); } }, { passive: true });
  mark();

  // 누르면 부드럽게 이동하고 주소 끝(#섹션)만 바꾼다
  const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  links.forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    const t = document.getElementById(a.dataset.id);
    t.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
    history.replaceState(null, '', '#' + a.dataset.id);
  }));
  // #섹션 주소로 들어오면 표가 다 그려진 뒤 다시 맞춘다
  if (location.hash && document.getElementById(location.hash.slice(1))) {
    const go = () => document.getElementById(location.hash.slice(1)).scrollIntoView({ block: 'start' });
    window.addEventListener('load', () => { go(); setTimeout(go, 1200); setTimeout(go, 3000); });
  }

  // 탭 알림 점: 오늘 새 소식이 있는 섹션
  const today = new Date(Date.now() + 9 * 36e5).toISOString().slice(0, 10);
  fetch('data/data_updates.json?t=' + Date.now()).then(r => r.ok ? r.json() : null).then(j => {
    const ev = ((j && j.events) || []).filter(e => e.date === today && (!PAGE || e.page === PAGE));
    secs.forEach((s, i) => {
      if (!s.dataset.dot) return;
      const rx = new RegExp(s.dataset.dot);
      const hit = ev.filter(e => rx.test(e.text || ''));
      const dot = links[i].querySelector('.dot');
      if (hit.length) { dot.hidden = false; links[i].title = `오늘 새 소식 ${hit.length}건: ${hit.map(e => e.text).join(' / ')}`; }
    });
  }).catch(() => {});
})();
