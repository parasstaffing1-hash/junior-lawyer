"""Generate TypeScript interfaces for the web client from the API's OpenAPI schema.

The frontend client is written by hand — endpoint names and argument shapes are
chosen for the UI, not derived mechanically — but the *response* types are the
API's own contract, so they are generated rather than retyped by hand. That
keeps them from drifting silently when a Pydantic model changes.

Usage (from apps/api, with the API importable):

    python scripts/generate_web_types.py ../web/lib/generated-types.ts

Regenerate whenever a schema the web app consumes changes; the file is checked
in so the web build does not depend on a running API.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# Runnable as `python scripts/generate_web_types.py` from apps/api without an
# editable install, matching the other scripts in this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

HEADER = """/**
 * GENERATED FILE — do not edit by hand.
 *
 * Produced by apps/api/scripts/generate_web_types.py from the API's OpenAPI
 * schema. Regenerate after changing any Pydantic model the web app consumes:
 *
 *     cd apps/api && python scripts/generate_web_types.py ../web/lib/generated-types.ts
 */
/* eslint-disable @typescript-eslint/no-explicit-any */

"""


def ts_name(schema_name: str) -> str:
    """Convert an OpenAPI schema name into a legal TypeScript identifier.

    FastAPI qualifies same-named schemas as `app__schemas__x__Name`, and splits
    a model used in both directions into `Name-Input` / `Name-Output`. Neither
    form is a valid identifier, so keep the trailing segment and strip the
    punctuation while preserving the Input/Output distinction.
    """
    name = schema_name.split("__")[-1]
    return re.sub(r"[^0-9A-Za-z_$]", "", name)


GENERIC_SEGMENTS = {"app", "schemas", "models", "api", "routes", "tools", "services"}


def qualified_ts_name(schema_name: str) -> str:
    """Disambiguating name for a schema whose short name is already taken.

    Two unrelated Pydantic models can share a class name (research.SourceRead
    and intelligence.SourceRead, for example). Emitting only the first would
    silently drop the other contract from the web types, so the loser is
    emitted under its module-qualified name instead: the nearest meaningful
    package segment, PascalCased, prefixed onto the short name.
    """
    parts = schema_name.split("__")
    short = ts_name(schema_name)
    context = [p for p in parts[:-1] if p not in GENERIC_SEGMENTS]
    if not context:
        return short
    prefix = "".join(segment.title().replace("_", "") for segment in context[-1:])
    return f"{prefix}{short}"


def type_expr(node: dict[str, Any], needed: set[str], names: dict[str, str] | None = None) -> str:
    if "$ref" in node:
        ref = node["$ref"].split("/")[-1]
        needed.add(ref)
        return (names or {}).get(ref) or ts_name(ref)

    for combiner in ("anyOf", "oneOf"):
        if combiner in node:
            parts = [type_expr(item, needed, names) for item in node[combiner]]
            # Pydantic renders Optional[x] as anyOf[x, null]; keep that readable.
            return " | ".join(dict.fromkeys(parts))
    if "allOf" in node and len(node["allOf"]) == 1:
        return type_expr(node["allOf"][0], needed, names)

    if "enum" in node:
        return " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in node["enum"])

    kind = node.get("type")
    if kind == "array":
        return f"{type_expr(node.get('items', {}), needed, names)}[]"
    if kind == "object":
        extra = node.get("additionalProperties")
        if isinstance(extra, dict) and extra:
            return f"Record<string, {type_expr(extra, needed, names)}>"
        return "Record<string, unknown>"
    if kind == "null":
        return "null";
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
    }.get(kind, "unknown")


def render(name: str, schema: dict[str, Any], needed: set[str], names: dict[str, str]) -> str:
    declared = names.get(name) or ts_name(name)
    if "enum" in schema and "properties" not in schema:
        values = " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in schema["enum"])
        return f"export type {declared} = {values};\n"

    required = set(schema.get("required", []))
    lines = [f"export interface {declared} {{"]
    for field, node in (schema.get("properties") or {}).items():
        # A field with a default is absent from OpenAPI's `required`, but these
        # are response models: FastAPI serializes defaults, so the key is always
        # present on the wire. Marking it optional only forced the UI to guard
        # values that cannot actually be missing.
        always_present = field in required or "default" in node
        optional = "" if always_present else "?"
        safe = field if re.fullmatch(r"[A-Za-z_$][\w$]*", field) else f'"{field}"'
        lines.append(f"  {safe}{optional}: {type_expr(node, needed, names)};")
    if len(lines) == 1:
        lines.append("  [key: string]: unknown;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "../web/lib/generated-types.ts")
    schemas = app.openapi()["components"]["schemas"]

    # Assign a TypeScript name to every schema first. FastAPI qualifies
    # same-named models per module, so two unrelated schemas can share a short
    # name; the first wins it and the rest are emitted module-qualified rather
    # than dropped, so no response contract goes missing from the web types.
    names: dict[str, str] = {}
    claimed: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []
    for name in sorted(schemas, key=ts_name):
        short = ts_name(name)
        if short not in claimed:
            claimed[short] = name
            names[name] = short
            continue
        qualified = qualified_ts_name(name)
        suffix = 2
        while qualified in claimed:
            qualified = f"{qualified_ts_name(name)}{suffix}"
            suffix += 1
        claimed[qualified] = name
        names[name] = qualified
        collisions.append((name, claimed[short], qualified))

    # Emit every schema: the set the web app needs grows as workspaces are wired,
    # and unused interfaces cost nothing at runtime.
    needed: set[str] = set()
    rendered: dict[str, str] = {}
    for name, schema in schemas.items():
        rendered[name] = render(name, schema, needed, names)

    missing = sorted(needed - set(schemas))
    if missing:
        print(f"warning: unresolved refs: {missing}", file=sys.stderr)

    body: list[str] = []
    collided = {name for name, _, _ in collisions}
    for name in sorted(rendered, key=lambda n: names[n]):
        if name in collided:
            kept = next(k for n, k, _ in collisions if n == name)
            body.append(f"// NOTE: {name} shares a class name with {kept}; emitted as {names[name]}.\n")
        body.append(rendered[name])

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HEADER + "\n".join(body), encoding="utf-8")
    print(f"wrote {len(rendered)} interfaces to {target} ({len(collisions)} module-qualified)")


if __name__ == "__main__":
    main()
