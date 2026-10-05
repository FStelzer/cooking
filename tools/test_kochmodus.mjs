// Node-Tests der reinen Kochmodus-Funktionen gegen das thit-kho-Beispiel.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { escapeTilde, fmtAmount, fmtClock, highlight, isoSeconds, noteMarkdown, normalizeState, remainderAfterAction, textWithAction,
         scaleAmount, scaleStepText, timerChoices, moreCount, resetState, isActive, normalizeTimers, plainTitle, shortTitle, timerOrigin, selection, selectionKey, variantText } from "../kochmodus/lib.js";

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
  assert.match(out, /Die 3 Eier und 1–1½ \*\*ganze\*\* Chilis/);
});
t("derived-Span (Schweinebauch) bleibt unangetastet; Freitext-Mengen auch", () => {
  assert.equal(scaleStepText(steps.blanchieren.text, steps.blanchieren, 2, ing), steps.blanchieren.text);
  assert.equal(scaleStepText(steps.reduzieren.text, steps.reduzieren, 2, ing), steps.reduzieren.text);
});
t("Faktor 1 ist Identität", () => assert.equal(scaleStepText(steps.karamell.text, steps.karamell, 1, ing), steps.karamell.text));
t("½ Salatgurke ×2 → 1 Salatgurke", () => assert.match(scaleStepText(steps["pickle-und-reis"].text, steps["pickle-und-reis"], 2, ing), /1 Salatgurke in Scheiben/));
t("Einkauf: need skaliert mit Rundung", () => {
  const z = r.derived.quantities.find((q) => q.ingredient === "zucker").total;
  assert.equal(fmtAmount(scaleAmount(z, 1.5, ing.zucker)), "7½ EL");
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
t("Alter localStorage-Zustand: Timer-Felder fallen weg, Müll verworfen", () => {
  const old = { done: { karamell: true }, notes: { karamell: "x" }, note: 7, timers: { "schmoren#0.0": 1760000000000 }, factor: "2" };
  const s = normalizeState(old);
  assert.equal("timers" in s, false, "Timer leben in km:timers, nicht im Rezept-Zustand");
  assert.equal(s.factor, 2); assert.equal(s.done.karamell, true); assert.deepEqual(s.shop, {});
  assert.equal(s.note, "");
  assert.deepEqual(normalizeState({ timers: "quatsch", done: [], factor: -1 }), { done: {}, note: "", shop: {}, factor: 1, order: "ablauf", variant: {} });
});
t("Gemischter Bruch: 1½ EL ×2 → 3 EL, ×0,5 → ¾ EL; 1,5 wird „1½“", () => {
  const st = { ingredients: [{ ref: "fischsauce", amount: { text: "1½ EL Fischsauce", value: 1.5, unit: "EL" } }] };
  assert.equal(scaleStepText("1½ EL Fischsauce dazu", st, 2, {}), "3 EL Fischsauce dazu");
  assert.equal(scaleStepText("1½ EL Fischsauce dazu", st, 0.5, {}), "¾ EL Fischsauce dazu");
  assert.equal(fmtAmount({ value: 1.5, unit: "EL" }), "1½ EL");
});
t("Varianten: Auswahl mit Default, only = oder je Dimension, und über Dimensionen", () => {
  const rec = { variants: [{ id: "mehl", default: "weizen", choices: [{ id: "weizen" }, { id: "dinkel" }] }, { id: "weg", default: "einfrieren", choices: [{ id: "einfrieren" }, { id: "kombi" }] }] };
  const sel = selection(rec, { mehl: "dinkel", weg: "quatsch" });
  assert.deepEqual(sel, { mehl: "dinkel", weg: "einfrieren" });
  assert.equal(selectionKey(sel), "mehl=dinkel,weg=einfrieren");
  assert.ok(isActive(["weg=einfrieren", "weg=kombi"], sel));
  assert.ok(!isActive(["weg=kombi"], sel));
  assert.ok(!isActive(["mehl=dinkel", "weg=kombi"], sel));
  assert.ok(isActive(undefined, sel));
});
t("Varianten: Menge tauschen, Klammer ohne Menge filtern, Dosierungen mitziehen", () => {
  const st = { alts: [{ text: "(Weizen-Roggen: 90 g, Dinkel: 40 g)", base: "80 g Wasser", baseQty: "80 g", options: [{ when: "mehl=weizen-roggen", text: "90 g", qty: true }, { when: "mehl=dinkel", text: "40 g", qty: true }] },
                      { text: "(Dinkel: 25, 50, 75)", options: [{ when: "mehl=dinkel", text: "25, 50, 75" }] }],
               ingredients: [{ ref: "wasser", amount: { text: "80 g Wasser", value: 80, unit: "g" }, byVariant: { "mehl=dinkel": [{ ref: "wasser", amount: { text: "40 g", value: 40, unit: "g" } }] } }] };
  const txt = "80 g Wasser (Weizen-Roggen: 90 g, Dinkel: 40 g) dazu. Nach 30, 60 und 90 Min. (Dinkel: 25, 50, 75) falten.";
  assert.equal(variantText(txt, st, { mehl: "weizen" }).text, "80 g Wasser dazu. Nach 30, 60 und 90 Min. falten.");
  const d = variantText(txt, st, { mehl: "dinkel" });
  assert.equal(d.text, '<mark class="variant">40 g Wasser</mark> dazu. Nach 30, 60 und 90 Min. <mark class="variant">(Dinkel: 25, 50, 75)</mark> falten.');
  assert.equal(scaleStepText(d.text, { ingredients: d.ingredients }, 2, {}), '<mark class="variant">80 g Wasser</mark> dazu. Nach 30, 60 und 90 Min. <mark class="variant">(Dinkel: 25, 50, 75)</mark> falten.');
});
t("Mehr-Hinweis zählt Handgriffe nach der Kurzansicht, nicht den kursiven Schluss", () => {
  assert.equal(moreCount({ text: "Reis waschen und garen.", action: "Reis waschen und garen." }), 0);
  assert.equal(moreCount({ text: "Pfanne heiß machen. 1 EL Öl hinein, warten. Würfel einlegen, nicht bewegen. *Sonst dünstet es.*", action: "Pfanne heiß machen." }), 2);
});
t("Neu kochen: Haken, Timer, Einkauf weg; Notiz, Faktor, Wahl bleiben", () => {
  const s = resetState({ done: { a: true }, shop: { x: true }, note: "n", factor: 2, order: "gang", variant: { mehl: "dinkel" } });
  assert.deepEqual(s, { done: {}, shop: {}, note: "n", factor: 2, order: "gang", variant: { mehl: "dinkel" } });
});
t("Timer rezeptübergreifend: Herkunft nur bei fremdem Rezept, Kurztitel", () => {
  assert.equal(shortTitle("🚧 Bò lúc lắc — vietnamesisches „Shaking Beef“ (4 Portionen)"), "Bò lúc lắc");
  assert.equal(shortTitle("Degustationsmenü — Hochzeitstag (4 Personen)"), "Degustationsmenü");
  assert.equal(plainTitle("Cheesecake (no-bake, Ø 22 cm, \\~12 Stücke)"), "Cheesecake (no-bake, Ø 22 cm, ~12 Stücke)");
  assert.equal(shortTitle("Bouillabaisse mit Fenchel-Orange-Salat (2 Erwachsene + Kind)"), "Bouillabaisse mit Fenchel-Orange-Salat");
  assert.equal(shortTitle("Bouillabaisse mit Fenchel-Orange-Salat (Schwangerschafts-Version, 2 Erwachsene + Kind)"), "Bouillabaisse mit Fenchel-Orange-Salat (Schwangerschafts-Version)");
  const t = { id: "a", end: 1, recipe: "gerichte/bo-luc-lac", recipeTitle: "Bò lúc lắc", stepText: "8. Chargen braten" };
  assert.deepEqual(timerOrigin(t, "gerichte/bo-luc-lac"), { foreign: false, text: "8. Chargen braten" });
  assert.deepEqual(timerOrigin(t, "backen/vollkornbroetchen"), { foreign: true, text: "Bò lúc lắc · 8. Chargen braten" });
  assert.deepEqual(timerOrigin({ id: "q", end: 1, recipe: null, stepText: "" }, "x"), { foreign: false, text: "" }, "Schnell-Timer aus der Liste");
  assert.deepEqual(normalizeTimers([null, { id: 1 }, { id: 2, end: 5 }]), [{ id: 2, end: 5 }]);
});
console.log(`${n} Tests ok`);
