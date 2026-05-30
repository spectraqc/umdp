# Contributing to UMDP

Thanks for your interest. UMDP grows by community contribution — broadcasters, studios, distributors, post houses, and QC vendors all have specs worth encoding and gaps worth filling.

## Three kinds of contribution

### 1. Add a profile

The easiest way to help. If your organisation publishes a delivery spec, encode it as a UMDP profile.

1. Fork this repo.
2. Create `profiles/<brand>_<subbrand>_<region>_<format>.json`. See the [naming convention](README.md#profile-naming-convention).
3. Encode against the schema. Use existing profiles in `profiles/` as templates.
4. Cite the source spec (PDF version, effective date, URL) in `governance.source`.
5. Run `python tools/validate.py profiles/your_profile.json` and confirm it passes.
6. Open a PR. CI will re-validate.

UMDP encodes the **facts** of a delivery spec (codec lists, loudness targets, timecode rules), not the source document's wording. Profiles can be derived from public, portal-login, *or* contracted source documents — see `governance.sourceAccess` in the schema — but every profile must follow the original-wording rule and the contributor attestations below.

### 2. Propose a schema field

If your spec needs a field UMDP does not have:

1. Open an issue using the **Schema change proposal** template before opening a PR.
2. Explain: which delivery spec needs it, what concept it captures, why existing fields can't represent it, what type/shape you propose.
3. After discussion, open a PR that updates `schema/umdp.schema.json`, adds an example to `docs/`, and bumps `CHANGELOG.md`.

### 3. Correct an existing profile

Profiles drift as broadcasters publish updates. If you find an inaccuracy:

1. Open an issue or PR with the diff.
2. Cite the authoritative source document and section.
3. Update `governance.spec_version` and `governance.effective_date` if the change reflects a new published version of the spec.

## Pull request rules

- Every PR runs `tools/validate.py` in CI. PRs that fail validation cannot be merged.
- Every schema change must include a `CHANGELOG.md` entry and a worked example in `docs/` or `examples/`.
- Every new profile must include `governance.source` and `governance.spec_version`.
- Keep PRs small. One new profile per PR. One schema field per PR.

## Style

- JSON files: 2-space indent, sorted keys are not required but preferred.
- Field names: snake_case.
- Comments live in `notes` fields inside the JSON, not in code comments. JSON does not support comments.
- Use `null` (not `0` or `-1`) to mean "not enforced" for numeric fields.

## Review

Schema changes are reviewed by the maintainers per [GOVERNANCE.md](GOVERNANCE.md). Profile additions are typically merged within a few days if CI passes and the source is cited.

---

## What you're attesting to

When you open a PR adding or correcting a profile, you are attesting that:

1. **The contribution encodes facts, not text.** The spec's actual wording, layout, tables, and prose remain copyright of the issuing organisation. You have re-expressed the technical *facts* (codec names, numeric thresholds, enum values, free-form notes you authored) in UMDP's structure.
2. **You have legitimate access to the source.** You obtained the source spec through a route the issuing organisation permits — public publication, a free portal login you signed up for, or a contracted production agreement you are a party to. You are not encoding a profile derived from leaked, scraped, or third-party-circulated copies of a spec you don't have your own access to.
3. **You have the right to share these facts.** Your relationship with the spec's issuing organisation does not contractually prohibit you from disclosing the encoded facts. If you're on an NDA that names the *spec document* but the *facts* are publicly knowable (e.g. the EBU R128 loudness target), encoding the facts is fine; if your NDA forbids disclosing the technical requirements themselves, do not encode them here.
4. **You are not encoding a profile that has been requested for takedown.** Before opening the PR, check the takedown register linked in the README. If the issuing organisation has requested removal, do not re-submit.
5. **You will respect corrections from the issuing organisation.** If the issuing organisation reaches the maintainers with corrections to a profile they originate, those corrections take priority over community edits.

By including a [DCO sign-off](#sign-off) on your commits, you certify each of the above.

## Original wording rule

Encode the spec's **values**, not its **prose**. Specifically:

- ✅ Field values copied verbatim where the value *is* the value (numeric thresholds, codec names, enum members, ISO codes, well-known acronyms like "EBU R128").
- ✅ Your own concise summary of a rule in a `notes` field — paraphrased, not quoted.
- ❌ Verbatim sentences, paragraphs, tables, or section headings from the source document copied into `notes`, `description`, or `summary` fields.
- ❌ The source document's prose rewritten with minor edits ("near-quotes") — substantially identical text in a different order still violates the rule.

A useful heuristic: if your `notes` reads like a summary you'd write to a colleague rather than text lifted from a PDF, you're in the right zone.

## Sign-off

Every commit must carry a [DCO](https://developercertificate.org/) sign-off:

```
Signed-off-by: Random J Developer <random@developer.example.org>
```

`git commit -s` adds this automatically. The sign-off certifies that you have the right to submit the contribution under the project's licence (CC BY 4.0 for spec content, MIT for tooling) and that you agree to the attestations above.

PRs without sign-off on every commit will be asked to amend before merge.

## Takedown

UMDP maintains a process for issuing organisations to request that a profile they originate be removed or that they take authoritative maintainership. See the [Takedown contact](README.md#takedown-contact) section of the README.

Contributors are asked to:

- Check the takedown register (linked from the README) before encoding a profile for any organisation.
- Not re-submit profiles that have been removed in response to a takedown request, unless the issuing organisation later re-authorises encoding.
- Forward any direct takedown communication you receive to the maintainers, rather than acting on it unilaterally.
