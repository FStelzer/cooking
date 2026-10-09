import { escapeTilde, plainTitle, fmtAmount, fmtClock, highlight, isActive, isoSeconds, moreCount, normalizeState, normalizeTimers,
         noteMarkdown, resetState, shortTitle, timerOrigin,
         scaleAmount, scaleStepText, selection, selectionKey, textWithAction, timerChoices, variantText } from "./lib.js";

const params = new URLSearchParams(location.search);
// Rezept: ?r=…, sonst das zuletzt geöffnete (installierte App), sonst die Rezeptliste
const lastRecipe = (() => { try { return localStorage.getItem("km:last"); } catch { return null; } })();  // Klartext, kein JSON
const RECIPE_URL = params.has("liste") ? null : params.get("r") || lastRecipe;
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (s) => marked.parse(escapeTilde(s || ""));
const mdInline = (s) => marked.parseInline(escapeTilde(s || ""));

let recipe, state, view = "kochen", openId = null;
const ingById = {};
const main = $("#main"), sheet = $("#sheet"), backdrop = $("#backdrop"), dock = $("#dock");

// ---- Zustand (localStorage: „km:<Rezept-ID>“, „km:timers“, „km:last“) ------------------
// Privates Fenster, gesperrter Speicher: alles läuft weiter, nur ohne Gedächtnis.
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};
const loadState = (id) => normalizeState(store.get("km:" + id));
function save() { store.set("km:" + recipe.id, state); }
// Timer gelten rezeptübergreifend (ein Nudel-Timer klingelt auch, wenn man zum nächsten Rezept wechselt)
const loadTimers = () => normalizeTimers(store.get("km:timers"));
let timers = loadTimers();
function saveTimers() { store.set("km:timers", timers); }
// Nach einer Timer-Änderung: Dock und die Laufzeit-Badges der Kochen-Liste, nicht die ganze Seite
function timersChanged({ persist = true } = {}) {
  if (persist) saveTimers();
  renderDock();
  if (recipe && view === "kochen") renderMain();
  if (openId) renderSheet();
}
const myTimers = () => timers.filter((t) => recipe && t.recipe === recipe.id);
// Anderer Tab hat Timer geändert: übernehmen und alles neu zeichnen, was Timer zeigt (Dock, Badges, Blatt)
window.addEventListener("storage", (e) => { if (e.key === "km:timers") { timers = loadTimers(); timersChanged({ persist: false }); } });
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
// Schritte eines Zeitplan-Eintrags: genannte Schritte und Tasks vereinigt, Schritte zuerst, ohne Dubletten
function entrySteps(e, byId, byTask) {
  const seen = new Set(), xs = [];
  for (const x of [...(e.steps || []).map((id) => byId[id]), ...(e.tasks || []).flatMap((t) => byTask[t] || [])]) {
    if (x && !seen.has(x.step.id)) { seen.add(x.step.id); xs.push(x); }
  }
  return xs;
}
function stepIndex() {
  const all = steps(), byId = Object.fromEntries(all.map((x) => [x.step.id, x])), byTask = {};
  for (const x of all) (byTask[x.task.id] ||= []).push(x);
  return { all, byId, byTask };
}

// ---- Ansichten -------------------------------------------------------------
// Kürzeste Restzeit der laufenden Timer eines Schritts (null = keiner)
function stepRemaining(stepId) {
  const ts = myTimers().filter((t) => t.step === stepId);
  return ts.length ? Math.min(...ts.map(remaining)) : null;
}
function runBadge(step) {
  const rem = stepRemaining(step.id);
  if (rem === null) return "";
  return `<span class="run ${rem <= 0 ? "ring" : ""}" data-run="${step.id}">${rem <= 0 ? "Fertig" : fmtClock(rem / 1000)}</span>`;
}
function stepRow(s, course = null, task = null) {
  const dur = s.duration ? `${s.duration.source || ""}${s.duration.estimated ? " (geschätzt)" : ""}` : "";
  const deps = !s.after ? "" : s.after.length ? "nach " + s.after.map(labelOf).filter(Boolean).join(", ") : "jederzeit";
  const meta = [course ? courseTitle(course) : "", dur, deps].filter(Boolean).join(" · ");
  const title = s.title || (task && task.name !== recipe.title ? task.name : "");
  return `<div class="row ${state.done[s.id] ? "done" : ""} ${s.after && !s.after.length ? "free" : ""} ${s.id === openId ? "current" : ""}" data-step="${s.id}">
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
  const { all, byId, byTask } = stepIndex();
  const placed = new Set();
  for (const p of sec.schedule.phases) {
    const es = liveEntries(sec.schedule).filter((e) => e.phase === p.id);
    if (!es.length) continue;
    html += `<section class="phase"><h2>${esc(p.label)}</h2>`;
    for (const e of es) {
      const xs = entrySteps(e, byId, byTask);
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
  const { byId, byTask } = stepIndex();
  const ids = (e) => entrySteps(e, byId, byTask).map((x) => x.step.id);
  const done = (e) => { const xs = ids(e); return xs.length && xs.every((id) => state.done[id]); };
  let h = `<div class="gantt-scroll"><div class="gantt" style="--cols:${sch.phases.length}"><div class="ph corner"></div>`;
  h += sch.phases.map((p) => `<div class="ph">${esc(p.label)}</div>`).join("");
  for (const lane of lanes) {
    h += `<div class="lane">${esc(lane.name)}</div>`;
    for (const p of sch.phases) {
      const es = sch.entries.filter((e) => e.phase === p.id && (e.course || null) === lane.id);
      h += `<div class="cell">` + es.map((e) => {
        // Chip öffnet den ersten Schritt; data-steps nennt alle, damit Wischen keinen auslässt
        const xs = ids(e), first = xs[0];
        return `<button class="chip ${done(e) ? "done" : ""} ${e.derived ? "derived" : ""} ${first ? "" : "plain"}" ${first ? `data-open="${first}" data-steps="${xs.join(" ")}"` : ""}>
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
  $("#title").textContent = plainTitle(recipe.title);
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
  const choices = (s.timers || []).flatMap((t, i) => timerChoices(t.duration).map((secs) => ({ i, label: t.label, secs })));
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
    ${choices.length ? `<h3>Timer</h3><div class="tbtns">${choices.map((t) => `<button class="tbtn" data-start="${t.i}" data-secs="${t.secs}" data-label="${esc(t.label)}">▶ ${esc(t.label)}<small>${fmtClock(t.secs)}</small></button>`).join("")}</div>` : ""}
    <label class="donebar"><input type="checkbox" class="chk" data-done="${s.id}" ${state.done[s.id] ? "checked" : ""}><b>${state.done[s.id] ? "Erledigt" : "Als erledigt abhaken"}</b></label>`;
}
// Reihenfolge, wie die Hauptansicht sie gerade zeigt (Ablauf, nach Gang, Plan …); Dubletten nur einmal.
// Plan-Chips stehen für mehrere Schritte (data-steps) — gewischt wird durch jeden davon.
function visibleOrder() {
  const ids = [...main.querySelectorAll("[data-open]")].flatMap((el) => el.dataset.steps?.split(" ") || [el.dataset.open]);
  return [...new Set(ids.length ? ids : steps().map((x) => x.step.id))];
}
function stepNav(dir) {
  const seq = visibleOrder(), next = seq[seq.indexOf(openId) + dir];
  if (next) { openId = next; markCurrent(); renderSheet(); sheet.scrollTop = 0; scrollToCurrent(); }
}
// Offenen Schritt in der Liste markieren, ohne die ganze Ansicht neu zu rendern (stepRow setzt die Klasse beim Rendern)
function markCurrent() {
  main.querySelectorAll(".row.current").forEach((r) => r.classList.remove("current"));
  if (openId) main.querySelectorAll(`.row[data-step="${CSS.escape(openId)}"]`).forEach((r) => r.classList.add("current"));
}
// Wischen im Detailblatt: links = nächster Schritt, rechts = vorheriger (nur klar horizontale Gesten)
let touch0 = null;
sheet.addEventListener("touchstart", (e) => { const t = e.touches[0]; touch0 = { x: t.clientX, y: t.clientY }; }, { passive: true });
sheet.addEventListener("touchend", (e) => {
  if (!touch0) return;
  const t = e.changedTouches[0], dx = t.clientX - touch0.x, dy = t.clientY - touch0.y; touch0 = null;
  if (Math.abs(dx) > 70 && Math.abs(dx) > 2 * Math.abs(dy)) stepNav(dx < 0 ? 1 : -1);
}, { passive: true });
// Breite Bildschirme (Tablet quer, Desktop): Detailblatt rechts neben der Liste statt darüber (CSS: body.sheet-open)
const split = () => matchMedia("(min-width: 900px)").matches;
function scrollToCurrent() { if (split()) main.querySelector(".row.current")?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
function openSheet(id) {
  openId = id; document.body.classList.add("sheet-open"); markCurrent(); renderSheet();
  sheet.classList.add("open"); backdrop.classList.add("open"); sheet.scrollTop = 0;
}
function closeSheet() { openId = null; document.body.classList.remove("sheet-open"); sheet.classList.remove("open"); backdrop.classList.remove("open"); renderMain(); }
backdrop.onclick = closeSheet;
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.target.id === "qmin" || e.target.id === "qlabel")) {
    const s = customSecs();
    if (s > 0) startQuick(s); else { toast("Minuten eingeben oder eine Vorwahl tippen"); $("#qmin")?.focus(); }
    return;
  }
  if (e.key === "Escape" && $("#quick")) { $("#quick").remove(); return; }
  if (!openId) return;
  if (e.target.matches?.("textarea, select, input:not([type=checkbox])")) return;  // Pfeiltasten und Escape gehören dem Eingabefeld
  if (e.key === "Escape") closeSheet();
  else if (e.key === "ArrowRight") stepNav(1);
  else if (e.key === "ArrowLeft") stepNav(-1);
});

// ---- Timer (Dock, überlebt Reload via Endzeit) -----------------------------
const remaining = (t) => (t.paused ? t.left : t.end - Date.now());
function startTimer(step, label, secs) {  // step = null: Schnell-Timer ohne Schrittbezug
  unlockAudio();
  timers.push({ id: Math.random().toString(36).slice(2, 9), label, end: Date.now() + secs * 1000, paused: false, left: 0,
                recipe: recipe?.id ?? null, recipeTitle: shortTitle(recipe?.title), step: step?.id ?? null,
                stepText: step ? `${step.label}. ${step.title || ""}`.trim() : "" });
  timersChanged(); toast(`Timer läuft: ${label}`);
}
function timerAction(id, act) {
  const t = timers.find((x) => x.id === id); if (!t) return;
  if (act === "stop") timers = timers.filter((x) => x.id !== id);
  else if (act === "plus") { if (t.paused) t.left += 60000; else t.end = Math.max(t.end, Date.now()) + 60000; }
  else if (act === "pause") { if (t.paused) { t.end = Date.now() + t.left; t.paused = false; } else { t.left = t.end - Date.now(); t.paused = true; } }
  timersChanged();
}
const QUICK = [1, 2, 3, 5, 8, 10, 12, 15, 20, 30, 45, 60];
function quickHtml() {
  return `<div class="quick" id="quick" role="dialog" aria-label="Schnell-Timer">
    <div class="qhead"><b>Schnell-Timer</b><button class="qclose" aria-label="Schließen">✕</button></div>
    <input id="qlabel" type="text" placeholder="Wofür? (z. B. Nudeln)" maxlength="40">
    <div class="qgrid">${QUICK.map((m) => `<button data-quick="${m * 60}">${m} Min.</button>`).join("")}</div>
    <div class="qcustom"><input id="qmin" type="number" min="0.5" step="0.5" placeholder="Min." aria-label="Minuten"><button data-quick="custom" class="btn primary">Start</button></div>
  </div>`;
}
const customSecs = () => Math.round((+$("#qmin")?.value || 0) * 60);
function startQuick(secs) {
  const label = $("#qlabel").value.trim() || `Timer ${fmtClock(secs)}`;
  $("#quick")?.remove(); startTimer(null, label, secs);
}
function renderDock() {
  const add = `<button class="addtimer" id="addTimer" aria-label="Schnell-Timer stellen">＋ Timer</button>`;
  if (!timers.length) { dock.innerHTML = add + `<span class="lead">Keine Timer aktiv — im Schritt oder hier per ＋.</span>`; return; }
  dock.innerHTML = add + `<span class="lead">${timers.length} Timer</span>` + timers.slice().sort((a, b) => remaining(a) - remaining(b)).map((t) => {
    const rem = remaining(t), ring = rem <= 0, o = timerOrigin(t, recipe?.id);
    const sub = o.foreign ? `<a class="origin" href="?r=${encodeURIComponent("../" + t.recipe + ".json")}">${esc(o.text)}</a>` : esc(o.text);
    return `<div class="tm ${ring ? "ring" : ""} ${t.paused ? "paused" : ""} ${o.foreign ? "foreign" : ""}" data-tid="${t.id}">
      <div class="lab"><b>${esc(t.label)}</b><span>${sub}</span></div>
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
  if (!timers.length) return;
  let ringing = false, structural = false;
  for (const t of timers) {
    const rem = remaining(t);
    if (rem <= 0) { ringing = true; if (!wasRinging.has(t.id)) { wasRinging.add(t.id); structural = true; } }
    else if (wasRinging.has(t.id)) { wasRinging.delete(t.id); structural = true; }
    const el = document.querySelector(`[data-time="${t.id}"]`); if (el && rem > 0) el.textContent = fmtClock(rem / 1000);
  }
  document.querySelectorAll("[data-run]").forEach((el) => {
    const rem = stepRemaining(el.dataset.run); if (rem > 0) el.textContent = fmtClock(rem / 1000);
  });
  if (structural) { renderDock(); if (recipe) renderMain(); }
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
  if (e.target.closest("#addTimer")) {
    // Fokus nur mit Maus/Tastatur — auf dem Handy schöbe die Bildschirmtastatur sich über die Vorwahlen
    if (!$("#quick")) { document.body.insertAdjacentHTML("beforeend", quickHtml()); if (matchMedia("(pointer: fine)").matches) $("#qlabel").focus(); }
    else $("#quick").remove();
    return;
  }
  if (e.target.closest(".qclose")) { $("#quick")?.remove(); return; }
  const q = e.target.closest("[data-quick]");
  if (q) { const secs = q.dataset.quick === "custom" ? customSecs() : +q.dataset.quick; if (secs > 0) startQuick(secs); return; }
  const nv = e.target.closest("[data-nav]"); if (nv) { stepNav(+nv.dataset.nav); return; }
  if (e.target.id === "reset") {
    if (confirm("Alle Haken, Timer und Einkaufs-Haken dieses Rezepts zurücksetzen?\nNotiz, Menge und Varianten-Wahl bleiben.")) {
      state = resetState(state); save(); timers = timers.filter((t) => t.recipe !== recipe.id); saveTimers(); renderAll(); toast("Zurückgesetzt — bereit zum Kochen");
    }
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

// ---- Rezeptliste (generiert: kochmodus/rezepte.json) ---------------------------
async function renderPicker() {
  document.body.classList.add("picker");
  renderDock();  // laufende Timer bleiben auch in der Rezeptliste sichtbar
  $("#title").textContent = "Kochmodus";
  $("#meta").textContent = "Rezept wählen";
  let list = [];
  try { list = await (await fetch("rezepte.json")).json(); } catch {}
  if (!list.length) { main.innerHTML = `<p class="empty">Keine Rezeptliste gefunden (<code>task index</code>).</p>`; return; }
  let html = "", group = null;
  for (const r of list) {
    if (r.group !== group) { group = r.group; html += `<h2>${esc(group)}</h2>`; }
    html += `<a class="pick" href="?r=${encodeURIComponent(r.path)}">${r.cooked ? "✅ " : ""}${r.wip ? "🚧 " : ""}${esc(plainTitle(r.title))}</a>`;
  }
  main.innerHTML = html;
}

// ---- Start -------------------------------------------------------------------
if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
const fromLast = RECIPE_URL && RECIPE_URL === lastRecipe && !params.get("r");
const sameOrigin = (u) => { try { return new URL(u, location.href).origin === location.origin; } catch { return false; } };
(async () => {
  if (!RECIPE_URL) return renderPicker();
  // Nur Rezepte dieser Seite: Rezepttext wird als Markdown/HTML gerendert, fremde Quellen hätten Zugriff auf km:*
  if (!sameOrigin(RECIPE_URL)) {
    main.innerHTML = `<p class="empty">Nur Rezepte dieser Seite können geöffnet werden: <code>${esc(RECIPE_URL)}</code></p>`; return;
  }
  try {
    const res = await fetch(RECIPE_URL);
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
    recipe = await res.json();
  } catch (err) {
    // Zuletzt geöffnetes Rezept nicht ladbar: Liste zeigen. Vergessen nur, wenn es das Rezept nicht mehr gibt (404) —
    // offline (Netzfehler, 503 vom Service Worker) bleibt die Erinnerung
    if (fromLast) {
      if (err.status === 404) store.del("km:last");
      return renderPicker();
    }
    main.innerHTML = `<p class="empty">Rezept konnte nicht geladen werden: <code>${esc(RECIPE_URL)}</code> (${esc(err.message)})</p>`; return;
  }
  for (const i of recipe.ingredients || []) ingById[i.id] = i;
  state = loadState(recipe.id);
  if (isMenu() && schedule()) view = "plan";
  renderAll();
  // Erst merken, wenn es sich rendern ließ — und nur Rezepte dieser Seite (der Start ohne ?r= lädt es ungefragt)
  try { localStorage.setItem("km:last", RECIPE_URL); } catch {}
  // Erster Besuch: das Rezept kam, bevor der Service Worker die Seite übernahm — einmal durch ihn holen, damit es offline da ist
  const sw = navigator.serviceWorker;
  if (sw && !sw.controller) sw.addEventListener("controllerchange", () => fetch(RECIPE_URL).catch(() => {}), { once: true });
})();
