// SkyQuery landing interactions. Vanilla, self-contained, reduced-motion aware.
(() => {
  "use strict";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = matchMedia("(pointer: fine)").matches;

  /* ---- Theme toggle (persisted, respects system default) ---- */
  const root = document.documentElement;
  // Dark is always the default; only an explicit user toggle (persisted) overrides it.
  const saved = localStorage.getItem("sq-theme");
  root.setAttribute("data-theme", saved === "light" ? "light" : "dark");
  document.getElementById("theme")?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    localStorage.setItem("sq-theme", next);
  });

  /* ---- Nav shadow on scroll ---- */
  const nav = document.getElementById("nav");
  const onScroll = () => nav?.classList.toggle("is-scrolled", window.scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---- Copy buttons ---- */
  document.querySelectorAll(".copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.getAttribute("data-copy") || "");
        const original = btn.textContent;
        btn.textContent = "Copied";
        btn.classList.add("is-done");
        setTimeout(() => { btn.textContent = original; btn.classList.remove("is-done"); }, 1600);
      } catch { /* clipboard blocked; ignore */ }
    });
  });

  /* ---- Install tabs ---- */
  const tabs = document.querySelector("[data-tabs]");
  if (tabs) {
    const buttons = tabs.querySelectorAll(".tabs__list button");
    const panels = tabs.querySelectorAll("[data-panel]");
    buttons.forEach((b) => b.addEventListener("click", () => {
      buttons.forEach((x) => x.classList.remove("is-active"));
      b.classList.add("is-active");
      const key = b.getAttribute("data-tab");
      panels.forEach((p) => { p.hidden = p.getAttribute("data-panel") !== key; });
    }));
  }

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

  /* ---- Animated Apophis terminal ---- */
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

  function renderInstant() {
    body.textContent = "";
    for (const l of SCRIPT) {
      const s = document.createElement("span");
      s.className = "ln " + l.cls;
      s.textContent = l.t + "\n";
      body.appendChild(s);
    }
  }
  function typeOut() {
    body.textContent = "";
    if (replay) replay.hidden = true;
    const caret = document.createElement("span");
    caret.className = "term__caret";
    let li = 0, ci = 0, span = null;
    (function tick() {
      if (li >= SCRIPT.length) { caret.remove(); if (replay) replay.hidden = false; return; }
      const line = SCRIPT[li];
      if (ci === 0) { span = document.createElement("span"); span.className = "ln " + line.cls; body.appendChild(span); }
      span.textContent = line.t.slice(0, ++ci);
      span.appendChild(caret);
      if (ci >= line.t.length) {
        span.textContent = line.t + "\n"; span.appendChild(caret);
        li++; ci = 0;
        setTimeout(tick, line.cls === "usr" ? 480 : (line.cls === "out" || line.cls === "src") ? 90 : 220);
      } else {
        setTimeout(tick, 12 + Math.random() * 24);
      }
    })();
  }
  if (body) {
    if (reduce) renderInstant();
    else new IntersectionObserver((e, obs) => {
      if (e[0].isIntersecting) { typeOut(); obs.disconnect(); }
    }, { threshold: 0.35 }).observe(document.querySelector(".term"));
    replay?.addEventListener("click", () => { if (!reduce) typeOut(); });
  }

  /* ---- Interactive constellation ----
     Stars twinkle and parallax; nearby stars link with hairlines, and stars
     near the cursor link to it. Constellation density grows as you scroll, so
     the sky "wires up" on the way down. One occasional shooting star. */
  const cv = document.getElementById("sky");
  if (cv) {
    const ctx = cv.getContext("2d");
    const dpr = Math.min(devicePixelRatio || 1, 2);
    let stars = [], w = 0, h = 0, mx = -9999, my = -9999, tx = 0, ty = 0, raf = 0, shoot = null, frame = 0;

    const css = (v) => getComputedStyle(root).getPropertyValue(v).trim();
    let starRGB = "231,231,239", accentRGB = "242,178,76";
    function refresh() {
      // Read theme-aware star tint from CSS so light mode dims correctly.
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
    function paint(now) {
      raf = requestAnimationFrame(paint);
      frame++;
      ctx.clearRect(0, 0, w, h);
      const prog = reduce ? 0.35 : scrollProgress();
      const linkAlpha = 0.14 + prog * 0.3;           // constellation lines strengthen on scroll
      const linkDist = (110 + prog * 40) * dpr;
      const ld2 = linkDist * linkDist;

      // Ease parallax toward a NORMALIZED pointer offset (-0.5..0.5), defaulting
      // to 0 when there is no pointer, so stars never fly off-screen.
      const hasPointer = fine && mx > 0;
      const targetX = hasPointer ? mx / innerWidth - 0.5 : 0;
      const targetY = hasPointer ? my / innerHeight - 0.5 : 0;
      tx += (targetX - tx) * 0.06; ty += (targetY - ty) * 0.06;

      const pts = [];
      for (const s of stars) {
        const tw = reduce ? 1 : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(s.ph + now * 0.001 * (s.sp * 40)));
        const px = s.x + (reduce ? 0 : tx * s.z * 26 * dpr);
        const py = s.y + (reduce ? 0 : ty * s.z * 26 * dpr);
        pts.push([px, py, s.amber]);
        ctx.beginPath();
        ctx.arc(px, py, s.r, 0, 6.283);
        ctx.fillStyle = s.amber
          ? `rgba(${accentRGB},${0.9 * tw})`
          : `rgba(${starRGB},${(0.45 + 0.5 * s.z) * tw})`;
        ctx.fill();
      }

      if (!reduce) {
        // Link nearby stars (constellation lines).
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
        // Link stars near the cursor to the cursor (interactive).
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
        // Shooting star.
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
      }
    }
    addEventListener("resize", resize, { passive: true });
    if (fine && !reduce) addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; }, { passive: true });
    addEventListener("pointerleave", () => { mx = -9999; my = -9999; });
    const themeBtn = document.getElementById("theme");
    themeBtn?.addEventListener("click", () => setTimeout(refresh, 0));
    resize();
    if (reduce) { refresh(); paint(0); cancelAnimationFrame(raf); }
    else raf = requestAnimationFrame(paint);
  }
})();
