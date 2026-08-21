# Standards as constraint sets

A profile that names **EBU R 128** and sets a target of −20 LUFS is not doing EBU R 128. Nothing in UMDP could say so before this directory existed, because the meaning of "EBU R 128" lived in whatever code happened to be looking — this repo's validator held one copy as literals, SpectraQC's spec editor held a second as a preset table, and its QC engine a third as a fallback dict. Three ideas of one standard, drifting independently.

Each file here is that meaning, once, as data: what the named standard **defines**, per UMDP field, with the clause it comes from and a verbatim quote so the claim can be checked against the document rather than trusted.

| File | Standard | Governs |
|------|----------|---------|
| `ebu-r128.json` | EBU R 128 (2023, v5) | `program`, `music_video` |
| `ebu-r128-s1.json` | EBU R 128 s1 (2020) | `commercial`, `promo`, `trailer`, `interstitial` |
| `atsc-a85.json` | ATSC A/85:2013 + Cor.1 | any content type |
| `itu-r-bs1770.json` | ITU-R BS.1770-5 | measurement only — constrains nothing |
| `standard.schema.json` | — | meta-schema every file above validates against |

## The rule is directional, per field

A flat lock would be wrong, and would have looked correct. All sixteen broadcaster profiles in this repo name EBU R 128 and all sixteen sit at −23.0 LUFS — but their tolerances run 0.2, 0.5, 1.0 and absent, and their true-peak ceilings −1.0, −2.0, −3.0 and absent. Those are not violations. Lock the fields flat and a broadcaster with a stricter house limit could not state its real requirement.

So each field carries one of four rules:

- **`locked`** — the constant that *defines* the standard. R 128's −23.0 LUFS target. Change it and you are doing something R 128-derived, not R 128, so an editor must not offer the field at all.
- **`bounded`** — a limit the spec may make **stricter** but never looser. The bound present (`max` or `min`) is the loosest the standard permits. R 128 sanctions this itself for true peak: *"Permitted Maximum True Peak Levels may be lower for different distribution systems and data reduction rates."*
- **`optional`** — the standard names the field and sets no value. R 128 recommends measuring Loudness Range but states no ceiling, so any ceiling is the spec's own requirement.
- **`not_applicable`** — the standard says a value must **not** be stated. R 128 s1: *"a maximum and/or minimum value for Loudness Range shall not be specified for programmes of this length/genre."*

Absence stays legal under all four. `nrk_hd` states no tolerance and `rte_hd` no true peak; "not stated in the source" is a valid profile outcome and is never filled in with a default. Omitting a field and setting it to `null` both mean that.

## Content class is part of the envelope

R 128 recommends (q) delegates short-form content to R 128 s1, and s1's envelope really is different: ±0.2 LU where R 128 permits ±1.0 for live programmes, and an LRA that shall not be stated at all. A file may therefore declare `applies_to.content_type`, and a supplement declares `supplements` naming the standard it refines. A profile with `content_type: commercial` that names "EBU R128" is measured against s1 — which is what R 128 itself says applies to it.

This split is the difference between a tolerance being *the standard's* and being a house tightening. `rtl_smallitems_hd` sits at ±0.2 LU because that is what s1 states for short-form, not because RTL invented a stricter limit.

## Field paths

Keys under `fields` are dot-separated UMDP paths from the profile root. A `[]` marks an array whose elements are governed individually:

```
assets.audio.loudness.standards[].target   → the element that names this standard
assets.audio.loudness.true_peak_max        → the profile's single peak ceiling
```

Anchoring on the element matters: a profile may name several jurisdictional standards, and −23.0 LUFS is R 128's constant, not A/85's.

## Adding a standard

1. Read the document. Every constraint needs a `cite` precise enough to find and a `quote` verbatim from it — a value you believe but cannot quote does not go in the file. That rule is the whole of SQC-1929: the profile audit found 601 assertions that could not be traced to their cited source, and this directory is not going to start a second set.
2. Record the `edition` you read. A later edition may change a locked constant, so the edition is part of the claim.
3. Name it in `aliases` however it appears in the wild, so already-published profiles resolve. Aliases exist to recognise names, not to license loose authoring — the spec editor picks from the defined set.
4. If the standard defines a parameter UMDP has no field for, put it in `not_yet_modelled` with its citation rather than dropping it, and open a ticket for the field.
5. `python tools/test_standards.py` and `python tools/validate.py`. A malformed constraint set fails validation outright — it would otherwise silently stop constraining, which is the failure this whole mechanism exists to remove.
