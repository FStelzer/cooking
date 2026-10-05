// Reine Funktionen des Kochmodus: Formatierung, Skalierung, Hervorhebung, Zeit.
// Keine Aggregation (L10): Einkaufsliste und Mengen kommen aus derived.*.

export const FRACTIONS = { 0.5: "½", 0.25: "¼", 0.75: "¾" };
const FRACTION_VALUES = { "½": 0.5, "¼": 0.25, "¾": 0.75 };

export function fmtNum(x) {
  if (FRACTIONS[x]) return FRACTIONS[x];
  if (x > 1 && FRACTIONS[x % 1]) return `${Math.floor(x)}${FRACTIONS[x % 1]}`; // 1,5 → „1½“
  if (Number.isInteger(x)) return String(x);
  return String(Math.round(x * 100) / 100).replace(".", ",");
}

export function fmtRange(lo, hi) {
  return hi == null || hi === lo ? fmtNum(lo) : `${fmtNum(lo)}–${fmtNum(hi)}`;
}

export function fmtAmount(a) {
  if (a.value == null) return a.text || "";
  let s = fmtRange(a.value, a.max);
  if (a.unit && a.unit !== "Stück") s += ` ${a.unit}`;
  return (a.approx ? "~" : "") + s;
}

// Rundung nach Einheit, damit „1,3333 Eier“ nicht entsteht.
export function roundFor(x, unit, mode) {
  if (mode === "fixed") return x;
  if (unit === "Stück" || mode === "step") return Math.max(0.5, Math.round(x * 2) / 2);
  if (unit === "EL" || unit === "TL") return Math.round(x * 4) / 4;
  if (unit === "g" || unit === "ml") return x >= 100 ? Math.round(x / 5) * 5 : Math.round(x);
  return Math.round(x * 100) / 100;
}

export function scaleAmount(a, factor, ingredient) {
  if (a.value == null || factor === 1) return a;
  const mode = ingredient?.scale;
  if (mode === "note") return a;
  const out = { ...a, value: roundFor(a.value * factor, a.unit, mode) };
  if (a.max != null) out.max = roundFor(a.max * factor, a.unit, mode);
  return out;
}

const LEAD = /^(~?)(\d*[½¼¾]|\d+(?:[,.]\d+)?)(\s?[–-]\s?(\d*[½¼¾]|\d+(?:[,.]\d+)?))?/;

function nthIndex(hay, needle, n) {
  let i = -1;
  for (let k = 0; k < n; k++) {
    i = hay.indexOf(needle, i + 1);
    if (i < 0) return -1;
  }
  return i;
}

// Ersetzt in step.text die Mengen-Spans (L11) durch skalierte Werte; nur spanForm=exact.
export function scaleStepText(text, step, factor, ingredientsById) {
  if (factor === 1) return text;
  const edits = [];
  for (const si of step.ingredients || []) {
    if ((si.spanForm || "exact") !== "exact" || si.amount.value == null) continue;
    const span = si.amount.text;
    const m = LEAD.exec(span);
    if (!m) continue;
    const idx = nthIndex(text, span, si.occurrence || 1);
    if (idx < 0) continue;
    const scaled = scaleAmount(si.amount, factor, ingredientsById[si.ref]);
    if (scaled === si.amount) continue;
    edits.push({ from: idx, to: idx + m[0].length, with: m[1] + fmtRange(scaled.value, scaled.max) });
  }
  edits.sort((a, b) => b.from - a.from);
  let out = text;
  for (const e of edits) out = out.slice(0, e.from) + e.with + out.slice(e.to);
  return out;
}

// Markiert Zitat-Annotationen im Rohtext (vor dem Markdown-Rendern).
export function highlight(text, step) {
  const spans = [];
  for (const c of step.cues || []) spans.push([c, "cue"]);
  for (const l of step.limits || []) spans.push([l, "limit"]);
  if (step.why) spans.push([step.why, "why"]);
  if (step.rescue) spans.push([step.rescue, "rescue"]);
  spans.sort((a, b) => b[0].length - a[0].length);
  let out = text;
  for (const [q, cls] of spans) {
    const i = out.indexOf(q);
    if (i < 0) continue;
    out = out.slice(0, i) + `<mark class="${cls}">` + q + "</mark>" + out.slice(i + q.length);
  }
  return out;
}

// Einzelne Tilde ist in GFM Durchstreichung; die Quelle schreibt teils bare ~ (ältere Dateien).
export function escapeTilde(md) {
  return md.replace(/(^|[^\\])~(?!~)/g, "$1\\~");
}

export function isoSeconds(d) {
  if (!d) return null;
  const m = /^([+-]?)P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(d);
  if (!m) return null;
  const s = (+m[2] || 0) * 86400 + (+m[3] || 0) * 3600 + (+m[4] || 0) * 60 + (+m[5] || 0);
  return m[1] === "-" ? -s : s;
}

export function timerChoices(range) {
  // Timer-Angebot: typical, sonst min und max getrennt (Koch entscheidet)
  const out = [];
  if (range.typical) out.push(isoSeconds(range.typical));
  else {
    if (range.min) out.push(isoSeconds(range.min));
    if (range.max && range.max !== range.min) out.push(isoSeconds(range.max));
  }
  return out;
}

export function fmtClock(secs) {
  const s = Math.max(0, Math.round(secs));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return (h ? `${h}:` : "") + String(m).padStart(h ? 2 : 1, "0") + ":" + String(r).padStart(2, "0");
}

// Export der allgemeinen Notiz als Markdown-Block zum Einfügen unter ## Learnings.
export function noteMarkdown(recipeId, text, date) {
  return [`### Notizen aus dem Kochmodus (${date})`, "", `<!-- ${recipeId} -->`, "", text.trim(), ""].join("\n");
}

// Volltext mit der Kurzansicht als fettem Präfix (keine Wiederholung, nichts fehlt).
export function textWithAction(text, step) {
  if (step.actionDerived) return text;
  const a = step.action.trim();
  return text.startsWith(a) ? `<strong class="action-span">${a}</strong>` + text.slice(a.length) : text;
}

// Rest des Schrittes nach der Kurzansicht (damit Details den ersten Satz nicht wiederholen).
export function remainderAfterAction(text, step) {
  if (step.actionDerived) return text;
  const a = step.action.trim();
  return text.startsWith(a) ? text.slice(a.length).trim() : text;
}

// Wie viele Handgriffe stehen nach der Kurzansicht noch im Schritt? Sätze des Rests, ohne den kursiven Schluss
// (Warum/Rettung) — damit die Übersicht nicht suggeriert, der erste Satz sei schon alles.
export function moreCount(step) {
  const rest = remainderAfterAction(step.text || "", step).replace(/\*(?!\*)[^*]+\*\s*$/, "").trim();
  if (!rest) return 0;
  return rest.split(/(?<=[.!?:])\s+(?=[A-ZÄÖÜ0-9*½¼¾])|\n+/).filter((x) => x.replace(/[*_\s—-]/g, "").length > 12).length;
}

// Gespeicherten Zustand auf die aktuelle Form bringen (alte Fassungen, kaputte Werte).
export function normalizeState(raw) {
  const s = raw && typeof raw === "object" ? raw : {};
  const obj = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : {});
  const factor = Number(s.factor);  // Timer liegen nicht mehr hier, sondern rezeptübergreifend in „km:timers“
  return { done: obj(s.done), note: typeof s.note === "string" ? s.note : "", shop: obj(s.shop), factor: factor > 0 ? factor : 1,
           order: s.order === "gang" ? "gang" : "ablauf", variant: obj(s.variant) };
}

// ---- Varianten (AP6): Auswahl pro Dimension, Filter, Inline-Alternativen ----
// Auswahl: { mehl: "dinkel", weg: "kombi" }; fehlende Dimensionen fallen auf den Default.
// ---- Timer, rezeptübergreifend (localStorage „km:timers“) ----------------------
// Ein Timer: { id, label, end, paused, left, recipe: Rezept-ID|null, recipeTitle, step, stepText }.
export function normalizeTimers(raw) {
  return (Array.isArray(raw) ? raw : []).filter((t) => t && typeof t === "object" && typeof t.end === "number" && t.id != null);
}
// Kurzname fürs Dock: „Bò lúc lắc — vietnamesisches …“ → „Bò lúc lắc“
export const shortTitle = (title) => String(title || "").split(/\s[—–]\s/)[0].replace(/\s*\([^)]*\)\s*$/, "").replace(/^🚧\s*/, "").trim();
// Zweite Zeile im Dock: Herkunftsrezept nur, wenn der Timer aus einem anderen Rezept stammt
export function timerOrigin(t, currentId) {
  const foreign = t.recipe && t.recipe !== currentId;
  return { foreign: !!foreign, text: [foreign ? t.recipeTitle || t.recipe : "", t.stepText || ""].filter(Boolean).join(" · ") };
}
// „Neu kochen“: Haken, Timer und Einkaufs-Haken weg; Notiz, Faktor, Reihenfolge und Varianten-Wahl bleiben.
export function resetState(state) {
  return { ...state, done: {}, shop: {} };
}

export function selection(recipe, chosen = {}) {
  return Object.fromEntries((recipe.variants || []).map((d) => [d.id, d.choices.some((c) => c.id === chosen[d.id]) ? chosen[d.id] : d.default]));
}
export const selectionKey = (sel) => Object.keys(sel).sort().map((k) => `${k}=${sel[k]}`).join(",");
// only: ["weg=einfrieren", "weg=kombi"] — innerhalb einer Dimension oder, über Dimensionen und.
export function isActive(only, sel) {
  if (!only?.length) return true;
  const byDim = {};
  for (const ref of only) { const [d, c] = ref.split("="); (byDim[d] ||= new Set()).add(c); }
  return Object.entries(byDim).every(([d, cs]) => cs.has(sel[d]));
}
const NUMX = "(?:\\d*[½¼¾]|\\d+(?:[,.]\\d+)?)";
const UNITX = "(?:kg|g|ml|l|L|EL|TL|Prisen|Prise|Stück|Bund|Zehen|Zehe|Scheiben|Scheibe|Tropfen|Eigelb|Eiweiß)";
const QTYU = new RegExp(`^~?${NUMX}(?:\\s?[–-]\\s?${NUMX})?(?:\\s?${UNITX}(?![\\wäöüß]))?`); // „12 g“, „4–6 g“, „2“
// Text und wirksame Dosierungen eines Schritts bei dieser Wahl. Klammer hinter einer Menge: Menge tauschen
// („80 g Wasser (Dinkel: 40 g)“ → „40 g Wasser“), sonst nur die passende Alternative zeigen, die anderen ausblenden.
export function variantText(text, step, sel) {
  const keys = new Set(Object.entries(sel).map(([k, v]) => `${k}=${v}`));
  let out = text;
  for (const alt of step.alts || []) {
    const idx = out.indexOf(alt.text);
    if (idx < 0) continue;
    const opt = alt.options.find((o) => keys.has(o.when));
    let from = idx, to = idx + alt.text.length, repl;
    const baseAt = alt.base ? idx - 1 - alt.base.length : -1;
    if (alt.base && baseAt >= 0 && out.slice(baseAt, idx - 1) === alt.base) {
      from = baseAt;
      if (!opt) repl = alt.base;
      else {
        const baseQ = QTYU.exec(alt.base)?.[0], qtyOnly = QTYU.exec(opt.text)?.[0] === opt.text.trim();
        repl = `<mark class="variant">${qtyOnly && baseQ ? opt.text + alt.base.slice(baseQ.length) : opt.text}</mark>`;
      }
    } else {
      if (out[from - 1] === " ") from -= 1;
      const seg = opt && alt.text.slice(1, -1).split(/, (?=[^,:]+: )/).find((x) => x.endsWith(": " + opt.text));
      repl = opt ? ` <mark class="variant">(${seg || opt.text})</mark>` : "";
    }
    out = out.slice(0, from) + repl + out.slice(to);
  }
  const ingredients = (step.ingredients || []).flatMap((si) => {
    const k = Object.keys(si.byVariant || {}).find((x) => keys.has(x));
    return k ? si.byVariant[k].map((d) => ({ ...d, occurrence: undefined })) : [si];
  });
  return { text: out, ingredients };
}
