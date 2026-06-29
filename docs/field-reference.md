# UMDP field reference

This is a high-level guide to the major UMDP sections. The authoritative definition is `schema/umdp.schema.json`.

## Top-level sections

| Section              | Purpose |
|----------------------|---------|
| `id`, `name`         | Identifier and display name. |
| `governance`         | Spec version, effective date, authoritative source, jurisdiction. |
| `delivery_paradigm`  | Delivery model: `file`, `package`, `ad`, `cinema`, `live`, `imf`, `dcp`. Open string — new paradigms may appear. |
| `inputs`             | What may be used as a source for the delivery (no upscaling, native frame rate only, etc.). |
| `assets`             | The actual deliverable: `video`, `audio`, `timed_text`, `metadata`, `ancillary`. |
| `structure`          | How the timeline is laid out: start timecode, segments, markers. |
| `packaging`          | How assets are bundled (IMF, DCP, MXF bundle, none). |
| `variants`           | Multi-language or multi-version output requirements. |
| `constraints`        | Cross-asset and signal-level rules (signal limits, duration matching, forbidden elements). |
| `segmentation`       | Region-typed check routing: how the timeline is segmented and which checks each region type mandates (0.8.0). |
| `test_signal`        | Conformance requirements for test-signal regions — bar type, line-up tone level/frequency, durations, countdown (0.9.0). |
| `validation`         | Optional explicit rule set with severities. |
| `workflow`           | QC requirements, approval entities, preclearance. |
| `compliance`         | Regulatory bodies, deadlines, contacts. |
| `delivery`           | Transport mechanism (Aspera, S3, Adstream, etc.). |
| `exhibition`         | Where the asset will be exhibited (broadcast, OTT, cinema, mobile). |
| `security`           | Encryption and DRM. |
| `regional_overrides` | Per-region deviations from the base spec. |
| `ad_tech`            | VAST version, third-party tracking, measurement. |
| `economics`          | Cost-model factors, profit-protection rules. |

## Key sub-sections

### `assets.video`

The most heavily used block. Covers codec, container, bitrate, resolution, aspect ratio, frame rate, scan type, color, bit depth, chroma subsampling, signal (interlace/field order), GOP, embedded timecode tracks, and safe area.

Each constraint typically has the shape:
```json
"<thing>": {
  "allowed": [...],
  "disallowed": [...],
  "notes": "..."
}
```
or:
```json
"<thing>": {
  "min": ...,
  "max": ...,
  "allowed": [...]
}
```

### `assets.audio`

Codec, sample rate, bit depth, track count, language mode, channel layout, loudness standards, sync requirements.

`loudness.standards` is an array because some specs (rare) require both an integrated and a short-term measurement, or list a regional override.

`sync` carries two *different* audio-to-video measurements. **Drift** — `max_drift_ms` (with optional `max_drift_ms_per_min` and `max_drift_ms_hard_fail_above`) — is progressive desync that accumulates over the timeline, and is what the A/V-sync-drift check enforces (typically 40 ms). **Offset** — `max_offset_ms` — is a single fixed lip-sync error; it is a distinct measurement (see [gaps.md](gaps.md) for its enforcement status). `must_match_video_duration` asserts the audio runs the full programme duration.

### `constraints.video.signal_limits`

Broadcast legal-signal limits. `luminance` and `rgb` each take `min`, `max`, and `tolerance_percent`. Use `max: null` to indicate no ceiling is enforced (typical for OTT specs).

### `structure.timeline`

`timecode_start` follows SMPTE format `HH:MM:SS:FF` (or `HH:MM:SS;FF` for drop-frame). Most broadcasters use `10:00:00:00`; commercials clearance bodies often the same.

### `segmentation`

Region-typed check routing (0.8.0). Lets a spec say that test-signal regions (bars & tone, slate/clock) are checked against the conformance set the spec requires *there*, rather than against programme-content artefact tests that produce false alarms on a static test signal. Optional — a profile without `segmentation` is treated as a single `programme` region with the full check set (unchanged behaviour).

| Field | Purpose |
|-------|---------|
| `source` | How region boundaries are found: `cpl_markers` (authoritative IMF CPL markers, SMPTE ST 2067-3), `heuristic` (best-effort content detection gated by `min_confidence`), or `none` (single programme region). Absent ⇒ `none`. |
| `min_confidence` | `0–1`. For `heuristic`: the floor below which a detected region is treated as `unknown` and the full check set runs (fail-safe). |
| `markers_conformance_bearing` | `true` when the spec mandates accurate markers (e.g. DPP IMF). A marker that disagrees with the essence then raises a conformance FAIL *and* falls back to run-everything. When `false`/absent a disagreement is WARN/INFO at most. |
| `region_checks` | Map of region type → array of mandated check keys. Region types: `programme`, `bars_and_tone`, `slate_clock`, `black`, `unknown`. A check **not** listed for a region is legitimately not required there (routing may suppress it); a region type absent from the map runs the full set. **A check listed here can never be suppressed by routing — a spec can never be violated.** |

See `profiles/dpp_imf.json` for a worked example (CPL markers, conformance-bearing, with `bars_and_tone`/`slate_clock` mandated sets).

### `test_signal`

Conformance requirements for the test-signal regions `segmentation` types (0.9.0). `segmentation` decides *where* a region is and *which* checks run; `test_signal` decides what those checks *require*, so a test signal is checked as a test signal rather than skipped. Optional — absent ⇒ a test-signal region is checked only for presence.

| Field | Purpose |
|-------|---------|
| `bars.type` | Required bar pattern (e.g. `ebu_100`, `smpte_rp219_75`, `arib`). Open string — territory-specific. |
| `bars.duration_s` / `bars.duration_tolerance_s` | Expected colour-bars duration and allowed deviation. Checked against the typed region's measured length. |
| `tone.level_dbfs` / `tone.level_tolerance_db` | Line-up tone alignment level (commonly −18 EBU / −20 SMPTE) and tolerance. |
| `tone.frequency_hz` | Line-up tone frequency (commonly 1000). |
| `tone.channels` | 1-based channel indices that must carry the tone (routing); omit for all channels. |
| `slate.duration_s` / `slate.duration_tolerance_s` | Expected slate duration and tolerance. |
| `clock.countdown_required` / `clock.duration_s` / `clock.duration_tolerance_s` | Countdown leader requirement, duration, tolerance. |

## Extension fields

Every UMDP object accepts unknown properties. If you need a field UMDP does not model, add it. If it proves broadly useful, propose it as a first-class field in a future minor release.
