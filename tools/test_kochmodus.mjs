// Node-Tests der reinen Kochmodus-Funktionen gegen das thit-kho-Beispiel.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { escapeTilde, fmtAmount, fmtClock, highlight, isoSeconds, notesMarkdown, scaleAmount,
         scaleStepText, timerChoices } from "../kochmodus/lib.js";

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
t("Notizen-Export im learnings.notes-Format", () => {
  const out = notesMarkdown("gerichte/thit-kho-trung", [{ slug: "karamell", label: "4", text: "dunkler\nging" }], "10/2026");
  assert.match(out, /- \*\*Schritt 4 \(step:karamell\):\*\* dunkler ging/);
});
console.log(`${n} Tests ok`);
