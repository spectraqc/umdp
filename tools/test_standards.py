#!/usr/bin/env python3
"""Tests for the standard constraint sets (SQC-1953).

Run with:  python tools/test_standards.py

The point of schema/standards/*.json is that one definition drives several
consumers, so a silent regression here doesn't just mis-report — it stops
constraining, everywhere, without anything going red. These cases pin the
behaviour that is easy to break and hard to notice: the directional rules, the
content-class split between R 128 and R 128 s1, and the three legal ways for a
profile to say nothing at all.

Uses stdlib unittest only (jsonschema is already a dependency of validate.py).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate import (  # noqa: E402
    check_standard_conformance,
    check_standards_definitions,
    load_standards,
    resolve_standard,
)

STANDARDS = load_standards()


def profile(*, content_type=None, standards=None, true_peak=None,
            short_term=None) -> dict:
    """A profile stub carrying only the loudness block under test."""
    loudness: dict = {}
    if standards is not None:
        loudness["standards"] = standards
    if true_peak is not None:
        loudness["true_peak_max"] = true_peak
    if short_term is not None:
        loudness["short_term_max"] = short_term
    data: dict = {"assets": {"audio": {"loudness": loudness}}}
    if content_type is not None:
        data["content_type"] = content_type
    return data


class DefinitionsAreWellFormed(unittest.TestCase):
    def test_repo_definitions_pass_their_own_meta_schema(self):
        self.assertEqual(check_standards_definitions(STANDARDS), [])

    def test_the_standards_this_ticket_defines_are_present(self):
        ids = {s["id"] for s in STANDARDS}
        self.assertLessEqual({"ebu-r128", "ebu-r128-s1", "atsc-a85", "itu-r-bs1770"}, ids)


class NameResolution(unittest.TestCase):
    def test_spacing_and_case_do_not_change_the_match(self):
        for spelling in ("EBU R 128", "EBU R128", "ebu r128", "R128"):
            with self.subTest(spelling=spelling):
                self.assertEqual(resolve_standard(spelling, STANDARDS)["id"], "ebu-r128")

    def test_an_undefined_name_resolves_to_nothing(self):
        self.assertIsNone(resolve_standard("Acme House Loudness v2", STANDARDS))

    def test_short_form_content_is_governed_by_the_supplement(self):
        # R 128 recommends (q) sends adverts and promos to R 128 s1, whose envelope
        # is genuinely different — so naming "EBU R128" on a commercial resolves there.
        self.assertEqual(resolve_standard("EBU R128", STANDARDS, "commercial")["id"], "ebu-r128-s1")
        self.assertEqual(resolve_standard("EBU R128", STANDARDS, "program")["id"], "ebu-r128")

    def test_a_standard_with_no_content_class_governs_all_of_them(self):
        for content_type in ("program", "commercial"):
            with self.subTest(content_type=content_type):
                self.assertEqual(
                    resolve_standard("ATSC A/85", STANDARDS, content_type)["id"], "atsc-a85",
                )


class LockedFields(unittest.TestCase):
    def test_the_defining_constant_may_not_be_changed(self):
        notes = check_standard_conformance(
            profile(content_type="program", standards=[{"name": "EBU R128", "target": -20.0}]),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("-23.0", notes[0])
        self.assertIn("variant", notes[0])

    def test_the_defining_constant_itself_is_silent(self):
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program", standards=[{"name": "EBU R128", "target": -23.0}]),
                STANDARDS,
            ),
            [],
        )


class BoundedFieldsAreDirectional(unittest.TestCase):
    def test_looser_than_the_bound_is_reported(self):
        notes = check_standard_conformance(
            profile(content_type="program",
                    standards=[{"name": "EBU R128", "target": -23.0, "tolerance": 2.0}]),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("looser", notes[0])

    def test_stricter_than_the_bound_is_silent(self):
        # RAI at ±0.2 and France TV at -3.0 dBTP are house limits INSIDE the
        # standard. A flat lock would make them unstateable — which is the whole
        # reason the rules are directional rather than equality checks.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program",
                        standards=[{"name": "EBU R128", "target": -23.0, "tolerance": 0.2}],
                        true_peak=-3.0),
                STANDARDS,
            ),
            [],
        )

    def test_a_true_peak_ceiling_above_the_standards_is_reported(self):
        notes = check_standard_conformance(
            profile(content_type="program", standards=[{"name": "EBU R128"}], true_peak=0.0),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("looser", notes[0])

    def test_a_short_term_ceiling_above_the_supplements_is_reported(self):
        # SQC-2029 — s1 recommends (d) caps Short-term Loudness at -18.0 LUFS.
        notes = check_standard_conformance(
            profile(content_type="commercial", standards=[{"name": "EBU R128"}],
                    short_term=-16.0),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("looser", notes[0])

    def test_a_stricter_short_term_ceiling_is_silent(self):
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="commercial", standards=[{"name": "EBU R128"}],
                        short_term=-20.0),
                STANDARDS,
            ),
            [],
        )

    def test_plain_r128_sets_no_short_term_ceiling_to_measure_against(self):
        # A programme profile may state one; it is that broadcaster's house
        # limit, and R 128 has nothing to say about it either way. Silence here
        # is the correct answer, not a missing check.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program", standards=[{"name": "EBU R128"}],
                        short_term=-16.0),
                STANDARDS,
            ),
            [],
        )

    def test_the_short_form_tolerance_is_tighter_than_the_programme_one(self):
        # ±1.0 LU is R 128's live-programme exception; R 128 s1 carries no
        # equivalent, so the same value is conformant on a programme and looser
        # than the standard on a commercial.
        spec = [{"name": "EBU R128", "target": -23.0, "tolerance": 1.0}]
        self.assertEqual(
            check_standard_conformance(profile(content_type="program", standards=spec), STANDARDS), [],
        )
        notes = check_standard_conformance(
            profile(content_type="commercial", standards=spec), STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("0.2", notes[0])


class AbsenceIsLegal(unittest.TestCase):
    def test_an_omitted_field_is_not_a_deviation(self):
        # clearcast_commercials states no tolerance and rte_hd no true peak.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="commercial", standards=[{"name": "EBU R128", "target": -23.0}]),
                STANDARDS,
            ),
            [],
        )

    def test_an_explicit_null_is_not_a_deviation(self):
        # nrk_hd writes tolerance: null — "the source states none", not zero.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program",
                        standards=[{"name": "EBU R128", "target": -23.0, "tolerance": None}]),
                STANDARDS,
            ),
            [],
        )


class NotApplicableFields(unittest.TestCase):
    def test_an_lra_ceiling_on_short_form_contradicts_the_standard(self):
        notes = check_standard_conformance(
            profile(content_type="commercial",
                    standards=[{"name": "EBU R128", "target": -23.0, "lra_max": 20}]),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("no value should be given", notes[0])

    def test_the_same_ceiling_on_a_programme_is_fine(self):
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program",
                        standards=[{"name": "EBU R128", "target": -23.0, "lra_max": 20}]),
                STANDARDS,
            ),
            [],
        )


class MultipleJurisdictions(unittest.TestCase):
    def test_each_named_standard_constrains_only_its_own_element(self):
        # A profile may name several jurisdictional standards; -23.0 is R 128's
        # constant and wrong for A/85, and vice versa, so anchoring the check on
        # the array element rather than the array is what keeps both quiet.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program", standards=[
                    {"name": "EBU R128", "target": -23.0, "jurisdiction": "EU"},
                    {"name": "ATSC A/85", "target": -24.0, "jurisdiction": "US"},
                ], true_peak=-2.0),
                STANDARDS,
            ),
            [],
        )

    def test_a_shared_true_peak_is_measured_against_every_named_standard(self):
        # -1.0 dBTP satisfies R 128 and is looser than A/85's -2.0; claiming both
        # means the profile is not A/85-conformant on peak, and should hear so.
        notes = check_standard_conformance(
            profile(content_type="program", standards=[
                {"name": "EBU R128", "target": -23.0},
                {"name": "ATSC A/85", "target": -24.0},
            ], true_peak=-1.0),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("ATSC A/85", notes[0])


class MeasurementStandards(unittest.TestCase):
    def test_bs1770_constrains_nothing(self):
        # BS.1770 specifies how to measure and states no target at all, so a spec
        # naming it alongside its own numbers is making its own claim, correctly.
        self.assertEqual(
            check_standard_conformance(
                profile(content_type="program",
                        standards=[{"name": "ITU-R BS.1770-3", "target": -27.0, "tolerance": 2.0}],
                        true_peak=-2.0),
                STANDARDS,
            ),
            [],
        )


class UndefinedStandards(unittest.TestCase):
    def test_an_unknown_name_is_reported_as_uncheckable(self):
        notes = check_standard_conformance(
            profile(content_type="program",
                    standards=[{"name": "Acme House Loudness", "target": -19.0}]),
            STANDARDS,
        )
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("not a defined standard", notes[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
