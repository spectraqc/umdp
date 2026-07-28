# Changelog

All notable changes to the UMDP schema are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/) and the project adheres to [Semantic Versioning](https://semver.org/).

## [0.14.0] — Per-field verification

### Added

- `governance.verification` — a **computed** roll-up of how much of this profile has actually been checked against its cited source: `status` (`unverified` / `partial` / `verified`), `assertions`, `verified_fields`, `unsourced_fields`, `verified_at`.
- `provenance/<id>.json` — optional per-field provenance sidecar. One record per value-bearing leaf field: the source document, where in it the value was found, the method (`human` / `model` / `literal`), and who confirmed it.
- `tools/validate.py`: recomputes `governance.verification` from the sidecar and **fails** if a profile's block disagrees with it. The roll-up cannot be hand-authored or inflated.
- `tools/validate.py` (SQC-1947): a value-bearing assertion with **no** provenance record at all now **fails** validation outright, not just an overstated `governance.verification`. Omitting a field stays legal; asserting one with nothing behind it does not. This is deliberately unconditional — CI is red on every one of the 16 shipped profiles until SQC-1946 backfills the remaining unsourced fields, rather than letting the debt this audit found sit invisible again.

### Why

An audit of the profile set found **601 of 936 value-bearing assertions could not be traced to their cited source at all** — 427 of them in eight profiles whose source document is not held anywhere. `governance.sourceSpec` vouches per *profile*, so a single URL stood behind 63–88 leaf fields that the document may state a dozen of, and nothing distinguished an asserted value from a sourced one.

A profile is a specification, not a recommendation. A value one digit out fails real deliveries: two timecode errors found this way were `bars_start` off by 90 seconds and `black_start` off by two frames. Consumers need to know which values were actually checked, and by what.

### Notes

- `verified` requires **human** records. Literal matching and model checking produce candidates for review, never verification — a machine agreeing with a value it was shown is not evidence the value is right.
- Omitting a field remains legal and is often the correct fix: UMDP models absence, so deleting an unsupportable assertion is a correction, not a loss.
- Downstream mirrors of the schema must be re-synced (SpectraQC `frontend/lib/umdp.schema.json`; its drift guard will fail CI otherwise).

## [0.13.0] — Canonical channel-layout & broadcast-system vocabulary

### Added

- `schema/enums/layouts.json` — recommended audio channel-layout identifiers for `assets.audio.layout.allowed_layouts`. Each token is a hyphenated channel list in EBU R123 / SMPTE broadcast order (L, R, C, LFE, Ls, Rs): `L-R` (stereo), `L-R-C-LFE-Ls-Rs` (discrete 5.1), `M1-M2` (dual mono).
- `schema/enums/broadcast-systems.json` — recommended broadcast-system / raster identifiers for `assets.video.signal.broadcast_system`, form `<lines><i|p>/<frame rate>` (e.g. `1080i/25`). Prefer this raster form over legacy analogue colour-system labels (PAL/SECAM/NTSC), which do not describe an HD/UHD signal.
- `assets.video.signal.notes` — optional free-text note on the signal object (matches the `notes` already on sibling value objects such as `bit_depth` and `gop`). Carries qualifications like ZDF's "1080p/25 also accepted."
- `tools/validate.py`: the controlled-vocabulary advisory (SQC-1490) now also covers `assets.audio.layout.allowed_layouts` and `assets.video.signal.broadcast_system`, `note`-ing any off-vocabulary token. Advisory only — never fails CI.

### Changed

- Normalised the layout vocabulary across the corpus: `5.1` (8 profiles) and the wrong-case `L-R-C-LFE-LS-RS` (3 profiles) → `L-R-C-LFE-Ls-Rs`; `Dual Mono` → `M1-M2`. `L-R` unchanged.
- Normalised `broadcast_system`: `PAL/EBU` → `1080i/25` (rtl_smallitems); `1080i/25 or 1080p/25` → `1080i/25` + signal note (zdf).

### Notes

- Layouts and `broadcast_system` remain free strings in the schema (adopters may extend); the vocabulary is advisory, mirroring codec/container. The live QC engine does not gate on either field — this is data-hygiene for clean cross-vendor profile diffs. Corpus now emits zero vocabulary notes.

## [0.12.0] — Subtitle/caption reading-speed & cue constraints (`assets.timed_text.constraints`)

### Added

- `assets.timed_text.constraints` now documents the subtitle/caption checks the QC engine already enforces (previously passing only via `additionalProperties: true`):
  - `max_chars_per_second` — maximum reading speed in characters per second. The engine measures cps as the cue's literal character count (lines stripped, joined by a single space) over the cue's on-screen duration, and fails a cue above this bound (e.g. `paramount_mez` uses 18). This is the **canonical** reading-speed field.
  - `max_cue_duration_s` — maximum on-screen duration of a single cue in seconds; a cue held longer fails.
  - `extended_chars_forbidden` — when `true`, text outside the delivery's permitted character set fails the check.
- `assets.audio.loudness.standards[].lra_max` — optional loudness-range ceiling (LU) per standard (e.g. EBU R128 ≈ 20), so the spec editor can carry the LRA constraint. Documented but not yet bound to a QC check — enforcement tracked separately (like `max_offset_ms`).

### Changed

- `reading_speed_cps` is now documented as a **legacy alias** of `max_chars_per_second` (the same characters-per-second measurement). The engine dual-reads it but prefers `max_chars_per_second`; author new profiles with `max_chars_per_second`.

### Notes

- Backwards compatible — every field is optional and `assets.timed_text.constraints` remains `additionalProperties: true`. Existing profiles (including any using `reading_speed_cps`) validate unchanged.
- Reconciles the canonical schema with the SpectraQC engine and spec editor, which had diverged: these three fields existed downstream (SQC-455/SQC-1297) but were never upstreamed. Brought current via SQC-1500.

## [0.11.0] — Closed value objects (`additionalProperties: false` on measurement blocks)

### Changed

- **Tightened validation on value/measurement objects.** The objects that carry measurement thresholds are now `additionalProperties: false`, so a key that isn't documented on one of them **fails** validation instead of passing silently — near-miss names (e.g. `av_sync_max_ms` vs `max_offset_ms`, SQC-1395) can no longer disable a constraint unnoticed. Locked objects: `assets.audio.sync`, `assets.audio.loudness` (+ `standards[]`), `assets.audio.bit_depth`, `assets.audio.track_count`, `constraints.video.signal_limits` (+ the `signal_limit` shape behind `luminance`/`rgb`), `constraints.timing.duration`, `assets.video.{resolution,aspect_ratio,frame_rate,bit_depth,signal,gop,timecode,safe_area}`, `assets.video.color.hdr`, and `test_signal.{bars,tone,slate,clock}`.
- Added an optional `notes` (string) to `assets.video.aspect_ratio` so it locks consistently with the other video value objects.

### Migrated

- `profiles/rte_hd.json`: `assets.audio.sync.av_sync_max_ms: 5` → `max_offset_ms: 5` (the documented field; matches `tg4_hd`). Enforcement of the offset is tracked in SQC-1397.

### Notes

- **Container** objects (`assets`, `constraints`, `packaging`, the asset roots, …) remain `additionalProperties: true` — vendors can still add extension fields without forking, and `tools/validate.py` reports those as advisory `note`s. Extensibility is unchanged where it was intended.
- This tightens validation on the locked objects (a profile that set an undocumented key on one of them would now fail). Scoped deliberately to value objects; shipped as a pre-1.0 minor rather than the full `1.0.0` strict-everywhere reversal. All bundled profiles validate.

## [0.10.0] — Documented A/V-sync drift thresholds (`assets.audio.sync`)

### Added

- `assets.audio.sync` now documents the A/V-sync **drift** thresholds that QC engines already enforce, which were previously undocumented (passing only via `additionalProperties: true`):
  - `max_drift_ms` — maximum tolerated progressive A/V sync drift in milliseconds before the A/V-sync-drift check fails (typically 40 ms). The primary, engine-bound sync threshold.
  - `max_drift_ms_per_min` — optional bound on the *rate* of progressive drift (ms per minute).
  - `max_drift_ms_hard_fail_above` — optional hard-fail boundary; drift between `max_drift_ms` and this value warns, above it errors (defaults to `max_drift_ms * 2`).
- `docs/field-reference.md`: `assets.audio.sync` now distinguishes drift from offset.
- `tools/validate.py`: an **advisory** (non-failing) report of profile keys not documented in the schema, so near-miss key names (e.g. `max_drift_ms` vs `max_offset_ms`) surface in review instead of passing silently under `additionalProperties: true`.

### Notes

- Backwards compatible — all `sync` fields are optional; existing profiles validate unchanged.
- `max_offset_ms` (fixed lip-sync offset) is a *distinct* measurement from drift and remains documented, but no QC check binds it yet — its enforcement is tracked as an open gap in `docs/gaps.md`.

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
