/* ============================================================
   SmartMES — Interaction Engine v2
   Optimized · Cursor-aware · Smooth
   ============================================================ */

(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Ambient orbs ---------- */
  function injectAmbient() {
    if (document.querySelector('.bg-ambient')) return;
    const ambient = document.createElement('div');
    ambient.className = 'bg-ambient';
    ambient.innerHTML = `
      <div class="orb-a"></div>
      <div class="orb-b"></div>
      <div class="orb-c"></div>
    `;
    document.body.insertBefore(ambient, document.body.firstChild);
  }

  /* ---------- Page loader bar ---------- */
  function initPageLoader() {
    if (document.querySelector('.page-loader')) return;
    const loader = document.createElement('div');
    loader.className = 'page-loader';
    document.body.appendChild(loader);
    window.__smLoader = loader;
  }

  /* ---------- Page transition on internal links ---------- */
  function initPageTransition() {
    if (reduceMotion) return;
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href) return;
      if (href.startsWith('#') ||
          href.startsWith('http') ||
          href.startsWith('mailto') ||
          href.startsWith('tel') ||
          a.target === '_blank' ||
          e.metaKey || e.ctrlKey || e.shiftKey) return;

      if (window.__smLoader) {
        window.__smLoader.classList.add('active');
      }
      document.body.classList.add('page-leaving');
    });

    // Remove loader on back-forward cache restore
    window.addEventListener('pageshow', (e) => {
      if (e.persisted) {
        document.body.classList.remove('page-leaving');
        if (window.__smLoader) window.__smLoader.classList.remove('active');
      }
    });
  }

  /* ---------- Live clock ---------- */
  function startClock() {
    const el = document.getElementById('liveClock');
    if (!el) return;
    const tick = () => {
      el.textContent = new Date().toLocaleTimeString('en-IN', { hour12: false });
    };
    tick();
    setInterval(tick, 1000);
  }

  /* ---------- Move chassis marker ---------- */
  function moveChassis(fromId, toId, chassisNo) {
    const marker = document.querySelector(`[data-chassis="${chassisNo}"]`);
    const target = document.querySelector(`[data-station-slot="${toId}"]`);
    if (!marker || !target) return;
    marker.style.transition = 'transform 0.7s cubic-bezier(0.16, 1, 0.3, 1)';
    marker.style.transform = 'translateX(40px) scale(0.9)';
    setTimeout(() => {
      marker.style.transform = '';
      target.appendChild(marker);
      marker.classList.add('bounce-in');
      setTimeout(() => marker.classList.remove('bounce-in'), 500);
    }, 480);
  }

  /* ---------- Count-up numbers ---------- */
  function animateCountUp() {
    document.querySelectorAll('[data-count]').forEach(el => {
      const target = parseInt(el.dataset.count, 10) || 0;
      if (!target) { el.textContent = '0'; return; }
      const duration = 1400;
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 4);
        el.textContent = Math.round(target * eased);
        if (p < 1) requestAnimationFrame(tick);
        else {
          el.textContent = target;
          el.classList.add('number-pop');
          setTimeout(() => el.classList.remove('number-pop'), 700);
        }
      };
      requestAnimationFrame(tick);
    });
  }

  /* ---------- Progress bars ---------- */
  function animateProgressBars() {
    document.querySelectorAll('[data-progress]').forEach(bar => {
      const target = parseInt(bar.dataset.progress, 10) || 0;
      bar.style.width = '0%';
      setTimeout(() => { bar.style.width = target + '%'; }, 160);
    });
  }

  /* ---------- Stagger cards ---------- */
  function staggerCards() {
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, i) => {
      if (card.classList.contains('stagger-in')) return;
      card.style.animationDelay = Math.min(i * 45, 500) + 'ms';
      card.classList.add('stagger-in');
    });
  }

  /* ---------- Cursor-tracked radial highlight on cards ---------- */
  function initCursorGlow() {
    if (reduceMotion) return;
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
      let rafId = null;
      card.addEventListener('mousemove', (e) => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          const rect = card.getBoundingClientRect();
          const mx = ((e.clientX - rect.left) / rect.width) * 100;
          const my = ((e.clientY - rect.top) / rect.height) * 100;
          card.style.setProperty('--mx', mx + '%');
          card.style.setProperty('--my', my + '%');
          rafId = null;
        });
      });
    });
  }

  /* ---------- 3D tilt ---------- */
  function initTilt() {
    if (reduceMotion) return;
    document.querySelectorAll('.tilt-card').forEach(card => {
      let rafId = null;
      card.addEventListener('mousemove', (e) => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          const rect = card.getBoundingClientRect();
          const x = (e.clientX - rect.left) / rect.width - 0.5;
          const y = (e.clientY - rect.top) / rect.height - 0.5;
          const rotX = -y * 4.5;
          const rotY = x * 4.5;
          card.style.transform =
            `perspective(1100px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateY(-2px)`;
          rafId = null;
        });
      });
      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
      });
    });
  }

  /* ---------- Button ripple ---------- */
  function initRipple() {
    if (reduceMotion) return;
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-glass, .btn-primary-glass');
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;
      const rip = document.createElement('span');
      rip.className = 'ripple';
      rip.style.width = rip.style.height = size + 'px';
      rip.style.left = x + 'px';
      rip.style.top = y + 'px';
      btn.appendChild(rip);
      setTimeout(() => rip.remove(), 700);
    });
  }

  /* ---------- Topbar scroll shadow ---------- */
  function initTopbarScroll() {
    const topbar = document.querySelector('.glass-topbar');
    if (!topbar) return;
    let lastY = window.scrollY;
    let ticking = false;
    const update = () => {
      if (window.scrollY > 6) topbar.classList.add('scrolled');
      else topbar.classList.remove('scrolled');
      ticking = false;
    };
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });
    update();
  }

  /* ---------- Scroll reveal ---------- */
  function initScrollReveal() {
    if (!('IntersectionObserver' in window)) return;
    const targets = document.querySelectorAll('.reveal');
    if (!targets.length) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.1 });
    targets.forEach(t => io.observe(t));
  }

  /* ---------- Bike rider ---------- */
  function launchBikeRide() {
    if (reduceMotion) return;
    const belt = document.querySelector('.conveyor-belt');
    if (!belt) return;
    if (belt.querySelector('.bike-rider')) return;
    const bike = document.createElement('div');
    bike.className = 'bike-rider';
    bike.innerHTML = `
      <svg viewBox="0 0 64 40" style="width:40px;height:26px;">
        <circle cx="14" cy="30" r="6.5" fill="none" stroke="#ffa262" stroke-width="2.2"/>
        <circle cx="50" cy="30" r="6.5" fill="none" stroke="#ffa262" stroke-width="2.2"/>
        <path d="M14 30 L28 30 L36 18 L50 30 M28 30 L36 18 L44 18 L50 30"
              stroke="#ffb88c" stroke-width="2.2" fill="none" stroke-linecap="round"/>
        <circle cx="36" cy="14" r="2.2" fill="#ff7a3d"/>
      </svg>
    `;
    belt.appendChild(bike);
    setTimeout(() => bike.remove(), 7000);
  }

  /* ---------- Confetti ---------- */
  function fireConfetti() {
    if (reduceMotion) return;
    const colors = ['#ff7a3d', '#ffa262', '#5b6cff', '#8ea0ff', '#4ade80'];
    const frag = document.createDocumentFragment();
    for (let i = 0; i < 70; i++) {
      const piece = document.createElement('div');
      piece.className = 'confetti-piece';
      piece.style.left = '50%';
      piece.style.top = '35%';
      const size = 5 + Math.random() * 8;
      piece.style.width = size + 'px';
      piece.style.height = size + 'px';
      piece.style.background = colors[Math.floor(Math.random() * colors.length)];
      piece.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
      frag.appendChild(piece);
      piece.animate([
        { transform: 'translate(0,0) rotate(0deg)', opacity: 1 },
        {
          transform: `translate(${(Math.random() - 0.5) * 850}px, ${340 + Math.random() * 400}px) rotate(${Math.random() * 900}deg)`,
          opacity: 0
        }
      ], {
        duration: 2400 + Math.random() * 1000,
        easing: 'cubic-bezier(0.16, 1, 0.3, 1)'
      });
      setTimeout(() => piece.remove(), 3600);
    }
    document.body.appendChild(frag);
  }

  /* ---------- Toast ---------- */
  function showToast(msg, type) {
    const palette = {
      success: { bg: 'rgba(74, 222, 128, 0.14)', border: 'rgba(74, 222, 128, 0.4)', color: '#86efac' },
      danger:  { bg: 'rgba(248, 113, 113, 0.14)', border: 'rgba(248, 113, 113, 0.4)', color: '#fca5a5' },
      info:    { bg: 'rgba(140, 160, 255, 0.14)', border: 'rgba(140, 160, 255, 0.4)', color: '#c7d2fe' }
    }[type] || { bg: 'rgba(255,255,255,0.08)', border: 'rgba(255,255,255,0.2)', color: '#e8ecf3' };

    const toast = document.createElement('div');
    toast.className = 'fixed bottom-6 right-6 z-50 px-5 py-3.5 rounded-2xl text-sm toast-in';
    toast.style.background = palette.bg;
    toast.style.border = `1px solid ${palette.border}`;
    toast.style.color = palette.color;
    toast.style.backdropFilter = 'blur(24px)';
    toast.style.webkitBackdropFilter = 'blur(24px)';
    toast.style.boxShadow = '0 16px 48px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.08)';
    toast.style.maxWidth = '340px';
    toast.textContent = msg;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.5s, transform 0.5s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(120%)';
      setTimeout(() => toast.remove(), 500);
    }, 3200);
  }

  /* ---------- Boot ---------- */
  window.addEventListener('DOMContentLoaded', () => {
    injectAmbient();
    initPageLoader();
    initPageTransition();
    startClock();
    animateCountUp();
    animateProgressBars();
    staggerCards();
    initCursorGlow();
    initTilt();
    initRipple();
    initTopbarScroll();
    initScrollReveal();
    initSidebarScroll();
    setTimeout(launchBikeRide, 2200);
    setInterval(launchBikeRide, 15000);
  });
  /* ---------- Preserve Sidebar Scroll Position ---------- */
  function initSidebarScroll() {
    const sidebar = document.getElementById('sidebarNav');
    if (!sidebar) return;

    // 1. Restore scroll position when the page loads
    const savedScroll = localStorage.getItem('smartmes_sidebar_scroll');
    if (savedScroll) {
      sidebar.scrollTop = parseInt(savedScroll, 10);
    }

    // 2. Save scroll position every time the user scrolls the menu
    sidebar.addEventListener('scroll', () => {
      localStorage.setItem('smartmes_sidebar_scroll', sidebar.scrollTop);
    });
  }
  /* ---------- Expose ---------- */
  window.SmartMES = {
    moveChassis,
    showToast,
    animateProgressBars,
    animateCountUp,
    fireConfetti,
    launchBikeRide,
  };
})();