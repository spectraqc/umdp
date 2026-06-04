# Changelog

All notable changes to the UMDP schema are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [0.9.0] — Test-signal conformance (`test_signal`)

### Added

- Top-level `test_signal` object: conformance requirements for the test-signal regions that `segmentation` (0.8.0) types. Region typing selects *which* checks run over a bars & tone / slate / clock region; `test_signal` says what those checks *require* there — so a test signal is checked as a test signal, never silently skipped.
  - `test_signal.bars` — `type` (bar pattern, e.g. `ebu_100`, `smpte_rp219_75`), `duration_s`, `duration_tolerance_s`.
  - `test_signal.tone` — line-up tone `level_dbfs` (e.g. -18 EBU / -20 SMPTE), `level_tolerance_db`, `frequency_hz` (e.g. 1000), `channels` (1-based routing).
  - `test_signal.slate` — `duration_s`, `duration_tolerance_s`.
  - `test_signal.clock` — `countdown_required`, `duration_s`, `duration_tolerance_s`.
- Example profile `profiles/dpp_imf.json` extended with a `test_signal` block (EBU 100% bars + -18 dBFS / 1 kHz line-up tone).
- `docs/field-reference.md`: `test_signal` documented.

### Notes

- Backwards compatible — `test_signal` and every sub-field is optional. A test-signal region with no `test_signal` block is checked only for presence. All existing profiles validate unchanged.

## [0.8.0] — Region-typed check routing (`segmentation`)

### Added

- Top-level `segmentation` object for region-typed check routing. Lets a spec declare that test-signal regions (bars & tone, slate/clock) are checked against the conformance set the spec mandates *there*, instead of against programme-content artefact tests that false-alarm on a static test signal.
  - `segmentation.source` — how region boundaries are found: `cpl_markers` (authoritative IMF CPL markers, SMPTE ST 2067-3), `heuristic` (best-effort content detection gated by `min_confidence`), or `none` (single programme region).
  - `segmentation.min_confidence` — `[0,1]` floor for `heuristic`; below it a detected region is treated as `unknown` and the full check set runs (fail-safe).
  - `segmentation.markers_conformance_bearing` — when `true`, a marker that disagrees with the essence raises a conformance FAIL (the spec mandated accurate markers, e.g. DPP IMF) in addition to falling back to run-everything; when `false`/absent, a disagreement is WARN/INFO at most.
  - `segmentation.region_checks` — per-region-type mandated check sets (region types `programme`, `bars_and_tone`, `slate_clock`, `black`, `unknown`). A check not listed for a region is legitimately not required there; a check that **is** listed can never be suppressed by routing — a spec can never be violated.
- Example profile `profiles/dpp_imf.json` demonstrating `cpl_markers` + `markers_conformance_bearing: true` + per-region mandated sets.
- `docs/field-reference.md`: `segmentation` documented under top-level sections and key sub-sections.

### Notes

- Backwards compatible — `segmentation` is optional and every sub-field is optional. Profiles without it are treated as a single `programme` region with the full check set, matching pre-0.8.0 behaviour. All existing profiles validate unchanged.

## [0.7.2] — `content_type` closed enum

### Added

- Top-level `content_type` field with a closed enum: `program`, `commercial`, `promo`, `trailer`, `interstitial`, `music_video`. Drives per-content-type QC rules (loudness regime, caption requirements, PSE applicability, structure, peak limits).
- News and sports deliberately excluded — pre-delivery QC of finished files of either is equivalent to `program`; the meaningful differences are all live-workflow concerns and live workflows are out of scope for UMDP.
- Sub-genres of long-form (feature vs. episode vs. documentary) not modelled here — same delivery spec, belongs in separate metadata.
- Aspect-ratio variants and technical artefact deliverables (slates, bars, test patterns) explicitly out of scope.
- Example profiles updated: `clearcast_commercials` (`commercial`); `rte_hd`, `svt_hd`, `tg4_hd` (`program`). `rtl_smallitems_hd` left unmarked since the spec spans commercials/promos/trailers.

### Notes

- Backwards compatible — `content_type` is optional. Profiles without it remain valid.
- American English (`program`) for the token; British spelling free in human-facing prose.

## [0.7.1] — Provenance fields

### Added

- `governance.sourceSpec` — direct URL to the source delivery specification the profile was encoded from. Optional in 0.7.1; intended to become required at 1.0 once the back-catalogue is populated.
- `governance.sourceAccess` — access category of `sourceSpec`. Enum: `public` (openly published), `portal-login` (behind a free login), `contracted` (available only under a production agreement), `unknown` (legacy profile encoded before this rule existed). Optional in 0.7.1.
- Example profiles updated with the new fields where known: `clearcast_commercials` (`portal-login`), `rte_hd` (`contracted`), `rtl_smallitems_hd` (`public` + URL).

### Notes

- Backwards compatible — existing profiles without the new fields continue to validate.
- See the UMDP legal & contribution policy for the rationale behind the new fields.

## [0.7.0] — Initial public release

First public release of UMDP as a standalone project.

### Added

- `assets.video.gop` — GOP structure constraints (`closed_required`, `max_length`). Promoted from a v7 schema gap to a first-class field.
- `assets.video.timecode` — Embedded timecode track requirements (`ltc_required`, `vitc_required`). Promoted from a v7 schema gap to a first-class field.
- `structure.timeline.timecode_start` — Required start timecode (e.g. `10:00:00:00`). Was present in the v7 type stub but documented as missing from most encoded specs; now first-class with a SMPTE timecode pattern.
- Draft 2020-12 JSON Schema replacing the v7 type-stub document.
- `tools/validate.py` — CLI validator for profiles.
- CI workflow validating every profile on every PR.
- Three seed profiles: `svt_hd` (Sweden), `rte_hd` (Ireland), `tg4_hd` (Ireland).

### Changed

- Numeric "constraint" fields where `null` means "not enforced" (`loudness.true_peak_max`, `safe_area.*_percent`, `preclearance.lead_time_days`, signal-limit min/max, loudness target/tolerance) now formally accept `null` in addition to a number.
- `delivery_paradigm` is an open-string field with documented examples rather than a closed enum, to admit `imf` and `dcp` without breaking existing profiles.

### Notes

- Every UMDP object is `additionalProperties: true`. Vendor extensions are valid; widely-used extensions are candidates for promotion in 0.8.x.
