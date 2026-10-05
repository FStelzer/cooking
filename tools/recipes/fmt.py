"""Zahlen- und Mengenformatierung (eine Stelle für alle Ausgaben)."""
from __future__ import annotations

FRACTIONS = {0.5: "½", 0.25: "¼", 0.75: "¾"}
FRACTION_VALUES = {v: k for k, v in FRACTIONS.items()} | {"⅓": .33}
# Zahlen-Grammatik (einzige Stelle): „½“, „1½“, „2,5“; Spanne „4–5“; Zirka-Präfix „ca. “ oder „\~“
NUMW = r"(?:\d*[½¼¾⅓]|\d+(?:[,.]\d+)?)"
RANGE = rf"{NUMW}(?:\s?[–-]\s?{NUMW})?"
APPROX = r"(?:ca\.\s?|\\?~)?"
SIZE_WORD = r"(?:\s(?:kleine|große|gute|gehäufte|gestrichene)[nrs]?)?"  # „2 gehäufte EL“
COUNT_UNIT = "Stück"  # kanonische Einheit für Zählmengen; wird in der Anzeige weggelassen


def parse_num(s: str) -> float:
    """„1½“ → 1.5, „½“ → 0.5, „2,5“ → 2.5 — einzige Stelle, die Zahlen aus dem Text liest."""
    if s and s[-1] in FRACTION_VALUES:
        return (int(s[:-1]) if s[:-1] else 0) + FRACTION_VALUES[s[-1]]
    return float(s.replace(",", "."))


def fmt_hm(secs: int, signed: bool = False) -> str:
    """Sekunden → „2:05“ (signed: „+0:15“ / „−1:30“)."""
    sign = ("+" if secs >= 0 else "−") if signed else ""
    secs = abs(secs) if signed else secs
    return f"{sign}{secs // 3600}:{secs % 3600 // 60:02d}"


def fmt_num(x: float) -> str:
    if x in FRACTIONS:
        return FRACTIONS[x]
    if x > 1 and x % 1 in FRACTIONS:  # 1,5 → „1½“
        return f"{int(x)}{FRACTIONS[x % 1]}"
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
