# UMDP — Universal Media Delivery Profile

UMDP is an open, machine-readable schema for broadcast, OTT, cinema, and ad-delivery technical specifications.

It lets a broadcaster, studio, post house, or QC vendor encode "what does this delivery need to look like" — codecs, containers, color, loudness, timecode, packaging, compliance — as a single JSON document that any tool can read.

**Schema version:** `0.9.0`
**Spec licence:** [CC BY 4.0](LICENSE) · **Tooling licence:** [MIT](LICENSE-MIT)

---

## Independence

UMDP is an independent open-source project. It is **not affiliated with, endorsed by, or sponsored by any of the broadcasters, studios, distributors, or platforms whose delivery requirements are encoded as profiles in this repository.** Organisation names, trademarks, and identifiers appear in profile filenames and `name`/`source` fields as descriptive metadata only — to identify *which* set of delivery facts a profile encodes, not to suggest endorsement of UMDP by that organisation.

If you are an authoritative representative of an organisation profiled here and want to either take maintainership of your own profile or have it removed, see [Takedown contact](#takedown-contact) below.

## Takedown contact

Email: `<TODO: takedown email>` (placeholder — to be replaced with a real address before public launch).

If you are authoritatively representing an organisation profiled in this repository and wish to:

- **Correct** a profile — open a PR or issue, or contact the address above; we will fast-track corrections from the originating organisation.
- **Take maintainership** of the profile for your organisation — contact the address above; we can route community PRs through you for review.
- **Have the profile removed** — contact the address above with verification of authority. Our target response window is **5 business days**.

Removed profiles are added to a takedown register. Contributors are asked not to re-submit profiles that have been removed in response to a takedown request — see [CONTRIBUTING.md § Takedown](CONTRIBUTING.md#takedown).

UMDP encodes **technical facts** about delivery requirements (codec names, loudness thresholds, file structure conventions). It does not host the source documents themselves, copy their wording, or reproduce their layout — see the [original wording rule](CONTRIBUTING.md#original-wording-rule).

---

## Why UMDP

Every broadcaster and platform writes its own delivery spec — usually as a PDF. Vendors and post houses re-implement the same fields by hand for every spec they support, and updates are easy to miss.

UMDP replaces the PDF with structured data:

- **One shape** — every spec describes codecs, audio loudness, timecode, etc. using the same field names.
- **Validatable** — drop a profile in a CI job and reject typos.
- **Diffable** — version-control your spec; reviewers can read a PR diff.
- **Tool-agnostic** — UMDP is just JSON; any QC tool, ingest pipeline, or asset manager can consume it.

UMDP is intentionally vendor-neutral. It is governed in the open and welcomes contributions from broadcasters, studios, distributors, post houses, and QC vendors.

---

## Repository layout

```
schema/umdp.schema.json   JSON Schema (Draft 2020-12) — the contract
schema/enums/             Recommended controlled vocabularies (codecs, containers, colour)
profiles/                 Real-world delivery specs encoded as UMDP documents
examples/                 Minimal annotated examples
docs/                     Field reference and contribution guidance
tools/validate.py         CLI validator — runs in CI on every PR
```

---

## Quickstart

```bash
# Install validator dependencies
pip install jsonschema

# Validate every profile in this repo
python tools/validate.py

# Validate a single profile
python tools/validate.py profiles/svt_hd.json
```

To use UMDP in your own pipeline, fetch `schema/umdp.schema.json` and validate against it with any Draft 2020-12 JSON Schema library — Python (`jsonschema`), Node (`ajv`), Go (`gojsonschema`), Java (`networknt/json-schema-validator`), etc.

---

## Profile naming convention

```
brand_subbrand_region_format.json
```

| Component  | Required | Example                             |
|------------|----------|-------------------------------------|
| `brand`    | Yes      | `svt`, `rte`, `tg4`                 |
| `subbrand` | No       | `iplayer`, `commercials`            |
| `region`   | No       | `se`, `ie`, `uk`                    |
| `format`   | Yes      | `hd`, `sd`, `uhd`, `mez`            |

The filename (without `.json`) is the spec's stable `id` and matches the document's `id` field.

---

## Contributing

UMDP grows by **forks and pull requests**. The most useful contributions are:

1. **A new profile** — encode a public delivery spec your organisation supports. Open a PR with the new file under `profiles/`.
2. **A schema field** — propose a new field with rationale: which spec needs it, what it represents, why existing fields can't carry it.
3. **A correction** — fix an inaccuracy in an existing profile against its source document. Cite the source.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and [GOVERNANCE.md](GOVERNANCE.md) for how schema changes are accepted and versioned.

CI runs `tools/validate.py` on every PR. Profiles must validate against the published schema before merge.

---

## Versioning

UMDP follows semantic versioning of the schema document. The current version is **0.9.0**.

The **single source of truth** for the schema version is the `$id` of [`schema/umdp.schema.json`](schema/umdp.schema.json). The schema `$comment`, the version strings in this README, and the top entry in [CHANGELOG.md](CHANGELOG.md) must all match it — `tools/validate.py` enforces this in CI, so the spots can't drift apart.

- **Patch** — clarifications, doc fixes, new profiles. Always backwards-compatible.
- **Minor** — new optional fields, new enum values, relaxed constraints.
- **Major** — breaking changes (renamed/removed fields, tightened types). Major versions ship with a migration note.

A profile's own `governance.spec_version` is the version of the **delivery spec it represents** (e.g. an internal v5.1 of a broadcaster's PDF) — not the UMDP schema version.

---

## Status

UMDP 0.9.0 covers the fields needed by every public-broadcaster, OTT-mezzanine, and ad-clearance spec we have profiled so far. It is `additionalProperties: true` throughout — vendors can add their own extension fields and propose them upstream as the ecosystem stabilises.

See [docs/gaps.md](docs/gaps.md) for known limitations and the proposal queue.

---

## Licence

The schema and profiles are licensed under [CC BY 4.0](LICENSE) — use them anywhere, attribute UMDP.
The validator and tooling code is licensed under [MIT](LICENSE-MIT).
