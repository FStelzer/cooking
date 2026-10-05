// Node-Tests der reinen Kochmodus-Funktionen gegen das thit-kho-Beispiel.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { escapeTilde, fmtAmount, fmtClock, highlight, isoSeconds, noteMarkdown, normalizeState, remainderAfterAction, textWithAction,
         scaleAmount, scaleStepText, timerChoices } from "../kochmodus/lib.js";

const r = JSON.parse(readFileSync(new URL("../schema/beispiele/thit-kho-trung.json", import.meta.url), "utf8"));
const ing = Object.fromEntries(r.ingredients.map((i) => [i.id, i]));
const steps = Object.fromEntries(r.sections.find((s) => s.type === "tasks").tasks[0].steps.map((s) => [s.id, s]));
let n = 0;
const t = (name, fn) => { fn(); n++; console.log("✓", name); };

t("Skalierung ×2 ersetzt beide Spans in Schritt 4, nicht die Rettung", () => {
  const out = scaleStepText(steps.karamell.text, steps.karamell, 2, ing);
  assert.match(out, /^6 EL Zucker mit 2 EL Wasser/);
  assert.match(out, /kostet 3 EL Zucker und 5 Minuten/);
});
t("Spanne 500–600 ml ×0,5 → 250–300 ml; Stück runden auf halbe", () => {
  const out = scaleStepText(steps.schmoren.text, steps.schmoren, 0.5, ing);
  assert.match(out, /Mit 250–300 ml Kokoswasser/);
  assert.match(out, /Die 3 Eier und 1–1,5 \*\*ganze\*\* Chilis/);
});
t("derived-Span (Schweinebauch) bleibt unangetastet; Freitext-Mengen auch", () => {
  assert.equal(scaleStepText(steps.blanchieren.text, steps.blanchieren, 2, ing), steps.blanchieren.text);
  assert.equal(scaleStepText(steps.reduzieren.text, steps.reduzieren, 2, ing), steps.reduzieren.text);
});
t("Faktor 1 ist Identität", () => assert.equal(scaleStepText(steps.karamell.text, steps.karamell, 1, ing), steps.karamell.text));
t("½ Salatgurke ×2 → 1 Salatgurke", () => assert.match(scaleStepText(steps["pickle-und-reis"].text, steps["pickle-und-reis"], 2, ing), /1 Salatgurke in Scheiben/));
t("Einkauf: need skaliert mit Rundung", () => {
  const z = r.derived.quantities.find((q) => q.ingredient === "zucker").total;
  assert.equal(fmtAmount(scaleAmount(z, 1.5, ing.zucker)), "7,5 EL");
  const s = r.derived.quantities.find((q) => q.ingredient === "schweinebauch").total;
  assert.equal(fmtAmount(scaleAmount(s, 0.5, ing.schweinebauch)), "450–500 g");
});
t("Hervorhebung markiert Cue, Warum und Rettung", () => {
  const h = highlight(steps.karamell.text, steps.karamell);
  assert.match(h, /<mark class="cue">tief bernsteinfarben<\/mark>/);
  assert.match(h, /<mark class="why">Zu hell/);
  assert.match(h, /<mark class="rescue">Zu schwarz/);
  assert.match(h, /<mark class="limit">\*\*nicht rühren\*\*/);
});
t("Tilde-Escape nur für bare Tilden", () => assert.equal(escapeTilde("~30 Min., \\~2 h"), "\\~30 Min., \\~2 h"));
t("ISO-Dauern und Timer-Angebot", () => {
  assert.equal(isoSeconds("PT1H30M"), 5400); assert.equal(isoSeconds("-PT20M"), -1200); assert.equal(isoSeconds("P2D"), 172800);
  assert.deepEqual(timerChoices(steps.schmoren.timers[0].duration), [5400, 7200]);
  assert.deepEqual(timerChoices(steps.marinieren.timers[0].duration), [900]);
  assert.equal(fmtClock(5400), "1:30:00"); assert.equal(fmtClock(90), "1:30");
});
t("Allgemeine Notiz als Markdown-Block", () => {
  const out = noteMarkdown("gerichte/thit-kho-trung", "Karamell dunkler\nging gut", "10/2026");
  assert.match(out, /^### Notizen aus dem Kochmodus \(10\/2026\)\n\n<!-- gerichte\/thit-kho-trung -->\n\nKaramell dunkler\nging gut\n$/);
});
t("Volltext mit fettem action-Präfix, nichts doppelt", () => {
  const h = textWithAction(steps.karamell.text, steps.karamell);
  assert.ok(h.startsWith('<strong class="action-span">3 EL Zucker'), h.slice(0, 60));
  assert.equal((h.match(/3 EL Zucker mit 1 EL Wasser/g) || []).length, 1);
  assert.equal(textWithAction(steps.schmoren.text, steps.schmoren), steps.schmoren.text); // abgeleitet → nur Text
});
t("Details wiederholen die Kurzansicht nicht", () => {
  const rest = remainderAfterAction(steps.karamell.text, steps.karamell);
  assert.ok(rest.startsWith("Warten, bis das Karamell"), rest);
  assert.equal(remainderAfterAction(steps["pickle-und-reis"].text, steps["pickle-und-reis"]), "");
  assert.equal(remainderAfterAction(steps.schmoren.text, steps.schmoren), steps.schmoren.text); // abgeleitet → alles
});
t("Alter localStorage-Zustand (timers als Objekt) wird migriert, Müll verworfen", () => {
  const old = { done: { karamell: true }, notes: { karamell: "x" }, note: 7, timers: { "schmoren#0.0": 1760000000000, kaputt: "nein" }, factor: "2" };
  const s = normalizeState(old);
  assert.deepEqual(s.timers.map((t) => [t.step, t.end]), [["schmoren", 1760000000000]]);
  assert.equal(s.factor, 2); assert.equal(s.done.karamell, true); assert.deepEqual(s.shop, {});
  assert.deepEqual(normalizeState(null).timers, []);
  assert.equal(s.note, "");
  assert.deepEqual(normalizeState({ timers: "quatsch", done: [], factor: -1 }), { done: {}, note: "", shop: {}, timers: [], factor: 1, order: "ablauf" });
});
console.log(`${n} Tests ok`);
