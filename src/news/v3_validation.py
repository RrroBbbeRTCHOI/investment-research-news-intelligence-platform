"""Grounded candidates are not verified facts or qualified company exposure."""

import re

from .constants import (
    ENTITY_ALIASES,
    MAG7,
    COUNTRY_ALIASES,
    SERVICE_ALIASES,
    SERVICE_OWNERS,
)
from .event_geography import geography
from .event_gate import assertion_status, HISTORICAL


SIGNIFICANT = re.compile(
    r'\b(?:earthquake|tsunami|war|sanctions?|export control|export restriction|'
    r'tariff|semiconductor|chip|AI|artificial intelligence|'
    r'cloud (?:computing|services?|outage)|datacenter|data center|power grid|'
    r'oil|energy|interest rate|central bank|inflation|antitrust|supply.chain|'
    r'factory|manufacturing|outage|production|cyberattack)\b',
    re.I,
)

NOISE = re.compile(
    r'\b(?:cruise passenger|carnival panorama|celebrity|national anthem|'
    r'princess diana|video game|lufia|stellar blade|horoscope)\b',
    re.I,
)


def prefilter(article):

    headline = article.get("headline") or ""

    text = " ".join(
        str(article.get(k) or "")
        for k in ["headline", "summary"]
    )

    direct = any(
        re.search(
            r"(?<!\w)" + re.escape(alias) + r"(?!\w)",
            text,
            re.I,
        )
        for ticker in MAG7
        for alias in ENTITY_ALIASES[ticker]
    )

    if direct:
        return {
            "state": "surface",
            "reason":
                "Watchlist company explicitly mentioned; qualification is separate.",
        }

    if NOISE.search(headline):
        return {
            "state": "reject",
            "reason":
                "Narrow non-economic headline pattern without a watchlist subject.",
        }

    if (
        re.search(
            r"\b(?:yen|dollar|currenc|FX)\w*\b",
            headline,
            re.I,
        )
        and not re.search(
            r"\b(?:announces?|announced|imposes?|imposed|intervenes?|"
            r"intervened|cuts? rates|raises? rates|capital controls)\b",
            headline,
            re.I,
        )
    ):
        return {
            "state": "background",
            "reason":
                "Routine currency commentary without an explicit new policy action.",
        }

    if SIGNIFICANT.search(text):
        return {
            "state": "surface",
            "reason":
                "Potential macro, technology or economic transmission event.",
        }

    return {
        "state": "background",
        "reason":
            "No identified watchlist or economic trigger; retained for review.",
    }


# Sentence boundaries are shared with geography.
# Do not change them in this patch.
def sentences(value):

    return [
        x.strip()
        for x in re.split(
            r'(?<=[.!?])\s+|'
            r'(?<=[.!?]["”’])\s+|'
            r'\n\s*\n',
            value or "",
        )
        if x.strip()
    ]


# Bounded lexical paraphrase rules, not fuzzy overlap
# or a claim of general NLI.
#
# Preserve predicate order, actors, modality,
# negation, numbers and quoted wording.
PARAPHRASES = (
    (
        r"\bchief executive(?: officer)?\b",
        "ceo",
    ),
    (
        r"\bartificial intelligence\b",
        "ai",
    ),
    (
        r"\btalked about\b",
        "discussed",
    ),
    (
        r"\b(?:dismissed|rejected)\b",
        "rejected",
    ),
    (
        r"\b(?:halted|stopped)\b",
        "stopped",
    ),
    (
        r"\b(?:postponed|delayed)\b",
        "delayed",
    ),
    (
        r"\b(?:rose|increased)\b",
        "increased",
    ),
    (
        r"\b(?:fell|declined|decreased)\b",
        "decreased",
    ),
    (
        r"\b(?:said|stated)\b",
        "said",
    ),
    (
        r"\bcould lead to\b",
        "could cause",
    ),
    (
        r"\bdescribed (.+?) as\b",
        r"called \1",
    ),
)


FUNCTION_WORDS = {
    "a",
    "an",
    "the",
    "has",
    "have",
    "had",
    "that",
}


PREDICATES = {
    "rejected",
    "stopped",
    "delayed",
    "increased",
    "decreased",
    "said",
    "discussed",
    "called",
    "announced",
    "warned",
    "reported",
    "requested",
}


CONTEXT_CONTROL = re.compile(
    r"\b(?:not|no|never|denied|deny|false|rumors?|unconfirmed|alleged|"
    r"if|unless|may|might|could|would|says?|said|states?|stated|"
    r"claims?|claimed|reports?|reported|warns?|warned|believes?|"
    r"believed|suggests?|suggested|argued|asserted|proposed|fears?|"
    r"concerns?|predictions?|forecasts?|according)\b|"
    r"\b\w+n['’]t\b",
    re.I,
)


def claim_tokens(value):

    value = " ".join(
        value.casefold()
        .replace("’", "'")
        .replace("'s", "")
        .replace("$", " usd ")
        .split()
    )

    for pattern, replacement in PARAPHRASES:
        value = re.sub(
            pattern,
            replacement,
            value,
        )

    return [
        x
        for x in re.findall(
            r"[^\W\d_]+|"
            r"[-+]?\d+(?:[.,]\d+)*|"
            r"[<>=%€£¥]",
            value,
        )
        if x not in FUNCTION_WORDS
    ]


def supported_clause(
    claim,
    citation,
    article,
):

    quote = citation["quote"]

    source = (
        article.get(
            citation["source_field"]
        )
        or ""
    )

    if (
        len(quote.strip()) < 8
        or quote not in source
    ):
        return False

    wanted = claim_tokens(
        claim
    )

    if not wanted:
        return False

    # Expand to the original surrounding sentence:
    # a clipped quote must not hide a reporting source,
    # conditional or negation before the quoted fragment.
    for unit in sentences(
        quote
    ):

        offset = (
            source.index(quote)
            + quote.index(unit)
        )

        prefix = re.split(
            r'(?<=[.!?])\s+|'
            r'(?<=[.!?]["”’])\s+|'
            r'\n\s*\n',
            source[:offset],
        )[-1]

        suffix = (
            ""
            if re.search(
                r'[.!?]["”’]?$',
                unit,
            )
            else re.split(
                r"(?<=[.!?])\s+",
                source[
                    offset + len(unit):
                ],
            )[0]
        )

        if (
            CONTEXT_CONTROL.search(
                prefix
            )
            or CONTEXT_CONTROL.search(
                suffix
            )
        ):
            continue

        available = claim_tokens(
            unit
        )

        for start in range(
            len(available)
            - len(wanted)
            + 1
        ):

            if (
                available[
                    start:
                    start + len(wanted)
                ]
                != wanted
            ):
                continue

            before = available[
                :start
            ]

            after = available[
                start + len(wanted):
            ]

            # Disallow dropped attribution/modality
            # in the corresponding sentence.
            if any(
                CONTEXT_CONTROL.fullmatch(
                    x
                )
                for x in before + after
            ):
                continue

            quoted = re.findall(
                r'["“]([^"”]+)["”]',
                claim,
            )

            if any(
                " ".join(
                    q.split()
                )
                not in
                " ".join(
                    unit.split()
                )
                for q in quoted
            ):
                continue

            return True

    return False


def ground_summary(
    value,
    citations,
    article,
):

    audit = []

    for sentence in sentences(
        value
    ):

        supports = [
            c
            for c in citations
            if supported_clause(
                sentence,
                c,
                article,
            )
        ]

        if not supports:

            # Joint support requires each complete
            # claim to retain its actor.
            parts = re.split(
                r"\s*;\s*|\s+and\s+",
                sentence,
            )

            first = claim_tokens(
                parts[0]
            )

            verb = next(
                (
                    i
                    for i, x
                    in enumerate(first)
                    if x in PREDICATES
                ),
                None,
            )

            subject = (
                " ".join(
                    first[:verb]
                )
                if verb is not None
                else ""
            )

            combined = []

            for part in parts:

                tokens = claim_tokens(
                    part
                )

                if (
                    tokens
                    and tokens[0]
                    in PREDICATES
                    and subject
                ):
                    part = (
                        subject
                        + " "
                        + part
                    )

                if not any(
                    x in PREDICATES
                    for x in claim_tokens(
                        part
                    )
                ):
                    combined = []
                    break

                matches = [
                    c
                    for c in citations
                    if supported_clause(
                        part,
                        c,
                        article,
                    )
                ]

                if not matches:
                    combined = []
                    break

                combined.extend(
                    matches
                )

            if len(parts) > 1:
                supports = combined

        direction = re.search(
            r"\b(?:buy|sell|bullish|bearish|"
            r"price target|stock will)\b",
            sentence,
            re.I,
        )

        accepted = (
            bool(supports)
            and not direction
        )

        row = {
            "sentence":
                sentence,

            "accepted":
                accepted,

            "supporting_quotes":
                list(
                    dict.fromkeys(
                        c["quote"]
                        for c
                        in supports
                    )
                ),

            "source_fields":
                list(
                    dict.fromkeys(
                        c["source_field"]
                        for c
                        in supports
                    )
                ),

            "reason":
                (
                    "Exact source support with bounded "
                    "meaning-preserving rewording."
                    if accepted
                    else
                    "Investment-direction wording is not "
                    "an article summary."
                    if direction
                    else
                    "No sufficient exact source support: "
                    "unsupported claim, attribution, "
                    "modality or negation."
                ),
        }

        if accepted:
            row.update(
                source_quote=
                    supports[0]["quote"],

                source_field=
                    supports[0][
                        "source_field"
                    ],
            )

        audit.append(
            row
        )

    kept = (
        " ".join(
            x["sentence"]
            for x in audit
            if x["accepted"]
        )
        or None
    )

    return {
        "value":
            kept,

        "status":
            (
                "source_grounded_candidate"
                if kept
                else "rejected"
            ),

        "sentence_validation":
            audit,

        "reason":
            (
                None
                if kept
                else
                "No summary sentences have "
                "sufficient source support."
            ),
    }


GEOGRAPHIC_CONTEXT = re.compile(
    r"\b(?:publisher|headquarters|headquartered|"
    r"based in|interview|nationality|US partner|"
    r"U\.S\. partner|referenced)\b",
    re.I,
)


def validated_geography(
    article
):

    # Remove contextual sentences only in the
    # V3 geography view.
    #
    # This does not alter article text,
    # legacy event matching or point-in-time
    # exposure inputs.
    clean = {
        **article
    }

    for field in (
        "headline",
        "summary",
        "body",
    ):

        clean[field] = " ".join(
            x
            for x in sentences(
                article.get(field)
            )
            if not GEOGRAPHIC_CONTEXT.search(
                x
            )
        )

    return geography(
        clean
    )


# =========================================================
# V3.1.2
# GROUNDED SEMANTIC CLASSIFICATION CANDIDATE
# =========================================================
#
# IMPORTANT:
#
# Gemini / LLM does NOT become final authority here.
#
# This layer only preserves a source-grounded semantic
# classification candidate so research_v3.py can perform
# deterministic arbitration later.
#
# AI candidates still cannot independently determine:
#
# - exposure qualification
# - final severity
# - geography
# - financial materiality
# - investment direction
# - expected return
#
# =========================================================


CLASSIFICATION_FIELDS = (
    "article_class",
    "event_type",
    "event_subtype",
)


GENERIC_CLASSIFICATIONS = {
    None,
    "",
    "general_news",
    "unknown",
    "unclassified",
}


def classification_arbitration_candidate(
    accepted,
    record,
):

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

    semantic = {
        field:
            accepted[field][
                "value"
            ]

        for field
        in CLASSIFICATION_FIELDS

        if field
        in accepted
    }

    if not semantic:

        return {
            "status":
                "no_grounded_semantic_classification",

            "deterministic":
                deterministic,

            "semantic_candidate":
                {},

            "decision":
                "deterministic_only",

            "reason":
                "No source-grounded semantic "
                "classification candidate is available.",

            "final":
                deterministic,

            "authority":
                "Final classification remains "
                "deterministic until research_v3 "
                "arbitration.",
        }

    comparable = [
        field
        for field
        in CLASSIFICATION_FIELDS
        if field
        in semantic
    ]

    disagreements = [
        field
        for field
        in comparable
        if (
            semantic[field]
            != deterministic.get(
                field
            )
        )
    ]

    if not disagreements:

        decision = (
            "aligned"
        )

        reason = (
            "Grounded semantic classification "
            "agrees with the existing "
            "deterministic classification."
        )

    else:

        det_event = (
            deterministic.get(
                "event_type"
            )
        )

        det_subtype = (
            deterministic.get(
                "event_subtype"
            )
        )

        generic_event = (
            det_event
            in GENERIC_CLASSIFICATIONS
            and det_subtype
            in GENERIC_CLASSIFICATIONS
        )

        if (
            generic_event
            and (
                "event_type"
                in semantic
                or "event_subtype"
                in semantic
            )
        ):

            decision = (
                "semantic_upgrade_candidate"
            )

            reason = (
                "Deterministic event classification "
                "is generic; grounded semantic "
                "classification may be considered "
                "by final deterministic arbitration."
            )

        else:

            decision = (
                "classification_conflict"
            )

            reason = (
                "Grounded semantic classification "
                "conflicts with a specific "
                "deterministic classification; "
                "final arbitration must resolve "
                "the main-event evidence."
            )

    return {
        "status":
            "grounded_semantic_candidate",

        "deterministic":
            deterministic,

        "semantic_candidate":
            semantic,

        "decision":
            decision,

        "reason":
            reason,

        "final":
            deterministic,

        "authority":
            "This validator exposes grounded "
            "candidates only; research_v3 remains "
            "final classification authority.",
    }


def validate_semantics(
    article,
    enrichment,
    record,
):

    semantic = (
        enrichment.get(
            "semantic"
        )
    )

    if not semantic:

        return {
            "status":
                "unavailable",

            "accepted":
                {},

            "rejections":
                [],

            "candidate_relationships":
                [],

            "classification_arbitration":
                {
                    "status":
                        "unavailable",

                    "decision":
                        "deterministic_only",

                    "reason":
                        "Semantic enrichment unavailable.",

                    "final":
                        {
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
                        },

                    "authority":
                        "Final classification remains "
                        "deterministic until research_v3 "
                        "arbitration.",
                },
        }

    accepted = {}
    rejections = []
    citations = {}

    for citation in semantic[
        "citations"
    ]:

        quote = (
            citation["quote"]
        )

        source = (
            article.get(
                citation[
                    "source_field"
                ]
            )
            or ""
        )

        if (
            len(
                quote.strip()
            ) >= 8
            and quote
            in source
        ):

            citations.setdefault(
                citation["field"],
                [],
            ).append(
                citation
            )

        else:

            rejections.append(
                {
                    "field":
                        citation[
                            "field"
                        ],

                    "reason":
                        "Citation is not a "
                        "substantive exact source span.",
                }
            )

    # A supported quote authenticates extraction
    # provenance, not semantic truth.
    for field in (
        "summary_short",
        "summary_full",
        "article_class",
        "primary_country",
        "event_type",
        "event_subtype",
        "economic_channels",
        "operational_event",
        "fundamental_change_detected",
    ):

        if (
            semantic.get(
                field
            )
            is not None
            and citations.get(
                field
            )
        ):

            accepted[field] = {
                "value":
                    semantic[field],

                "citations":
                    citations[field],

                "status":
                    "source_grounded_candidate",
            }

    # =====================================================
    # SUMMARY VALIDATION
    # =====================================================

    summary_validation = {}

    for field in (
        "summary_short",
        "summary_full",
    ):

        result = ground_summary(
            semantic.get(
                field
            ),
            citations.get(
                field,
                [],
            ),
            article,
        )

        summary_validation[
            field
        ] = result

        accepted.pop(
            field,
            None,
        )

        if (
            result[
                "value"
            ]
            is not None
        ):

            accepted[
                field
            ] = result

        else:

            rejections.append(
                {
                    "field":
                        field,

                    "reason":
                        result[
                            "reason"
                        ],
                }
            )

    # =====================================================
    # V3.1.2
    # CLASSIFICATION CANDIDATE PRESERVATION
    # =====================================================

    classification_arbitration = (
        classification_arbitration_candidate(
            accepted,
            record,
        )
    )

    # =====================================================
    # GEOGRAPHY
    # =====================================================

    country = (
        accepted.get(
            "primary_country"
        )
    )

    if country:

        final_geo = (
            validated_geography(
                article
            )
        )

        supported = (
            final_geo.get(
                "event_country"
            )
            == country[
                "value"
            ]
            and any(
                (
                    not
                    GEOGRAPHIC_CONTEXT.search(
                        citation[
                            "quote"
                        ]
                    )
                )
                and
                (
                    geography(
                        {
                            citation[
                                "source_field"
                            ]:
                                citation[
                                    "quote"
                                ]
                        }
                    ).get(
                        "event_country"
                    )
                    == country[
                        "value"
                    ]
                )
                for citation
                in country[
                    "citations"
                ]
            )
        )

        if not supported:

            accepted.pop(
                "primary_country"
            )

            rejections.append(
                {
                    "field":
                        "primary_country",

                    "reason":
                        "Country failed deterministic "
                        "event-geography validation; "
                        "contextual location is not "
                        "event location.",
                }
            )

    # =====================================================
    # TICKER / RELATIONSHIP VALIDATION
    # =====================================================

    actual = {
        ticker_record[
            "ticker"
        ]:
            ticker_record

        for ticker_record
        in record.get(
            "ticker_analysis",
            [],
        )
    }

    candidates = []

    for kind in (
        "direct_ticker_candidates",
        "candidate_indirect_tickers",
    ):

        for ticker in semantic[
            kind
        ]:

            ticker_record = (
                actual.get(
                    ticker
                )
            )

            qualified = bool(
                ticker_record
                and ticker_record.get(
                    "qualification",
                    "",
                ).startswith(
                    "qualified_"
                )
            )

            if (
                kind
                == "candidate_indirect_tickers"
            ):

                qualified = bool(
                    qualified
                    and ticker_record.get(
                        "evidence"
                    )
                )

            candidates.append(
                {
                    "ticker":
                        ticker,

                    "kind":
                        kind,

                    "state":
                        (
                            "qualified"
                            if qualified
                            else
                            "unverified"
                            if ticker
                            in MAG7
                            else
                            "rejected"
                        ),

                    "reason":
                        (
                            "Existing deterministic "
                            "result supports relationship."
                            if qualified
                            else
                            "No eligible matching "
                            "exposure/action evidence; "
                            "candidate cannot qualify "
                            "itself."
                        ),

                    "edge_ids":
                        (
                            [
                                edge[
                                    "edge_id"
                                ]
                                for edge
                                in ticker_record.get(
                                    "evidence",
                                    [],
                                )
                            ]
                            if qualified
                            else []
                        ),
                }
            )

    return {
        "status":
            "validated_constraints",

        "accepted":
            accepted,

        "summary_validation":
            summary_validation,

        "rejections":
            rejections,

        "candidate_relationships":
            candidates,

        "classification_arbitration":
            classification_arbitration,

        "notice":
            "Source-grounded AI extraction is not "
            "independent fact verification. "
            "Candidate fields do not qualify ticker exposure.",
    }


# =========================================================
# DIRECT EVENT SUBJECT VALIDATION
# =========================================================


def validated_operational_subjects(
    article,
    record,
    *,
    allow_arbitrated=False,
):

    """
    Bounded deterministic direct-event subject validation.

    This function may run after V3.1.2 classification
    arbitration, but semantic ticker candidates never
    qualify themselves.

    A ticker is returned only when source text contains
    an affirmed direct-subject pattern supported by the
    final accepted event type.
    """

    if (
        not record["gate"]["is_event"]
        and not allow_arbitrated
    ):
        return {}

    event = (
        record.get(
            "event"
        )
        or {}
    )

    event_type = (
        event.get(
            "event_type"
        )
    )

    headline = (
        article.get(
            "headline"
        )
        or ""
    )

    summary = (
        article.get(
            "summary"
        )
        or ""
    )

    result = {}


    # =====================================================
    # COMMON ASSERTION SAFETY
    # =====================================================

    def usable_claim(
        text,
        match,
    ):

        if not match:
            return False

        if HISTORICAL.search(
            text
        ):
            return False

        # Do not convert speculation, plans or forecasts
        # into a qualified event subject.
        if re.search(
            r"\b(?:may|might|could|risk|"
            r"planned|plans?|expects?|forecast|"
            r"rumou?r|reportedly considering)\b",
            text,
            re.I,
        ):
            return False

        return (
            assertion_status(
                text,
                match.start(),
                match.end(),
            )
            == "affirmed"
        )


    # =====================================================
    # 1. NAMED CLOUD / SERVICE OUTAGE
    # =====================================================
    #
    # Examples:
    #
    # Amazon Web Services suffered a major outage
    # Major outage on Amazon Web Services
    # AWS service outage
    #
    # Only the service OWNER becomes the direct subject.
    #
    # A downstream company/service merely mentioned as
    # affected does NOT inherit the outage relationship.
    # =====================================================

    if (
        event_type
        == "infrastructure_outage"
    ):

        for (
            service,
            aliases,
        ) in SERVICE_ALIASES.items():

            ticker = (
                SERVICE_OWNERS.get(
                    service
                )
            )

            if ticker not in MAG7:
                continue

            names = "|".join(
                re.escape(
                    alias
                )
                for alias
                in sorted(
                    aliases,
                    key=len,
                    reverse=True,
                )
            )

            patterns = (

                # Amazon Web Services suffered
                # a major outage
                (
                    r"\b(?:"
                    + names
                    + r")\b\s+"
                    r"(?:suffered|experienced|reported|had)"
                    r"\s+(?:a\s+)?"
                    r"(?:major\s+)?"
                    r"(?:service\s+)?"
                    r"outage\b"
                ),

                # Major outage on Amazon Web Services
                (
                    r"\b(?:major\s+)?"
                    r"outage\s+"
                    r"(?:on|at|affecting)\s+"
                    r"(?:"
                    + names
                    + r")\b"
                ),

                # AWS service outage
                # Azure cloud outage
                (
                    r"\b(?:"
                    + names
                    + r")\b"
                    r"(?:\s+\w+){0,3}\s+"
                    r"(?:service\s+)?"
                    r"(?:outage|disruption)\b"
                ),
            )

            for (
                source_field,
                text,
            ) in (
                (
                    "headline",
                    headline,
                ),
                (
                    "summary",
                    summary,
                ),
            ):

                match = next(
                    (
                        found
                        for pattern
                        in patterns
                        if (
                            found
                            := re.search(
                                pattern,
                                text,
                                re.I,
                            )
                        )
                    ),
                    None,
                )

                if usable_claim(
                    text,
                    match,
                ):

                    result[
                        ticker
                    ] = {
                        "evidence":
                            text,

                        "source_field":
                            source_field,

                        "basis":
                            (
                                "V3 explicit named "
                                "service outage subject"
                            ),
                    }

                    break


    # =====================================================
    # 2. EXISTING PRODUCTION-HALT RULE
    # =====================================================
    #
    # Preserve old V3 behaviour.
    # =====================================================

    if (
        event_type
        == "supply_chain"
    ):

        for ticker in MAG7:

            names = "|".join(
                re.escape(
                    alias
                )
                for alias
                in ENTITY_ALIASES[
                    ticker
                ]
            )

            pattern = (
                r"^\s*(?:"
                + names
                + r")"
                r"(?:[’\x27]s)?\s+"
                r"(?:\w+\s+){0,4}"
                r"(?:production halt|"
                r"factory halt|"
                r"production shutdown|"
                r"manufacturing halt)\b"
            )

            match = re.search(
                pattern,
                headline,
                re.I,
            )

            if usable_claim(
                headline,
                match,
            ):

                result[
                    ticker
                ] = {
                    "evidence":
                        headline,

                    "source_field":
                        "headline",

                    "basis":
                        (
                            "V3 explicit accepted "
                            "operational subject"
                        ),
                }


    # =====================================================
    # 3. EXPORT-CONTROL RESPONSE SUBJECT
    # =====================================================
    #
    # Example:
    #
    # Nvidia Tightens Asian Customer Approvals
    # as US Chip Export Controls Intensify
    #
    # This establishes Nvidia as the explicit company
    # ACTION SUBJECT.
    #
    # It does NOT create an Exposure Knowledge Layer edge.
    # It does NOT infer financial impact.
    # =====================================================

    if (
        event_type
        == "trade_export_control"

        and re.search(
            r"\b(?:export controls?|"
            r"export restrictions?|"
            r"export curbs?|"
            r"export licens\w*|"
            r"trade restrictions?)\b",
            headline
            + " "
            + summary,
            re.I,
        )
    ):

        for ticker in MAG7:

            names = "|".join(
                re.escape(
                    alias
                )
                for alias
                in ENTITY_ALIASES[
                    ticker
                ]
            )

            pattern = (
                r"^\s*(?:"
                + names
                + r")"
                r"(?:[’\x27]s)?\s+"

                # Allow a small modifier window
                # before the actual action.
                r"(?:\w+\s+){0,2}"

                r"(?:tightens?|tightened|"
                r"restricts?|restricted|"
                r"reduces?|reduced|"
                r"limits?|limited|"
                r"pauses?|paused|"
                r"halts?|halted)\s+"

                r"(?:\w+\s+){0,4}"

                r"(?:customer approvals?|"
                r"approvals?|"
                r"sales|"
                r"shipments?|"
                r"orders?)\b"
            )

            match = re.search(
                pattern,
                headline,
                re.I,
            )

            if usable_claim(
                headline,
                match,
            ):

                result[
                    ticker
                ] = {
                    "evidence":
                        headline,

                    "source_field":
                        "headline",

                    "basis":
                        (
                            "V3 explicit export-control "
                            "response subject"
                        ),
                }


    return result