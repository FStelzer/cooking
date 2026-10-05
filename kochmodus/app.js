import { escapeTilde, fmtAmount, fmtClock, highlight, isActive, isoSeconds, moreCount, noteMarkdown, normalizeState, resetState,
         scaleAmount, scaleStepText, selection, selectionKey, textWithAction, timerChoices, variantText } from "./lib.js";

const params = new URLSearchParams(location.search);
const RECIPE_URL = params.get("r") || "../gerichte/thit-kho-trung.json";
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (s) => marked.parse(escapeTilde(s || ""));
const mdInline = (s) => marked.parseInline(escapeTilde(s || ""));

let recipe, state, view = "kochen", openId = null;
const ingById = {};
const main = $("#main"), sheet = $("#sheet"), backdrop = $("#backdrop"), dock = $("#dock");

// ---- Zustand (localStorage, Schlüssel = Rezept-ID + Slug) -----------------
function loadState(id) {
  let raw = null;
  try { raw = JSON.parse(localStorage.getItem("km:" + id)); } catch {}
  return normalizeState(raw);
}
function save() { try { localStorage.setItem("km:" + recipe.id, JSON.stringify(state)); } catch {} }
const factor = () => +state.factor || 1;

// ---- Rezept-Helfer (Menü = Gänge mit eigenen Tasks) -------------------------
const isMenu = () => recipe.kind === "menu";
function courses() { return recipe.sections.filter((s) => s.type === "courses").flatMap((s) => s.courses); }
// Varianten: nur Tasks/Schritte/Zeitpläne der aktuellen Wahl (Lesen zeigt weiter alles)
const sel = () => selection(recipe, state.variant);
const live = (x) => isActive(x.only, sel());
function tasksOf(r, course = null) {
  const own = r.sections.filter((s) => s.type === "tasks").flatMap((s) => s.tasks.filter(live)
    .map((task) => ({ course, task: task.only || task.steps.some((st) => st.only) ? { ...task, steps: task.steps.filter(live) } : task })));
  return own.concat(courses().flatMap((c) => (r === recipe ? tasksOf(c, c) : [])));
}
function steps() { return tasksOf(recipe).flatMap(({ course, task }) => task.steps.map((step) => ({ course, task, step }))); }
const stepOf = (id) => steps().find((x) => x.step.id === id)?.step;
const labelOf = (ref) => stepOf(ref.replace(/^step:/, ""))?.label; // ausgeblendete Vorgänger fallen weg
function scaled(text, step) {
  const v = variantText(text, step, sel());
  return scaleStepText(v.text, { ...step, ingredients: v.ingredients }, factor(), ingById);
}
function courseTitle(c) { return c ? (recipe.courses?.find((x) => x.ref === c.id)?.name || c.title.replace(/^\d+\.\s*/, "")) : "Menü"; }
function schedules() { return recipe.sections.filter((s) => s.type === "schedule" && live(s.schedule)); }
function schedule() { return schedules()[0]; }
const liveEntries = (sch) => sch.entries.filter(live);

// ---- Ansichten -------------------------------------------------------------
function runBadge(step) {
  const ts = state.timers.filter((t) => t.step === step.id);
  if (!ts.length) return "";
  const rem = Math.min(...ts.map(remaining));
  return `<span class="run ${rem <= 0 ? "ring" : ""}" data-run="${step.id}">${rem <= 0 ? "Fertig" : fmtClock(rem / 1000)}</span>`;
}
function stepRow(s, course = null, task = null) {
  const dur = s.duration ? `${s.duration.source || ""}${s.duration.estimated ? " (geschätzt)" : ""}` : "";
  const deps = !s.after ? "" : s.after.length ? "nach " + s.after.map(labelOf).filter(Boolean).join(", ") : "jederzeit";
  const meta = [course ? courseTitle(course) : "", dur, deps].filter(Boolean).join(" · ");
  const title = s.title || (task && task.name !== recipe.title ? task.name : "");
  return `<div class="row ${state.done[s.id] ? "done" : ""} ${s.after && !s.after.length ? "free" : ""}" data-step="${s.id}">
    <input type="checkbox" class="chk" data-done="${s.id}" aria-label="${esc(title || s.label)} erledigt" ${state.done[s.id] ? "checked" : ""}>
    <div class="body" data-open="${s.id}">
      <div class="t">${esc(s.label)}. ${mdInline(title)}</div>
      ${meta ? `<div class="m">${esc(meta)}</div>` : ""}
      <div class="a md">${md(scaled(s.action, s))}</div>${(n => n ? `<div class="more">+ ${n} weitere${n === 1 ? "r Handgriff" : " Handgriffe"} ›</div>` : "")(moreCount(s))}${runBadge(s)}
    </div></div>`;
}
function plainRow(key, text, extra = "") {
  return `<div class="row plain ${state.done[key] ? "done" : ""}">
    <input type="checkbox" class="chk" data-done="${esc(key)}" aria-label="erledigt" ${state.done[key] ? "checked" : ""}>
    <div class="body"><div class="t plain">${mdInline(text)}</div>${extra ? `<div class="m">${esc(extra)}</div>` : ""}</div></div>`;
}
function renderKochen() {
  let html = `<p class="legend">Antippen öffnet Details, Timer und Notiz. <span class="free-hint">Gestrichelter Rand</span> = jederzeit möglich, ohne Vorgänger. <mark class="cue">Erkennungszeichen</mark><mark class="limit">Grenze</mark><mark class="why">Warum</mark><mark class="rescue">Rettung</mark></p>`;
  const sec = schedule();
  if (!isMenu() || !sec) {
    html += steps().map(({ step, course, task }) => stepRow(step, course, task)).join("");
    main.innerHTML = html; return;
  }
  const byCourse = state.order === "gang";
  html += `<div class="seg" role="group" aria-label="Reihenfolge" style="margin-bottom:10px"><button data-order="ablauf" aria-pressed="${!byCourse}">Ablauf</button><button data-order="gang" aria-pressed="${byCourse}">Nach Gang</button></div>`;
  if (byCourse) {
    for (const c of courses()) {
      const ts = tasksOf(c);
      html += `<section class="course"><h2>${mdInline(c.title)}</h2>`;
      if (!ts.length) { html += `<p class="empty">Noch nicht als Schritte modelliert — Text unter „Lesen“.</p></section>`; continue; }
      for (const { task } of ts) html += `<h3>${esc(task.name)}${task.phaseHint ? ` <span class="fine">· ${esc(task.phaseHint)}</span>` : ""}</h3>` + task.steps.map((st) => stepRow(st, null, task)).join("");
      html += `</section>`;
    }
    main.innerHTML = html; return;
  }
  // Ablauf (Default): Reihenfolge = Zeitplan (Phasen → Einträge → Schritte); Gänge mischen sich.
  const all = steps(), byId = Object.fromEntries(all.map((x) => [x.step.id, x]));
  const byTask = {}; for (const x of all) (byTask[x.task.id] ||= []).push(x);
  const placed = new Set();
  for (const p of sec.schedule.phases) {
    const es = liveEntries(sec.schedule).filter((e) => e.phase === p.id);
    if (!es.length) continue;
    html += `<section class="phase"><h2>${esc(p.label)}</h2>`;
    for (const e of es) {
      // Eintrag nennt Schritte und/oder Tasks: Vereinigung, Schritte zuerst, ohne Dubletten
      const seen = new Set(), xs = [];
      for (const x of [...(e.steps || []).map((id) => byId[id]), ...(e.tasks || []).flatMap((t) => byTask[t] || [])]) {
        if (x && !seen.has(x.step.id)) { seen.add(x.step.id); xs.push(x); }
      }
      if (!xs.length) { html += plainRow(`e:${p.id}:${e.text}`, e.text, e.course ? courseTitle(courses().find((c) => c.id === e.course)) : ""); continue; }
      html += `<p class="entry-head">${mdInline(e.text)}${e.derived ? ' <span class="fine">(abgeleitet)</span>' : ""}</p>`;
      for (const x of xs) { placed.add(x.step.id); html += stepRow(x.step, x.course, x.task); }
    }
    html += `</section>`;
  }
  const rest = all.filter((x) => !placed.has(x.step.id));
  if (rest.length) html += `<section class="phase"><h2>Ohne Platz im Zeitplan</h2>` + rest.map((x) => stepRow(x.step, x.course, x.task)).join("") + `</section>`;
  main.innerHTML = html;
}
function renderPlan() {
  const secs = schedules();
  if (!secs.length) { main.innerHTML = `<p class="empty">Kein Zeitplan für diese Auswahl.</p>`; return; }
  main.innerHTML = secs.map((sec) => (secs.length > 1 ? `<h2>${mdInline(sec.title)}</h2>` : "") + planHtml(sec)).join("");
}
function planHtml(sec) {
  const sch = { ...sec.schedule, entries: liveEntries(sec.schedule) }, lanes = [{ id: null, name: "Menü" }, ...courses().map((c) => ({ id: c.id, name: courseTitle(c) }))];
  const allTasks = Object.fromEntries(tasksOf(recipe).map(({ task }) => [task.id, task]));
  const done = (e) => {
    const ids = [...(e.steps || []), ...(e.tasks || []).flatMap((t) => (allTasks[t]?.steps || []).map((s) => s.id))];
    return ids.length && ids.every((id) => state.done[id]);
  };
  let h = `<div class="gantt-scroll"><div class="gantt" style="--cols:${sch.phases.length}"><div class="ph corner"></div>`;
  h += sch.phases.map((p) => `<div class="ph">${esc(p.label)}</div>`).join("");
  for (const lane of lanes) {
    h += `<div class="lane">${esc(lane.name)}</div>`;
    for (const p of sch.phases) {
      const es = sch.entries.filter((e) => e.phase === p.id && (e.course || null) === lane.id);
      h += `<div class="cell">` + es.map((e) => {
        const first = (e.tasks || []).map((t) => allTasks[t]?.steps[0]?.id).find(Boolean) || (e.steps || [])[0];
        return `<button class="chip ${done(e) ? "done" : ""} ${e.derived ? "derived" : ""} ${first ? "" : "plain"}" ${first ? `data-open="${first}"` : ""}>
          <span class="t">${mdInline(e.text)}</span>${e.at ? `<span class="m">${esc(e.at.offset.replace(/^([+-]?)PT/, "$1").toLowerCase())} zu ${esc(e.at.ref.split(":")[1])}</span>` : ""}</button>`;
      }).join("") + `</div>`;
    }
  }
  return h + `</div></div>` + (sec.note ? `<div class="md fine" style="margin-top:12px">${md(sec.note)}</div>` : "")
    + `<p class="fine">Chips mit Rand sind modellierte Aufgaben (antippen öffnet den ersten Schritt), graue sind nur Text. Gestrichelt = aus dem Rezept abgeleitet, steht nicht im Original-Zeitplan.</p>`;
}
function shoppingHtml() {
  const top = recipe.derived, key = selectionKey(sel());
  const d = !top?.variants || selectionKey(top.select || {}) === key ? top : top.variants.find((v) => v.key === key) || top;
  if (!d) return `<p class="empty">Kein <code>derived</code>-Block im JSON — <code>cli derive</code> ausführen.</p>`;
  const f = factor();
  let html = "", store = null;
  // Vorne das Gebinde (was man kauft), der Bedarf nur, wenn er abweicht: „1 Bund Frühlingszwiebeln · braucht 3“
  const flat = (x) => (x || "").replace(/\s+/g, "").replace(/^~|\\~/g, "");
  const needNote = (buy, need) => buy && need && flat(buy) !== flat(need) ? ` <span class="fine">· braucht ${esc(need)}</span>` : "";
  for (const g of d.shopping) {
    if (g.store !== store) { store = g.store; html += `<h3>${esc(store)}</h3>`; }
    if (g.group) html += `<p class="fine"><b>${esc(g.group)}</b></p>`;
    html += `<ul class="shop">` + g.items.map((it) => {
      const have = it.inStock || state.shop[it.ingredient];
      const need = f === 1 ? it.display : fmtAmount(scaleAmount(it.need, f, ingById[it.ingredient]));
      const note = it.note ? ` <span class="fine">${mdInline(it.note.replace(/^\*\(?|\)?\*$/g, ""))}</span>` : "";
      const crs = (ingById[it.ingredient]?.courses || []).map((c) => c.replace("gang-", "G")).join("+");
      return `<li class="${have ? "have" : ""}"><input type="checkbox" class="chk" data-shop="${it.ingredient}" ${have ? "checked" : ""}>
        <span>${it.optional ? "Optional: " : ""}${esc(it.buy?.text || need || "")} ${esc(it.name)}${needNote(it.buy?.text, need)}${crs ? ` <span class="fine">(${crs})</span>` : ""}${note}</span></li>`;
    }).join("") + `</ul>`;
  }
  return html;
}
function renderEinkauf() { main.innerHTML = shoppingHtml() + `<p class="fine">Häkchen bleiben nur in diesem Browser. Mengen ×${factor()}.</p>`; }
function renderSections(r, level) {
  let html = "";
  for (const sec of r.sections) {
    const hx = `h${level}`;
    html += `<${hx}>${mdInline(sec.title)}</${hx}>`;
    if (sec.type === "markdown") html += `<div class="md">${md(sec.markdown)}</div>`;
    else if (sec.type === "shopping") html += shoppingHtml();
    else if (sec.type === "tasks") for (const task of sec.tasks) {
      if (task.heading) html += `<div class="md">${md(task.heading)}</div>`;
      for (const s of task.steps) html += `<div class="card"><div class="md">${md(s.heading || `**${s.label}. ${s.title || ""}**`)}${md(highlight(scaleStepText(s.text, s, factor(), ingById), s))}</div></div>`;
    } else if (sec.type === "courses") for (const c of sec.courses) {
      html += `<h${level + 1}>${mdInline(c.title)}</h${level + 1}>` + (c.intro ? `<div class="md">${md(c.intro)}</div>` : "") + renderSections(c, level + 2);
    } else if (sec.type === "schedule") {
      const sch = sec.schedule;
      html += sch.phases.map((p) => `<p><b>${esc(p.label)}</b></p><ul>` + sch.entries.filter((e) => e.phase === p.id).map((e) => `<li>${mdInline(e.text)}${e.derived ? " <span class='fine'>(abgeleitet)</span>" : ""}</li>`).join("") + `</ul>`).join("");
      if (sec.note) html += `<div class="md">${md(sec.note)}</div>`;
    } else if (sec.type === "learnings") {
      html += `<div class="md">${md(sec.summary)}${md(sec.details)}</div>`;
      if (sec.notes?.length) html += `<p><b>Notizen mit Schritt-Bezug</b></p><ul>` + sec.notes.map((n) => `<li><code>${esc(n.ref)}</code> ${n.status === "open" ? "⏳" : "✓"} ${mdInline(n.text)}</li>`).join("") + `</ul>`;
    } else if (sec.type === "todo") html += `<ul>` + sec.items.map((i) => `<li>${i.checked ? "☑" : "☐"} ${mdInline(i.text)}</li>`).join("") + `</ul>`;
  }
  return html;
}
function renderLesen() {
  main.innerHTML = (recipe.statusNote ? `<div class="md">${md(recipe.statusNote)}</div>` : "") + (recipe.intro ? `<div class="md">${md(recipe.intro)}</div>` : "") + renderSections(recipe, 2);
}
function exportMarkdown() {
  const d = new Date(), date = `${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
  return noteMarkdown(recipe.id, state.note || "", date);
}
function renderNotizen() {
  main.innerHTML = `<p class="fine">Eine Notiz zum ganzen ${isMenu() ? "Menü" : "Rezept"}: was lief gut, was beim nächsten Mal anders. Einarbeiten ins Rezept ist später Rezeptarbeit.</p>
    <textarea id="noteBox" rows="10" placeholder="z. B. Gang 2: Gel-Süße passte, Beurre blanc hätte 10 Min. früher starten müssen …">${esc(state.note || "")}</textarea>
    <div class="toolbar"><button class="btn primary" id="copyMd" ${state.note?.trim() ? "" : "disabled"}>Als Markdown kopieren</button><span class="status">Zum Einfügen unter „## Learnings“.</span></div>
    <h3>Vorschau</h3><textarea id="mdOut" readonly rows="6">${esc(exportMarkdown())}</textarea>`;
  const nb = $("#noteBox"); let nt;
  nb.oninput = () => { state.note = nb.value; clearTimeout(nt); nt = setTimeout(() => { save(); $("#mdOut").value = exportMarkdown(); $("#copyMd").disabled = !state.note.trim(); }, 300); };
}
function renderVariants() {
  const el = $("#variants"), dims = recipe.variants || [];
  el.hidden = !dims.length;
  const cur = sel();
  el.innerHTML = dims.map((d) => `<label class="var">${esc(d.label)} <select data-variant="${d.id}">` +
    d.choices.map((c) => `<option value="${c.id}" ${c.id === cur[d.id] ? "selected" : ""}>${esc(c.label)}</option>`).join("") + `</select></label>`).join("");
}
function renderHeader() {
  $("#title").textContent = recipe.title;
  renderVariants();
  const y = recipe.yields?.value ? fmtAmount(scaleAmount({ value: recipe.yields.value, unit: recipe.yields.unit }, factor())) : recipe.yields?.text || "";
  $("#meta").textContent = [recipe.persons?.text || y, recipe.times?.text].filter(Boolean).join(" · ");
  const all = steps(), d = all.filter(({ step }) => state.done[step.id]).length;
  $("#progress").textContent = `${d} von ${all.length} Schritten`;
  $("#fill").style.width = `${all.length ? (d / all.length) * 100 : 0}%`;
  $("#planBtn").hidden = !schedule();
  document.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  document.querySelectorAll("[data-factor]").forEach((b) => b.setAttribute("aria-pressed", String(+b.dataset.factor === factor())));
  $("#factor").value = factor();
}
function renderMain() { ({ kochen: renderKochen, plan: renderPlan, einkauf: renderEinkauf, lesen: renderLesen, notizen: renderNotizen })[view](); }
function renderAll() { renderHeader(); renderMain(); renderDock(); if (openId) renderSheet(); }

// ---- Sheet (Details, Timer, Notiz) ----------------------------------------
function renderSheet() {
  const ctx = steps().find((x) => x.step.id === openId);
  if (!ctx) return;
  const { step: s, task, course } = ctx;
  const timers = (s.timers || []).flatMap((t, i) => timerChoices(t.duration).map((secs) => ({ i, label: t.label, secs })));
  const lbl = [course ? courseTitle(course) : null, task.name !== recipe.title ? task.name.replace(/\\~/g, "~") : null, `Schritt ${s.label}`].filter(Boolean).join(" · ");
  const scaledStep = { ...s, action: scaled(s.action, s) };
  const body = highlight(textWithAction(scaled(s.text, s), scaledStep), s);
  const details = [];
  if (s.duration) details.push(["Dauer", `${s.duration.source || [s.duration.min, s.duration.max].filter(Boolean).join("–") || s.duration.typical}${s.duration.estimated ? " (geschätzt)" : ""}`]);
  if (s.after) details.push(["Voraussetzung", s.after.length ? "Schritt " + s.after.map(labelOf).filter(Boolean).join(", ") : "keine — jederzeit möglich"]);
  if (s.start) details.push(["Zeitpunkt", `${s.start.offset.source || s.start.offset.min || s.start.offset.typical} (relativ zu ${esc(s.start.ref)})`]);
  if (s.temps?.length) details.push(["Temperatur", s.temps.map((t) => t.text).join(" · ")]);
  if (s.endCondition) details.push(["Fertig wenn", s.endCondition.text]);
  if (s.equipment?.length) details.push(["Gerät", s.equipment.join(", ")]);
  if (s.technique) details.push(["Technik", s.technique]);
  for (const p of task.produces || []) if (task.steps[task.steps.length - 1].id === s.id) details.push(["Ergibt", `${p.name}${p.hold?.source ? " — " + p.hold.source : ""}${p.storage?.note ? " (" + p.storage.note + ")" : ""}`]);
  if (task.consumes?.length && task.steps[0].id === s.id) details.push(["Braucht", task.consumes.map((c) => c.replace("product:", "")).join(", ")]);
  const seq = visibleOrder(), pos = seq.indexOf(s.id);
  const nav = pos < 0 ? "" : `<div class="nav"><button data-nav="-1" aria-label="Vorheriger Schritt" ${pos > 0 ? "" : "disabled"}>‹</button><small>${pos + 1}/${seq.length}</small><button data-nav="1" aria-label="Nächster Schritt" ${pos < seq.length - 1 ? "" : "disabled"}>›</button></div>`;
  sheet.innerHTML = `
    <div class="sheet-head"><h2 id="sheetTitle"><span class="lbl">${esc(lbl)}</span>${mdInline(s.title || task.name)}</h2>${nav}<button class="close" aria-label="Schließen">✕</button></div>
    <div class="md fulltext">${md(body)}</div>
    ${details.length ? `<dl class="details">${details.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdInline(v)}</dd>`).join("")}</dl>` : ""}
    ${s.events?.length ? `<h3>Zwischendurch</h3><ul>${s.events.map((e) => `<li>⏱ ${fmtClock(isoSeconds(e.at.typical || e.at.min))}: ${mdInline(e.text)}</li>`).join("")}</ul>` : ""}
    ${timers.length ? `<h3>Timer</h3><div class="tbtns">${timers.map((t) => `<button class="tbtn" data-start="${t.i}" data-secs="${t.secs}" data-label="${esc(t.label)}">▶ ${esc(t.label)}<small>${fmtClock(t.secs)}</small></button>`).join("")}</div>` : ""}
    <label class="donebar"><input type="checkbox" class="chk" data-done="${s.id}" ${state.done[s.id] ? "checked" : ""}><b>${state.done[s.id] ? "Erledigt" : "Als erledigt abhaken"}</b></label>`;
}
// Reihenfolge, wie die Hauptansicht sie gerade zeigt (Ablauf, nach Gang, Plan …); Dubletten nur einmal
function visibleOrder() {
  const ids = [...main.querySelectorAll("[data-open]")].map((el) => el.dataset.open);
  return [...new Set(ids.length ? ids : steps().map((x) => x.step.id))];
}
function stepNav(dir) {
  const seq = visibleOrder(), next = seq[seq.indexOf(openId) + dir];
  if (next) { openId = next; renderSheet(); sheet.scrollTop = 0; }
}
// Wischen im Detailblatt: links = nächster Schritt, rechts = vorheriger (nur klar horizontale Gesten)
let touch0 = null;
sheet.addEventListener("touchstart", (e) => { const t = e.touches[0]; touch0 = { x: t.clientX, y: t.clientY }; }, { passive: true });
sheet.addEventListener("touchend", (e) => {
  if (!touch0) return;
  const t = e.changedTouches[0], dx = t.clientX - touch0.x, dy = t.clientY - touch0.y; touch0 = null;
  if (Math.abs(dx) > 70 && Math.abs(dx) > 2 * Math.abs(dy)) stepNav(dx < 0 ? 1 : -1);
}, { passive: true });
function openSheet(id) { openId = id; renderSheet(); sheet.classList.add("open"); backdrop.classList.add("open"); sheet.scrollTop = 0; }
function closeSheet() { openId = null; sheet.classList.remove("open"); backdrop.classList.remove("open"); renderMain(); }
backdrop.onclick = closeSheet;
document.addEventListener("keydown", (e) => {
  if (!openId) return;
  if (e.key === "Escape") closeSheet();
  else if (e.key === "ArrowRight") stepNav(1);
  else if (e.key === "ArrowLeft") stepNav(-1);
});

// ---- Timer (Dock, überlebt Reload via Endzeit) -----------------------------
const remaining = (t) => (t.paused ? t.left : t.end - Date.now());
function startTimer(step, label, secs) {
  unlockAudio();
  state.timers.push({ id: Math.random().toString(36).slice(2, 9), step: step.id, label, end: Date.now() + secs * 1000, paused: false, left: 0 });
  save(); renderAll(); toast(`Timer läuft: ${label}`);
}
function timerAction(id, act) {
  const t = state.timers.find((x) => x.id === id); if (!t) return;
  if (act === "stop") state.timers = state.timers.filter((x) => x.id !== id);
  else if (act === "plus") { if (t.paused) t.left += 60000; else t.end = Math.max(t.end, Date.now()) + 60000; }
  else if (act === "pause") { if (t.paused) { t.end = Date.now() + t.left; t.paused = false; } else { t.left = t.end - Date.now(); t.paused = true; } }
  save(); renderAll();
}
function renderDock() {
  if (!state.timers.length) { dock.innerHTML = `<span class="lead">Keine Timer aktiv. Timer startest du in einem Schritt.</span>`; return; }
  dock.innerHTML = `<span class="lead">${state.timers.length} Timer</span>` + state.timers.slice().sort((a, b) => remaining(a) - remaining(b)).map((t) => {
    const s = stepOf(t.step), rem = remaining(t), ring = rem <= 0;
    return `<div class="tm ${ring ? "ring" : ""} ${t.paused ? "paused" : ""}" data-tid="${t.id}">
      <div class="lab"><b>${esc(t.label)}</b><span>${s ? esc(s.label + ". " + (s.title || "")) : ""}</span></div>
      <div class="time" data-time="${t.id}">${ring ? "Fertig" : fmtClock(rem / 1000)}</div>
      ${ring ? `<button data-tact="stop" aria-label="Timer beenden">OK</button><button data-tact="plus" aria-label="Eine Minute mehr">+1</button>`
             : `<button data-tact="plus" aria-label="Eine Minute mehr">+1</button><button data-tact="pause" aria-label="${t.paused ? "Fortsetzen" : "Pausieren"}">${t.paused ? "▶" : "❚❚"}</button><button data-tact="stop" aria-label="Timer löschen">✕</button>`}
    </div>`;
  }).join("");
}
let audioCtx = null;
function unlockAudio() { try { audioCtx ||= new (window.AudioContext || window.webkitAudioContext)(); if (audioCtx.state === "suspended") audioCtx.resume(); } catch {} }
function beep() {
  if (!audioCtx) return;
  try {
    const now = audioCtx.currentTime;
    [0, .25, .5].forEach((o) => { const os = audioCtx.createOscillator(), g = audioCtx.createGain(); os.type = "square"; os.frequency.value = 880;
      g.gain.setValueAtTime(.0001, now + o); g.gain.exponentialRampToValueAtTime(.25, now + o + .02); g.gain.exponentialRampToValueAtTime(.0001, now + o + .18);
      os.connect(g).connect(audioCtx.destination); os.start(now + o); os.stop(now + o + .2); });
  } catch {}
}
let lastBeep = 0; const wasRinging = new Set();
setInterval(() => {
  if (!recipe) return;
  let ringing = false, structural = false;
  for (const t of state.timers) {
    const rem = remaining(t);
    if (rem <= 0) { ringing = true; if (!wasRinging.has(t.id)) { wasRinging.add(t.id); structural = true; } }
    else if (wasRinging.has(t.id)) { wasRinging.delete(t.id); structural = true; }
    const el = document.querySelector(`[data-time="${t.id}"]`); if (el && rem > 0) el.textContent = fmtClock(rem / 1000);
  }
  document.querySelectorAll("[data-run]").forEach((el) => {
    const ts = state.timers.filter((t) => t.step === el.dataset.run); if (!ts.length) return;
    const rem = Math.min(...ts.map(remaining)); if (rem > 0) el.textContent = fmtClock(rem / 1000);
  });
  if (structural) { renderDock(); renderMain(); }
  if (ringing && Date.now() - lastBeep > 2000) { lastBeep = Date.now(); beep(); try { navigator.vibrate?.([300, 150, 300]); } catch {} }
}, 500);

// ---- Wake Lock ---------------------------------------------------------------
let wakeLock = null, wantWake = false;
const wakeBtn = $("#wake");
async function setWake(on) {
  wantWake = on;
  try {
    if (on) { wakeLock = await navigator.wakeLock.request("screen"); wakeLock.addEventListener("release", () => { wakeLock = null; if (!wantWake) wakeBtn.setAttribute("aria-pressed", "false"); }); }
    else if (wakeLock) { await wakeLock.release(); wakeLock = null; }
    wakeBtn.setAttribute("aria-pressed", String(on));
  } catch { wantWake = false; wakeBtn.setAttribute("aria-pressed", "false"); toast("Wach halten wird hier nicht unterstützt."); }
}
wakeBtn.onclick = () => { unlockAudio(); setWake(!wantWake); };
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && wantWake && !wakeLock) setWake(true); });

// ---- Ereignisse -------------------------------------------------------------
document.addEventListener("click", (e) => {
  if (e.target.closest(".close")) return closeSheet();
  const nv = e.target.closest("[data-nav]"); if (nv) { stepNav(+nv.dataset.nav); return; }
  if (e.target.id === "reset") {
    if (confirm("Alle Haken, Timer und Einkaufs-Haken dieses Rezepts zurücksetzen?\nNotiz, Menge und Varianten-Wahl bleiben.")) { state = resetState(state); save(); renderAll(); toast("Zurückgesetzt — bereit zum Kochen"); }
    return;
  }
  const st = e.target.closest("[data-start]"); if (st) { startTimer(stepOf(openId), st.dataset.label, +st.dataset.secs); return; }
  const o = e.target.closest("[data-open]"); if (o && !sheet.contains(o)) { openSheet(o.dataset.open); return; }
  const ta = e.target.closest("[data-tact]"); if (ta) { timerAction(ta.closest("[data-tid]").dataset.tid, ta.dataset.tact); return; }
  const v = e.target.closest("[data-view]"); if (v) { view = v.dataset.view; renderAll(); return; }
  const f = e.target.closest("[data-factor]"); if (f) { state.factor = +f.dataset.factor; save(); renderAll(); return; }
  const od = e.target.closest("[data-order]"); if (od) { state.order = od.dataset.order; save(); renderMain(); return; }
  if (e.target.id === "copyMd") {
    const txt = exportMarkdown();
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => toast("Kopiert"))
      .catch(() => { const ta = $("#mdOut"); ta.focus(); ta.select(); toast("Markiert, jetzt kopieren"); });
    return;
  }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.done) {
    // Schritt mit mehr als der Kurzansicht: Haken in der Liste öffnet erst die Details, abgehakt wird dort
    const st = stepOf(t.dataset.done);
    if (t.checked && st && !sheet.contains(t) && moreCount(st)) { t.checked = false; openSheet(st.id); return; }
    if (t.checked) state.done[t.dataset.done] = true; else delete state.done[t.dataset.done]; save(); renderAll();
  }
  else if (t.dataset.shop) { state.shop[t.dataset.shop] = t.checked; save(); t.closest("li").classList.toggle("have", t.checked); }
  else if (t.id === "factor") { state.factor = +t.value || 1; save(); renderAll(); }
  else if (t.dataset.variant) { state.variant = { ...state.variant, [t.dataset.variant]: t.value }; save(); renderAll(); }
});
let toastT; function toast(m) { const el = $("#toast"); el.textContent = m; el.style.display = "block"; clearTimeout(toastT); toastT = setTimeout(() => (el.style.display = "none"), 2200); }

// ---- Start -------------------------------------------------------------------
(async () => {
  try { recipe = await (await fetch(RECIPE_URL)).json(); }
  catch (err) { main.innerHTML = `<p class="empty">Rezept konnte nicht geladen werden: <code>${esc(RECIPE_URL)}</code> (${esc(err.message)})</p>`; return; }
  for (const i of recipe.ingredients || []) ingById[i.id] = i;
  state = loadState(recipe.id);
  if (isMenu() && schedule() && !state.viewSeen) view = "plan";
  renderAll();
})();
