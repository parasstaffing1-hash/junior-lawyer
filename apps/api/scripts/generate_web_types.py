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


def type_expr(node: dict[str, Any], needed: set[str]) -> str:
    if "$ref" in node:
        ref = node["$ref"].split("/")[-1]
        needed.add(ref)
        return ts_name(ref)

    for combiner in ("anyOf", "oneOf"):
        if combiner in node:
            parts = [type_expr(item, needed) for item in node[combiner]]
            # Pydantic renders Optional[x] as anyOf[x, null]; keep that readable.
            return " | ".join(dict.fromkeys(parts))
    if "allOf" in node and len(node["allOf"]) == 1:
        return type_expr(node["allOf"][0], needed)

    if "enum" in node:
        return " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in node["enum"])

    kind = node.get("type")
    if kind == "array":
        return f"{type_expr(node.get('items', {}), needed)}[]"
    if kind == "object":
        extra = node.get("additionalProperties")
        if isinstance(extra, dict) and extra:
            return f"Record<string, {type_expr(extra, needed)}>"
        return "Record<string, unknown>"
    if kind == "null":
        return "null";
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
    }.get(kind, "unknown")


def render(name: str, schema: dict[str, Any], needed: set[str]) -> str:
    if "enum" in schema and "properties" not in schema:
        values = " | ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in schema["enum"])
        return f"export type {ts_name(name)} = {values};\n"

    required = set(schema.get("required", []))
    lines = [f"export interface {ts_name(name)} {{"]
    for field, node in (schema.get("properties") or {}).items():
        optional = "" if field in required else "?"
        safe = field if re.fullmatch(r"[A-Za-z_$][\w$]*", field) else f'"{field}"'
        lines.append(f"  {safe}{optional}: {type_expr(node, needed)};")
    if len(lines) == 1:
        lines.append("  [key: string]: unknown;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "../web/lib/generated-types.ts")
    schemas = app.openapi()["components"]["schemas"]

    # Emit every schema: the set the web app needs grows as workspaces are wired,
    # and unused interfaces cost nothing at runtime.
    needed: set[str] = set()
    rendered: dict[str, str] = {}
    for name, schema in schemas.items():
        rendered[name] = render(name, schema, needed)

    missing = sorted(needed - set(schemas))
    if missing:
        print(f"warning: unresolved refs: {missing}", file=sys.stderr)

    # Collapse FastAPI's qualified duplicates, keeping the first definition and
    # reporting the clash rather than emitting invalid duplicate declarations.
    seen: dict[str, str] = {}
    body: list[str] = []
    for name in sorted(rendered, key=ts_name):
        short = ts_name(name)
        if short in seen:
            body.append(f"// NOTE: {name} collides with {seen[short]}; kept the first.\n")
            continue
        seen[short] = name
        body.append(rendered[name])

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HEADER + "\n".join(body), encoding="utf-8")
    print(f"wrote {len(seen)} interfaces to {target}")


if __name__ == "__main__":
    main()
