#!/usr/bin/env python3
"""Tests for the bulk field-setter (SQC-1975).

Run with:  python tools/test_bulk_set.py

This tool writes to profiles/ AND provenance/ AND the derived
governance.verification block. The failure that matters is not a crash — it is
a silent one: a bulk edit that lands a value while quietly leaving no provenance
record (which fails validation, SQC-1947), or leaving a stale assertion count
(which also fails, since the roll-up is computed not authored), or — worst —
writing a record that counts toward `verified` for a value nobody checked
against a source. These pin all three.

Uses stdlib unittest only.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bulk_set  # noqa: E402
from validate import compute_verification, _leaf_assertions  # noqa: E402


class Args:
    """Stand-in for the argparse namespace apply_to_profile reads."""
    def __init__(self, **kw):
        self.state = bulk_set.DEFAULT_STATE
        self.method = bulk_set.DEFAULT_METHOD
        self.source = None
        self.note = None
        self.verified_at = None
        self.dry_run = True
        for k, v in kw.items():
            setattr(self, k, v)


class PathParsing(unittest.TestCase):
    def test_plain_and_indexed(self):
        self.assertEqual(bulk_set.parse_path("a.b.c"), ["a", "b", "c"])
        self.assertEqual(bulk_set.parse_path("a.b[0].c"), ["a", "b", 0, "c"])
        self.assertEqual(bulk_set.parse_path("a[2]"), ["a", 2])

    def test_rejects_malformed(self):
        for bad in ("a..b", "a[x]", ""):
            with self.assertRaises(ValueError, msg=bad):
                bulk_set.parse_path(bad)

    def test_get_reports_missing_rather_than_raising(self):
        obj = {"a": {"b": [1]}}
        self.assertIs(bulk_set.get_path(obj, ["a", "nope"]), bulk_set._MISS)
        self.assertIs(bulk_set.get_path(obj, ["a", "b", 5]), bulk_set._MISS)
        self.assertEqual(bulk_set.get_path(obj, ["a", "b", 0]), 1)

    def test_creates_intermediate_dicts(self):
        obj = {}
        bulk_set.set_path(obj, ["assets", "video", "signal", "field_order"], ["tff"])
        self.assertEqual(obj["assets"]["video"]["signal"]["field_order"], ["tff"])

    def test_refuses_to_invent_list_elements(self):
        # A profile's arrays are authored, not sparse — silently growing one
        # would fabricate a value nobody wrote.
        with self.assertRaises(KeyError):
            bulk_set.set_path({}, ["a", 0, "b"], 1)
        with self.assertRaises(KeyError):
            bulk_set.set_path({"a": []}, ["a", 3], 1)

    def test_refuses_to_descend_into_a_scalar(self):
        with self.assertRaises(KeyError):
            bulk_set.set_path({"a": 5}, ["a", "b"], 1)


def _profile(**over):
    base = {
        "id": "t", "name": "T", "delivery_paradigm": "file",
        "governance": {"jurisdiction": ["SE"]},
        "assets": {"video": {"codec": {"allowed": ["avc_intra_100"]}}},
    }
    base.update(over)
    return base


class ProvenanceSemantics(unittest.TestCase):
    """The part that must never quietly go wrong."""

    def setUp(self):
        self.tmp = Path(bulk_set.PROFILES_DIR).parent / ".bulk_set_test_tmp"

    def test_default_record_cannot_count_toward_verified(self):
        # `verified` needs state='stated' AND method='human'. The defaults are
        # deliberately neither, so a bulk edit can never inflate a profile.
        data = _profile()
        recs = {p: {"state": bulk_set.DEFAULT_STATE, "method": bulk_set.DEFAULT_METHOD}
                for p, _v in _leaf_assertions(data)}
        v = compute_verification(data, recs)
        self.assertEqual(v["status"], "unverified")
        self.assertEqual(v["verified_fields"], 0)
        # …but every assertion IS recorded, so SQC-1947 is satisfied.
        self.assertEqual(v["unsourced_fields"], 0)

    def test_default_method_is_not_a_human_method(self):
        from validate import HUMAN_METHODS
        self.assertNotIn(bulk_set.DEFAULT_METHOD, HUMAN_METHODS)

    def test_human_stated_without_source_is_refused(self):
        # The one combination that inflates verification requires a real source.
        with self.assertRaises(SystemExit):
            bulk_set.main(["--profile", "svt_hd", "--set", 'a.b=1',
                           "--method", "human", "--state", "stated", "--dry-run"])
        with self.assertRaises(SystemExit):
            bulk_set.main(["--profile", "svt_hd", "--set", 'a.b=1',
                           "--method", "human", "--state", "stated",
                           "--source", "n/a", "--dry-run"])


class ApplyToProfile(unittest.TestCase):
    """Exercised against a real profile file, always with dry_run=True."""

    PROFILE = bulk_set.PROFILES_DIR / "svt_hd.json"

    def setUp(self):
        if not self.PROFILE.exists():
            self.skipTest("svt_hd.json not present")
        self.original = self.PROFILE.read_text()

    def tearDown(self):
        # Nothing should have been written, but prove it rather than assume.
        self.assertEqual(self.PROFILE.read_text(), self.original,
                         "dry run wrote to disk")

    def test_dry_run_writes_nothing(self):
        bulk_set.apply_to_profile(
            self.PROFILE, [("assets.video.signal.field_order", ["tff"])], Args())
        # tearDown asserts the file is untouched.

    def test_setting_a_new_field_creates_a_record_and_bumps_assertions(self):
        before = json.loads(self.original)
        n_before = len(list(_leaf_assertions(before)))
        r = bulk_set.apply_to_profile(
            self.PROFILE, [("assets.video.signal.field_order", ["tff"])], Args())
        if not r["changed"]:
            self.skipTest("svt_hd already declares field_order")
        self.assertEqual(r["new_records"], 1)
        self.assertEqual(r["verification"]["assertions"], n_before + 1)
        self.assertEqual(r["verification"]["unsourced_fields"], 0)

    def test_idempotent(self):
        existing = json.loads(self.original)
        codec = existing["assets"]["video"]["codec"]["allowed"]
        r = bulk_set.apply_to_profile(
            self.PROFILE, [("assets.video.codec.allowed", codec)], Args())
        self.assertEqual(r["changed"], [])
        self.assertEqual(r["new_records"], 0)
        self.assertTrue(any("already set" in why for _p, why in r["skipped"]))

    def test_a_boolean_needs_no_provenance_record(self):
        # _leaf_assertions excludes booleans as authoring judgements, so the
        # gate never asks for a record — and neither must this tool invent one,
        # or the sidecar fills with entries validate.py will never look at.
        r = bulk_set.apply_to_profile(
            self.PROFILE, [("assets.video.gop.closed_required", True)], Args())
        self.assertEqual(r["new_records"], 0)


class Selection(unittest.TestCase):
    def test_jurisdiction_selects_by_governance(self):
        picked = bulk_set.select_profiles(
            Args(profile=None, jurisdiction="SE,NO", all=False))
        stems = {p.stem for p in picked}
        self.assertIn("svt_hd", stems)
        self.assertIn("nrk_hd", stems)
        self.assertNotIn("rte_hd", stems)

    def test_jurisdiction_is_case_insensitive(self):
        a = bulk_set.select_profiles(Args(profile=None, jurisdiction="se", all=False))
        b = bulk_set.select_profiles(Args(profile=None, jurisdiction="SE", all=False))
        self.assertEqual({p.stem for p in a}, {p.stem for p in b})
        self.assertTrue(a, "expected at least one SE profile")

    def test_unknown_profile_id_is_an_error_not_a_silent_noop(self):
        with self.assertRaises(SystemExit):
            bulk_set.select_profiles(
                Args(profile="no_such_profile", jurisdiction=None, all=False))

    def test_no_match_selects_nothing(self):
        self.assertEqual(
            bulk_set.select_profiles(Args(profile=None, jurisdiction="ZZ", all=False)), [])


class AuthorityAuthored(unittest.TestCase):
    def test_verification_is_left_alone(self):
        # SQC-1949 — a distinct claim, not a weaker one. validate.py skips the
        # provenance-derived checks entirely, so recomputing a roll-up here
        # would write a block the schema's if/then forbids.
        tmp = bulk_set.PROFILES_DIR / "_tmp_authority_test.json"
        data = _profile()
        data["governance"]["verification"] = {"status": "authority_authored"}
        tmp.write_text(json.dumps(data))
        try:
            r = bulk_set.apply_to_profile(
                tmp, [("assets.video.signal.field_order", ["tff"])], Args())
            self.assertTrue(r["authority"])
            self.assertIsNone(r["verification"])
        finally:
            tmp.unlink()


class CliParsing(unittest.TestCase):
    def test_bad_json_value_is_rejected_with_a_hint(self):
        with self.assertRaises(SystemExit):
            bulk_set.main(["--profile", "svt_hd", "--set", "a.b=tff", "--dry-run"])

    def test_set_without_equals_is_rejected(self):
        with self.assertRaises(SystemExit):
            bulk_set.main(["--profile", "svt_hd", "--set", "a.b", "--dry-run"])

    def test_selection_is_required(self):
        with self.assertRaises(SystemExit):
            bulk_set.main(["--set", "a.b=1", "--dry-run"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
