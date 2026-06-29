#!/usr/bin/env python3
"""
Validate the UMDP repository: profile JSON files plus repo-level invariants.

Usage:
    tools/validate.py                          # validate every file in profiles/
    tools/validate.py path/to/profile.json     # validate a specific file
    tools/validate.py profiles/*.json

Three classes of check run:

  * JSON Schema   — every target validates against schema/umdp.schema.json.
  * Convention    — every profile's top-level `id` equals its filename stem,
                    and ids are unique across the set (SQC-1118 / SQC-87).
  * Version       — the schema `$id` is the single source of truth for the
                    schema version; `$comment`, README and CHANGELOG must
                    agree with it (SQC-1117).

One advisory (non-failing) report also runs:

  * Undocumented  — profile keys not declared in the schema's `properties`
    keys           (allowed only by `additionalProperties: true`). Printed as
                    `note` lines so near-miss key names surface in review;
                    never fails CI (SQC-1395).

Any failure prints a FAIL line and the script exits non-zero, so CI blocks
the merge. Advisory `note` lines do not affect the exit code.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.stderr.write(
        "jsonschema is required. Install with: pip install jsonschema\n"
    )
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "umdp.schema.json"
PROFILES_DIR = REPO_ROOT / "profiles"
README_PATH = REPO_ROOT / "README.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

SEMVER = r"\d+\.\d+\.\d+"


def load_schema() -> dict:
    with SCHEMA_PATH.open() as fh:
        return json.load(fh)


def gather_targets(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    return sorted(PROFILES_DIR.glob("*.json"))


def schema_version(schema: dict) -> str | None:
    """Canonical schema version, parsed from the schema `$id` URN."""
    match = re.search(rf"urn:umdp:schema:({SEMVER})", schema.get("$id", ""))
    return match.group(1) if match else None


def check_version_consistency(schema: dict) -> list[str]:
    """The schema `$id` version is canonical; every other spot must match it."""
    canonical = schema_version(schema)
    if canonical is None:
        return [f"schema $id does not contain a version: {schema.get('$id')!r}"]

    errors: list[str] = []

    def expect(label: str, source: str, pattern: str) -> None:
        match = re.search(pattern, source)
        if match is None:
            errors.append(f"{label}: no version string found (expected {canonical})")
        elif match.group(1) != canonical:
            errors.append(
                f"{label}: {match.group(1)} != schema $id {canonical}"
            )

    expect("schema $comment", schema.get("$comment", ""), rf"UMDP ({SEMVER})")

    readme = README_PATH.read_text()
    expect("README badge", readme, rf"\*\*Schema version:\*\*\s*`({SEMVER})`")
    expect("README versioning", readme, rf"current version is \*\*({SEMVER})\*\*")
    expect("README status", readme, rf"UMDP ({SEMVER}) covers")

    changelog = CHANGELOG_PATH.read_text()
    expect("CHANGELOG top entry", changelog, rf"(?m)^##\s*\[({SEMVER})\]")

    return errors


def _resolve_ref(node: dict, root: dict) -> dict:
    """Follow local ``$ref`` chains (``#/$defs/Name``) to the target subschema.
    Non-local or unresolvable refs are returned unchanged."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 32:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return node
        target: object = root
        for part in ref[2:].split("/"):
            if not isinstance(target, dict):
                return node
            target = target.get(part, {})
        node = target  # type: ignore[assignment]
        seen += 1
    return node


def undocumented_keys(schema: dict, data: object, root: dict, path: str = "") -> list[str]:
    """SQC-1395 — advisory walk: dotted paths of keys present in ``data`` but
    not declared in the matching schema node's ``properties``. Because the
    schema is ``additionalProperties: true`` throughout, jsonschema accepts
    these silently; surfacing them catches near-miss key names (e.g.
    ``max_drift_ms`` vs ``max_offset_ms``) in review. Only reports where the
    schema documents a property set — free-form objects are left alone."""
    schema = _resolve_ref(schema, root)
    found: list[str] = []
    if not isinstance(schema, dict):
        return found
    if isinstance(data, dict):
        props = schema.get("properties")
        if isinstance(props, dict):
            for key, value in data.items():
                child = f"{path}.{key}" if path else key
                if key in props:
                    found += undocumented_keys(props[key], value, root, child)
                else:
                    found.append(child)
    elif isinstance(data, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, value in enumerate(data):
                found += undocumented_keys(items, value, root, f"{path}[{i}]")
    return found


def validate_file(validator: Draft202012Validator, path: Path) -> list[str]:
    try:
        with path.open() as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    return [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in errors
    ]


def is_profile(path: Path) -> bool:
    return path.resolve().parent == PROFILES_DIR


def main() -> int:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    failed = 0

    version_errors = check_version_consistency(schema)
    if version_errors:
        failed += 1
        print("FAIL version consistency")
        for err in version_errors:
            print(f"  - {err}")
    else:
        print(f"ok   version consistency ({schema_version(schema)})")

    targets = gather_targets(sys.argv[1:])
    if not targets:
        print("no profiles to validate")
        return 1 if failed else 0

    ids: dict[str, str] = {}  # id -> first filename that claimed it
    for path in targets:
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        errs = validate_file(validator, path)

        # Convention checks apply only to profiles/, and only if the file
        # parsed cleanly enough to read its id.
        if is_profile(path) and not any(e.startswith("invalid JSON") for e in errs):
            with path.open() as fh:
                data = json.load(fh)
            profile_id = data.get("id")
            if profile_id != path.stem:
                errs.append(
                    f"convention: id {profile_id!r} != filename stem {path.stem!r} "
                    "(filename without .json must equal top-level id)"
                )
            if isinstance(profile_id, str):
                if profile_id in ids:
                    errs.append(
                        f"convention: duplicate id {profile_id!r} "
                        f"(also used by {ids[profile_id]})"
                    )
                else:
                    ids[profile_id] = str(rel)

        if errs:
            failed += 1
            print(f"FAIL {rel}")
            for err in errs:
                print(f"  - {err}")
        else:
            print(f"ok   {rel}")

        # SQC-1395 — advisory only: surface keys the schema doesn't document.
        if is_profile(path) and not any(e.startswith("invalid JSON") for e in errs):
            with path.open() as fh:
                data = json.load(fh)
            for key_path in undocumented_keys(schema, data, schema):
                print(f"note {rel}: undocumented key {key_path!r} "
                      "(allowed by additionalProperties; not in schema)")

    if failed:
        print(f"\n{failed} check(s) failed")
        return 1
    print(f"\nall {len(targets)} profile(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
