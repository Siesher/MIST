// Slide animations: typewriter, particles, slide-trigger machinery.

(function() {
  const stage = document.querySelector('deck-stage');
  if (!stage) return;

  // typewriter
  function typewriter(el) {
    if (el.dataset.typed === '1') return;
    const full = el.dataset.text || el.textContent;
    el.dataset.text = full;
    el.textContent = '';
    el.dataset.typed = '1';
    let i = 0;
    const speed = parseInt(el.dataset.speed || '28', 10);
    function step() {
      if (i <= full.length) {
        el.textContent = full.slice(0, i);
        i++;
        setTimeout(step, speed);
      } else {
        el.classList.add('typed-done');
      }
    }
    step();
  }

  // particle field
  function spawnParticles(canvas) {
    if (canvas.dataset.spawned === '1') return;
    canvas.dataset.spawned = '1';
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.clientWidth * 2;
    const h = canvas.height = canvas.clientHeight * 2;
    const N = parseInt(canvas.dataset.count || '60', 10);
    const colors = ['#7dd3fc', '#bb9af7', '#2dd4bf', '#c678ff'];
    const parts = Array.from({length: N}, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: -Math.random() * 0.5 - 0.1,
      r: Math.random() * 2 + 0.5,
      a: Math.random() * 0.6 + 0.2,
      c: colors[Math.floor(Math.random() * colors.length)]
    }));
    function tick() {
      ctx.clearRect(0, 0, w, h);
      for (const p of parts) {
        p.x += p.vx; p.y += p.vy;
        if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
        if (p.x < -10) p.x = w + 10;
        if (p.x > w + 10) p.x = -10;
        ctx.globalAlpha = p.a;
        ctx.fillStyle = p.c;
        ctx.shadowColor = p.c;
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * 2, 0, Math.PI * 2);
        ctx.fill();
      }
      canvas._raf = requestAnimationFrame(tick);
    }
    tick();
  }

  function activate(section) {
    if (!section) return;
    section.querySelectorAll('[data-typewriter]').forEach(typewriter);
    section.querySelectorAll('canvas.particles').forEach(spawnParticles);
    // restart fade-up animations by toggling class
    section.querySelectorAll('.fade-up, .fade-in').forEach(el => {
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = '';
    });
  }

  // run once on load
  setTimeout(() => activate(stage.querySelector('section')), 100);

  // listen to slide changes from deck-stage (which posts to parent — we listen on window)
  let last = -1;
  function poll() {
    const sections = stage.querySelectorAll('section');
    let cur = 0;
    sections.forEach((s, i) => {
      const r = s.getBoundingClientRect();
      if (r.top < window.innerHeight / 2 && r.bottom > window.innerHeight / 2) cur = i;
    });
    // deck-stage may use index attr
    const idxAttr = stage.getAttribute('current') || stage.dataset.current;
    if (idxAttr != null && !isNaN(+idxAttr)) cur = +idxAttr;
    if (cur !== last) {
      last = cur;
      activate(sections[cur]);
    }
  }
  // we hook into postMessage that deck-stage emits
  window.addEventListener('message', (e) => {
    if (e.data && typeof e.data.slideIndexChanged === 'number') {
      const sections = stage.querySelectorAll('section');
      activate(sections[e.data.slideIndexChanged]);
    }
  });
  // fallback poll
  setInterval(poll, 400);
})();
