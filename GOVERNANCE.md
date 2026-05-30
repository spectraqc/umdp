# UMDP Governance

UMDP is an open project. This document describes how decisions are made and how the schema evolves.

## Principles

1. **Vendor-neutral.** No single broadcaster, studio, or QC vendor controls UMDP. Anyone can fork, contribute, and adopt.
2. **Real specs only.** UMDP fields exist because at least one published delivery spec needs them. Speculative fields are rejected.
3. **Backwards-compatible by default.** Schema changes that break existing profiles require a major version bump and a documented migration.
4. **Extension-friendly.** Every UMDP object accepts `additionalProperties`, so adopters can add custom fields without forking. Extensions that prove broadly useful become first-class fields in the next minor release.

## Versioning

UMDP follows semantic versioning at the schema level.

| Bump | Trigger |
|------|---------|
| **Major** (`0.x.x` → `1.0.0`) | Removing or renaming a field. Tightening a type. Anything that invalidates an existing profile. |
| **Minor** (`0.7.0` → `0.8.0`) | New optional field. New enum value. Loosened constraint. |
| **Patch** (`0.7.0` → `0.7.1`) | Documentation. New profile. Bug fix in tooling. |

A profile's `governance.spec_version` is the version of the **delivery spec it represents** (e.g. EBU R128 v4, an internal broadcaster PDF v5.1) — not the UMDP schema version.

## How a schema change is accepted

1. **Issue first.** Open a *Schema change proposal* issue describing what spec requires the field and what shape you propose.
2. **Discussion.** Maintainers and the community comment. The bar is real-world necessity, not theoretical completeness.
3. **PR.** Once a shape is agreed, open a PR that:
   - Updates `schema/umdp.schema.json`.
   - Adds at least one profile or example using the new field.
   - Updates `CHANGELOG.md` under the next release header.
4. **Merge.** Two maintainer approvals required for schema changes. One approval for profile additions or doc fixes.

## How a profile change is accepted

- **New profile** — one maintainer approval; CI must pass; `governance.source` must cite a public document.
- **Profile correction** — one maintainer approval; the PR description must reference the authoritative source and section.

## Maintainers

Initial maintainers are listed in `MAINTAINERS.md`. Adding a maintainer requires consensus from existing maintainers. Removing one requires the same.

## Disputes

If a contributor disagrees with a decision, the standard escalation is:

1. Comment on the PR or issue.
2. Open a separate issue tagged `governance` to discuss the principle.
3. If unresolved, maintainers convene and decide by majority. Decisions are recorded in the issue.

## Forking

UMDP is permissively licensed. If your organisation needs a divergent profile that the upstream community will not accept, fork freely. Contributing your changes back is encouraged but not required.
