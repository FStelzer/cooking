"""Site-Generatoren: `_sidebar.md` und der Learnings-Block in CLAUDE.md.

    python3 -m tools.recipes.site sidebar     # schreibt _sidebar.md
    python3 -m tools.recipes.site learnings   # ersetzt den Block zwischen <!-- learnings:start/end -->
    python3 -m tools.recipes.site index       # schreibt kochmodus/rezepte.json (Rezeptliste der Kochmodus-App)
    python3 -m tools.recipes.site --check …   # schreibt nichts, Exit 1 wenn etwas veraltet ist

Ersetzt die früheren awk-Blöcke im Taskfile; die Ausgabe ist zeichengleich (per Diff
belegt). Regeln: Titel = erste `# `-Zeile (sonst Dateiname), `🚧 ` am Titel = „in
arbeit", `## Learnings`-Sektion = gekocht (✅). Learnings sortieren nach dem ersten
MM/JJJJ der Kurzfassung (undatiert zuerst), dann nach Titel ohne Akzente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"schema", "tools", "kochmodus", "node_modules"}  # keine Rezepte (CLAUDE.md)


def title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].lstrip(" ")
    return path.stem


def is_wip(title: str) -> bool:
    return title.startswith("🚧")


def is_cooked(path: Path) -> bool:
    return any(l.startswith("## Learnings") for l in path.read_text(encoding="utf-8").splitlines())


def recipe_dirs() -> list[Path]:
    return sorted(d for d in ROOT.iterdir() if d.is_dir() and not d.name.startswith(".") and d.name not in SKIP_DIRS)


def md_files(d: Path) -> list[Path]:
    return sorted(d.glob("*.md"))


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def sidebar() -> str:
    out = ["- [Ideen-Backlog](/ideen.md)"]
    wip = [f for d in recipe_dirs() for f in md_files(d) if is_wip(title_of(f))]
    if wip:
        out.append("- **🚧 in arbeit**")
        for f in wip:
            out.append(f"  - [{title_of(f).removeprefix('🚧').removeprefix(' ')}](/{rel(f)})")
    for d in recipe_dirs():
        files = [f for f in md_files(d) if not is_wip(title_of(f))]
        if not files:
            continue
        out.append(f"- **{d.name}**")
        for f in files:
            out.append(f"  - [{'✅ ' if is_cooked(f) else ''}{title_of(f)}](/{rel(f)})")
    return "\n".join(out) + "\n"


def _sort_text(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


def learnings_entries() -> list[str]:
    rows = []
    for d in recipe_dirs():
        for f in md_files(d):
            text = f.read_text(encoding="utf-8")
            title = title_of(f).removeprefix("🚧").lstrip(" ")
            m = re.search(r"^## Learnings[^\n]*\n(.*?)(?=^##|\Z)", text, re.S | re.M)  # endet an jeder ##/###-Zeile (Kurzfassung)
            if not m:
                continue
            body = m.group(1).strip("\n")
            if not body:
                continue
            dm = re.search(r"(\d{2})/(\d{4})", body)
            key = f"{dm.group(2)}-{dm.group(1)}" if dm else "0000-00"
            entry = f"- ✅ **{title}** (siehe `{rel(f)}`)\n" + "\n".join(("  " + l) if l else "" for l in body.split("\n"))
            rows.append((key, _sort_text(entry), entry))
    return [e for _, _, e in sorted(rows)]


def learnings_block(claude_md: str) -> str:
    gen = "".join(e + "\n\n" for e in learnings_entries())
    start, end = "<!-- learnings:start -->", "<!-- learnings:end -->"
    i, j = claude_md.index(start), claude_md.index(end)
    return claude_md[: i + len(start)] + "\n\n" + gen + claude_md[j:]


def recipe_index() -> str:
    """Alle Rezepte mit gebautem JSON, Ordnung wie die Sidebar: Rezeptliste der Kochmodus-App (offline-fähig)."""
    items = []
    for d in recipe_dirs():
        for f in md_files(d):
            if not f.with_suffix(".json").exists():
                continue
            title = title_of(f)
            items.append({"path": "../" + rel(f.with_suffix(".json")), "title": title.removeprefix("🚧").lstrip(" "),
                          "group": d.name, "wip": is_wip(title), "cooked": is_cooked(f)})
    return json.dumps(items, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("what", choices=["sidebar", "learnings", "index"])
    p.add_argument("--check", action="store_true", help="nur prüfen, nichts schreiben")
    a = p.parse_args(argv)
    target = ROOT / {"sidebar": "_sidebar.md", "learnings": "CLAUDE.md", "index": "kochmodus/rezepte.json"}[a.what]
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    new = {"sidebar": sidebar, "index": recipe_index, "learnings": lambda: learnings_block(old)}[a.what]()
    if a.check:
        print(f"{target.name}: {'aktuell' if new == old else 'VERALTET (task ' + a.what + ')'}")
        return int(new != old)
    target.write_text(new, encoding="utf-8")
    print(f"{target.name} geschrieben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
