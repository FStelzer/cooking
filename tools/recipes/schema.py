"""Check A: JSON-Schema-Validierung."""
from __future__ import annotations

import functools
import textwrap

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .util import SCHEMA_PATH, load_json


@functools.cache
def validator() -> Draft202012Validator:
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def check_a(recipe: dict) -> list[str]:
    errs = []
    for e in sorted(validator().iter_errors(recipe), key=lambda e: list(e.absolute_path)):
        if e.context:  # verbleibende oneOf/anyOf: treffendsten Unterfehler zeigen
            e = best_match(e.context)
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(f"A {path}: {textwrap.shorten(e.message, 140, placeholder='…')}")
    return errs
