"""Zahlen- und Mengenformatierung (eine Stelle für alle Ausgaben)."""
from __future__ import annotations

FRACTIONS = {0.5: "½", 0.25: "¼", 0.75: "¾"}
FRACTION_VALUES = {v: k for k, v in FRACTIONS.items()}
COUNT_UNIT = "Stück"  # kanonische Einheit für Zählmengen; wird in der Anzeige weggelassen


def fmt_num(x: float) -> str:
    if x in FRACTIONS:
        return FRACTIONS[x]
    if float(x).is_integer():
        return str(int(x))
    return f"{x:g}".replace(".", ",")


def fmt_range(lo: float, hi: float | None) -> str:
    return fmt_num(lo) if hi in (None, lo) else f"{fmt_num(lo)}–{fmt_num(hi)}"


def fmt_amount(value: float | None, mx: float | None, unit: str | None, approx: bool = False) -> str:
    if value is None:
        return ""
    s = fmt_range(value, mx)
    if unit and unit != COUNT_UNIT:
        s += f" {unit}"
    return ("~" if approx else "") + s
