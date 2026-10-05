"""Check A: JSON-Schema-Validierung."""
from __future__ import annotations

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .util import SCHEMA_PATH, load_json

_validator: Draft202012Validator | None = None


def validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        _validator = Draft202012Validator(schema)
    return _validator


def _fmt(e) -> str:
    path = "/".join(str(p) for p in e.absolute_path) or "<root>"
    msg = e.message if len(e.message) < 140 else e.message[:137] + "…"
    return f"A {path}: {msg}"


def check_a(recipe: dict) -> list[str]:
    errs = []
    for e in sorted(validator().iter_errors(recipe), key=lambda e: list(e.absolute_path)):
        # Bei oneOf über "type" diskriminieren: nur Unterfehler des passenden Zweigs zeigen.
        if e.context:
            branches = e.schema.get("oneOf") or e.schema.get("anyOf") or []
            inst_type = e.instance.get("type") if isinstance(e.instance, dict) else None
            matching = [c for c in e.context
                        if inst_type is not None
                        and branches[c.relative_schema_path[0]].get("properties", {}).get("type", {}).get("const") == inst_type]
            if matching:
                for c in sorted(matching, key=lambda c: list(c.absolute_path)):
                    if c.context:
                        c = best_match(c.context)
                    errs.append(_fmt(c))
                continue
            e = best_match(e.context)
        errs.append(_fmt(e))
    return errs
