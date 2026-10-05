"""CLI: python3 -m tools.recipes.cli {check|derive|shopping|diff} …"""
from __future__ import annotations

import argparse
import json
import sys

from .coverage import check_b, check_c, check_d
from .diff import diff
from .parse import parse_recipe
from .schema import check_a
from .shopping import check_k, derive, render_shopping
from .timing import check_e, check_f, check_g, check_h, check_l
from .util import ROOT, load_json, read_source, source_path


def _structural(recipe: dict) -> list[str]:
    """A und D: Vorbedingung für alles, was den Zutaten-Graph auswertet (derive, K).
    Ein vorhandener derived-Block wird ignoriert — er wird ohnehin neu geschrieben."""
    body = {k: v for k, v in recipe.items() if k != "derived"}
    errs = check_a(body)
    return errs or check_d(body)[0]


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
            for e, r in (check_b(recipe, src), check_c(recipe, src), check_k(recipe, src),
                         check_e(recipe, src), check_f(recipe, src), check_g(recipe), check_h(recipe), check_l(recipe, src)):
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


def _parse_md(path: str):
    p = Path(path).resolve()
    rid = str(p.relative_to(ROOT)).removesuffix(".md")
    return parse_recipe(p.read_text(encoding="utf-8"), rid), p.with_suffix(".json")


def cmd_build(args) -> int:
    failed = False
    for path in args.paths:
        (recipe, lint), out = _parse_md(path)
        if errs := _structural(recipe):
            print(f"{path}: Parser-Ergebnis verletzt Schema/Referenzen:\n  " + "\n  ".join(errs))
            failed = True
            continue
        recipe["derived"] = derive(recipe)
        text = json.dumps(recipe, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            old = out.read_text(encoding="utf-8") if out.exists() else ""
            same = json.loads(old or "{}") | {"derived": None} == json.loads(text) | {"derived": None} if old else False
            print(f"{out}: {'aktuell' if same else 'VERALTET'}")
            failed |= not same
        else:
            out.write_text(text, encoding="utf-8")
            print(f"{path} → {out.relative_to(ROOT)} ({len(lint.msgs)} Hinweise, `cli lint` zeigt sie)")
    return int(failed)


def cmd_lint(args) -> int:
    for path in args.paths:
        (recipe, lint), _ = _parse_md(path)
        print(f"== {path}: {len(lint.msgs)} Hinweis(e)")
        for m in lint.msgs:
            print("  ", m)
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
    p = sub.add_parser("build", help="Markdown (REZEPTFORMAT.md) → JSON daneben, inkl. derived")
    p.add_argument("paths", nargs="+")
    p.add_argument("--check", action="store_true", help="nur prüfen, ob das JSON aktuell ist (CI)")
    p.set_defaults(run=cmd_build)
    p = sub.add_parser("lint", help="Parser-Hinweise zu einer Markdown-Datei")
    p.add_argument("paths", nargs="+")
    p.set_defaults(run=cmd_lint)
    p = sub.add_parser("diff", help="Feld-Diff zweier Konvertierungen derselben Quelle (Check I)")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(run=cmd_diff)
    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
