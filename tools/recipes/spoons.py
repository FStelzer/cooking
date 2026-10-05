"""Löffel ↔ Milliliter/Gramm: Anzeige-Regel für die Kochansicht.

Rohwerte bleiben, wie sie in der Quelle stehen (L2). Für die Anzeige gilt:
- Löffelangaben (TL/EL) werden als Löffel gezeigt; steht am Ingredient ein
  `unitHint` (z. B. EL → g, Faktor 12), kommt der metrische Wert in Klammern.
- Metrische Werte, die einem Löffel-Vielfachen entsprechen (5/15 ml metrisch
  oder 4,93/14,79 ml US-Umrechnung, ±3 %), werden als Löffel gezeigt, der
  Rohwert in Klammern: 14,7 ml → „1 EL (14,7 ml)“.
- Explizites `amount.display` hat Vorrang vor der Heuristik.
"""
from __future__ import annotations

SPOON_ML = {"EL": (15.0, 14.79), "TL": (5.0, 4.93)}
TOLERANCE = 0.01  # 1 %: trennt 14,7 (US) von 15 (metrisch), auch bei Vielfachen
HALF_STEPS = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10)


def _fmt(x: float) -> str:
    if x == 0.5:
        return "½"
    if float(x).is_integer():
        return str(int(x))
    return f"{x:g}".replace(".", ",")


def spoon_equivalent(value: float, unit: str | None, metric: bool = False):
    """(k, 'EL'|'TL') wenn value ml ein Löffel-Vielfaches ist, sonst None.

    metric=False: nur US-Umrechnungswerte (14,79/4,93 ml) — eindeutig aus Löffeln
    entstanden, sicher für Einkaufsliste. metric=True: zusätzlich 15/5 ml, für die
    Kochansicht, wo „3 EL (45 ml)“ beim Abmessen hilft."""
    if unit != "ml" or value is None:
        return None
    for spoon, (metric_base, us_base) in SPOON_ML.items():
        for base in ((metric_base, us_base) if metric else (us_base,)):
            for k in HALF_STEPS:
                if abs(value - k * base) <= TOLERANCE * k * base:
                    return k, spoon
    return None


def display_text(amount: dict, ingredient: dict | None = None, metric: bool = False) -> str:
    """Anzeige-String; nutzt amount.display, sonst Heuristik (siehe spoon_equivalent)."""
    v, mx, u = amount.get("value"), amount.get("max"), amount.get("unit")
    if v is None:
        return amount["text"]
    raw = _fmt(v) if mx in (None, v) else f"{_fmt(v)}–{_fmt(mx)}"
    raw_u = f"{raw} {u}" if u and u != "Stück" else raw
    d = amount.get("display")
    if d:
        dv = _fmt(d["value"]) if d.get("max") in (None, d["value"]) else f"{_fmt(d['value'])}–{_fmt(d['max'])}"
        return f"{dv} {d['unit']} ({raw_u})"
    eq = spoon_equivalent(v, u, metric)
    if eq and mx in (None, v):
        k, spoon = eq
        return f"{_fmt(k)} {spoon} ({raw_u})"
    hint = (ingredient or {}).get("unitHint")
    if u in SPOON_ML and hint and hint.get("from") == u:
        lo = v * hint["factor"]
        hi = (mx or v) * hint["factor"]
        metric = _fmt(lo) if hi == lo else f"{_fmt(lo)}–{_fmt(hi)}"
        return f"{raw_u} (≈ {metric} {hint['to']})"
    return raw_u
