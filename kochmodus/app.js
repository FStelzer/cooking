import { escapeTilde, fmtAmount, fmtClock, highlight, isoSeconds, normalizeState, notesMarkdown,
         remainderAfterAction, scaleAmount, scaleStepText, timerChoices } from "./lib.js";

const params = new URLSearchParams(location.search);
const RECIPE_URL = params.get("r") || "../schema/beispiele/thit-kho-trung.json";
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
function tasksOf(r, course = null) {
  const own = r.sections.filter((s) => s.type === "tasks").flatMap((s) => s.tasks.map((task) => ({ course, task })));
  return own.concat(courses().flatMap((c) => (r === recipe ? tasksOf(c, c) : [])));
}
function steps() { return tasksOf(recipe).flatMap(({ course, task }) => task.steps.map((step) => ({ course, task, step }))); }
const stepOf = (id) => steps().find((x) => x.step.id === id)?.step;
const labelOf = (ref) => stepOf(ref.replace(/^step:/, ""))?.label;
const scaled = (text, step) => scaleStepText(text, step, factor(), ingById);
function hasNote(id) { return !!state.notes[id]?.trim(); }
function courseTitle(c) { return c ? (recipe.courses?.find((x) => x.ref === c.id)?.name || c.title.replace(/^\d+\.\s*/, "")) : "Menü"; }
function schedule() { return recipe.sections.find((s) => s.type === "schedule"); }

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
      <div class="t">${esc(s.label)}. ${mdInline(title)}${hasNote(s.id) ? '<span class="hasnote" title="Notiz vorhanden"></span>' : ""}</div>
      ${meta ? `<div class="m">${esc(meta)}</div>` : ""}
      <div class="a md">${md(scaled(s.action, s))}</div>${runBadge(s)}
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
    const es = sec.schedule.entries.filter((e) => e.phase === p.id);
    if (!es.length) continue;
    html += `<section class="phase"><h2>${esc(p.label)}</h2>`;
    for (const e of es) {
      const xs = e.steps?.length ? e.steps.map((id) => byId[id]).filter(Boolean) : (e.tasks || []).flatMap((t) => byTask[t] || []);
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
  const sec = schedule();
  if (!sec) { main.innerHTML = `<p class="empty">Kein Zeitplan im Rezept.</p>`; return; }
  const sch = sec.schedule, lanes = [{ id: null, name: "Menü" }, ...courses().map((c) => ({ id: c.id, name: courseTitle(c) }))];
  const allTasks = Object.fromEntries(tasksOf(recipe).map(({ task }) => [task.id, task]));
  const done = (e) => (e.tasks || []).length && e.tasks.every((t) => allTasks[t]?.steps.every((s) => state.done[s.id]));
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
  main.innerHTML = h + `</div></div>` + (sec.note ? `<div class="md fine" style="margin-top:12px">${md(sec.note)}</div>` : "")
    + `<p class="fine">Chips mit Rand sind modellierte Aufgaben (antippen öffnet den ersten Schritt), graue sind nur Text. Gestrichelt = aus dem Rezept abgeleitet, steht nicht im Original-Zeitplan.</p>`;
}
function shoppingHtml() {
  const d = recipe.derived;
  if (!d) return `<p class="empty">Kein <code>derived</code>-Block im JSON — <code>cli derive</code> ausführen.</p>`;
  const f = factor();
  let html = "", store = null;
  for (const g of d.shopping) {
    if (g.store !== store) { store = g.store; html += `<h3>${esc(store)}</h3>`; }
    if (g.group) html += `<p class="fine"><b>${esc(g.group)}</b></p>`;
    html += `<ul class="shop">` + g.items.map((it) => {
      const have = it.inStock || state.shop[it.ingredient];
      const need = f === 1 ? it.display : fmtAmount(scaleAmount(it.need, f, ingById[it.ingredient]));
      const note = it.note ? ` <span class="fine">${mdInline(it.note.replace(/^\*\(?|\)?\*$/g, ""))}</span>` : "";
      const crs = (ingById[it.ingredient]?.courses || []).map((c) => c.replace("gang-", "G")).join("+");
      return `<li class="${have ? "have" : ""}"><input type="checkbox" class="chk" data-shop="${it.ingredient}" ${have ? "checked" : ""}>
        <span>${it.optional ? "Optional: " : ""}${it.buy ? esc(it.buy.text) + " " : ""}${need ? esc(need) + " " : ""}${esc(it.name)}${crs ? ` <span class="fine">(${crs})</span>` : ""}${note}</span></li>`;
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
      for (const s of task.steps) html += `<div class="card"><div class="md">${md(s.heading || `**${s.label}. ${s.title || ""}**`)}${md(highlight(scaled(s.text, s), s))}</div></div>`;
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
  return notesMarkdown(recipe.id, steps().filter(({ step }) => hasNote(step.id)).map(({ step, course }) => ({ slug: step.id, label: (course ? course.id.replace("gang-", "G") + "/" : "") + step.label, text: state.notes[step.id] })), date);
}
function renderNotizen() {
  const noted = steps().filter(({ step }) => hasNote(step.id));
  if (!noted.length) { main.innerHTML = `<p class="empty">Noch keine Notizen. Öffne einen Schritt und halte fest, was beim nächsten Mal anders laufen soll.</p>`; return; }
  main.innerHTML = `<div class="toolbar"><button class="btn primary" id="copyMd">Als Markdown kopieren</button><span class="status">Zum Einfügen unter „## Learnings“ im Rezept.</span></div>`
    + noted.map(({ step }) => `<div class="note" data-open="${step.id}"><b>${esc(step.label)}. ${esc(step.title || "")}</b>${esc(state.notes[step.id])}</div>`).join("")
    + `<h3>Vorschau</h3><textarea id="mdOut" readonly rows="8">${esc(exportMarkdown())}</textarea>`;
}
function renderHeader() {
  $("#title").textContent = recipe.title;
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
  const rest = remainderAfterAction(scaled(s.text, s), { ...s, action: scaled(s.action, s) });
  const timers = (s.timers || []).flatMap((t, i) => timerChoices(t.duration).map((secs) => ({ i, label: t.label, secs })));
  const lbl = [course ? courseTitle(course) : null, task.name !== (recipe.title) ? task.name : null, `Schritt ${s.label}`, s.duration?.source].filter(Boolean).join(" · ");
  sheet.innerHTML = `
    <div class="sheet-head"><h2 id="sheetTitle"><span class="lbl">${esc(lbl)}</span>${mdInline(s.title || task.name)}</h2><button class="close" aria-label="Schließen">✕</button></div>
    <div class="md action">${md(scaled(s.action, s))}</div>
    ${rest ? `<div class="md">${md(highlight(rest, s))}</div>` : ""}
    ${s.events?.length ? `<h3>Zwischendurch</h3><ul>${s.events.map((e) => `<li>⏱ ${fmtClock(isoSeconds(e.at.typical || e.at.min))}: ${mdInline(e.text)}</li>`).join("")}</ul>` : ""}
    ${timers.length ? `<h3>Timer</h3><div class="tbtns">${timers.map((t) => `<button class="tbtn" data-start="${t.i}" data-secs="${t.secs}" data-label="${esc(t.label)}">▶ ${esc(t.label)}<small>${fmtClock(t.secs)}</small></button>`).join("")}</div>` : ""}
    <label class="donebar"><input type="checkbox" class="chk" data-done="${s.id}" ${state.done[s.id] ? "checked" : ""}><b>${state.done[s.id] ? "Erledigt" : "Als erledigt abhaken"}</b></label>
    <h3>Notiz fürs nächste Mal</h3>
    <textarea id="noteBox" placeholder="Was lief gut, was ändern? z. B. Karamell dunkler, nächstes Mal 30 Sek. länger.">${esc(state.notes[s.id] || "")}</textarea>`;
  const nb = $("#noteBox", sheet); let nt;
  nb.oninput = () => { state.notes[s.id] = nb.value; clearTimeout(nt); nt = setTimeout(save, 400); };
}
function openSheet(id) { openId = id; renderSheet(); sheet.classList.add("open"); backdrop.classList.add("open"); sheet.scrollTop = 0; }
function closeSheet() { openId = null; sheet.classList.remove("open"); backdrop.classList.remove("open"); renderMain(); }
backdrop.onclick = closeSheet;
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && openId) closeSheet(); });

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
  }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.done) { if (t.checked) state.done[t.dataset.done] = true; else delete state.done[t.dataset.done]; save(); renderAll(); }
  else if (t.dataset.shop) { state.shop[t.dataset.shop] = t.checked; save(); t.closest("li").classList.toggle("have", t.checked); }
  else if (t.id === "factor") { state.factor = +t.value || 1; save(); renderAll(); }
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
