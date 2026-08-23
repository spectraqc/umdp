#!/usr/bin/env python3
"""Bulk-apply a field to a selected set of profiles, with honest provenance.

SQC-1975 — the manual alternative is opening N profiles and hand-editing the
same key into each, which is where a typo becomes a wrong delivery spec. This
selects profiles by jurisdiction (or by id), sets a dotted path in each, and —
crucially — keeps the two derived artefacts that a hand-edit silently breaks in
step:

  1. **The provenance record.** Since SQC-1947 a value-bearing assertion with NO
     record in provenance/<id>.json FAILS validation outright. So adding a field
     without a record does not "work and get tidied later" — it breaks the repo.

  2. **The governance.verification roll-up.** It is COMPUTED from the sidecar,
     never authored, and validate.py fails if a profile's block disagrees. Add a
     field and the assertion count moves, so the block must be recomputed.

Both are recomputed here using validate.py's OWN functions rather than a second
copy of the rules — if the definition of a value-bearing assertion changes, this
tool follows it automatically instead of drifting out of agreement with the gate
that judges it.

Why a bulk edit is NOT `method="human"`
======================================
`human` has a specific meaning in this repo: a person confirmed THE CITED SOURCE
DOCUMENT states this value. That is the only method that counts toward
`governance.verification.status="verified"`, and the whole provenance system
exists because 601 of 936 assertions turned out to be untraceable to their cited
source (SQC-1935/1947).

Applying one value across N profiles in a single command is, by construction,
not a per-profile source confirmation — it is a maintainer's assertion. So the
default written here is:

    state  = "unsourced"     the cited source was not consulted for this value
    method = "asserted"      a maintainer asserted it; not human/model/literal

Neither counts toward `verified` (that needs state="stated" AND method="human"),
so a bulk edit can never inflate a profile's verification. That is the point.

`--state` / `--method` can override this for the legitimate case where you HAVE
confirmed each source — but a combination that would count toward `verified`
requires a real `--source` and prints a loud warning naming every profile whose
status would change.

USAGE
=====
    # Carl's example — Upper Field First across the Nordics
    python3 tools/bulk_set.py --jurisdiction SE,NO,DK,FI \
        --set assets.video.signal.field_order='["tff"]' \
        --note 'Nordic HD house format' --dry-run

    # explicit profiles, several fields at once
    python3 tools/bulk_set.py --profile svt_hd,nrk_hd \
        --set assets.video.signal.field_order='["tff"]' \
        --set assets.video.scan_type='["interlaced"]'

    # a genuinely source-confirmed bulk add
    python3 tools/bulk_set.py --profile svt_hd \
        --set assets.video.signal.field_order='["tff"]' \
        --state stated --method human --source 'SVT_Leveransspec_v9.pdf'

Nothing is written without a run that omits --dry-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the gate's own rules — see module docstring.
from validate import (  # noqa: E402
    PROFILES_DIR,
    PROVENANCE_DIR,
    HUMAN_METHODS,
    _leaf_assertions,
    compute_verification,
    load_provenance,
)

DEFAULT_STATE = "unsourced"
DEFAULT_METHOD = "asserted"

SIDECAR_COMMENT = ("Per-field provenance. Only method='human' counts toward "
                   "governance.verification.status='verified'.")


# ── path handling ────────────────────────────────────────────────────────────

def parse_path(dotted: str) -> list:
    """'a.b[0].c' -> ['a', 'b', 0, 'c']. List indices become ints."""
    parts: list = []
    for chunk in dotted.split("."):
        if not chunk:
            raise ValueError(f"empty segment in path {dotted!r}")
        name, _, rest = chunk.partition("[")
        if name:
            parts.append(name)
        while rest:
            idx, _, rest = rest.partition("]")
            if not idx.isdigit():
                raise ValueError(f"bad list index in path {dotted!r}")
            parts.append(int(idx))
            rest = rest.lstrip(".").lstrip("[") if rest else ""
    return parts


def get_path(obj, parts: list):
    """Value at parts, or a sentinel miss."""
    cur = obj
    for p in parts:
        if isinstance(p, int):
            if not isinstance(cur, list) or p >= len(cur):
                return _MISS
            cur = cur[p]
        else:
            if not isinstance(cur, dict) or p not in cur:
                return _MISS
            cur = cur[p]
    return cur


class _Miss:
    def __repr__(self):
        return "<not set>"


_MISS = _Miss()


def set_path(obj, parts: list, value) -> None:
    """Set parts to value, creating intermediate dicts. Refuses to invent list
    elements — a profile's arrays are authored, not sparse."""
    cur = obj
    for i, p in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if isinstance(p, int):
            if not isinstance(cur, list) or p >= len(cur):
                raise KeyError(f"list index {p} does not exist at {parts[:i+1]}")
            cur = cur[p]
            continue
        if p not in cur or cur[p] is None:
            if isinstance(nxt, int):
                raise KeyError(f"refusing to create list at {'.'.join(map(str, parts[:i+1]))}")
            cur[p] = {}
        cur = cur[p]
        if not isinstance(cur, (dict, list)):
            raise KeyError(f"{'.'.join(map(str, parts[:i+1]))} is a scalar; cannot descend")
    last = parts[-1]
    if isinstance(last, int):
        if not isinstance(cur, list) or last >= len(cur):
            raise KeyError(f"list index {last} does not exist")
        cur[last] = value
    else:
        cur[last] = value


# ── selection ────────────────────────────────────────────────────────────────

def select_profiles(args) -> list[Path]:
    paths = sorted(PROFILES_DIR.glob("*.json"))
    if args.profile:
        wanted = {p.strip() for p in args.profile.split(",") if p.strip()}
        chosen = [p for p in paths if p.stem in wanted]
        missing = wanted - {p.stem for p in chosen}
        if missing:
            sys.exit(f"error: no such profile(s): {', '.join(sorted(missing))}")
        return chosen
    if args.jurisdiction:
        codes = {c.strip().upper() for c in args.jurisdiction.split(",") if c.strip()}
        out = []
        for p in paths:
            try:
                gov = json.loads(p.read_text()).get("governance") or {}
            except json.JSONDecodeError:
                continue
            juris = gov.get("jurisdiction")
            if isinstance(juris, list) and {str(j).upper() for j in juris} & codes:
                out.append(p)
        return out
    return paths  # --all


# ── the edit ─────────────────────────────────────────────────────────────────

def apply_to_profile(path: Path, edits: list[tuple[str, object]], args) -> dict:
    """Returns a report; mutates nothing on disk unless args.dry_run is False."""
    data = json.loads(path.read_text())
    pid = path.stem
    gov = data.get("governance") or {}
    authority = (gov.get("verification") or {}).get("status") == "authority_authored"

    before = {p for p, _v in _leaf_assertions(data)}
    changed, skipped = [], []

    for dotted, value in edits:
        parts = parse_path(dotted)
        current = get_path(data, parts)
        if current is not _MISS and current == value:
            skipped.append((dotted, "already set"))
            continue
        try:
            set_path(data, parts, value)
        except KeyError as e:
            skipped.append((dotted, f"cannot set: {e}"))
            continue
        changed.append((dotted, current, value))

    if not changed:
        return {"profile": pid, "changed": [], "skipped": skipped,
                "new_records": 0, "verification": None, "authority": authority}

    # Every NEW value-bearing leaf needs a record, or SQC-1947 fails the profile.
    # Derived from validate.py's own _leaf_assertions so booleans, nulls and free
    # text are excluded exactly as the gate excludes them.
    after = {p for p, _v in _leaf_assertions(data)}
    new_leaves = sorted(after - before)

    records = load_provenance(pid)
    sidecar_path = PROVENANCE_DIR / f"{pid}.json"
    if sidecar_path.exists():
        sidecar = json.loads(sidecar_path.read_text())
    else:
        sidecar = {"profile": pid, "$comment": SIDECAR_COMMENT, "fields": {}}
    sidecar.setdefault("fields", {})

    rec_template = {"state": args.state, "method": args.method}
    if args.source:
        rec_template["source"] = args.source
    if args.note:
        rec_template["note"] = args.note
    if args.verified_at:
        rec_template["verified_at"] = args.verified_at

    for leaf in new_leaves:
        sidecar["fields"][leaf] = dict(rec_template)
        records[leaf] = dict(rec_template)

    # The roll-up is derived; recompute or validate.py fails on the mismatch.
    verification = None
    if not authority:
        verification = compute_verification(data, records)
        data.setdefault("governance", {})["verification"] = verification

    if not args.dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        if new_leaves:
            PROVENANCE_DIR.mkdir(exist_ok=True)
            sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n")

    return {"profile": pid, "changed": changed, "skipped": skipped,
            "new_records": len(new_leaves), "verification": verification,
            "authority": authority}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sel = p.add_mutually_exclusive_group(required=True)
    sel.add_argument("--profile", help="Comma-separated profile ids (svt_hd,nrk_hd).")
    sel.add_argument("--jurisdiction", help="Comma-separated ISO codes; selects any "
                                            "profile whose governance.jurisdiction matches.")
    sel.add_argument("--all", action="store_true", help="Every profile in profiles/.")
    p.add_argument("--set", action="append", required=True, metavar="PATH=JSON",
                   help='Dotted path and a JSON value, e.g. '
                        'assets.video.signal.field_order=\'["tff"]\'. Repeatable.')
    p.add_argument("--state", default=DEFAULT_STATE,
                   help=f"Provenance state (default {DEFAULT_STATE!r}).")
    p.add_argument("--method", default=DEFAULT_METHOD,
                   help=f"Provenance method (default {DEFAULT_METHOD!r}). "
                        "'human' is the ONLY value counting toward verified.")
    p.add_argument("--source", default=None, help="Source document for the record.")
    p.add_argument("--note", default=None, help="Free-text note stored on each record.")
    p.add_argument("--verified-at", default=None, dest="verified_at",
                   help="ISO date; only meaningful with --method human.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would change and write nothing.")
    args = p.parse_args(argv)

    edits = []
    for raw in args.set:
        key, sep, val = raw.partition("=")
        if not sep:
            sys.exit(f"error: --set needs PATH=JSON, got {raw!r}")
        try:
            edits.append((key.strip(), json.loads(val)))
        except json.JSONDecodeError as e:
            sys.exit(f"error: --set value for {key!r} is not valid JSON ({e}). "
                     f'Strings need quotes: {key}=\'"tff"\'')

    targets = select_profiles(args)
    if not targets:
        print("no profiles matched the selection — nothing to do")
        return 0

    counts_as_verified = args.method in HUMAN_METHODS and args.state == "stated"
    if counts_as_verified:
        if not args.source or args.source.strip().lower() in ("", "n/a"):
            sys.exit("error: --method human with --state stated claims each profile's "
                     "CITED SOURCE states this value, so --source is required. "
                     "If this is a maintainer assertion, use the defaults "
                     f"(--state {DEFAULT_STATE} --method {DEFAULT_METHOD}).")
        print("WARNING: these records will count toward governance.verification — "
              "only proceed if you have confirmed the source of EACH profile below.\n")

    reports = [apply_to_profile(t, edits, args) for t in targets]

    touched = 0
    for r in reports:
        for dotted, old, new in r["changed"]:
            was = "" if old is _MISS else f" (was {json.dumps(old)})"
            print(f"{r['profile']:<24} {dotted}  -> {json.dumps(new)}{was}")
        for dotted, why in r["skipped"]:
            print(f"{r['profile']:<24} {dotted}  {why}")
        if r["changed"]:
            touched += 1
            bits = [f"+{r['new_records']} provenance record(s)"]
            if r["authority"]:
                bits.append("verification untouched (authority_authored)")
            elif r["verification"]:
                v = r["verification"]
                bits.append(f"verification -> {v['status']} "
                            f"({v['verified_fields']}/{v['assertions']} verified, "
                            f"{v['unsourced_fields']} unsourced)")
            print(f"{'':<24} {'; '.join(bits)}")

    verb = "would change" if args.dry_run else "changed"
    print(f"\n{touched} of {len(targets)} selected profile(s) {verb}.")
    if args.dry_run:
        print("Dry run — nothing written. Re-run without --dry-run.")
    elif touched:
        print("Now run: python3 tools/validate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
