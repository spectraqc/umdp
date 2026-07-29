#!/usr/bin/env python3
"""
Validate the UMDP repository: profile JSON files plus repo-level invariants.

Usage:
    tools/validate.py                          # validate every file in profiles/
    tools/validate.py path/to/profile.json     # validate a specific file
    tools/validate.py profiles/*.json

Five classes of check run:

  * JSON Schema   — every target validates against schema/umdp.schema.json.
  * Convention    — every profile's top-level `id` equals its filename stem,
                    and ids are unique across the set (SQC-1118 / SQC-87).
  * Version       — the schema `$id` is the single source of truth for the
                    schema version; `$comment`, README and CHANGELOG must
                    agree with it (SQC-1117).
  * Provenance    — every value-bearing leaf field must have a record in
                    provenance/<id>.json (SQC-1947); a declared
                    governance.verification roll-up must match what's
                    computed from that sidecar, never hand-authored
                    (SQC-1935). Omitting a field stays legal — UMDP models
                    absence — this only targets an asserted value with
                    nothing shown to support it. This is currently RED on
                    every shipped profile: 0.14.0 (SQC-1935) added the
                    mechanism but deliberately backfilled only 8 of 16
                    profiles; SQC-1946 is paying down the rest. That's the
                    intended state, not a bug in this gate — it exists so
                    the debt can't grow while it's paid down, per SQC-1947.
                    Skipped entirely for status=authority_authored (SQC-1949)
                    — an org-authored spec has no third-party source to trace
                    values to at all, so this framework doesn't apply.
  * Sense         — internal contradictions that make a profile impossible to
    (hard-fail)     satisfy regardless of who authored it or why: a min above
                    its own max, a bit-depth floor no allowed value can meet,
                    field order on exclusively-progressive content, an
                    incompatible codec/container pairing (SQC-1949). Runs on
                    every profile, not just authority_authored ones — an
                    internal contradiction is a bug in a reference profile
                    too.

Three advisory (non-failing) reports also run:

  * Undocumented  — profile keys not declared in the schema's `properties`.
    keys           On *value* objects (signal_limits, loudness, sync, …) these
                    now hard-fail via `additionalProperties: false` (0.11.0); on
                    *container* objects, still `additionalProperties: true`, an
                    unknown key is legal extension and is reported as a `note`
                    so near-miss names surface in review (SQC-1395). Never fails
                    CI on its own.

  * Controlled    — codec / container / audio-codec / channel-layout /
    vocabulary     broadcast-system tokens in a profile that are not in the
                    recommended lists (schema/enums/*.json). The schema leaves
                    these fields as free strings (adopters may extend), so this
                    only `note`s free-text / near-miss spellings (e.g. 'AVC Intra'
                    vs 'avc_intra_100', '5.1' vs 'L-R-C-LFE-Ls-Rs') so profiles
                    diff cleanly across vendors (SQC-1490, extended SQC-1532).
                    Never fails CI on its own.

  * Sense         — a profile names a standard (EBU R128, ATSC A/85, …) but
    (warn)          sets a value the standard doesn't define — e.g. claims R128
                    but a target other than -23.0 LUFS (SQC-1949). The org may
                    deviate deliberately (staging exists to carry exactly
                    that), but must NOTICE a silent deviation from a standard
                    the profile itself names. Never fails CI on its own.

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
ENUMS_DIR = REPO_ROOT / "schema" / "enums"
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
    not declared in the matching schema node's ``properties``. Container
    objects are ``additionalProperties: true``, so jsonschema accepts extension
    keys on them silently; surfacing them catches near-miss key names (e.g.
    ``max_drift_ms`` vs ``max_offset_ms``) in review. Value objects are closed
    (``additionalProperties: false``, 0.11.0) so jsonschema already hard-fails
    their unknown keys; a note there is just a louder echo. Only reports where
    the schema documents a property set — free-form objects are left alone."""
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


def load_controlled_vocab() -> dict[str, set[str]]:
    """SQC-1490 — the recommended identifiers from schema/enums/*.json, as id
    sets, keyed by the profile field they govern. Advisory only: the main schema
    does not enforce these (schema/enums/README.md). Missing/unreadable enum
    files yield empty sets, which disables the advisory for that field (never
    errors). SQC-1532 extends coverage to channel layouts and broadcast_system."""
    def ids(path: Path, *keys: str) -> set[str]:
        try:
            doc = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return set()
        out: set[str] = set()
        for key in keys:
            for entry in doc.get(key, []):
                if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    out.add(entry["id"])
        return out

    codecs = ENUMS_DIR / "codecs.json"
    containers = ENUMS_DIR / "containers.json"
    layouts = ENUMS_DIR / "layouts.json"
    broadcast_systems = ENUMS_DIR / "broadcast-systems.json"
    return {
        "assets.video.codec": ids(codecs, "video"),
        "assets.audio.codec": ids(codecs, "audio"),
        "assets.video.container": ids(containers, "containers"),
        "assets.audio.layout.allowed_layouts": ids(layouts, "layouts"),
        "assets.video.signal.broadcast_system": ids(broadcast_systems, "broadcast_systems"),
    }


def non_canonical_tokens(data: object, vocab: dict[str, set[str]]) -> list[str]:
    """SQC-1490 / SQC-1532 — advisory: codec / container / audio-codec / layout /
    broadcast-system tokens in a profile that are not in the recommended
    controlled vocabulary. These fields are free strings in the schema (so
    jsonschema accepts anything); surfacing off-vocab tokens catches free-text /
    near-miss spellings (e.g. 'AVC Intra' vs 'avc_intra_100', '5.1' vs
    'L-R-C-LFE-Ls-Rs') so profiles diff cleanly. Empty vocab ⇒ field skipped.

    The governed field's value takes one of three shapes, handled by leaf type:
      * bucket object — {allowed:[...], disallowed:[...]} (codec, container);
      * bare list     — allowed_layouts;
      * scalar string — broadcast_system."""
    if not isinstance(data, dict):
        return []
    assets = data.get("assets")
    assets = assets if isinstance(assets, dict) else {}
    notes: list[str] = []
    for field, allowed_vocab in vocab.items():
        if not allowed_vocab:
            continue
        node: object = assets
        for part in field.split(".")[1:]:  # skip leading "assets"
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict):
            # bucket object: check allowed/disallowed token lists
            for bucket in ("allowed", "disallowed"):
                for tok in node.get(bucket) or []:
                    if isinstance(tok, str) and tok not in allowed_vocab:
                        notes.append(
                            f"{field}.{bucket} token {tok!r} not in the recommended "
                            "vocabulary (schema/enums/*.json)"
                        )
        elif isinstance(node, (list, str)):
            # bare list or scalar string: check the token(s) directly
            tokens = node if isinstance(node, list) else [node]
            for tok in tokens:
                if isinstance(tok, str) and tok not in allowed_vocab:
                    notes.append(
                        f"{field} token {tok!r} not in the recommended "
                        "vocabulary (schema/enums/*.json)"
                    )
    return notes


PROVENANCE_DIR = REPO_ROOT / "provenance"
HUMAN_METHODS = {"human"}


def _leaf_assertions(obj, prefix: str = ""):
    """Yield (dotted_path, value) for every VALUE-BEARING leaf, expanding lists by index.

    Booleans, nulls and free text are authoring judgements rather than values a specification
    states, so they are not assertions a source can be asked to support and are excluded from
    the counts. `governance` is metadata about the profile, not a claim about the delivery.

    SQC-1954 — id/name/delivery_paradigm/content_type are excluded too: across a full pass of
    real profiles (SQC-1946/1938) these four consistently surfaced as "unsourced" even though
    none of them is a value a broadcaster's spec document states. `id` and `name` are this
    profile's own authored identifier and title; `delivery_paradigm` and `content_type` are how
    the author categorised the delivery, not a fact the source asserts. Every one of the 10
    profiles reconciled so far needed a source="n/a" workaround record for exactly these four
    fields — that's the rule being wrong, not 10 coincidences.
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            if not prefix and key in ("governance", "id", "name", "delivery_paradigm", "content_type"):
                continue
            yield from _leaf_assertions(val, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, list):
        for n, val in enumerate(obj):
            yield from _leaf_assertions(val, f"{prefix}[{n}]")
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, str) and (len(obj) > 60 or prefix.endswith("notes")):
        return
    else:
        yield prefix, obj


def load_provenance(profile_id: str) -> dict:
    path = PROVENANCE_DIR / f"{profile_id}.json"
    if not path.exists():
        return {}
    try:
        blob = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return blob.get("fields", {}) if isinstance(blob, dict) else {}


def compute_verification(data: dict, records: dict) -> dict:
    """The roll-up, derived from the sidecar. Never read from the profile.

    'verified' requires a HUMAN record on every assertion. Literal matching and model checking
    produce candidates for review, not verification: a machine agreeing with a value it was
    handed is not evidence the value is right, and treating it as such is how 601 unsourced
    assertions came to look authoritative in the first place.
    """
    assertions = [p for p, _v in _leaf_assertions(data)]
    verified, dates = 0, []
    for path in assertions:
        rec = records.get(path)
        if isinstance(rec, dict) and rec.get("method") in HUMAN_METHODS and rec.get("state") == "stated":
            verified += 1
            if rec.get("verified_at"):
                dates.append(rec["verified_at"])
    unsourced = sum(1 for p in assertions if p not in records)
    if assertions and verified == len(assertions):
        status = "verified"
    elif verified:
        status = "partial"
    else:
        status = "unverified"
    out = {"status": status, "assertions": len(assertions),
           "verified_fields": verified, "unsourced_fields": unsourced}
    if dates:
        out["verified_at"] = max(dates)
    return out


def check_verification(data: dict, profile_id: str) -> list[str]:
    """A profile may not overstate how much of it has been checked."""
    declared = (data.get("governance") or {}).get("verification")
    if declared is not None and declared.get("status") == "authority_authored":
        # SQC-1949 — a different claim, not a weaker point on the same scale: the
        # authoring party IS the authority, so there is nothing to compute against
        # provenance/. The schema's if/then already requires nothing else be declared.
        return []
    computed = compute_verification(data, load_provenance(profile_id))
    if declared is None:
        if computed["status"] != "unverified":
            return ["governance.verification missing but provenance records exist "
                    f"(compute it: {json.dumps(computed, sort_keys=True)})"]
        return []
    errors = []
    for key, want in computed.items():
        got = declared.get(key)
        if got != want:
            errors.append(
                f"governance.verification.{key}: declared {got!r} but computed {want!r} "
                "from provenance/ — the roll-up is derived, not authored"
            )
    return errors


def check_provenance(data: dict, profile_id: str) -> list[str]:
    """SQC-1947 — every value-bearing assertion must have a provenance record.

    This is what 601 unsourced assertions (SQC-1935/1946) were: a value the
    profile stated as fact with nothing behind it but governance.sourceSpec
    vouching for the whole document. Omitting a field stays legal — UMDP
    already models absence, and "not stated in source" is a correct profile
    outcome, so _leaf_assertions() never sees a field that isn't there.
    Booleans, nulls and free text are authoring judgements rather than values
    a spec states and are excluded the same way (see _leaf_assertions). This
    only targets an assertion that exists with no record at all; it does not
    require the record to be method="human" — that bar is verified_fields /
    governance.verification.status, a stronger, separate claim.

    SQC-1949 — skipped entirely for status=authority_authored: there is no cited
    source document to trace a value to, so "no provenance record" isn't a gap
    here the way it is for a reference profile.
    """
    if (data.get("governance") or {}).get("verification", {}).get("status") == "authority_authored":
        return []
    records = load_provenance(profile_id)
    unsourced = [p for p, _v in _leaf_assertions(data) if p not in records]
    if not unsourced:
        return []
    shown = ", ".join(unsourced[:5])
    more = f" (+{len(unsourced) - 5} more)" if len(unsourced) > 5 else ""
    return [
        f"{len(unsourced)} value-bearing assertion(s) have no provenance record in "
        f"provenance/{profile_id}.json: {shown}{more}"
    ]


def _at(obj, *path):
    """Navigate a dotted path through nested dicts; None if any hop is missing/wrong-typed."""
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


# SQC-1949 — a profile whose values contradict EACH OTHER can never be satisfied by any
# real delivery, regardless of who authored it or why (an org-authored spec is authoritative
# about WHAT it wants, never about whether its own numbers are self-consistent). Deliberately
# narrow and literal-minded — same spirit as the husk/version-conflict detectors elsewhere in
# this file: catch a real contradiction, never infer or guess at one.
_INCOMPATIBLE_CODEC_CONTAINER = {
    ("avc_intra_100", "mp4"), ("avc_intra_50", "mp4"), ("avc_intra_200", "mp4"),
    ("xdcam_hd_422_50", "mp4"), ("d10", "mp4"), ("d10", "mov"),
}


def check_sense_hard(data: dict) -> list[str]:
    errors = []

    tc = _at(data, "assets", "audio", "track_count")
    if isinstance(tc, dict) and isinstance(tc.get("min"), (int, float)) and isinstance(tc.get("max"), (int, float)):
        if tc["min"] > tc["max"]:
            errors.append(f"assets.audio.track_count: min ({tc['min']}) > max ({tc['max']})")

    for label in ("luminance", "rgb"):
        limits = _at(data, "constraints", "video", "signal_limits", label)
        if isinstance(limits, dict) and isinstance(limits.get("min"), (int, float)) and isinstance(limits.get("max"), (int, float)):
            if limits["min"] >= limits["max"]:
                errors.append(
                    f"constraints.video.signal_limits.{label}: min ({limits['min']}) >= "
                    f"max ({limits['max']}) — not a valid range"
                )

    bit_depth = _at(data, "assets", "video", "bit_depth")
    if isinstance(bit_depth, dict) and isinstance(bit_depth.get("min"), (int, float)) and isinstance(bit_depth.get("allowed"), list):
        allowed_nums = [v for v in bit_depth["allowed"] if isinstance(v, (int, float))]
        if allowed_nums and bit_depth["min"] > min(allowed_nums):
            errors.append(
                f"assets.video.bit_depth: min ({bit_depth['min']}) exceeds every value in "
                f"allowed ({allowed_nums}) — no allowed bit depth can satisfy the minimum"
            )

    scan_type = _at(data, "assets", "video", "scan_type")
    field_order = _at(data, "assets", "video", "signal", "field_order")
    if isinstance(scan_type, list) and scan_type == ["progressive"] and field_order:
        errors.append(
            "assets.video: scan_type is exclusively 'progressive' but signal.field_order "
            f"is set ({field_order}) — field order only applies to interlaced content"
        )

    codec = _at(data, "assets", "video", "codec", "allowed") or []
    container = _at(data, "assets", "video", "container", "allowed") or []
    if isinstance(codec, list) and isinstance(container, list):
        for c in codec:
            for w in container:
                if (c, w) in _INCOMPATIBLE_CODEC_CONTAINER:
                    errors.append(f"assets.video: codec {c!r} is not deliverable in container {w!r}")

    return errors


def check_sense_warn(data: dict) -> list[str]:
    """SQC-1949 — a profile that NAMES a standard but sets a value the standard doesn't
    define is a silent-deviation risk: the org may have a legitimate, deliberate reason
    (staging exists to carry exactly that), but must NOTICE, not drift unknowingly.
    Advisory only, never fails validation — deliberately narrow (a handful of the most
    common named standards), same spirit as the controlled-vocabulary notes above."""
    notes = []
    standards = _at(data, "assets", "audio", "loudness", "standards") or []
    for std in standards:
        if not isinstance(std, dict):
            continue
        name = str(std.get("name", ""))
        target, tol = std.get("target"), std.get("tolerance")
        if "128" in name:
            if isinstance(target, (int, float)) and target != -23.0:
                notes.append(f"loudness.standards names {name!r} but target={target} (R128 defines -23.0 LUFS)")
            if isinstance(tol, (int, float)) and tol > 1.0:
                notes.append(
                    f"loudness.standards names {name!r} but tolerance={tol} "
                    "(R128's live/impractical-target exception caps at ±1.0 LU)"
                )
        if "85" in name and "atsc" in name.lower():
            if isinstance(target, (int, float)) and target != -24.0:
                notes.append(f"loudness.standards names {name!r} but target={target} (ATSC A/85 defines -24.0 LKFS)")

    true_peak = _at(data, "assets", "audio", "loudness", "true_peak_max")
    if any("128" in str(s.get("name", "")) for s in standards if isinstance(s, dict)):
        if isinstance(true_peak, (int, float)) and true_peak > -1.0:
            notes.append(f"loudness names EBU R128 but true_peak_max={true_peak} dBTP (R128 caps at -1 dBTP)")

    bit_depth_allowed = _at(data, "assets", "video", "bit_depth", "allowed") or []
    color_range = _at(data, "assets", "video", "color", "range") or []
    # Only checkable when bit depth is unambiguous: a profile accepting both 8- and
    # 10-bit codecs (e.g. clearcast_commercials) has no single "implied" legal range,
    # and declaring the stricter one is a legitimate choice, not a deviation to notice.
    if "limited" in color_range and len(bit_depth_allowed) == 1:
        expect = (64, 940) if bit_depth_allowed[0] == 10 else (16, 235) if bit_depth_allowed[0] == 8 else None
        if expect:
            for label in ("luminance", "rgb"):
                limits = _at(data, "constraints", "video", "signal_limits", label)
                if not isinstance(limits, dict):
                    continue
                mn, mx = limits.get("min"), limits.get("max")
                if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and (mn, mx) != expect:
                    notes.append(
                        f"signal_limits.{label} is ({mn}, {mx}) but {bit_depth_allowed[0]}-bit limited range "
                        f"implies {expect} (could be the base range with EBU R103 tolerance already folded "
                        "in, e.g. 64-940 ±5%/-1%/+3% ≈ 20-984 — worth confirming that's intentional)"
                    )

    broadcast_system = _at(data, "assets", "video", "signal", "broadcast_system")
    frame_rate_allowed = _at(data, "assets", "video", "frame_rate", "allowed") or []
    if isinstance(broadcast_system, str):
        m = re.search(r"/(\d+(?:\.\d+)?)", broadcast_system)
        if m and frame_rate_allowed and m.group(1) not in [str(v) for v in frame_rate_allowed]:
            notes.append(
                f"signal.broadcast_system={broadcast_system!r} implies frame rate {m.group(1)}, "
                f"but frame_rate.allowed={frame_rate_allowed} doesn't include it"
            )

    return notes


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

    vocab = load_controlled_vocab()

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
                errs.extend(check_verification(data, profile_id))
                errs.extend(check_provenance(data, profile_id))
                errs.extend(check_sense_hard(data))
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
            # SQC-1490 — advisory only: off-vocabulary codec/container tokens.
            for msg in non_canonical_tokens(data, vocab):
                print(f"note {rel}: {msg}")
            # SQC-1949 — advisory only: deviates from a standard the profile itself names.
            for msg in check_sense_warn(data):
                print(f"note {rel}: {msg}")

    if failed:
        print(f"\n{failed} check(s) failed")
        return 1
    print(f"\nall {len(targets)} profile(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
