"""CLI: python3 -m tools.recipes.cli check schema/beispiele/*.json [-v]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .coverage import check_b, check_c, check_d
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
                for fn in (lambda r, s: check_b(r, s), lambda r, s: check_c(r, s), lambda r, s: check_d(r)):
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.recipes.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Checks A–D gegen die Quelle laufen lassen")
    c.add_argument("paths", nargs="+")
    c.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.paths, args.verbose)
    return 2


if __name__ == "__main__":
    sys.exit(main())
