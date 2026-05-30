#!/usr/bin/env python3
"""
Validate one or more UMDP profile JSON files against the UMDP schema.

Usage:
    tools/validate.py                          # validate every file in profiles/
    tools/validate.py path/to/profile.json     # validate a specific file
    tools/validate.py profiles/*.json
"""

from __future__ import annotations

import json
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


def load_schema() -> dict:
    with SCHEMA_PATH.open() as fh:
        return json.load(fh)


def gather_targets(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    profiles_dir = REPO_ROOT / "profiles"
    return sorted(profiles_dir.glob("*.json"))


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


def main() -> int:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    targets = gather_targets(sys.argv[1:])
    if not targets:
        print("no profiles to validate")
        return 0

    failed = 0
    for path in targets:
        rel = path.relative_to(REPO_ROOT) if path.is_absolute() else path
        errs = validate_file(validator, path)
        if errs:
            failed += 1
            print(f"FAIL {rel}")
            for err in errs:
                print(f"  - {err}")
        else:
            print(f"ok   {rel}")

    if failed:
        print(f"\n{failed} of {len(targets)} profile(s) failed validation")
        return 1
    print(f"\nall {len(targets)} profile(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
