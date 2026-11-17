import { escapeTilde, plainTitle, fmtAmount, fmtClock, highlight, isActive, isoSeconds, moreCount, normalizeState, normalizeTimers,
         noteMarkdown, phaseLabel, fmtSpan, resetState, shiftClock, shortTitle, timeline, timerOrigin,
         scaleAmount, scaleStepText, selection, selectionKey, textWithAction, timerChoices, variantText } from "./lib.js";

const params = new URLSearchParams(location.search);
// Rezept: ?r=…, sonst das zuletzt geöffnete (installierte App), sonst die Rezeptliste
const lastRecipe = (() => { try { return localStorage.getItem("km:last"); } catch { return null; } })();  // Klartext, kein JSON
const RECIPE_URL = params.has("liste") ? null : params.get("r") || lastRecipe;
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (s) => marked.parse(escapeTilde(s || ""));
const mdInline = (s) => marked.parseInline(escapeTilde(s || ""));

let recipe, recipeText = "", state, view = "kochen", openId = null;
let ingById = {};
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
// Anzeige-Nummer: blendet die Variante Schritte aus, laufen die sichtbaren pro Rezept/Gang lückenlos durch (16 → 17 statt 16 → 21)
function stepNumbers() {
  const nums = {};
  for (const scope of [recipe, ...courses()]) {
    const tasks = scope.sections.filter((s) => s.type === "tasks").flatMap((s) => s.tasks);
    const all = tasks.flatMap((t) => t.steps), vis = tasks.filter(live).flatMap((t) => t.steps.filter(live));
    vis.forEach((st, i) => { nums[st.id] = vis.length < all.length ? String(i + 1) : st.label; });
  }
  return nums;
}
// Im Menü mischen Ablauf und Plan die Gänge: dort trägt die Nummer den Gang („3.7“ = Gang 3, Schritt 7).
// „Nach Gang“ zeigt die Gänge getrennt und bleibt bei der Nummer aus dem Rezepttext.
const coursePrefix = (id) => { const m = /^gang-(\d+)-/.exec(id); return isMenu() && m ? m[1] + "." : ""; };
const num = (s, prefixed = false) => (prefixed ? coursePrefix(s.id) : "") + (stepNumbers()[s.id] ?? s.label);
const labelOf = (ref, prefixed = false) => { const s = stepOf(ref.replace(/^step:/, "")); return s && num(s, prefixed); }; // ausgeblendete Vorgänger fallen weg
function scaled(text, step) {
  const v = variantText(text, step, sel());
  return scaleStepText(v.text, { ...step, ingredients: v.ingredients }, factor(), ingById);
}
function courseTitle(c) { return c ? (recipe.courses?.find((x) => x.ref === c.id)?.name || c.title.replace(/^\d+\.\s*/, "")) : "Menü"; }
function schedules() { return recipe.sections.filter((s) => s.type === "schedule" && live(s.schedule)); }
function schedule() { return schedules()[0]; }
const liveEntries = (sch) => sch.entries.filter(live);
// Schritte eines Zeitplan-Eintrags: e.steps ist vollständig und in Rezeptreihenfolge (Parser: namentlich schlägt
// Komponente) — hier wird nichts mehr aus e.tasks ergänzt, sonst stünden Schritte doppelt und verdreht im Ablauf.
function entrySteps(e, byId) {
  return (e.steps || []).map((id) => byId[id]).filter(Boolean);
}
// ---- Essenszeit: Uhrzeiten des Zeitplans hängen an einer einstellbaren Zeit (Default: die des Rezepts) ----
// Jeder Zeitplan (Varianten!) bringt seine eigene Vorgabe mit; die eigene Wahl gilt für alle.
const defaultServe = (sec = schedule()) => sec?.schedule.anchorOverride?.time || recipe.anchor?.time || null;
const serveTime = (sec = schedule()) => state.serve || defaultServe(sec);
const hasTiming = () => { const sch = schedule()?.schedule; return !!sch && (sch.phases.some((p) => p.at != null) || sch.entries.some((e) => e.at)); };
const clk = (secs, sec) => shiftClock(serveTime(sec), secs);
function timelineOf(sec) {
  const serve = Object.fromEntries((recipe.courses || []).map((c) => [c.ref, isoSeconds(c.serve) || 0]));
  return timeline({ ...sec.schedule, entries: liveEntries(sec.schedule) }, stepIndex().byId, serve);
}
// „19:50–20:10“ für einen verzeiteten Schritt bzw. Eintrag; leer ohne Essenszeit
const whenOf = (segs, sec) => {
  const xs = (segs || []).filter((g) => g.timed);
  if (!xs.length || !serveTime(sec)) return "";
  const a = Math.min(...xs.map((g) => g.start)), b = Math.max(...xs.map((g) => g.end));
  return b > a ? `${clk(a, sec)}–${clk(b, sec)}` : clk(a, sec);
};
// Zeile unter dem Phasen-Titel: bis wann die Phase dauert bzw. wie viel aktive Arbeit in ihr steckt
function phaseSpan(p, sec, win) {
  const w = win[p.id], sch = sec.schedule;
  if (!w) return "";
  if (!w.timed || !serveTime(sec)) return w.active ? `ca. ${fmtSpan(w.active)} aktive Arbeit` : "";
  if (w.end == null || w.end <= w.start) return "";
  const next = Math.min(...sch.phases.map((x) => (x.at != null && x.part === "service" ? isoSeconds(x.at) : null)).filter((t) => t != null && t > w.start));
  return `bis ca. ${clk(w.end, sec)}` + (w.end > next ? ` <span class="over">— läuft in den nächsten Block (${clk(next, sec)})</span>` : "");
}
function renderServe() {
  const el = $("#serve");
  el.hidden = !hasTiming();
  if (el.hidden) return;
  const def = defaultServe(), st = serveTime(), sec = schedule();
  let sum = "Uhrzeit eintragen — dann stehen im Plan und im Ablauf Uhrzeiten.";
  if (st) {
    const { segs } = timelineOf(sec), ends = [...segs.values()].flat().filter((g) => g.timed).map((g) => g.end);
    const cs = isMenu() ? (recipe.courses || []).map((c) => `Gang ${c.n} ${clk(isoSeconds(c.serve) || 0)}`) : [];
    const last = Math.max(0, ...ends, ...(recipe.courses || []).map((c) => isoSeconds(c.serve) || 0));
    sum = [...cs, last > 0 ? `Ende ca. ${clk(last)}` : ""].filter(Boolean).join(" · ");
  }
  const reset = state.serve && def && state.serve !== def ? `<button class="btn" id="serveReset">↺ ${esc(def)}</button>` : "";
  // Beim Tippen im Zeitfeld nur die Zusammenfassung erneuern, sonst verliert das Feld den Fokus
  if (document.activeElement?.id === "serveTime") { $("#serveSum").innerHTML = esc(sum); $("#serveReset")?.remove(); el.querySelector("label").insertAdjacentHTML("afterend", reset); return; }
  el.innerHTML = `<label class="var">${esc(recipe.anchor?.time ? recipe.anchor.label : "Essen")} um <input type="time" id="serveTime" value="${esc(st || "")}"></label>${reset}<span class="fine" id="serveSum">${esc(sum)}</span>`;
}
function stepIndex() {
  const all = steps(), byId = Object.fromEntries(all.map((x) => [x.step.id, x]));
  return { all, byId };
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
function stepRow(s, course = null, task = null, when = "") {
  const dur = s.duration ? `${s.duration.source || ""}${s.duration.estimated ? " (geschätzt)" : ""}` : "";
  const pre = course != null; // mit Gang im Bild (Ablauf): Nummern mit Gang-Präfix
  const deps = !s.after ? "" : s.after.length ? "nach " + s.after.map((r) => labelOf(r, pre)).filter(Boolean).join(", ") : "jederzeit";
  const meta = [when, course ? courseTitle(course) : "", dur, deps].filter(Boolean).join(" · ");
  const title = s.title || (task && task.name !== recipe.title ? task.name : "");
  return `<div class="row ${state.done[s.id] ? "done" : ""} ${s.after && !s.after.length ? "free" : ""} ${s.id === openId ? "current" : ""}" data-step="${s.id}">
    <input type="checkbox" class="chk" data-done="${s.id}" aria-label="${esc(title || num(s, pre))} erledigt" ${state.done[s.id] ? "checked" : ""}>
    <div class="body" data-open="${s.id}">
      <div class="t">${esc(num(s, pre))}${pre && coursePrefix(s.id) ? "" : "."} ${mdInline(title)}</div>
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
  const { all, byId } = stepIndex();
  const placed = new Set(), { segs, win } = timelineOf(sec);
  for (const p of sec.schedule.phases) {
    const es = liveEntries(sec.schedule).filter((e) => e.phase === p.id);
    if (!es.length) continue;
    const span = phaseSpan(p, sec, win);
    html += `<section class="phase"><h2>${esc(phaseLabel(p, serveTime(sec)))}</h2>${span ? `<p class="span">${span}</p>` : ""}`;
    for (const e of es) {
      const xs = entrySteps(e, byId);
      if (!xs.length) { html += plainRow(`e:${p.id}:${e.text}`, e.text, e.course ? courseTitle(courses().find((c) => c.id === e.course)) : ""); continue; }
      html += `<p class="entry-head">${mdInline(e.text)}${e.derived ? ' <span class="fine">(abgeleitet)</span>' : ""}</p>`;
      for (const x of xs) { placed.add(x.step.id); html += stepRow(x.step, x.course, x.task, whenOf((segs.get(e) || []).filter((g) => g.id === x.step.id), sec)); }
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
  const { byId } = stepIndex(), { segs, win } = timelineOf(sec);
  const ids = (e) => entrySteps(e, byId).map((x) => x.step.id);
  const done = (e) => { const xs = ids(e); return xs.length && xs.every((id) => state.done[id]); };
  let h = `<div class="gantt-scroll"><div class="gantt" style="--cols:${sch.phases.length}"><div class="ph corner"></div>`;
  h += sch.phases.map((p) => { const span = phaseSpan(p, sec, win); return `<div class="ph">${esc(phaseLabel(p, serveTime(sec)))}${span ? `<small>${span}</small>` : ""}</div>`; }).join("");
  for (const lane of lanes) {
    h += `<div class="lane">${esc(lane.name)}</div>`;
    for (const [col, p] of sch.phases.entries()) {
      const es = sch.entries.filter((e) => e.phase === p.id && (e.course || null) === lane.id);
      h += `<div class="cell">` + es.map((e) => {
        // Chip öffnet den ersten Schritt; data-steps nennt alle, damit Wischen keinen auslässt
        const xs = ids(e), first = xs[0];
        return `<button class="chip ${done(e) ? "done" : ""} ${e.derived ? "derived" : ""} ${first ? "" : "plain"}" ${first ? `data-open="${first}" data-steps="${xs.join(" ")}" data-col="${col}"` : ""}>
          <span class="t">${mdInline(e.text)}</span>${whenOf(segs.get(e), sec) ? `<span class="m">${whenOf(segs.get(e), sec)}</span>` : e.at ? `<span class="m">${esc(e.at.offset.replace(/^([+-]?)PT/, "$1").toLowerCase())} zu ${esc(e.at.ref.split(":")[1])}</span>` : ""}</button>`;
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
      const note = it.note ? ` <span class="fine">(${mdInline(it.note.replace(/^\*\(?|\)?\*$/g, ""))})</span>` : "";
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
      if (task.intro) html += `<div class="md">${md(task.intro)}</div>`;
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
  renderVariants(); renderServe();
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
  const lbl = [course ? courseTitle(course) : null, task.name !== recipe.title ? task.name.replace(/\\~/g, "~") : null, `Schritt ${num(s, true)}`].filter(Boolean).join(" · ");
  const scaledStep = { ...s, action: scaled(s.action, s) };
  const body = highlight(textWithAction(scaled(s.text, s), scaledStep), s);
  const details = [];
  if (s.duration) details.push(["Dauer", `${s.duration.source || [s.duration.min, s.duration.max].filter(Boolean).join("–") || s.duration.typical}${s.duration.estimated ? " (geschätzt)" : ""}`]);
  if (s.after) details.push(["Voraussetzung", s.after.length ? "Schritt " + s.after.map((r) => labelOf(r, true)).filter(Boolean).join(", ") : "keine — jederzeit möglich"]);
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
    ${task.intro && task.steps[0].id === s.id ? `<div class="md intro">${md(task.intro)}${factor() !== 1 ? `<p class="fine">Mengen hier unskaliert (×1).</p>` : ""}</div>` : ""}
    <div class="md fulltext">${md(body)}</div>
    ${details.length ? `<dl class="details">${details.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdInline(v)}</dd>`).join("")}</dl>` : ""}
    ${s.events?.length ? `<h3>Zwischendurch</h3><ul>${s.events.map((e) => `<li>⏱ ${fmtClock(isoSeconds(e.at.typical || e.at.min))}: ${mdInline(e.text)}</li>`).join("")}</ul>` : ""}
    ${choices.length ? `<h3>Timer</h3><div class="tbtns">${choices.map((t) => `<button class="tbtn" data-start="${t.i}" data-secs="${t.secs}" data-label="${esc(t.label)}">▶ ${esc(t.label)}<small>${fmtClock(t.secs)}</small></button>`).join("")}</div>` : ""}
    <label class="donebar"><input type="checkbox" class="chk" data-done="${s.id}" ${state.done[s.id] ? "checked" : ""}><b>${state.done[s.id] ? "Erledigt" : "Als erledigt abhaken"}</b></label>`;
}
// Reihenfolge, wie die Hauptansicht sie gerade zeigt (Ablauf, nach Gang, Plan …); Dubletten nur einmal.
// Plan-Chips stehen für mehrere Schritte (data-steps) — gewischt wird durch jeden davon.
function visibleOrder() {
  // Plan: das Raster steht Gang für Gang im DOM — gewischt wird zeitlich, Phase für Phase (stabil: Gänge in ihrer Reihenfolge)
  const els = [...main.querySelectorAll("[data-open]")].sort((a, b) => (+a.dataset.col || 0) - (+b.dataset.col || 0));
  const ids = els.flatMap((el) => el.dataset.steps?.split(" ") || [el.dataset.open]);
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
// Zurück-Taste schließt das Blatt (auf dem Handy ist es Vollbild): ein Verlaufseintrag pro Öffnen, nicht pro Schritt
function openSheet(id) {
  if (!openId) history.pushState({ km: "sheet" }, "");
  openId = id; document.body.classList.add("sheet-open"); markCurrent(); renderSheet();
  sheet.classList.add("open"); backdrop.classList.add("open"); sheet.scrollTop = 0;
}
function closeSheet() { openId = null; document.body.classList.remove("sheet-open"); sheet.classList.remove("open"); backdrop.classList.remove("open"); renderMain(); }
function requestClose() { if (history.state?.km === "sheet") history.back(); else closeSheet(); }
window.addEventListener("popstate", () => { if (openId) closeSheet(); });
backdrop.onclick = requestClose;
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.target.id === "qmin" || e.target.id === "qlabel")) {
    const s = customSecs();
    if (s > 0) startQuick(s); else { toast("Minuten eingeben oder eine Vorwahl tippen"); $("#qmin")?.focus(); }
    return;
  }
  if (e.key === "Escape" && $("#quick")) { $("#quick").remove(); return; }
  if (!openId) return;
  if (e.target.matches?.("textarea, select, input:not([type=checkbox])")) return;  // Pfeiltasten und Escape gehören dem Eingabefeld
  if (e.key === "Escape") requestClose();
  else if (e.key === "ArrowRight") stepNav(1);
  else if (e.key === "ArrowLeft") stepNav(-1);
});

// ---- Timer (Dock, überlebt Reload via Endzeit) -----------------------------
const remaining = (t) => (t.paused ? t.left : t.end - Date.now());
function startTimer(step, label, secs) {  // step = null: Schnell-Timer ohne Schrittbezug
  unlockAudio();
  timers.push({ id: Math.random().toString(36).slice(2, 9), label, end: Date.now() + secs * 1000, paused: false, left: 0,
                recipe: recipe?.id ?? null, recipeTitle: shortTitle(recipe?.title), step: step?.id ?? null,
                stepText: step ? `${num(step)}. ${step.title || ""}`.trim() : "" });
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
  if (e.target.closest(".close")) return requestClose();
  if (e.target.id === "reload") return location.reload();
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
  if (e.target.id === "serveReset") { state.serve = null; save(); document.activeElement?.blur(); renderAll(); return; }
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
  else if (t.id === "serveTime") { state.serve = t.value && t.value !== defaultServe() ? t.value : null; save(); renderAll(); }
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
const LOAD_MS = 10000;  // länger als das SW-Warten aufs Netz (4 s), damit ein Cache-Stand vorher antworten kann
async function fetchRecipe(url) {
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), LOAD_MS);
  try {
    const res = await fetch(url, { signal: ctl.signal });
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
    return { text: await res.text(), offline: res.headers.get("x-km-offline") === "1" };
  } catch (err) {
    throw err.name === "AbortError" ? new Error(`keine Antwort nach ${LOAD_MS / 1000} s`) : err;
  } finally { clearTimeout(t); }
}
function applyRecipe({ text, offline }) {
  const r = JSON.parse(text);
  recipe = r; recipeText = text; ingById = {};
  for (const i of recipe.ingredients || []) ingById[i.id] = i;
  $("#status").textContent = offline ? "Offline-Stand · Lokal gespeichert" : "Lokal gespeichert";
}
function fail(html) { main.innerHTML = `<p class="empty">${html}</p><p><button class="btn" id="reload">Neu laden</button></p>`; }
// Seite war im Hintergrund (Handy): Rezept neu holen und nur bei Änderung neu zeichnen — Haken, Timer, Notiz bleiben
let lastCheck = Date.now();
async function refreshRecipe() {
  navigator.serviceWorker?.getRegistration().then((r) => r?.update()).catch(() => {});  // neue App-Version suchen
  if (!recipe || Date.now() - lastCheck < 30000) return;
  lastCheck = Date.now();
  let got;
  try { got = await fetchRecipe(RECIPE_URL); } catch { return; }
  if (got.offline || got.text === recipeText) return;
  try { applyRecipe(got); } catch { return; }
  if (openId && !stepOf(openId)) requestClose();
  renderAll(); toast("Rezept aktualisiert");
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshRecipe(); });
window.addEventListener("pageshow", (e) => { if (e.persisted) refreshRecipe(); });

const sw = "serviceWorker" in navigator && location.protocol !== "file:" ? navigator.serviceWorker : null;
if (sw) {
  // Neue App-Version übernimmt die Seite: einmal neu laden, damit Seite und Skripte zusammenpassen (Zustand liegt in
  // localStorage). Erster Besuch (noch kein SW): nur das Rezept einmal durch ihn holen, damit es offline da ist.
  const updating = !!sw.controller;
  sw.addEventListener("controllerchange", () => {
    if (updating) location.reload(); else if (RECIPE_URL) fetch(RECIPE_URL).catch(() => {});
  }, { once: true });
  sw.register("sw.js").catch(() => {});
}
if (history.state?.km === "sheet") history.replaceState(null, "");  // nach Reload ist kein Blatt offen
const fromLast = RECIPE_URL && RECIPE_URL === lastRecipe && !params.get("r");
const sameOrigin = (u) => { try { return new URL(u, location.href).origin === location.origin; } catch { return false; } };
(async () => {
  if (!RECIPE_URL) return renderPicker();
  // Nur Rezepte dieser Seite: Rezepttext wird als Markdown/HTML gerendert, fremde Quellen hätten Zugriff auf km:*
  if (!sameOrigin(RECIPE_URL)) {
    main.innerHTML = `<p class="empty">Nur Rezepte dieser Seite können geöffnet werden: <code>${esc(RECIPE_URL)}</code></p>`; return;
  }
  try {
    applyRecipe(await fetchRecipe(RECIPE_URL));
  } catch (err) {
    // Zuletzt geöffnetes Rezept nicht ladbar: Liste zeigen. Vergessen nur, wenn es das Rezept nicht mehr gibt (404) —
    // offline (Netzfehler, 503 vom Service Worker) bleibt die Erinnerung
    if (fromLast) {
      if (err.status === 404) store.del("km:last");
      return renderPicker();
    }
    return fail(`Rezept konnte nicht geladen werden: <code>${esc(RECIPE_URL)}</code> (${esc(err.message)})`);
  }
  if (typeof marked === "undefined") return fail("Die Markdown-Bibliothek (marked) wurde nicht geladen — Netz prüfen, dann neu laden.");
  state = loadState(recipe.id);
  if (isMenu() && schedule()) view = "plan";
  try { renderAll(); } catch (err) { return fail(`Anzeige fehlgeschlagen: ${esc(err.message)}`); }
  // Erst merken, wenn es sich rendern ließ — und nur Rezepte dieser Seite (der Start ohne ?r= lädt es ungefragt)
  try { localStorage.setItem("km:last", RECIPE_URL); } catch {}
})();
