// SkyQuery landing interactions. Vanilla, self-contained, reduced-motion aware.
(() => {
  "use strict";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = matchMedia("(pointer: fine)").matches;
  const root = document.documentElement;
  const statusEl = document.getElementById("a11y-status");
  const announce = (msg) => { if (statusEl) statusEl.textContent = msg; };

  /* ---- Theme toggle (persisted, respects explicit choice only) ---- */
  const saved = localStorage.getItem("sq-theme");
  root.setAttribute("data-theme", saved === "light" ? "light" : "dark");
  const themeBtn = document.getElementById("theme");
  function syncThemeLabel() {
    if (!themeBtn) return;
    const light = root.getAttribute("data-theme") === "light";
    themeBtn.setAttribute("aria-pressed", light ? "true" : "false");
    themeBtn.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
  }
  syncThemeLabel();
  themeBtn?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    localStorage.setItem("sq-theme", next);
    syncThemeLabel();
    announce(next === "light" ? "Light theme" : "Dark theme");
  });

  /* ---- Mobile nav ---- */
  const navToggle = document.getElementById("nav-toggle");
  const primaryNav = document.getElementById("primary-nav");
  function setNavOpen(open) {
    if (!navToggle || !primaryNav) return;
    primaryNav.classList.toggle("is-open", open);
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    navToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }
  navToggle?.addEventListener("click", () => {
    setNavOpen(navToggle.getAttribute("aria-expanded") !== "true");
  });
  primaryNav?.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => setNavOpen(false));
  });
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") setNavOpen(false);
  });

  /* ---- Nav shadow on scroll ---- */
  const nav = document.getElementById("nav");
  const onScroll = () => nav?.classList.toggle("is-scrolled", window.scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---- Copy buttons + live region ---- */
  document.querySelectorAll(".copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.getAttribute("data-copy") || "");
        const original = btn.textContent;
        btn.textContent = "Copied";
        btn.classList.add("is-done");
        announce("Copied to clipboard");
        setTimeout(() => { btn.textContent = original; btn.classList.remove("is-done"); }, 1600);
      } catch { announce("Copy failed"); }
    });
  });

  /* ---- Install tabs (ARIA + keyboard) ---- */
  const tabs = document.querySelector("[data-tabs]");
  if (tabs) {
    const buttons = [...tabs.querySelectorAll('[role="tab"]')];
    const panels = [...tabs.querySelectorAll("[data-panel]")];
    function activate(btn, focus) {
      buttons.forEach((x) => {
        const on = x === btn;
        x.classList.toggle("is-active", on);
        x.setAttribute("aria-selected", on ? "true" : "false");
        x.tabIndex = on ? 0 : -1;
      });
      const key = btn.getAttribute("data-tab");
      panels.forEach((p) => { p.hidden = p.getAttribute("data-panel") !== key; });
      if (focus) btn.focus();
    }
    buttons.forEach((b, i) => {
      b.addEventListener("click", () => activate(b, false));
      b.addEventListener("keydown", (e) => {
        let next = -1;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % buttons.length;
        else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + buttons.length) % buttons.length;
        else if (e.key === "Home") next = 0;
        else if (e.key === "End") next = buttons.length - 1;
        if (next >= 0) { e.preventDefault(); activate(buttons[next], true); }
      });
    });
  }

  /* ---- Scrollable regions need keyboard access ---- */
  function markScrollable(el) {
    if (!el || el.tabIndex >= 0) return;
    if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) {
      el.tabIndex = 0;
      if (!el.getAttribute("role")) el.setAttribute("role", "region");
      if (!el.getAttribute("aria-label")) {
        const tag = el.tagName.toLowerCase();
        el.setAttribute("aria-label", tag === "table" ? "Scrollable table" : "Scrollable code");
      }
    }
  }
  const markAllScrollable = () => {
    document.querySelectorAll(".prose pre, .prose table, .code pre, .term__body, .manifest").forEach(markScrollable);
  };
  markAllScrollable();
  addEventListener("resize", markAllScrollable, { passive: true });

  /* ---- Scroll reveal ---- */
  const revealables = document.querySelectorAll(".band > .eyebrow, .band > h2, .band .lead, .crosslist, .flow, .cols > .col, .features > .feature, .manifest, .note, .steps > .step, .answer");
  revealables.forEach((el) => el.classList.add("reveal"));
  if (reduce) {
    revealables.forEach((el) => el.classList.add("is-in"));
  } else {
    const ro = new IntersectionObserver((entries, obs) => {
      for (const e of entries) {
        if (e.isIntersecting) { e.target.classList.add("is-in"); obs.unobserve(e.target); }
      }
    }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
    revealables.forEach((el) => ro.observe(el));
  }

  /* ---- Animated Apophis terminal (pausable) ---- */
  const SCRIPT = [
    { cls: "usr", t: "> when does 99942 Apophis next pass close to Earth, and how big is it?" },
    { cls: "sys", t: "* skyquery.get_ephemeris(target=\"99942 Apophis\", observer=\"geocentric\")" },
    { cls: "out", t: "  EPOCH (UT)        RA [ICRS]     DEC        DELTA (AU)   V" },
    { cls: "out", t: "  2029-04-13 22:00  114.54546    +33.17437   0.00025725   4.26" },
    { cls: "sys", t: "* skyquery.get_small_body(\"Apophis\")" },
    { cls: "out", t: "  diameter 0.34 km   H 19.09 mag   class Aten (PHA)" },
    { cls: "src", t: "  source: JPL Horizons + SBDB . frame ICRS . unit-tagged" },
    { cls: "ans", t: "= Apophis passes ~0.10 lunar distances from Earth on 2029-04-13, inside" },
    { cls: "ans", t: "  geostationary orbit. It is roughly 340 m across." },
  ];
  const body = document.querySelector(".term__body");
  const replay = document.querySelector(".term__replay");
  const pauseBtn = document.querySelector(".term__pause");
  let termTimer = 0;
  let termPaused = false;
  let termRunning = false;

  function clearTermTimer() {
    if (termTimer) { clearTimeout(termTimer); termTimer = 0; }
  }
  function renderInstant() {
    if (!body) return;
    clearTermTimer();
    termRunning = false;
    body.textContent = "";
    for (const l of SCRIPT) {
      const s = document.createElement("span");
      s.className = "ln " + l.cls;
      s.textContent = l.t + "\n";
      body.appendChild(s);
    }
    if (pauseBtn) pauseBtn.hidden = true;
    if (replay) replay.hidden = false;
  }
  let termTick = null;
  function typeOut() {
    if (!body) return;
    clearTermTimer();
    body.textContent = "";
    termPaused = false;
    termRunning = true;
    if (replay) replay.hidden = true;
    if (pauseBtn) {
      pauseBtn.hidden = false;
      pauseBtn.textContent = "Pause demo";
      pauseBtn.setAttribute("aria-pressed", "false");
    }
    const caret = document.createElement("span");
    caret.className = "term__caret";
    let li = 0, ci = 0, span = null;
    termTick = function tick() {
      if (!termRunning || termPaused) return;
      if (li >= SCRIPT.length) {
        caret.remove();
        termRunning = false;
        termTick = null;
        if (pauseBtn) pauseBtn.hidden = true;
        if (replay) replay.hidden = false;
        announce("Demo finished");
        return;
      }
      const line = SCRIPT[li];
      if (ci === 0) { span = document.createElement("span"); span.className = "ln " + line.cls; body.appendChild(span); }
      span.textContent = line.t.slice(0, ++ci);
      span.appendChild(caret);
      if (ci >= line.t.length) {
        span.textContent = line.t + "\n"; span.appendChild(caret);
        li++; ci = 0;
        termTimer = setTimeout(tick, line.cls === "usr" ? 480 : (line.cls === "out" || line.cls === "src") ? 90 : 220);
      } else {
        termTimer = setTimeout(tick, 12 + Math.random() * 24);
      }
    };
    termTick();
  }
  pauseBtn?.addEventListener("click", () => {
    if (!termRunning && !termPaused) return;
    if (!termPaused) {
      termPaused = true;
      clearTermTimer();
      pauseBtn.setAttribute("aria-pressed", "true");
      pauseBtn.textContent = "Resume demo";
      announce("Demo paused");
      return;
    }
    termPaused = false;
    pauseBtn.setAttribute("aria-pressed", "false");
    pauseBtn.textContent = "Pause demo";
    announce("Demo resumed");
    if (termTick) termTick();
    else renderInstant();
  });
  if (body) {
    if (reduce) renderInstant();
    else {
      const term = document.querySelector(".term");
      if (term) {
        new IntersectionObserver((e, obs) => {
          if (e[0].isIntersecting) { typeOut(); obs.disconnect(); }
        }, { threshold: 0.35 }).observe(term);
      }
      replay?.addEventListener("click", () => { if (!reduce) typeOut(); });
    }
  }

  /* ---- Interactive constellation (pausable) ---- */
  const cv = document.getElementById("sky");
  const motionBtn = document.getElementById("motion");
  let skyPaused = reduce || localStorage.getItem("sq-motion") === "paused";
  function syncMotionLabel() {
    if (!motionBtn) return;
    motionBtn.hidden = !cv;
    motionBtn.setAttribute("aria-pressed", skyPaused ? "true" : "false");
    motionBtn.setAttribute("aria-label", skyPaused ? "Play background motion" : "Pause background motion");
    motionBtn.title = skyPaused ? "Play background motion" : "Pause background motion";
    motionBtn.querySelector("span") && (motionBtn.querySelector("span").textContent = skyPaused ? "▶" : "⏸");
  }
  syncMotionLabel();

  if (cv) {
    const ctx = cv.getContext("2d");
    const dpr = Math.min(devicePixelRatio || 1, 2);
    let stars = [], w = 0, h = 0, mx = -9999, my = -9999, tx = 0, ty = 0, raf = 0, shoot = null;

    let starRGB = "231,231,239", accentRGB = "242,178,76";
    function refresh() {
      starRGB = root.getAttribute("data-theme") === "light" ? "40,40,46" : "231,231,239";
      accentRGB = "242,178,76";
    }
    function scrollProgress() {
      const max = document.body.scrollHeight - innerHeight;
      return max > 0 ? Math.min(1, window.scrollY / max) : 0;
    }
    function resize() {
      w = cv.width = innerWidth * dpr;
      h = cv.height = innerHeight * dpr;
      const n = innerWidth < 640 ? 60 : Math.min(150, Math.round((innerWidth * innerHeight) / 12000));
      stars = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        z: Math.random() * 0.8 + 0.2, r: (Math.random() * 1.25 + 0.35) * dpr,
        amber: Math.random() < 0.1, ph: Math.random() * 6.28, sp: Math.random() * 0.02 + 0.004,
      }));
      refresh();
    }
    function maybeShoot() {
      if (shoot || Math.random() > 0.004) return;
      const edge = Math.random() * w;
      shoot = { x: edge, y: -20 * dpr, vx: (Math.random() * 2 - 1) * 6 * dpr, vy: (Math.random() * 3 + 5) * dpr, life: 1 };
    }
    function paintFrame(now, animate) {
      ctx.clearRect(0, 0, w, h);
      const prog = (!animate || skyPaused) ? 0.35 : scrollProgress();
      const linkAlpha = 0.14 + prog * 0.3;
      const linkDist = (110 + prog * 40) * dpr;
      const ld2 = linkDist * linkDist;

      const hasPointer = fine && mx > 0 && animate && !skyPaused;
      const targetX = hasPointer ? mx / innerWidth - 0.5 : 0;
      const targetY = hasPointer ? my / innerHeight - 0.5 : 0;
      if (animate && !skyPaused) { tx += (targetX - tx) * 0.06; ty += (targetY - ty) * 0.06; }
      else { tx = 0; ty = 0; }

      const pts = [];
      for (const s of stars) {
        const tw = (!animate || skyPaused) ? 1 : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(s.ph + now * 0.001 * (s.sp * 40)));
        const px = s.x + ((!animate || skyPaused) ? 0 : tx * s.z * 26 * dpr);
        const py = s.y + ((!animate || skyPaused) ? 0 : ty * s.z * 26 * dpr);
        pts.push([px, py, s.amber]);
        ctx.beginPath();
        ctx.arc(px, py, s.r, 0, 6.283);
        ctx.fillStyle = s.amber
          ? `rgba(${accentRGB},${0.9 * tw})`
          : `rgba(${starRGB},${(0.45 + 0.5 * s.z) * tw})`;
        ctx.fill();
      }

      if (animate && !skyPaused) {
        ctx.lineWidth = dpr;
        for (let i = 0; i < pts.length; i++) {
          for (let j = i + 1; j < pts.length; j++) {
            const dx = pts[i][0] - pts[j][0], dy = pts[i][1] - pts[j][1];
            const d2 = dx * dx + dy * dy;
            if (d2 < ld2) {
              ctx.strokeStyle = `rgba(${starRGB},${linkAlpha * (1 - d2 / ld2)})`;
              ctx.beginPath(); ctx.moveTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[j][0], pts[j][1]); ctx.stroke();
            }
          }
        }
        if (fine && mx > 0) {
          const cr2 = (170 * dpr) ** 2;
          for (const [px, py, amber] of pts) {
            const dx = px - mx * dpr, dy = py - my * dpr, d2 = dx * dx + dy * dy;
            if (d2 < cr2) {
              const rgb = amber ? accentRGB : starRGB;
              ctx.strokeStyle = `rgba(${rgb},${0.4 * (1 - d2 / cr2)})`;
              ctx.beginPath(); ctx.moveTo(mx * dpr, my * dpr); ctx.lineTo(px, py); ctx.stroke();
            }
          }
        }
        maybeShoot();
        if (shoot) {
          shoot.x += shoot.vx; shoot.y += shoot.vy; shoot.life -= 0.012;
          if (shoot.life <= 0 || shoot.y > h + 40 * dpr) shoot = null;
          else {
            ctx.strokeStyle = `rgba(${accentRGB},${0.7 * shoot.life})`;
            ctx.lineWidth = 1.6 * dpr; ctx.lineCap = "round";
            ctx.beginPath(); ctx.moveTo(shoot.x, shoot.y); ctx.lineTo(shoot.x - shoot.vx * 3, shoot.y - shoot.vy * 3); ctx.stroke();
            ctx.lineWidth = dpr;
          }
        }
      } else {
        // Still draw static constellation lines at low opacity when paused.
        ctx.lineWidth = dpr;
        for (let i = 0; i < pts.length; i++) {
          for (let j = i + 1; j < pts.length; j++) {
            const dx = pts[i][0] - pts[j][0], dy = pts[i][1] - pts[j][1];
            const d2 = dx * dx + dy * dy;
            if (d2 < ld2) {
              ctx.strokeStyle = `rgba(${starRGB},${linkAlpha * (1 - d2 / ld2)})`;
              ctx.beginPath(); ctx.moveTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[j][0], pts[j][1]); ctx.stroke();
            }
          }
        }
      }
    }
    function paint(now) {
      raf = requestAnimationFrame(paint);
      paintFrame(now, true);
    }
    function stopLoop() {
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      paintFrame(0, false);
    }
    function startLoop() {
      stopLoop();
      raf = requestAnimationFrame(paint);
    }

    motionBtn?.addEventListener("click", () => {
      skyPaused = !skyPaused;
      localStorage.setItem("sq-motion", skyPaused ? "paused" : "play");
      syncMotionLabel();
      announce(skyPaused ? "Background motion paused" : "Background motion playing");
      if (skyPaused) stopLoop();
      else startLoop();
    });

    addEventListener("resize", () => { resize(); if (skyPaused || reduce) paintFrame(0, false); }, { passive: true });
    if (fine && !reduce) addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; }, { passive: true });
    addEventListener("pointerleave", () => { mx = -9999; my = -9999; });
    themeBtn?.addEventListener("click", () => setTimeout(() => {
      refresh();
      if (skyPaused || reduce) paintFrame(0, false);
    }, 0));
    resize();
    if (reduce || skyPaused) { refresh(); paintFrame(0, false); }
    else raf = requestAnimationFrame(paint);
  }
})();
