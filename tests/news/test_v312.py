"""Focused V3.1.2 grounded semantic classification arbitration tests.

No live API calls. These tests exercise only bounded semantic-to-canonical
mapping and deterministic arbitration. Exposure, severity, geography and
financial-impact authority are intentionally outside this patch.
"""

import unittest

from .helpers import article

from src.news.research_v3 import (
    _apply_classification,
    _classification_arbitration,
    _semantic_event_candidate,
)


def accepted_field(
    value,
    quote="Supported source evidence.",
    source_field="headline",
):

    return {
        "value": value,
        "citations": [
            {
                "field": "test",
                "quote": quote,
                "source_field": source_field,
            }
        ],
        "status": "source_grounded_candidate",
    }


def validation(**fields):

    return {
        "status": "validated_constraints",
        "accepted": {
            key: accepted_field(value)
            for key, value
            in fields.items()
        },
        "rejections": [],
        "candidate_relationships": [],
    }


def record(
    article_class="general_news",
    event_type="general_news",
    event_subtype="general_news",
):

    return {
        "classification": article_class,
        "status": article_class,

        "event": {
            "event_type": event_type,
            "event_subtype": event_subtype,
            "evidence_fields": {},
        },

        "ticker_analysis": [],

        "severity": {
            "level": "Unknown",
        },
    }


# =========================================================
# SEMANTIC → CANONICAL TAXONOMY
# =========================================================

class SemanticCanonicalMappingTests(
    unittest.TestCase
):

    def test_cpi_maps_to_macro_inflation_data(
        self
    ):

        a = article(
            "Consumer prices rose 0.4% in August.",
            headline=(
                "Consumer prices rose 0.4% in August; "
                "core inflation was higher than estimated"
            ),
        )

        accepted = validation(
            event_type="Inflation",
            event_subtype="Consumer Price Index",
            economic_channels=[
                "Inflation",
                "Consumer Prices",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "macro_monetary",

                "event_subtype":
                    "inflation_data",
            },
        )


    def test_regulatory_investigation_maps_to_enforcement(
        self
    ):

        a = article(
            (
                "The US government is investigating "
                "alleged AI chip smuggling in violation "
                "of export restrictions."
            ),
            headline=(
                "US Probes Apex Logistics Over Alleged "
                "Nvidia AI Chip Smuggling"
            ),
        )

        accepted = validation(
            event_type=
                "Regulatory and Legal",

            event_subtype=
                "Investigation",

            economic_channels=[
                "regulatory_compliance",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "trade_export_control",

                "event_subtype":
                    "regulatory_enforcement",
            },
        )


    def test_supplier_campus_maps_to_capacity_expansion(
        self
    ):

        a = article(
            (
                "TSMC opened an advanced packaging "
                "supplier campus to improve CoWoS "
                "validation."
            ),
            headline=(
                "TSMC Opens Kaohsiung Supplier Campus "
                "to Close Packaging Validation Gap"
            ),
        )

        accepted = validation(
            event_type=
                "Facility Opening",

            event_subtype=
                "Supplier Campus",

            economic_channels=[
                "Semiconductor Supply Chain",
                "Advanced Packaging",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "supply_chain",

                "event_subtype":
                    "capacity_expansion",
            },
        )


    def test_packaging_allocation_maps_to_capacity_constraint(
        self
    ):

        a = article(
            (
                "Microsoft is competing for limited "
                "CoWoS advanced packaging capacity."
            ),
            headline=(
                "Microsoft Maia 300 Seeks TSMC Units; "
                "Nvidia Controls Packaging Queue"
            ),
        )

        accepted = validation(
            event_type=
                "supply_chain_constraint",

            event_subtype=
                "packaging_allocation",

            economic_channels=[
                "advanced_packaging_capacity",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "supply_chain",

                "event_subtype":
                    "capacity_constraint",
            },
        )


    def test_cloud_outage_maps_to_infrastructure_outage(
        self
    ):

        a = article(
            (
                "Amazon Web Services suffered an outage "
                "affecting online services."
            ),
            headline=(
                "Major outage on Amazon Web Services "
                "disrupts popular websites"
            ),
        )

        accepted = validation(
            event_type=
                "operational_disruption",

            event_subtype=
                "it_outage",

            economic_channels=[
                "technology_infrastructure",
                "cloud_computing",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "infrastructure_outage",

                "event_subtype":
                    "outage",
            },
        )


    def test_hormuz_attack_maps_to_shipping_disruption(
        self
    ):

        a = article(
            (
                "The US military fired at a tanker "
                "during a naval blockade."
            ),
            headline=(
                "Strait of Hormuz: US fires at tanker "
                "as new Iran blockade begins"
            ),
        )

        accepted = validation(
            event_type=
                "military_action",

            event_subtype=
                "naval_blockade",

            economic_channels=[
                "oil_transport",
                "shipping_lanes",
                "energy_exports",
            ],
        )["accepted"]

        self.assertEqual(
            _semantic_event_candidate(
                a,
                accepted,
            ),
            {
                "event_type":
                    "geopolitical_conflict",

                "event_subtype":
                    "shipping_disruption",
            },
        )


# =========================================================
# DETERMINISTIC ARBITRATION
# =========================================================

class ArbitrationTests(
    unittest.TestCase
):

    def test_generic_general_news_can_be_upgraded(
        self
    ):

        a = article(
            (
                "Amazon Web Services suffered an outage "
                "affecting online services."
            ),
            headline=(
                "Major outage on Amazon Web Services "
                "disrupts popular websites"
            ),
        )

        v = validation(
            article_class=
                "supply_chain_event",

            event_type=
                "operational_disruption",

            event_subtype=
                "it_outage",

            economic_channels=[
                "technology_infrastructure",
                "cloud_computing",
            ],
        )

        r = record()

        decision = (
            _classification_arbitration(
                a,
                r,
                v,
            )
        )

        self.assertTrue(
            decision[
                "applied"
            ]
        )

        self.assertEqual(
            decision[
                "decision"
            ],
            "semantic_upgrade",
        )

        self.assertEqual(
            decision[
                "final"
            ],
            {
                "article_class":
                    "technology_event",

                "event_type":
                    "infrastructure_outage",

                "event_subtype":
                    "outage",
            },
        )


    def test_specific_conflict_is_deferred_by_default(
        self
    ):

        a = article(
            (
                "A company discussed an "
                "unrelated issue."
            ),
            headline=
                "Company commentary",
        )

        v = validation(
            article_class=
                "geopolitical_event",

            event_type=
                "military_action",

            event_subtype=
                "naval_blockade",

            economic_channels=[
                "shipping_lanes",
            ],
        )

        r = record(
            "commentary",
            "commentary",
            "commentary",
        )

        decision = (
            _classification_arbitration(
                a,
                r,
                v,
            )
        )

        self.assertFalse(
            decision[
                "applied"
            ]
        )

        self.assertEqual(
            decision[
                "decision"
            ],
            "conflict_deferred",
        )

        self.assertEqual(
            decision[
                "final"
            ][
                "event_type"
            ],
            "commentary",
        )


    def test_hormuz_main_event_can_override_background_tariff_classification(
        self
    ):

        headline = (
            "Strait of Hormuz: US fires at tanker "
            "as new Iran blockade begins"
        )

        a = article(
            (
                "The article also discusses historical "
                "sanctions and trade restrictions."
            ),
            headline=headline,
        )

        v = validation(
            article_class=
                "geopolitical_event",

            event_type=
                "military_action",

            event_subtype=
                "naval_blockade",

            economic_channels=[
                "oil_transport",
                "shipping_lanes",
            ],
        )

        # Main-event override requires
        # headline-grounded classification evidence.
        for key in (
            "article_class",
            "event_type",
        ):

            v[
                "accepted"
            ][
                key
            ][
                "citations"
            ][
                0
            ][
                "quote"
            ] = headline

            v[
                "accepted"
            ][
                key
            ][
                "citations"
            ][
                0
            ][
                "source_field"
            ] = "headline"

        r = record(
            "actionable_event",
            "trade_export_control",
            "tariffs",
        )

        decision = (
            _classification_arbitration(
                a,
                r,
                v,
            )
        )

        self.assertTrue(
            decision[
                "applied"
            ]
        )

        self.assertEqual(
            decision[
                "decision"
            ],
            "main_event_override",
        )

        self.assertEqual(
            decision[
                "final"
            ][
                "event_type"
            ],
            "geopolitical_conflict",
        )

        self.assertEqual(
            decision[
                "final"
            ][
                "event_subtype"
            ],
            "shipping_disruption",
        )


    def test_unmapped_semantic_label_cannot_override(
        self
    ):

        a = article(
            "Management discussed AI safety.",
            headline=
                "Nvidia CEO discusses AI safety",
        )

        v = validation(
            article_class=
                "geopolitical_event",

            event_type=
                "war",

            event_subtype=
                "war",
        )

        r = record(
            "commentary",
            "commentary",
            "commentary",
        )

        decision = (
            _classification_arbitration(
                a,
                r,
                v,
            )
        )

        self.assertFalse(
            decision[
                "applied"
            ]
        )

        self.assertEqual(
            decision[
                "decision"
            ],
            "deterministic_only",
        )

        self.assertEqual(
            decision[
                "final"
            ][
                "event_type"
            ],
            "commentary",
        )


# =========================================================
# SAFETY / NON-EXPANSION GUARDS
# =========================================================

class ApplicationGuardTests(
    unittest.TestCase
):

    def test_apply_changes_only_classification_fields(
        self
    ):

        r = record()

        r[
            "ticker_analysis"
        ] = [
            {
                "ticker":
                    "AMZN",

                "qualification":
                    "candidate_requires_review",

                "relationship_type":
                    "direct_mention",
            }
        ]

        r[
            "severity"
        ] = {
            "level":
                "Medium",

            "score":
                0.5,
        }

        original_ticker = dict(
            r[
                "ticker_analysis"
            ][
                0
            ]
        )

        original_severity = dict(
            r[
                "severity"
            ]
        )

        assessment = {
            "applied":
                True,

            "final":
                {
                    "article_class":
                        "technology_event",

                    "event_type":
                        "infrastructure_outage",

                    "event_subtype":
                        "outage",
                },
        }

        accepted = {
            "event_type":
                accepted_field(
                    "operational_disruption",
                    "outage",
                    "headline",
                ),

            "event_subtype":
                accepted_field(
                    "it_outage",
                    "outage",
                    "headline",
                ),
        }

        _apply_classification(
            r,
            assessment,
            accepted,
        )

        self.assertEqual(
            r[
                "classification"
            ],
            "technology_event",
        )

        self.assertEqual(
            r[
                "event"
            ][
                "event_type"
            ],
            "infrastructure_outage",
        )

        self.assertEqual(
            r[
                "event"
            ][
                "event_subtype"
            ],
            "outage",
        )

        # Classification arbitration must not
        # modify ticker relationship authority.
        self.assertEqual(
            r[
                "ticker_analysis"
            ][
                0
            ],
            original_ticker,
        )

        # Classification arbitration must not
        # modify deterministic severity.
        self.assertEqual(
            r[
                "severity"
            ],
            original_severity,
        )

        self.assertEqual(
            r[
                "event"
            ][
                "evidence_fields"
            ][
                "event_type"
            ][
                "basis"
            ],
            (
                "source_grounded_semantic_candidate_"
                "deterministically_arbitrated"
            ),
        )


    def test_not_applied_leaves_record_unchanged(
        self
    ):

        r = record(
            "commentary",
            "commentary",
            "commentary",
        )

        before = {
            "classification":
                r[
                    "classification"
                ],

            "event_type":
                r[
                    "event"
                ][
                    "event_type"
                ],

            "event_subtype":
                r[
                    "event"
                ][
                    "event_subtype"
                ],
        }

        _apply_classification(
            r,
            {
                "applied":
                    False,

                "final":
                    {
                        "article_class":
                            "geopolitical_event",

                        "event_type":
                            "geopolitical_conflict",

                        "event_subtype":
                            "shipping_disruption",
                    },
            },
            {},
        )

        self.assertEqual(
            r[
                "classification"
            ],
            before[
                "classification"
            ],
        )

        self.assertEqual(
            r[
                "event"
            ][
                "event_type"
            ],
            before[
                "event_type"
            ],
        )

        self.assertEqual(
            r[
                "event"
            ][
                "event_subtype"
            ],
            before[
                "event_subtype"
            ],
        )


if __name__ == "__main__":
    unittest.main()