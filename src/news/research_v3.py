"""Offline V3 enrichment over preserved V2 evidence/point-in-time matching."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .research_v2 import build_research_output_v2
from .research_policy import priority
from .pipeline import ROOT, _resolve_prediction_time
from .exposure_matcher import load_exposure_edges
from .historical_context import load_archive
from .v3_config import Config
from .v3_validation import (
    prefilter,
    validate_semantics,
    validated_operational_subjects,
    validated_geography,
)
from .v3_scoring import quantify
from .llm.analyzer import Analyzer, atomic_json


# =========================================================
# V3.1.2
# CLASSIFICATION ARBITRATION
# =========================================================

GENERIC_EVENT_VALUES = {
    None,
    "",
    "general_news",
    "unknown",
    "unclassified",
}


EVENT_CLASS = {
    "macro_monetary":
        "macro_event",

    "geopolitical_conflict":
        "geopolitical_event",

    "trade_export_control":
        "regulatory_event",

    "supply_chain":
        "supply_chain_event",

    "infrastructure_outage":
        "technology_event",
}


def _norm(value):

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()


def _accepted_value(
    accepted,
    key,
):

    item = (
        accepted.get(key)
        or {}
    )

    return item.get(
        "value"
    )


def _semantic_event_candidate(
    article,
    accepted,
):

    """
    Convert a source-grounded free-form semantic
    classification into the existing deterministic
    event taxonomy.

    This is intentionally bounded.

    Gemini does not create arbitrary new event types.
    """

    event_type = _norm(
        _accepted_value(
            accepted,
            "event_type",
        )
    )

    event_subtype = _norm(
        _accepted_value(
            accepted,
            "event_subtype",
        )
    )

    channels = (
        _accepted_value(
            accepted,
            "economic_channels",
        )
        or []
    )

    channel_text = " ".join(
        _norm(x)
        for x in channels
    )

    labels = " ".join(
        x
        for x in (
            event_type,
            event_subtype,
            channel_text,
        )
        if x
    )

    source = " ".join(
        str(
            article.get(k)
            or ""
        )
        for k in (
            "headline",
            "summary",
        )
    ).casefold()

    # -----------------------------------------------------
    # Geopolitical / shipping disruption
    # -----------------------------------------------------

    if any(
        x in labels
        for x in (
            "military action",
            "military conflict",
            "naval blockade",
            "shipping attack",
        )
    ):

        subtype = (
            "shipping_disruption"
            if re.search(
                r"\b(?:shipping|tanker|naval|"
                r"blockade|strait)\b",
                labels + " " + source,
            )
            else
            "conflict"
        )

        return {
            "event_type":
                "geopolitical_conflict",

            "event_subtype":
                subtype,
        }

    # -----------------------------------------------------
    # Infrastructure / cloud outage
    # -----------------------------------------------------

    if (
        "outage"
        in labels
        or (
            "operational disruption"
            in labels
            and re.search(
                r"\b(?:cloud|it|network|"
                r"technology infrastructure|"
                r"software services)\b",
                labels,
            )
        )
    ):

        return {
            "event_type":
                "infrastructure_outage",

            "event_subtype":
                "outage",
        }

    # -----------------------------------------------------
    # Inflation / CPI
    # -----------------------------------------------------

    if (
        "consumer price index"
        in labels
        or re.search(
            r"\bcpi\b",
            labels,
        )
        or "inflation"
        in event_type
    ):

        return {
            "event_type":
                "macro_monetary",

            "event_subtype":
                "inflation_data",
        }

    # -----------------------------------------------------
    # Export-control enforcement investigation
    # -----------------------------------------------------

    if (
        "investigation"
        in event_subtype
        and re.search(
            r"\b(?:export controls?|"
            r"export restrictions?|"
            r"smuggl\w*|"
            r"restricted ai chips?|"
            r"illegal semiconductor trade)\b",
            source,
        )
    ):

        return {
            "event_type":
                "trade_export_control",

            "event_subtype":
                "regulatory_enforcement",
        }

    # -----------------------------------------------------
    # Export controls
    # -----------------------------------------------------

    if (
        "export control"
        in labels
        or "export restriction"
        in labels
    ):

        return {
            "event_type":
                "trade_export_control",

            "event_subtype":
                "export_controls",
        }

    # -----------------------------------------------------
    # Advanced-packaging / supply-chain constraint
    # -----------------------------------------------------

    if any(
        x in labels
        for x in (
            "supply chain constraint",
            "packaging allocation",
            "advanced packaging capacity",
        )
    ):

        return {
            "event_type":
                "supply_chain",

            "event_subtype":
                "capacity_constraint",
        }

    # -----------------------------------------------------
    # Semiconductor supplier / capacity expansion
    # -----------------------------------------------------

    if (
        any(
            x in labels
            for x in (
                "facility opening",
                "supplier campus",
            )
        )
        and re.search(
            r"\b(?:semiconductor|"
            r"advanced packaging|"
            r"cowos|"
            r"chip supply chain|"
            r"tsmc)\b",
            labels + " " + source,
        )
    ):

        return {
            "event_type":
                "supply_chain",

            "event_subtype":
                "capacity_expansion",
        }

    return None


def _headline_classification_support(
    accepted,
):

    """
    Require explicit headline grounding before a
    semantic candidate may override an existing
    specific deterministic classification.
    """

    for field in (
        "event_type",
        "event_subtype",
        "article_class",
    ):

        citations = (
            accepted.get(field)
            or {}
        ).get(
            "citations",
            [],
        )

        for citation in citations:

            if (
                citation.get(
                    "source_field"
                )
                == "headline"
            ):

                return True

    return False


def _classification_arbitration(
    article,
    record,
    validation,
):

    """
    Conservative classification arbitration.

    AI may help resolve classification only.

    It does NOT independently determine:
    - exposure qualification
    - severity
    - financial materiality
    - investment direction
    """

    accepted = (
        validation.get(
            "accepted"
        )
        or {}
    )

    deterministic = {
        "article_class":
            record.get(
                "classification"
            ),

        "event_type":
            (
                record.get(
                    "event"
                )
                or {}
            ).get(
                "event_type"
            ),

        "event_subtype":
            (
                record.get(
                    "event"
                )
                or {}
            ).get(
                "event_subtype"
            ),
    }

    candidate = (
        _semantic_event_candidate(
            article,
            accepted,
        )
    )

    final = dict(
        deterministic
    )

    # -----------------------------------------------------
    # No safe mapping
    # -----------------------------------------------------

    if not candidate:

        return {
            "decision":
                "deterministic_only",

            "reason":
                "No grounded semantic event candidate "
                "maps safely into the existing event "
                "taxonomy.",

            "deterministic":
                deterministic,

            "canonical_semantic_candidate":
                None,

            "final":
                final,

            "applied":
                False,
        }

    candidate = {
        **candidate,

        "article_class":
            EVENT_CLASS[
                candidate[
                    "event_type"
                ]
            ],
    }

    det_type = (
        deterministic.get(
            "event_type"
        )
    )

    det_subtype = (
        deterministic.get(
            "event_subtype"
        )
    )

    # -----------------------------------------------------
    # Already aligned
    # -----------------------------------------------------

    if (
        det_type
        == candidate[
            "event_type"
        ]
        and
        det_subtype
        == candidate[
            "event_subtype"
        ]
    ):

        return {
            "decision":
                "aligned",

            "reason":
                "Grounded semantic candidate agrees "
                "with the deterministic event "
                "classification.",

            "deterministic":
                deterministic,

            "canonical_semantic_candidate":
                candidate,

            "final":
                final,

            "applied":
                False,
        }

    # -----------------------------------------------------
    # Generic deterministic classification
    #
    # general_news may be upgraded when:
    #
    # 1. semantic fields survived grounding
    # 2. they map into our bounded taxonomy
    # 3. deterministic classifier had no specific event
    # -----------------------------------------------------

    if (
        det_type
        in GENERIC_EVENT_VALUES

        and det_subtype
        in GENERIC_EVENT_VALUES

        and deterministic.get(
            "article_class"
        )
        == "general_news"
    ):

        final = dict(
            candidate
        )

        return {
            "decision":
                "semantic_upgrade",

            "reason":
                "Generic deterministic classification "
                "upgraded by a source-grounded semantic "
                "candidate mapped through bounded "
                "deterministic taxonomy rules.",

            "deterministic":
                deterministic,

            "canonical_semantic_candidate":
                candidate,

            "final":
                final,

            "applied":
                True,
        }

    # -----------------------------------------------------
    # Main-event precedence
    #
    # Extremely narrow V3.1.2 conflict rule.
    #
    # Example:
    #
    # headline:
    # tanker / military action / blockade
    #
    # body background:
    # sanctions / tariffs
    #
    # The main current event should not become tariffs.
    # -----------------------------------------------------

    headline = (
        article.get(
            "headline"
        )
        or ""
    )

    main_event_override = (
        det_type
        == "trade_export_control"

        and candidate[
            "event_type"
        ]
        == "geopolitical_conflict"

        and
        _headline_classification_support(
            accepted
        )

        and re.search(
            r"\b(?:blockade|tanker|ship|shipping|"
            r"military|airstrike|missile|"
            r"fires? at|attacked?)\b",
            headline,
            re.I,
        )
    )

    if main_event_override:

        final = dict(
            candidate
        )

        return {
            "decision":
                "main_event_override",

            "reason":
                "Headline-grounded geopolitical/"
                "shipping action outranks a conflicting "
                "trade-policy classification derived "
                "from background context.",

            "deterministic":
                deterministic,

            "canonical_semantic_candidate":
                candidate,

            "final":
                final,

            "applied":
                True,
        }

    # -----------------------------------------------------
    # Specific conflict not safely resolved
    # -----------------------------------------------------

    return {
        "decision":
            "conflict_deferred",

        "reason":
            "Specific deterministic classification "
            "retained because the grounded semantic "
            "conflict does not satisfy the bounded "
            "override rule.",

        "deterministic":
            deterministic,

        "canonical_semantic_candidate":
            candidate,

        "final":
            final,

        "applied":
            False,
    }


def _apply_classification(
    record,
    assessment,
    accepted,
):

    """
    Apply only an arbitration result that explicitly
    passed the bounded rules above.

    Exposure / ticker qualification is not recomputed.
    """

    if not assessment.get(
        "applied"
    ):

        return

    final = (
        assessment[
            "final"
        ]
    )

    event = (
        record[
            "event"
        ]
    )

    old_classification = (
        record.get(
            "classification"
        )
    )

    record[
        "classification"
    ] = final[
        "article_class"
    ]

    event[
        "event_type"
    ] = final[
        "event_type"
    ]

    event[
        "event_subtype"
    ] = final[
        "event_subtype"
    ]

    # Preserve consistency for records where status
    # simply mirrored the original classification.
    if (
        record.get(
            "status"
        )
        == old_classification
    ):

        record[
            "status"
        ] = record[
            "classification"
        ]

    # Keep the final classification auditable.
    #
    # This evidence is explicitly labelled as a
    # source-grounded semantic candidate that was
    # accepted by deterministic arbitration.
    evidence = (
        event.setdefault(
            "evidence_fields",
            {},
        )
    )

    for field in (
        "event_type",
        "event_subtype",
    ):

        citations = (
            accepted.get(
                field
            )
            or {}
        ).get(
            "citations",
            [],
        )

        citation = (
            citations[0]
            if citations
            else None
        )

        evidence[
            field
        ] = {
            "value":
                final[field],

            "evidence":
                (
                    citation.get(
                        "quote"
                    )
                    if citation
                    else None
                ),

            "source_field":
                (
                    citation.get(
                        "source_field"
                    )
                    if citation
                    else None
                ),

            "basis":
                "source_grounded_semantic_candidate_"
                "deterministically_arbitrated",
        }


# =========================================================
# MAIN V3 PIPELINE
# =========================================================


def _apply_direct_event_subjects(
    article,
    record,
    *,
    allow_arbitrated=False,
):
    """Apply bounded deterministic direct-event-subject qualification."""

    if _resolve_prediction_time(article) is None:
        return []

    applied = []

    for ticker, evidence in validated_operational_subjects(
        article,
        record,
        allow_arbitrated=allow_arbitrated,
    ).items():

        ticker_record = next(
            (
                row
                for row in record.get("ticker_analysis", [])
                if row.get("ticker") == ticker
            ),
            None,
        )

        if (
            ticker_record is None
            or ticker_record.get("relationship_type") != "direct_mention"
        ):
            continue

        ticker_record.update(
            qualification="qualified_direct_event_subject",
            relationship_type="direct_event_subject",
            direct_event_evidence=evidence,

            relevance={
                "level": "High",
                "relationship_score":
                    ticker_record.get("relevance_score"),
                "interpretation":
                    "Direct accepted event subject; "
                    "not financial impact.",
            },

            evidence_assessment={
                "level": "Moderate",
                "reason":
                    "Explicit article event subject; "
                    "not independent confirmation.",
            },

            financial_materiality={
                "level": "Not yet quantified",
                "reason":
                    "No validated event-specific financial "
                    "amount/denominator established.",
            },

            research_priority=priority(
                "High",
                record["severity"]["level"],
                "Moderate",
            ),
        )

        applied.append(ticker)

    return applied


def _sync_candidate_relationship_audit(
    validation,
    record,
    tickers,
):
    """
    Keep the semantic candidate audit consistent after
    deterministic direct-event-subject qualification.
    """

    if not tickers:
        return

    actual = {
        row["ticker"]: row
        for row in record.get("ticker_analysis", [])
    }

    for candidate in validation.get(
        "candidate_relationships",
        [],
    ):

        ticker = candidate.get("ticker")

        if ticker not in tickers:
            continue

        ticker_record = actual.get(ticker)

        if not ticker_record:
            continue

        if not ticker_record.get(
            "qualification",
            "",
        ).startswith("qualified_"):
            continue

        candidate.update(
            state="qualified",
            reason=
                "Existing deterministic result "
                "supports relationship.",
            edge_ids=[
                edge["edge_id"]
                for edge
                in ticker_record.get("evidence", [])
            ],
        )


def build_research_output_v3(
    articles,
    edges,
    *,
    config=None,
    analyzer=None,
    knowledge=None,
    archive=None,
    now=None,
):

    config = (
        config
        or Config()
    )

    analyzer = (
        analyzer
        or Analyzer(
            config
        )
    )

    now = (
        now
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    # -----------------------------------------------------
    # Preserve V2 evidence / PIT / exposure foundation
    # -----------------------------------------------------

    result = (
        build_research_output_v2(
            articles,
            edges,
            knowledge=knowledge,
            archive=archive,
            now=now,
        )
    )

    result[
        "schema_version"
    ] = "news_research_v3"

    # -----------------------------------------------------
    # Article loop
    # -----------------------------------------------------

    for article, record in zip(
        articles,
        result[
            "articles"
        ],
    ):

        if not record.get(
            "usable"
        ):

            record[
                "feed"
            ] = {
                "state":
                    "reject",

                "reason":
                    "Unusable/duplicate content.",
            }

            continue

        # Existing source URL identity is canonical;
        # support older normalized url spelling.
        record[
            "article_url"
        ] = (
            article.get(
                "article_url"
            )
            or article.get(
                "url"
            )
        )

        # -------------------------------------------------
        # Cheap deterministic prefilter
        # -------------------------------------------------

        feed = (
            prefilter(
                article
            )
        )

        # -------------------------------------------------
        # Semantic enrichment
        # -------------------------------------------------

        enrichment = (
            analyzer.analyze_article(
                article
            )
            if feed[
                "state"
            ]
            != "reject"

            else {
                "status":
                    "skipped",

                "reason":
                    "cheap_noise_filter",

                "semantic":
                    None,
            }
        )

        record[
            "enrichment"
        ] = enrichment

        record[
            "enrichment"
        ][
            "point_in_time_note"
        ] = (
            "Generated at the recorded enrichment time; "
            "not evidence the AI output was available "
            "when the article was published. "
            "Exposure eligibility still uses the "
            "original article replay time."
        )

        # -------------------------------------------------
        # Existing deterministic direct-event subjects
        #
        # Run before arbitration so already accepted
        # deterministic events keep their existing behavior.
        # -------------------------------------------------

        pre_arbitration_subjects = _apply_direct_event_subjects(
            article,
            record,
        )

        # -------------------------------------------------
        # Geography
        #
        # Remains deterministic and conservative.
        # -------------------------------------------------

        record[
            "geography"
        ] = (
            validated_geography(
                article
            )
        )

        geo = (
            record[
                "geography"
            ]
        )

        record[
            "event"
        ].update(
            country=
                geo[
                    "event_country"
                ],

            primary_country=
                geo[
                    "event_country"
                ],

            region=
                geo[
                    "event_region"
                ],

            city=
                geo[
                    "event_city"
                ],

            latitude=
                geo[
                    "latitude"
                ],

            longitude=
                geo[
                    "longitude"
                ],

            location_basis=
                geo[
                    "location_basis"
                ],

            coordinate_precision=
                geo[
                    "coordinate_precision"
                ],
        )

        # -------------------------------------------------
        # Semantic validation
        # -------------------------------------------------

        validation = (
            validate_semantics(
                article,
                enrichment,
                record,
            )
        )

        record[
            "semantic_validation"
        ] = validation

        accepted = (
            validation[
                "accepted"
            ]
        )

        semantic = (
            enrichment.get(
                "semantic"
            )
            or {}
        )

        # -------------------------------------------------
        # V3.1.2
        # Final classification arbitration
        # -------------------------------------------------

        arbitration = (
            _classification_arbitration(
                article,
                record,
                validation,
            )
        )

        _apply_classification(
            record,
            arbitration,
            accepted,
        )

        # -------------------------------------------------
        # Post-arbitration direct-event subject validation
        #
        # Only runs when bounded classification arbitration
        # actually changed the final event classification.
        #
        # Gemini ticker candidates still cannot qualify
        # themselves. Qualification requires deterministic
        # source-text evidence.
        # -------------------------------------------------

        post_arbitration_subjects = []

        if arbitration.get("applied"):

            post_arbitration_subjects = (
                _apply_direct_event_subjects(
                    article,
                    record,
                    allow_arbitrated=True,
                )
            )

            _sync_candidate_relationship_audit(
                validation,
                record,
                post_arbitration_subjects,
            )

        # -------------------------------------------------
        # Classification audit
        # -------------------------------------------------

        record[
            "classification_assessment"
        ] = {
            "candidates":
                {
                    key:
                        semantic.get(
                            key
                        )

                    for key
                    in (
                        "article_class",
                        "event_type",
                        "event_subtype",
                        "operational_event",
                        "fundamental_change_detected",
                    )
                },

            "source_grounded_candidates":
                {
                    key:
                        value

                    for key, value
                    in accepted.items()

                    if key
                    in (
                        "article_class",
                        "event_type",
                        "event_subtype",
                        "operational_event",
                        "fundamental_change_detected",
                    )
                },

            "validator_candidate":
                validation.get(
                    "classification_arbitration"
                ),

            "arbitration":
                arbitration,

            "final":
                {
                    "article_class":
                        record[
                            "classification"
                        ],

                    "event_type":
                        record[
                            "event"
                        ][
                            "event_type"
                        ],

                    "event_subtype":
                        record[
                            "event"
                        ][
                            "event_subtype"
                        ],
                },

            "authority":
                (
                    "Grounded semantic candidates may "
                    "refine classification only through "
                    "bounded deterministic arbitration; "
                    "exposure, severity and financial "
                    "impact remain independently controlled."
                ),

            "direct_event_subjects_pre_arbitration":
                pre_arbitration_subjects,

            "direct_event_subjects_post_arbitration":
                post_arbitration_subjects,

            # Exposure Knowledge Layer is deliberately
            # not rerun after classification arbitration.
            # Only the narrow deterministic direct-subject
            # validator may run again.
            "downstream_relationships_recomputed":
                False,
        }

        # -------------------------------------------------
        # Grounded article summary
        # -------------------------------------------------

        record[
            "article_summary"
        ] = {
            key:
                accepted.get(
                    key,
                    {},
                ).get(
                    "value"
                )

            for key
            in (
                "summary_short",
                "summary_full",
            )
        }

        record[
            "article_summary"
        ].update(
            source=
                (
                    "ai_source_grounded"
                    if any(
                        record[
                            "article_summary"
                        ].values()
                    )
                    else
                    "unavailable"
                ),

            notice=
                (
                    "AI summary of the supplied article; "
                    "not independent verification."
                ),
        )

        # -------------------------------------------------
        # Severity
        #
        # V3.1.2 classification arbitration does NOT
        # allow Gemini to override final severity.
        # -------------------------------------------------

        record[
            "severity_assessment"
        ] = {
            "severity_candidate":
                semantic.get(
                    "severity_candidate"
                ),

            "severity_reason":
                semantic.get(
                    "severity_reason"
                ),

            "severity_confidence":
                semantic.get(
                    "severity_confidence"
                ),

            "severity_final":
                record[
                    "severity"
                ][
                    "level"
                ],

            "severity_source":
                "rule",

            "validation":
                (
                    "LLM candidate retained for audit; "
                    "final severity requires the existing "
                    "non-negated article rules."
                ),

            "rule_evidence":
                record[
                    "severity"
                ].get(
                    "components",
                    [],
                ),
        }

        # -------------------------------------------------
        # Feed
        # -------------------------------------------------

        if (
            feed[
                "state"
            ]
            == "background"

            and accepted.get(
                "article_class",
                {},
            ).get(
                "value"
            )
            in (
                "macro_event",
                "geopolitical_event",
                "supply_chain_event",
                "regulatory_event",
                "technology_event",
            )
        ):

            feed = {
                "state":
                    "surface",

                "reason":
                    "Source-grounded semantic economic-"
                    "event candidate; relationship still "
                    "independently validated.",
            }

        if any(
            t[
                "qualification"
            ].startswith(
                "qualified_"
            )
            for t
            in record[
                "ticker_analysis"
            ]
        ):

            feed = {
                "state":
                    "surface",

                "reason":
                    "Deterministically qualified "
                    "watchlist relationship.",
            }

        record[
            "feed"
        ] = feed

        # -------------------------------------------------
        # Quantitative V3 layer
        # -------------------------------------------------

        for ticker_record in record[
            "ticker_analysis"
        ]:

            ticker_record[
                "quantitative"
            ] = quantify(
                article,
                ticker_record,
                record,
                config,
                now,
            )

            if (
                ticker_record[
                    "relationship_type"
                ]
                == "direct_company_subject"
            ):

                ticker_record[
                    "analyst_interpretation"
                ] = (
                    f"{ticker_record['ticker']} is the "
                    "article's direct company subject. "
                    "The current classification is "
                    "management commentary; no confirmed "
                    "operational, regulatory or financial "
                    "change is established by the available "
                    "validation. No measurable fundamental "
                    "impact has been established."
                )

            elif ticker_record.get(
                "evidence"
            ):

                channels = (
                    ", ".join(
                        ticker_record.get(
                            "economic_channels",
                            [],
                        )
                    ).replace(
                        "_",
                        " ",
                    )
                )

                ticker_record[
                    "analyst_interpretation"
                ] = (
                    f"{ticker_record['ticker']} has an "
                    "evidence-backed exposure path through "
                    f"{channels}. Verify whether the "
                    "reported event affects the cited "
                    "business or facility; the event-specific "
                    "financial extent is not yet quantified."
                )

    # =====================================================
    # RESEARCH QUEUE
    # =====================================================

    surfaced = {
        article[
            "article_id"
        ]

        for article
        in result[
            "articles"
        ]

        if article[
            "feed"
        ][
            "state"
        ]
        == "surface"
    }

    result[
        "research_queue"
    ] = [
        dict(
            article_id=
                article[
                    "article_id"
                ],

            event_id=
                article[
                    "event"
                ][
                    "event_id"
                ],

            ticker=
                ticker[
                    "ticker"
                ],

            qualification=
                ticker[
                    "qualification"
                ],

            priority=
                ticker[
                    "research_priority"
                ][
                    "level"
                ],

            direction=
                ticker[
                    "direction"
                ],
        )

        for article
        in result[
            "articles"
        ]

        if article[
            "article_id"
        ]
        in surfaced

        for ticker
        in article[
            "ticker_analysis"
        ]
    ]

    order = {
        "Urgent":
            0,

        "High":
            1,

        "Medium":
            2,

        "Review":
            3,

        "Low":
            4,
    }

    result[
        "research_queue"
    ].sort(
        key=lambda q: (
            order[
                q[
                    "priority"
                ]
            ],
            q[
                "article_id"
            ],
            q[
                "ticker"
            ],
        )
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    result[
        "summary"
    ].update(
        surface=
            len(
                surfaced
            ),

        background=
            sum(
                article[
                    "feed"
                ][
                    "state"
                ]
                == "background"

                for article
                in result[
                    "articles"
                ]
            ),

        noise_rejected=
            sum(
                article[
                    "feed"
                ][
                    "state"
                ]
                == "reject"

                for article
                in result[
                    "articles"
                ]
            ),

        llm_calls=
            analyzer.calls,

        qualified_pairs=
            sum(
                queue[
                    "qualification"
                ].startswith(
                    "qualified_"
                )

                for queue
                in result[
                    "research_queue"
                ]
            ),

        review_candidates=
            sum(
                queue[
                    "qualification"
                ]
                == "candidate_requires_review"

                for queue
                in result[
                    "research_queue"
                ]
            ),

        cache_hits=
            sum(
                bool(
                    article.get(
                        "enrichment",
                        {},
                    ).get(
                        "cache_hit"
                    )
                )

                for article
                in result[
                    "articles"
                ]
            ),

        enrichment_success=
            sum(
                article.get(
                    "enrichment",
                    {},
                ).get(
                    "status"
                )
                == "available"

                for article
                in result[
                    "articles"
                ]
            ),

        enrichment_failure=
            sum(
                article.get(
                    "enrichment",
                    {},
                ).get(
                    "status"
                )
                == "unavailable"

                for article
                in result[
                    "articles"
                ]
            ),
    )

    result[
        "summary"
    ][
        "enrichment_status_counts"
    ] = dict(
        Counter(
            article.get(
                "enrichment",
                {},
            ).get(
                "reason"
            )
            or article.get(
                "enrichment",
                {},
            ).get(
                "status",
                "not_processed",
            )

            for article
            in result[
                "articles"
            ]
        )
    )

    # =====================================================
    # POLICY DISCLOSURE
    # =====================================================

    result[
        "policies"
    ][
        "v3"
    ] = (
        "Source-grounded semantic classification may "
        "refine final taxonomy only through bounded "
        "deterministic arbitration; AI candidates never "
        "directly qualify exposure, severity, financial "
        "impact or investment direction."
    )

    return result


# =========================================================
# CLI
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=
            ROOT
            / "data/news/research/"
              "news_research_v3_current.json",
    )

    parser.add_argument(
        "--exposure-workbook",
        type=Path,
    )

    parser.add_argument(
        "--historical-map",
        type=Path,
    )

    parser.add_argument(
        "--historical-dir",
        type=Path,
    )

    args = (
        parser.parse_args()
    )

    config = (
        Config.from_env()
    )

    edges, knowledge = (
        load_exposure_edges(
            ROOT,
            args.exposure_workbook,
        )
    )

    articles = (
        json.loads(
            args.input.read_text()
        )[
            "articles"
        ]
    )

    result = (
        build_research_output_v3(
            articles,
            edges,
            config=config,
            knowledge=knowledge,
            archive=
                load_archive(
                    ROOT,
                    args.historical_map,
                    args.historical_dir,
                ),
        )
    )

    atomic_json(
        args.output,
        result,
    )

    print(
        json.dumps(
            result[
                "summary"
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()