"""CLI: python3 -m tools.recipes.cli check schema/beispiele/*.json [-v]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import json

from .coverage import check_b, check_c, check_d
from .diff import diff
from .shopping import check_k, derive, render_shopping
from .schema import check_a
from .util import load_json, read_source, source_path


def cmd_check(paths: list[str], verbose: bool) -> int:
    failed = 0
    for p in paths:
        path = Path(p)
        recipe = load_json(path)
        print(f"== {path}")
        errs = check_a(recipe)
        reps: list[str] = []
        if not errs:
            if not source_path(recipe).exists():
                errs.append(f"Quelle fehlt: {source_path(recipe)}")
            else:
                src = read_source(recipe)
                if "derived" not in recipe:
                    recipe = dict(recipe, derived=derive(recipe))
                    reps.append("K derived-Block fehlt — für die Prüfung im Speicher berechnet (`cli derive` schreibt ihn)")
                for fn in (check_b, check_c, lambda r, s: check_d(r), check_k):
                    e, r = fn(recipe, src)
                    errs += e
                    reps += r
        for e in errs:
            print("  FAIL", e)
        if verbose or not errs:
            for r in reps:
                print("  info", r)
        if errs:
            failed += 1
            print(f"  -> {len(errs)} Fehler")
        else:
            print("  -> ok")
    return 1 if failed else 0


def cmd_derive(paths: list[str]) -> int:
    for p in paths:
        path = Path(p)
        recipe = load_json(path)
        recipe["derived"] = derive(recipe)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"derived → {path} ({len(recipe['derived']['quantities'])} Zutaten, hash {recipe['derived']['sourceHash']})")
    return 0


def cmd_shopping(path: str) -> int:
    print(render_shopping(load_json(Path(path))), end="")
    return 0


def cmd_diff(a: str, b: str) -> int:
    for line in diff(load_json(Path(a)), load_json(Path(b))):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.recipes.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Checks A–D und K gegen die Quelle laufen lassen")
    c.add_argument("paths", nargs="+")
    c.add_argument("-v", "--verbose", action="store_true")
    d = sub.add_parser("derive", help="derived-Block (Einkaufsliste, Mengen) berechnen und ins JSON schreiben")
    d.add_argument("paths", nargs="+")
    s = sub.add_parser("shopping", help="Einkaufsliste als Markdown ausgeben")
    s.add_argument("path")
    f = sub.add_parser("diff", help="Feld-Diff zweier Konvertierungen derselben Quelle (Check I)")
    f.add_argument("a")
    f.add_argument("b")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.paths, args.verbose)
    if args.cmd == "derive":
        return cmd_derive(args.paths)
    if args.cmd == "shopping":
        return cmd_shopping(args.path)
    if args.cmd == "diff":
        return cmd_diff(args.a, args.b)
    return 2


if __name__ == "__main__":
    sys.exit(main())
