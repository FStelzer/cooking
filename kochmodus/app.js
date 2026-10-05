import { escapeTilde, fmtAmount, fmtClock, highlight, isoSeconds, notesMarkdown, scaleAmount,
         scaleStepText, timerChoices } from "./lib.js";

const params = new URLSearchParams(location.search);
const RECIPE_URL = params.get("r") || "../schema/beispiele/thit-kho-trung.json";
const $ = (sel, el = document) => el.querySelector(sel);
const md = (s) => marked.parse(escapeTilde(s || ""), { breaks: false });
const mdInline = (s) => marked.parseInline(escapeTilde(s || ""));

let recipe, state, view = "kochen";
const ingById = {};

// ---- Zustand (localStorage, Schlüssel = Rezept-ID + Slug) -----------------
function loadState(id) {
  try { return JSON.parse(localStorage.getItem("km:" + id)) || {}; } catch { return {}; }
}
function saveState() {
  try { localStorage.setItem("km:" + recipe.id, JSON.stringify(state)); } catch {}
}
function factor() { return +state.factor || 1; }

// ---- Rendering -------------------------------------------------------------
function stepsOf(r) {
  const out = [];
  for (const sec of r.sections) if (sec.type === "tasks")
    for (const task of sec.tasks) for (const step of task.steps) out.push({ task, step });
  return out;
}

function stepBody(step, full) {
  const f = factor();
  const text = scaleStepText(step.text, step, f, ingById);
  const action = scaleStepText(step.action, step, f, ingById);
  if (!full) return `<div class="md">${md(action)}</div>`;
  return `<div class="md">${md(highlight(text, step))}</div>`;
}

function timerHtml(step) {
  const timers = [];
  (step.timers || []).forEach((t, i) => timerChoices(t.duration).forEach((secs, j) =>
    timers.push({ key: `${step.id}#${i}.${j}`, label: `${t.label} ${fmtClock(secs)}`, secs })));
  if (!timers.length) return "";
  return `<div class="timers">` + timers.map((t) => {
    const end = state.timers?.[t.key];
    const cls = end ? (end <= Date.now() ? "timer due" : "timer running") : "timer";
    return `<button class="${cls}" data-timer="${t.key}" data-secs="${t.secs}">${t.label}</button>`;
  }).join("") + `</div>`;
}

function eventsHtml(step) {
  if (!step.events?.length) return "";
  return `<div class="events fine">` + step.events.map((e) =>
    `⏱ ${fmtClock(isoSeconds(e.at.typical || e.at.min))}: ${mdInline(e.text)}`).join("<br>") + `</div>`;
}

function depsHtml(step, all) {
  if (!step.after) return "";
  if (!step.after.length) return `<div class="deps">jederzeit möglich</div>`;
  const labels = step.after.map((ref) => all.find((x) => "step:" + x.step.id === ref)?.step.label).filter(Boolean);
  return `<div class="deps">nach Schritt ${labels.join(", ")}</div>`;
}

function renderKochen() {
  const all = stepsOf(recipe);
  const cards = all.map(({ step }) => {
    const done = !!state.done?.[step.id];
    const dur = step.duration ? ` <span class="fine">(${step.duration.source || ""}${step.duration.estimated ? ", geschätzt" : ""})</span>` : "";
    return `<section class="card${done ? " done" : ""}" data-step="${step.id}">
      <div class="head">
        <input type="checkbox" data-done="${step.id}" ${done ? "checked" : ""}>
        <div><h3>${step.label}. ${mdInline(step.title || "")}${dur}</h3>${depsHtml(step, all)}</div>
      </div>
      <div class="body">${stepBody(step, false)}
        <details><summary>Details, Warum, Rettung</summary>${stepBody(step, true)}</details>
        ${timerHtml(step)}${eventsHtml(step)}
        <textarea class="note" data-note="${step.id}" placeholder="Notiz zu diesem Schritt …">${state.notes?.[step.id] || ""}</textarea>
      </div></section>`;
  }).join("");
  const legend = `<p class="legend"><mark class="cue">Erkennungszeichen</mark> <mark class="limit">Grenze</mark> <mark class="why">Warum</mark> <mark class="rescue">Rettung</mark></p>`;
  return legend + cards + `<p><button class="btn" id="export">Notizen exportieren</button> <button class="btn" id="reset">Abhaken zurücksetzen</button></p><pre class="export" id="exportOut" hidden></pre>`;
}

function renderEinkauf() {
  const d = recipe.derived;
  if (!d) return `<p>Kein <code>derived</code>-Block im JSON — <code>cli derive</code> ausführen.</p>`;
  const f = factor();
  let html = "", store = null;
  for (const g of d.shopping) {
    if (g.store !== store) { store = g.store; html += `<h3>${store}</h3>`; }
    if (g.group) html += `<p><b>${g.group}:</b></p>`;
    html += `<ul class="shop">` + g.items.map((it) => {
      const have = it.inStock || state.shop?.[it.ingredient];
      const need = f === 1 ? it.display : fmtAmount(scaleAmount(it.need, f, ingById[it.ingredient]));
      const buy = it.buy ? `${it.buy.text} ` : "";
      const note = it.note ? ` <span class="fine">${mdInline(it.note.replace(/^\*\(?|\)?\*$/g, ""))}</span>` : "";
      return `<li class="${have ? "have" : ""}"><input type="checkbox" data-shop="${it.ingredient}" ${have ? "checked" : ""}>
        <span>${it.optional ? "Optional: " : ""}${buy}${need ? need + " " : ""}${it.name}${note}</span></li>`;
    }).join("") + `</ul>`;
  }
  return html + `<p class="fine">Abgehakt wird nur hier im Browser gespeichert. Mengen ×${f}.</p>`;
}

function renderLesen() {
  let html = `<div class="md">${md(recipe.intro)}</div>`;
  for (const sec of recipe.sections) {
    html += `<h2>${sec.title}</h2>`;
    if (sec.type === "markdown") html += `<div class="md">${md(sec.markdown)}</div>`;
    else if (sec.type === "shopping") html += renderEinkauf();
    else if (sec.type === "tasks") for (const task of sec.tasks) for (const step of task.steps)
      html += `<div class="card"><div class="md">${md(step.heading || `**${step.label}. ${step.title || ""}**`)}</div>${stepBody(step, true)}${eventsHtml(step)}</div>`;
    else if (sec.type === "learnings") {
      html += `<div class="md">${md(sec.summary)}${md(sec.details)}</div>`;
      if (sec.notes?.length) html += `<p><b>Notizen mit Schritt-Bezug:</b></p><ul>` + sec.notes.map((n) => `<li><code>${n.ref}</code> ${n.status === "open" ? "⏳" : "✓"} ${mdInline(n.text)}</li>`).join("") + `</ul>`;
    } else if (sec.type === "todo") html += `<ul>` + sec.items.map((i) => `<li>${i.checked ? "☑" : "☐"} ${mdInline(i.text)}</li>`).join("") + `</ul>`;
  }
  return html;
}

function render() {
  $("#title").textContent = recipe.title;
  const y = recipe.yields?.value ? `${fmtAmount(scaleAmount({ value: recipe.yields.value, unit: recipe.yields.unit }, factor()))}` : recipe.yields?.text;
  $("#meta").innerHTML = `<span>${y || ""}</span>` + (recipe.times ? `<span>· ${recipe.times.text}</span>` : "");
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $("#factor").value = factor();
  $("#main").innerHTML = view === "kochen" ? renderKochen() : view === "einkauf" ? renderEinkauf() : renderLesen();
}

// ---- Timer -----------------------------------------------------------------
let audioCtx;
function beep() {
  try {
    audioCtx ||= new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.connect(g); g.connect(audioCtx.destination); o.frequency.value = 880; g.gain.value = .2;
    o.start(); o.stop(audioCtx.currentTime + .6);
  } catch {}
  navigator.vibrate?.([200, 100, 200]);
}
const alarmed = new Set();
function tick() {
  const now = Date.now();
  document.querySelectorAll("[data-timer]").forEach((b) => {
    const end = state.timers?.[b.dataset.timer];
    if (!end) return;
    const left = (end - now) / 1000;
    b.textContent = b.textContent.replace(/[\d:]+$/, fmtClock(left));
    if (left <= 0) {
      b.classList.add("due");
      if (!alarmed.has(b.dataset.timer)) { alarmed.add(b.dataset.timer); beep(); document.title = "⏰ " + recipe.title; }
    }
  });
}
setInterval(tick, 1000);

// ---- Ereignisse ------------------------------------------------------------
document.addEventListener("click", (e) => {
  const t = e.target.closest("button");
  if (!t) return;
  if (t.dataset.view) { view = t.dataset.view; render(); }
  else if (t.dataset.factor) { state.factor = +t.dataset.factor; saveState(); render(); }
  else if (t.dataset.timer) {
    state.timers ||= {};
    if (state.timers[t.dataset.timer]) { delete state.timers[t.dataset.timer]; alarmed.delete(t.dataset.timer); document.title = "Kochmodus"; }
    else state.timers[t.dataset.timer] = Date.now() + 1000 * +t.dataset.secs;
    saveState(); render(); tick();
  } else if (t.id === "export") {
    const notes = stepsOf(recipe).filter(({ step }) => state.notes?.[step.id]?.trim())
      .map(({ step }) => ({ slug: step.id, label: step.label, text: state.notes[step.id] }));
    const d = new Date(), date = `${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
    const out = $("#exportOut"); out.hidden = false; out.textContent = notesMarkdown(recipe.id, notes, date);
    navigator.clipboard?.writeText(out.textContent).catch(() => {});
  } else if (t.id === "reset") { state.done = {}; state.timers = {}; saveState(); render(); }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.done) { (state.done ||= {})[t.dataset.done] = t.checked; saveState(); t.closest(".card").classList.toggle("done", t.checked); }
  else if (t.dataset.shop) { (state.shop ||= {})[t.dataset.shop] = t.checked; saveState(); t.closest("li").classList.toggle("have", t.checked); }
  else if (t.id === "factor") { state.factor = +t.value || 1; saveState(); render(); }
});
document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.dataset.note) { (state.notes ||= {})[t.dataset.note] = t.value; saveState(); }
});

// ---- Start -----------------------------------------------------------------
(async () => {
  try {
    recipe = await (await fetch(RECIPE_URL)).json();
  } catch (err) {
    $("#main").innerHTML = `<p>Rezept konnte nicht geladen werden: <code>${RECIPE_URL}</code> (${err.message})</p>`;
    return;
  }
  for (const i of recipe.ingredients || []) ingById[i.id] = i;
  state = loadState(recipe.id);
  render();
  navigator.wakeLock?.request("screen").catch(() => {});  // Bildschirm an, wenn erlaubt
})();
