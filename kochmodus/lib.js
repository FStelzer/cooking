// Reine Funktionen des Kochmodus: Formatierung, Skalierung, Hervorhebung, Zeit.
// Keine Aggregation (L10): Einkaufsliste und Mengen kommen aus derived.*.

export const FRACTIONS = { 0.5: "½", 0.25: "¼", 0.75: "¾" };
const FRACTION_VALUES = { "½": 0.5, "¼": 0.25, "¾": 0.75 };

export function fmtNum(x) {
  if (FRACTIONS[x]) return FRACTIONS[x];
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

const LEAD = /^(~?)(\d+(?:[,.]\d+)?|½|¼|¾)(\s?[–-]\s?(\d+(?:[,.]\d+)?))?/;

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

// Export im learnings.notes[]-Format (L13) als Markdown-Block zum Einfügen.
export function notesMarkdown(recipeId, notes, date) {
  const lines = [`### Notizen aus dem Kochmodus (${date})`, "", `<!-- ${recipeId}, Format: learnings.notes[] -->`];
  for (const n of notes) lines.push(`- **Schritt ${n.label} (step:${n.slug}):** ${n.text.trim().replace(/\n+/g, " ")}`);
  return lines.join("\n") + "\n";
}

// Rest des Schrittes nach der Kurzansicht (damit Details den ersten Satz nicht wiederholen).
export function remainderAfterAction(text, step) {
  if (step.actionDerived) return text;
  const a = step.action.trim();
  return text.startsWith(a) ? text.slice(a.length).trim() : text;
}
