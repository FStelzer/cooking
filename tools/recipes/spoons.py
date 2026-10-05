"""Löffel ↔ Milliliter/Gramm: Anzeige-Regel für Einkaufsliste und Kochansicht.

Rohwerte bleiben, wie sie in der Quelle stehen (L2). Für die Anzeige gilt:
- Löffelangaben (TL/EL) werden als Löffel gezeigt; steht am Ingredient ein
  `unitHint` (z. B. EL → g, Faktor 12), kommt der metrische Wert in Klammern.
- Metrische Werte aus US-Umrechnungen (14,79/4,93 ml, Vielfache in halben
  Schritten, ±1 %) werden als Löffel gezeigt, der Rohwert in Klammern:
  14,7 ml → „1 EL (14,7 ml)“. metric=True erlaubt zusätzlich 15/5 ml (Kochansicht).
- Explizites `amount.display` hat Vorrang vor der Heuristik.
"""
from __future__ import annotations

from .fmt import fmt_amount, fmt_num, fmt_range

SPOON_ML = {"EL": (15.0, 14.79), "TL": (5.0, 4.93)}  # (metrisch, US)
TOLERANCE = 0.01  # 1 %: trennt 14,7 (US) von 15 (metrisch), auch bei Vielfachen
HALF_STEPS = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10)


def spoon_equivalent(value: float, unit: str | None, metric: bool = False) -> tuple[float, str] | None:
    """(k, 'EL'|'TL'), wenn value ml ein Löffel-Vielfaches ist, sonst None."""
    if unit != "ml" or value is None:
        return None
    for spoon, (metric_base, us_base) in SPOON_ML.items():
        for base in ((metric_base, us_base) if metric else (us_base,)):
            for k in HALF_STEPS:
                if abs(value - k * base) <= TOLERANCE * k * base:
                    return k, spoon
    return None


def display_text(amount: dict, ingredient: dict | None = None, metric: bool = False) -> str:
    """Reiner Text (kein Markdown); nutzt amount.display, sonst Heuristik."""
    v, mx, u = amount.get("value"), amount.get("max"), amount.get("unit")
    if v is None:
        return amount["text"]
    raw = fmt_amount(v, mx, u, bool(amount.get("approx")))
    if d := amount.get("display"):
        return f"{fmt_range(d['value'], d.get('max'))} {d['unit']} ({raw})"
    if mx in (None, v) and (eq := spoon_equivalent(v, u, metric)):
        return f"{fmt_num(eq[0])} {eq[1]} ({raw})"
    hint = (ingredient or {}).get("unitHint")
    if u in SPOON_ML and hint and hint.get("from") == u:
        f = hint["factor"]
        return f"{raw} (≈ {fmt_range(v * f, (mx or v) * f)} {hint['to']})"
    return raw
