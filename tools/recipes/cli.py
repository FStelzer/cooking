"""CLI: python3 -m tools.recipes.cli {check|derive|shopping|diff} …"""
from __future__ import annotations

import argparse
import json
import sys

from .coverage import check_b, check_c, check_d
from .diff import diff
from .schema import check_a
from .shopping import check_k, derive, render_shopping
from .util import load_json, read_source, source_path


def _structural(recipe: dict) -> list[str]:
    """A und D: Vorbedingung für alles, was den Zutaten-Graph auswertet (derive, K)."""
    errs = check_a(recipe)
    return errs or check_d(recipe)[0]


def cmd_check(args) -> int:
    failed = False
    for path in args.paths:
        recipe = load_json(path)
        print(f"== {path}")
        errs, reps = check_a(recipe), []
        if not errs:
            errs, reps = check_d(recipe)
        if not errs and not source_path(recipe).exists():
            errs.append(f"Quelle fehlt: {source_path(recipe)}")
        if not errs:
            src = read_source(recipe)
            for e, r in (check_b(recipe, src), check_c(recipe, src), check_k(recipe, src)):
                errs += e
                reps += r
        for e in errs:
            print("  FAIL", e)
        if args.verbose or not errs:
            for r in reps:
                print("  info", r)
        print(f"  -> {len(errs)} Fehler" if errs else "  -> ok")
        failed |= bool(errs)
    return int(failed)


def cmd_derive(args) -> int:
    failed = False
    for path in args.paths:
        recipe = load_json(path)
        if errs := _structural(recipe):
            print(f"{path}: nicht geschrieben, erst Check A/D beheben:\n  " + "\n  ".join(errs))
            failed = True
            continue
        recipe["derived"] = derive(recipe)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"derived → {path} ({len(recipe['derived']['quantities'])} Zutaten, hash {recipe['derived']['sourceHash']})")
    return int(failed)


def cmd_shopping(args) -> int:
    recipe = load_json(args.path)
    if errs := _structural(recipe):
        print("\n".join(errs), file=sys.stderr)
        return 1
    print(render_shopping(recipe), end="")
    return 0


def cmd_diff(args) -> int:
    print("\n".join(diff(load_json(args.a), load_json(args.b))))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.recipes.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="Checks A, D, B, C, K gegen die Quelle laufen lassen")
    p.add_argument("paths", nargs="+")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(run=cmd_check)
    p = sub.add_parser("derive", help="derived-Block (Einkaufsliste, Mengen) berechnen und ins JSON schreiben")
    p.add_argument("paths", nargs="+")
    p.set_defaults(run=cmd_derive)
    p = sub.add_parser("shopping", help="Einkaufsliste als Markdown ausgeben")
    p.add_argument("path")
    p.set_defaults(run=cmd_shopping)
    p = sub.add_parser("diff", help="Feld-Diff zweier Konvertierungen derselben Quelle (Check I)")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(run=cmd_diff)
    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
