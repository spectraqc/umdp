# Known gaps and proposal queue

This document tracks fields that real delivery specs need but UMDP does not yet model well, and extension fields used by individual profiles that may become first-class in a future release.

## Resolved in 0.7.0

- **GOP structure** — `assets.video.gop.{closed_required,max_length}`. Closed-GOP is mandatory at most broadcasters and was the most-failed automated check before being driven from the spec.
- **Embedded timecode tracks** — `assets.video.timecode.{ltc_required,vitc_required}`. Many MXF specs require LTC and/or VITC.
- **Start timecode** — `structure.timeline.timecode_start`. Now first-class, with a SMPTE timecode pattern (`HH:MM:SS:FF` or drop-frame `HH:MM:SS;FF`).

## Open gaps

These are areas where the schema accepts ad-hoc shapes today but would benefit from standardisation once enough profiles use a comparable structure.

### Sub-format video blocks (HD vs UHD on one spec)

Some platform specs describe HD and UHD variants in one document with different bitrates, profiles, and bit depths per resolution. A first-class shape — perhaps `assets.video.variants[]` keyed by resolution class — would normalise this.

### Dolby Vision / HDR metadata details

`assets.video.color.hdr` covers the basics (formats, metadata required, fallback required). Full Dolby Vision specs require finer detail: CM version, XML version, L1 metadata coverage. Candidate for promotion once two or more profiles use compatible shapes.

### IMF packaging detail

OTT mezzanine specs encode packaging requirements (CPL structure, frame-count constraints, virtual track counts) under a sub-block of `assets`, while UMDP models packaging at the top level. We need to decide whether IMF-specific packaging belongs at the top level alongside generic packaging, or as a sub-block under `assets`.

### Audio mastering / M&E mix detail

Mastering specifications (M&E mix structure, Atmos room minimums, downmix coefficients) are richer than what the current `assets.audio.loudness` captures. Candidate for a sibling block once we have more comparable shapes.

### Forbidden-elements taxonomy

`constraints.content.forbidden_elements` is a free-form string array. Different specs use different vocabularies (`bars_and_tone`, `color_bars`, `slate`, `slates`, `placards`, ...). A controlled vocabulary under `schema/enums/` would help diff between profiles.

## Proposal process

Open a *Schema change proposal* issue, link the spec(s) that need it, and propose a shape. See [GOVERNANCE.md](../GOVERNANCE.md).
