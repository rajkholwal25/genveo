document.addEventListener("DOMContentLoaded", () => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ----- Success popup modal (from a success flash, e.g. after Save) -----
  const showModal = (title, message, kind) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    const isErr = kind === "error";
    overlay.innerHTML =
      '<div class="result-modal">' +
      '<div class="result-icon ' + (isErr ? "is-error" : "is-success") + '">' +
      (isErr
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>') +
      "</div>" +
      "<h3>" + title + "</h3>" +
      "<p>" + message + "</p>" +
      '<button type="button" class="btn btn-primary btn-block">Got it</button>' +
      "</div>";
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("show"));
    const close = () => {
      overlay.classList.remove("show");
      setTimeout(() => overlay.remove(), 280);
    };
    overlay.querySelector("button").addEventListener("click", close);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    if (!isErr) setTimeout(close, 3500);
  };

  const successFlash = document.querySelector(".flash-success");
  if (successFlash) {
    showModal("All done", successFlash.textContent.trim(), "success");
    successFlash.remove();
  } else {
    const errFlash = document.querySelector(".flash-error");
    if (errFlash && /updat|sav|photo|password|match/i.test(errFlash.textContent)) {
      showModal("Couldn't save", errFlash.textContent.trim(), "error");
      errFlash.remove();
    }
  }

  // ----- "Saving…" overlay while uploads are in flight -----
  document.querySelectorAll('form[enctype="multipart/form-data"]').forEach((form) => {
    form.addEventListener("submit", () => {
      if (!form.checkValidity()) return; // let the browser show field errors
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay show saving-overlay";
      overlay.innerHTML =
        '<div class="result-modal"><div class="spinner"></div>' +
        "<h3>Saving your changes…</h3><p>Uploading and updating your profile.</p></div>";
      document.body.appendChild(overlay);
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Saving…";
      }
    });
  });

  // ----- Auto-hide flash messages -----
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => el.remove(), 4500);
  });

  // ----- Stagger entrance animations -----
  document.querySelectorAll(".category-grid .category-card").forEach((card, i) => {
    card.style.animationDelay = `${0.05 * i}s`;
  });
  document.querySelectorAll(".cards-grid .profile-card").forEach((card, i) => {
    card.style.animationDelay = `${0.08 * i}s`;
  });

  // ----- Role tab switching on auth pages -----
  document.querySelectorAll(".role-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const role = tab.dataset.role;
      if (role) {
        const url = new URL(window.location);
        url.searchParams.set("role", role);
        window.location.href = url.toString();
      }
    });
  });

  // ----- Instagram-style photo gallery (swipe + dots + arrows) -----
  document.querySelectorAll("[data-gallery]").forEach((media) => {
    const track = media.querySelector(".ig-track");
    if (!track) return;
    const dots = media.querySelectorAll(".ig-dot");
    const prev = media.querySelector(".ig-nav.prev");
    const next = media.querySelector(".ig-nav.next");
    const slideW = () => track.clientWidth;

    const update = () => {
      const i = Math.round(track.scrollLeft / slideW());
      dots.forEach((d, di) => d.classList.toggle("active", di === i));
      if (prev) prev.style.visibility = i <= 0 ? "hidden" : "visible";
      if (next) next.style.visibility = i >= dots.length - 1 ? "hidden" : "visible";
    };

    track.addEventListener("scroll", () => window.requestAnimationFrame(update), { passive: true });
    if (prev) prev.addEventListener("click", () => track.scrollBy({ left: -slideW(), behavior: "smooth" }));
    if (next) next.addEventListener("click", () => track.scrollBy({ left: slideW(), behavior: "smooth" }));
    update();
  });

  // ----- File-size limit (1 MB) for gallery photos + icons -----
  const MAX_MB = 1;
  const overSized = (input) =>
    Array.from(input.files).find((f) => f.size > MAX_MB * 1024 * 1024);

  // ----- File-drop: size check + show chosen filenames -----
  document.querySelectorAll(".file-drop input[type=file]").forEach((input) => {
    input.addEventListener("change", () => {
      const big = overSized(input);
      const out = input.closest(".file-drop").querySelector(".file-names");
      if (big) {
        showModal(
          "Image too large",
          'Please upload an image below 1 MB. "' + big.name + '" is ' +
            (big.size / 1024 / 1024).toFixed(1) + " MB.",
          "error"
        );
        input.value = "";
        if (out) out.textContent = "";
        return;
      }
      const names = Array.from(input.files).map((f) => f.name);
      if (out) out.textContent = names.length ? names.join(", ") : "";
    });
  });

  // ----- Admin live table search -----
  document.querySelectorAll(".admin-search[data-search]").forEach((input) => {
    const table = document.querySelector(input.getAttribute("data-search"));
    if (!table) return;
    const wrap = input.closest(".admin-search-wrap");
    const rows = () => table.querySelectorAll("tbody tr");
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      let shown = 0;
      rows().forEach((tr) => {
        const match = tr.textContent.toLowerCase().includes(q);
        tr.style.display = match ? "" : "none";
        if (match) shown++;
      });
      if (wrap) wrap.dataset.empty = shown === 0 ? "true" : "false";
    });
  });

  // ----- Photo delete (AJAX, avoids nesting a <form> in the edit form) -----
  document.querySelectorAll(".photo-del[data-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!window.confirm("Remove this photo?")) return;
      btn.disabled = true;
      try {
        const res = await fetch(btn.dataset.del, { method: "POST" });
        if (res.ok || res.redirected) {
          btn.closest(".photo-thumb").remove();
        } else {
          btn.disabled = false;
        }
      } catch {
        btn.disabled = false;
      }
    });
  });

  // ----- Avatar adjuster: drag to reposition, slider to zoom, then crop -----
  const openAdjuster = (input, file) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const V = 300;
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay show";
      overlay.innerHTML =
        '<div class="adjust-modal">' +
        "<h3>Adjust your photo</h3><p>Drag to reposition • slide to zoom</p>" +
        '<div class="adjust-stage"><canvas class="adjust-canvas" width="' + V + '" height="' + V + '"></canvas><div class="adjust-ring"></div></div>' +
        '<input type="range" class="adjust-zoom" min="1" max="3" step="0.01" value="1">' +
        '<div class="adjust-actions"><button type="button" class="btn btn-ghost" data-cancel>Cancel</button><button type="button" class="btn btn-primary" data-apply>Apply</button></div>' +
        "</div>";
      document.body.appendChild(overlay);

      const canvas = overlay.querySelector(".adjust-canvas");
      const ctx = canvas.getContext("2d");
      const zoom = overlay.querySelector(".adjust-zoom");
      const base = Math.max(V / img.width, V / img.height);
      let scale = base;
      let ox = (V - img.width * scale) / 2;
      let oy = (V - img.height * scale) / 2;

      const draw = () => {
        const w = img.width * scale, h = img.height * scale;
        ox = Math.min(0, Math.max(V - w, ox));
        oy = Math.min(0, Math.max(V - h, oy));
        ctx.clearRect(0, 0, V, V);
        ctx.drawImage(img, ox, oy, w, h);
      };
      draw();

      zoom.addEventListener("input", () => {
        const ns = base * parseFloat(zoom.value);
        const c = V / 2;
        ox = c - (c - ox) * (ns / scale);
        oy = c - (c - oy) * (ns / scale);
        scale = ns;
        draw();
      });

      let drag = false, lx = 0, ly = 0;
      canvas.addEventListener("pointerdown", (e) => {
        drag = true; lx = e.clientX; ly = e.clientY; canvas.setPointerCapture(e.pointerId);
      });
      canvas.addEventListener("pointermove", (e) => {
        if (!drag) return;
        ox += e.clientX - lx; oy += e.clientY - ly; lx = e.clientX; ly = e.clientY; draw();
      });
      canvas.addEventListener("pointerup", () => (drag = false));

      const close = () => { overlay.remove(); URL.revokeObjectURL(url); };
      overlay.querySelector("[data-cancel]").addEventListener("click", () => { input.value = ""; close(); });
      overlay.addEventListener("click", (e) => { if (e.target === overlay) { input.value = ""; close(); } });
      overlay.querySelector("[data-apply]").addEventListener("click", () => {
        const OUT = 512, r = OUT / V;
        const out = document.createElement("canvas");
        out.width = OUT; out.height = OUT;
        out.getContext("2d").drawImage(img, ox * r, oy * r, img.width * scale * r, img.height * scale * r);
        out.toBlob((blob) => {
          const dt = new DataTransfer();
          dt.items.add(new File([blob], "avatar.jpg", { type: "image/jpeg" }));
          input.files = dt.files;
          const circle = input.closest(".avatar-edit-circle");
          circle.querySelector(".avatar-edit-img").src = out.toDataURL("image/jpeg");
          circle.dataset.has = "1";
          close();
        }, "image/jpeg", 0.92);
      });
    };
    img.src = url;
  };

  document.querySelectorAll(".avatar-edit-circle input[type=file]").forEach((input) => {
    input.addEventListener("change", () => {
      const f = input.files[0];
      if (f) openAdjuster(input, f);
    });
  });

  // ----- Icon-upload chip: size check + reflect chosen file -----
  document.querySelectorAll(".icon-upload input[type=file]").forEach((input) => {
    input.addEventListener("change", () => {
      const chip = input.closest(".icon-upload");
      const out = chip.querySelector(".icon-upload-name");
      const big = overSized(input);
      if (big) {
        showModal("Image too large", "Please upload an image below 1 MB.", "error");
        input.value = "";
      }
      const f = input.files[0];
      if (out) out.textContent = f ? f.name : "Icon image";
      chip.classList.toggle("has-file", !!f);
    });
  });

  if (reduceMotion) return;

  // ----- Cursor-following ambient glow -----
  const glow = document.createElement("div");
  glow.className = "cursor-glow";
  document.body.appendChild(glow);

  const grain = document.createElement("div");
  grain.className = "grain-overlay";
  document.body.appendChild(grain);

  let glowX = window.innerWidth / 2;
  let glowY = window.innerHeight / 2;
  let curX = glowX;
  let curY = glowY;

  window.addEventListener("pointermove", (e) => {
    glowX = e.clientX;
    glowY = e.clientY;
    glow.classList.add("active");
  });
  window.addEventListener("pointerleave", () => glow.classList.remove("active"));

  (function animateGlow() {
    curX += (glowX - curX) * 0.12;
    curY += (glowY - curY) * 0.12;
    glow.style.left = `${curX}px`;
    glow.style.top = `${curY}px`;
    requestAnimationFrame(animateGlow);
  })();

  // ----- Interactive 3D tilt + spotlight on cards -----
  const tiltCards = document.querySelectorAll(
    ".role-card, .profile-card, .category-card, .stat-card"
  );
  tiltCards.forEach((card) => {
    card.classList.add("tilt");

    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;

      // Spotlight position for the radial glow
      card.style.setProperty("--mx", `${px * 100}%`);
      card.style.setProperty("--my", `${py * 100}%`);

      // 3D tilt (gentle)
      const rotX = (py - 0.5) * -8;
      const rotY = (px - 0.5) * 8;
      card.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateY(-6px)`;
    });

    card.addEventListener("pointerleave", () => {
      card.style.transform = "";
    });
  });

  // ----- Magnetic buttons (skip full-width buttons so clicks never miss) -----
  document.querySelectorAll(".btn-primary:not(.btn-block)").forEach((btn) => {
    btn.addEventListener("pointermove", (e) => {
      const r = btn.getBoundingClientRect();
      const mx = e.clientX - r.left - r.width / 2;
      const my = e.clientY - r.top - r.height / 2;
      btn.style.transform = `translate(${mx * 0.12}px, ${my * 0.2 - 2}px)`;
    });
    btn.addEventListener("pointerleave", () => {
      btn.style.transform = "";
    });
  });

  // ----- Button ripple on click -----
  document.querySelectorAll(".btn").forEach((btn) => {
    btn.addEventListener("pointerdown", (e) => {
      const r = btn.getBoundingClientRect();
      const size = Math.max(r.width, r.height);
      const ripple = document.createElement("span");
      ripple.className = "ripple";
      ripple.style.width = ripple.style.height = `${size}px`;
      ripple.style.left = `${e.clientX - r.left - size / 2}px`;
      ripple.style.top = `${e.clientY - r.top - size / 2}px`;
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });

  // ----- Navbar reacts to scroll -----
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    const onScroll = () => navbar.classList.toggle("scrolled", window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // ----- Count-up animation for stat numbers -----
  const animateCount = (el) => {
    const raw = el.textContent.trim();
    const match = raw.match(/[\d,]+(\.\d+)?/);
    if (!match) return;
    const target = parseFloat(match[0].replace(/,/g, ""));
    if (isNaN(target) || target === 0) return;

    const prefix = raw.slice(0, match.index);
    const suffix = raw.slice(match.index + match[0].length);
    const hasComma = match[0].includes(",");
    const duration = 1200;
    let startTs = null;

    const fmt = (n) =>
      hasComma ? Math.round(n).toLocaleString("en-IN") : Math.round(n).toString();

    const step = (ts) => {
      if (!startTs) startTs = ts;
      const p = Math.min((ts - startTs) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      el.textContent = prefix + fmt(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = prefix + fmt(target) + suffix;
    };
    requestAnimationFrame(step);
  };

  // ----- Scroll reveal + trigger count-ups -----
  const numbers = document.querySelectorAll(".stat-card .number, .card-stats .stat-value");
  const io = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("visible");
        if (entry.target.matches(".stat-card .number, .stat-value")) {
          animateCount(entry.target);
        }
        obs.unobserve(entry.target);
      });
    },
    { threshold: 0.2, rootMargin: "0px 0px -40px 0px" }
  );

  // reveal sections that sit lower on the page
  document
    .querySelectorAll(".admin-section, .section-title, .empty-state")
    .forEach((el) => {
      el.classList.add("reveal");
      io.observe(el);
    });

  numbers.forEach((el) => io.observe(el));
});
