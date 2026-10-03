"""Article-location evidence independent of gate/ticker matches; map points are coarse."""

import json
import re

from functools import lru_cache
from pathlib import Path

from .constants import (
    COUNTRY_ALIASES,
    LOCATION_COUNTRIES,
)

from .event_gate import (
    clauses,
    assertion_status,
    HISTORICAL,
)


ROOT = Path(__file__).resolve().parents[2]


# =========================================================
# COARSE NAMED-LOCATION REFERENCES
# =========================================================
#
# These are map anchors only.
#
# They are NOT claimed incident coordinates.
#
# Named cross-border / maritime features deliberately
# do not force a country assignment.
# =========================================================

NAMED_LOCATIONS = {
    "Strait of Hormuz": {
        "aliases": (
            "Strait of Hormuz",
        ),

        "country":
            None,

        "region":
            "Strait of Hormuz",

        # Coarse central map reference only.
        "latitude":
            26.56,

        "longitude":
            56.25,
    },
}


# =========================================================
# COARSE CITY REFERENCES
# =========================================================
#
# Used only when the article explicitly establishes
# the city as the event location.
#
# These are representative city anchors,
# not exact facility coordinates.
# =========================================================

CITY_POINTS = {
    "Kaohsiung": (
        22.63,
        120.30,
    ),
}


# =========================================================
# INSTITUTIONAL EVENT ORIGINS
# =========================================================
#
# V3.1.5
#
# This is deliberately separate from COUNTRY_ALIASES.
#
# "Fed" is not a geographic place.
#
# Institutional geography is used only when:
#
# 1. no stronger explicit geographic evidence exists;
# 2. the named institution is clearly the current
#    event subject; and
# 3. an affirmed institutional policy action is present.
#
# A background mention of an institution is NOT enough.
# =========================================================

INSTITUTIONAL_ORIGINS = {
    "Federal Reserve": {
        "aliases": (
            "Federal Reserve",
            "Fed",
            "FOMC",
        ),

        "country":
            "United States",
    },
}


INSTITUTIONAL_POLICY_ACTION = re.compile(
    r"""
    \b
    (?:
        holds? |
        held |
        keeps? |
        kept |
        leaves? |
        left |
        maintains? |
        maintained |
        raises? |
        raised |
        hikes? |
        hiked |
        cuts? |
        cut |
        lowers? |
        lowered |
        increases? |
        increased |
        reduces? |
        reduced |
        votes? |
        voted |
        decides? |
        decided |
        announces? |
        announced
    )
    \b
    """,
    re.I | re.X,
)


INSTITUTIONAL_POLICY_OBJECT = re.compile(
    r"""
    \b
    (?:
        interest\s+rates? |
        rates? |
        federal\s+funds |
        target\s+range |
        policy\s+rate |
        monetary\s+policy |
        rate\s+hike |
        rate\s+cut |
        hike |
        cut
    )
    \b
    """,
    re.I | re.X,
)


INSTITUTIONAL_SPECULATION = re.compile(
    r"""
    \b
    (?:
        may |
        might |
        could |
        expected |
        expects? |
        forecast\w* |
        consider\w* |
        considering |
        discuss\w* |
        risk\s+of |
        possibility |
        possible |
        likely |
        reportedly\s+considering
    )
    \b
    """,
    re.I | re.X,
)


# =========================================================
# COUNTRY MAP POINTS
# =========================================================


@lru_cache(maxsize=1)
def country_points():

    # Existing Natural Earth country label coordinates:
    # cartographic representative points,
    # NOT reported incident coordinates or
    # company headquarters.

    data = json.loads(
        (
            ROOT
            / "static/data/countries.geojson"
        ).read_text()
    )

    return {
        feature["properties"]["ADMIN"]:
            (
                feature["properties"].get(
                    "LABEL_Y"
                ),
                feature["properties"].get(
                    "LABEL_X"
                ),
            )

        for feature
        in data["features"]
    }


# =========================================================
# HELPERS
# =========================================================


def _is_explicit_location_context(
    field,
    clause,
    match,
):

    """
    Standard explicit location framing.

    Accepted examples:

    Strait of Hormuz: ...
    ... in the Strait of Hormuz
    ... near Taiwan
    ... at Gurnee
    """

    prefix = (
        clause[
            :match.start()
        ]
    )

    framed = (
        field == "headline"
        and not prefix.strip()
    )

    locative = re.search(
        r"\b(?:in|near|off|across|"
        r"throughout|outside|at)\s+"
        r"(?:the\s+)?$",
        prefix,
        re.I,
    )

    return bool(
        framed
        or locative
    )


def _is_facility_city_context(
    clause,
    match,
):

    """
    Narrow facility-action geography rule.

    Example:

        TSMC Opens Kaohsiung Supplier Campus

    Kaohsiung is accepted because:

    1. an explicit current facility action precedes it; and
    2. a facility noun immediately follows the city.

    This is intentionally narrow and does not turn every
    company/city co-mention into an event location.
    """

    prefix = (
        clause[
            :match.start()
        ]
    )

    suffix = (
        clause[
            match.end():
        ]
    )

    action = re.search(
        r"\b(?:"
        r"opens?|opened|"
        r"launches?|launched|"
        r"builds?|built|"
        r"starts?|started|"
        r"begins?|began|"
        r"expands?|expanded"
        r")\s+"
        r"(?:a\s+|an\s+|the\s+)?$",
        prefix,
        re.I,
    )

    facility = re.search(
        r"^\s+"
        r"(?:\w+\s+){0,3}"
        r"(?:"
        r"campus|"
        r"facility|"
        r"plant|"
        r"factory|"
        r"site|"
        r"fab|"
        r"office|"
        r"datacenter|"
        r"data\s+center"
        r")\b",
        suffix,
        re.I,
    )

    return bool(
        action
        and facility
    )


def _is_institutional_event_subject(
    clause,
    match,
):
    """
    Require the institution to be directly tied to a
    current affirmed policy action.

    Good:
        Fed holds interest rates steady
        FOMC raises the target range
        Federal Reserve cuts rates

    Not enough:
        Analysts expect the Fed to cut rates
        Markets discuss possible Fed action
        Fed may cut rates
        Previous Fed decisions affected markets
    """

    # -----------------------------------------------------
    # 1. Reject speculation that governs the institution
    #    from BEFORE the institution mention.
    #
    # Example:
    #     Analysts expect the Fed to cut rates
    #
    # The word "expect" appears before "Fed", so looking
    # only after the institution would miss it.
    # -----------------------------------------------------

    prefix_window = clause[
        max(
            0,
            match.start() - 70,
        ):
        match.start()
    ]

    governing_speculation = re.search(
        r"\b(?:"
        r"expect(?:s|ed)?|"
        r"forecast\w*|"
        r"anticipat\w*|"
        r"consider\w*|"
        r"discuss\w*|"
        r"possible|"
        r"likely"
        r")\b"
        r"(?:(?!\b(?:but|however|yet)\b).){0,40}"
        r"(?:the\s+)?$",
        prefix_window,
        re.I,
    )

    if governing_speculation:
        return False


    # -----------------------------------------------------
    # 2. Look for the institution's policy action AFTER
    #    the institution mention.
    # -----------------------------------------------------

    suffix_start = (
        match.end()
    )

    suffix_end = min(
        len(clause),
        match.end() + 100,
    )

    suffix = clause[
        suffix_start:
        suffix_end
    ]


    action = (
        INSTITUTIONAL_POLICY_ACTION.search(
            suffix
        )
    )

    if not action:
        return False


    # Action must be close to the institution.
    if action.start() > 30:
        return False


    policy_object = (
        INSTITUTIONAL_POLICY_OBJECT.search(
            suffix
        )
    )

    if not policy_object:
        return False


    # Policy object must also be close enough to belong
    # to the institutional action.
    if policy_object.start() > 80:
        return False


    evidence_end = max(
        action.end(),
        policy_object.end(),
    )


    # -----------------------------------------------------
    # 3. Reject speculation appearing AFTER institution.
    #
    # Examples:
    #     Fed may cut rates
    #     Fed could raise rates
    #     Fed is expected to cut rates
    # -----------------------------------------------------

    if INSTITUTIONAL_SPECULATION.search(
        suffix[
            :evidence_end
        ]
    ):
        return False


    # -----------------------------------------------------
    # 4. Final assertion check.
    # -----------------------------------------------------

    action_start = (
        suffix_start
        + action.start()
    )

    action_end = (
        suffix_start
        + action.end()
    )


    if (
        assertion_status(
            clause,
            action_start,
            action_end,
        )
        != "affirmed"
    ):
        return False


    return True


# =========================================================
# NAMED GEOGRAPHIC FEATURES
# =========================================================


def _named_location_candidates(
    article,
):

    candidates = []

    for (
        field,
        _,
        clause,
    ) in clauses(
        article
    ):

        if HISTORICAL.search(
            clause
        ):
            continue

        for (
            canonical,
            definition,
        ) in NAMED_LOCATIONS.items():

            for alias in definition[
                "aliases"
            ]:

                pattern = (
                    r"(?<!\w)"
                    + re.escape(alias)
                    + r"(?!\w)"
                )

                for match in re.finditer(
                    pattern,
                    clause,
                    re.I,
                ):

                    if not _is_explicit_location_context(
                        field,
                        clause,
                        match,
                    ):
                        continue

                    if (
                        assertion_status(
                            clause,
                            match.start(),
                            match.end(),
                        )
                        != "affirmed"
                    ):
                        continue

                    candidates.append(
                        {
                            "location_name":
                                canonical,

                            "country":
                                definition[
                                    "country"
                                ],

                            "region":
                                definition[
                                    "region"
                                ],

                            "latitude":
                                definition[
                                    "latitude"
                                ],

                            "longitude":
                                definition[
                                    "longitude"
                                ],

                            "source_field":
                                field,

                            "evidence":
                                clause,
                        }
                    )

        # Preserve the existing headline-first
        # preference.
        if (
            candidates
            and field
            == "headline"
        ):
            break

    return candidates


# =========================================================
# INSTITUTIONAL EVENT ORIGIN
# =========================================================


def _institutional_origin_candidates(
    article,
):

    candidates = []

    for (
        field,
        _,
        clause,
    ) in clauses(
        article
    ):

        if HISTORICAL.search(
            clause
        ):
            continue


        for (
            institution,
            definition,
        ) in INSTITUTIONAL_ORIGINS.items():

            for alias in definition[
                "aliases"
            ]:

                flags = (
                    0
                    if alias
                    in (
                        "Fed",
                        "FOMC",
                    )
                    else re.I
                )

                pattern = (
                    r"(?<!\w)"
                    + re.escape(alias)
                    + r"(?!\w)"
                )


                for match in re.finditer(
                    pattern,
                    clause,
                    flags,
                ):

                    if not _is_institutional_event_subject(
                        clause,
                        match,
                    ):
                        continue


                    if (
                        assertion_status(
                            clause,
                            match.start(),
                            match.end(),
                        )
                        != "affirmed"
                    ):
                        continue


                    candidates.append(
                        {
                            "institution":
                                institution,

                            "alias":
                                alias,

                            "country":
                                definition[
                                    "country"
                                ],

                            "source_field":
                                field,

                            "evidence":
                                clause,
                        }
                    )


        # Preserve headline-first preference.
        if (
            candidates
            and field
            == "headline"
        ):
            break


    return candidates


# =========================================================
# COUNTRY RESULT HELPER
# =========================================================


def _country_coordinates(
    country,
):

    country_key = (
        "United States of America"

        if country
        == "United States"

        else country
    )

    return country_points().get(
        country_key,
        (
            None,
            None,
        ),
    )


# =========================================================
# MAIN GEOGRAPHY
# =========================================================


def geography(
    article
):

    result = dict(
        event_country=None,
        event_region=None,
        event_city=None,

        latitude=None,
        longitude=None,

        location_basis=
            "unresolved",

        location_confidence=
            None,

        coordinate_basis=
            None,

        evidence=[],

        coordinate_precision=
            None,
    )


    # =====================================================
    # 1. EXPLICIT NAMED GEOGRAPHIC FEATURE
    # =====================================================
    #
    # Example:
    #
    # Strait of Hormuz
    #
    # This layer runs before country assignment because
    # cross-border / maritime geography must not be forced
    # into an arbitrary country.
    # =====================================================

    named_candidates = (
        _named_location_candidates(
            article
        )
    )

    if named_candidates:

        names = list(
            dict.fromkeys(
                candidate[
                    "location_name"
                ]
                for candidate
                in named_candidates
            )
        )

        result[
            "evidence"
        ] = named_candidates

        # Competing named locations remain unresolved.
        if len(names) != 1:
            return result

        chosen = (
            named_candidates[0]
        )

        result.update(
            event_country=
                chosen[
                    "country"
                ],

            event_region=
                chosen[
                    "region"
                ],

            event_city=
                None,

            latitude=
                chosen[
                    "latitude"
                ],

            longitude=
                chosen[
                    "longitude"
                ],

            location_basis=
                "explicit_named_location",

            location_confidence=
                (
                    "Article-supported named geographic "
                    "feature; exact incident point unresolved"
                ),

            coordinate_basis=
                (
                    "Static named-location reference point "
                    "(coarse map anchor)"
                ),

            coordinate_precision=
                "named_location_approximation",
        )

        return result


    # =====================================================
    # 2. EXPLICIT COUNTRY / CITY / REGION
    # =====================================================

    aliases = {
        key:
            key

        for key
        in country_points()

        if len(key) > 3
    }

    aliases.update(
        COUNTRY_ALIASES
    )

    aliases.update(
        {
            "Saudi":
                "Saudi Arabia",

            "Saudi Arabia":
                "Saudi Arabia",

            "UK":
                "United Kingdom",

            "U.S.":
                "United States",
        }
    )


    locations = dict(
        LOCATION_COUNTRIES
    )

    locations.update(
        {
            "Gurnee":
                "United States",

            # Explicit city needed by the frozen
            # semiconductor supply-chain case.
            "Kaohsiung":
                "Taiwan",
        }
    )


    candidates = []


    for (
        field,
        _,
        clause,
    ) in clauses(
        article
    ):

        if HISTORICAL.search(
            clause
        ):
            continue


        combined = {
            **aliases,
            **locations,
        }


        for (
            alias,
            country,
        ) in combined.items():

            flags = (
                0
                if len(alias) <= 3
                else re.I
            )

            pattern = (
                r"(?<!\w)"
                + re.escape(alias)
                + r"(?!\w)"
            )


            for match in re.finditer(
                pattern,
                clause,
                flags,
            ):

                explicit = (
                    _is_explicit_location_context(
                        field,
                        clause,
                        match,
                    )
                )


                facility_city = (
                    alias
                    in locations

                    and alias
                    != "Texas"

                    and _is_facility_city_context(
                        clause,
                        match,
                    )
                )


                if not (
                    explicit
                    or facility_city
                ):
                    continue


                if (
                    assertion_status(
                        clause,
                        match.start(),
                        match.end(),
                    )
                    != "affirmed"
                ):
                    continue


                city = (
                    alias

                    if (
                        alias
                        in locations

                        and alias
                        != "Texas"
                    )

                    else None
                )


                region = (
                    alias

                    if alias
                    == "Texas"

                    else None
                )


                candidates.append(
                    {
                        "country":
                            country,

                        "city":
                            city,

                        "region":
                            region,

                        "source_field":
                            field,

                        "evidence":
                            clause,
                    }
                )


        # Preserve existing headline-first behaviour.
        if (
            candidates
            and field
            == "headline"
        ):
            break


    countries = list(
        dict.fromkeys(
            candidate[
                "country"
            ]

            for candidate
            in candidates
        )
    )


    # =====================================================
    # 3. EXPLICIT GEOGRAPHY WINS
    # =====================================================
    #
    # Institutional origin is only a fallback.
    #
    # Therefore:
    #
    # one explicit country  -> use it
    # competing countries   -> remain unresolved
    # no explicit country   -> try institutional origin
    # =====================================================


    if len(countries) > 1:

        result[
            "evidence"
        ] = candidates

        return result


    if len(countries) == 1:

        result[
            "evidence"
        ] = candidates


        country = (
            countries[0]
        )


        # Prefer a specific city/region candidate
        # when one was explicitly established.
        city = next(
            (
                candidate[
                    "city"
                ]

                for candidate
                in candidates

                if candidate[
                    "city"
                ]
            ),
            None,
        )


        region = next(
            (
                candidate[
                    "region"
                ]

                for candidate
                in candidates

                if candidate[
                    "region"
                ]
            ),
            None,
        )


        # =================================================
        # CITY COORDINATE
        # =================================================

        if (
            city
            in CITY_POINTS
        ):

            (
                latitude,
                longitude,
            ) = CITY_POINTS[
                city
            ]


            result.update(
                event_country=
                    country,

                event_city=
                    city,

                event_region=
                    region,

                latitude=
                    latitude,

                longitude=
                    longitude,

                location_basis=
                    "explicit_article_location",

                location_confidence=
                    (
                        "Article-supported city; "
                        "exact site unresolved"
                    ),

                coordinate_basis=
                    (
                        "Static city reference point "
                        "(coarse map anchor)"
                    ),

                coordinate_precision=
                    "city_approximation",
            )


            return result


        # =================================================
        # COUNTRY COORDINATE
        # =================================================

        (
            latitude,
            longitude,
        ) = _country_coordinates(
            country
        )


        result.update(
            event_country=
                country,

            event_city=
                city,

            event_region=
                region,

            latitude=
                latitude,

            longitude=
                longitude,

            location_basis=
                "explicit_article_location",

            location_confidence=
                (
                    "Article-supported country; "
                    "exact site unresolved"
                ),

            coordinate_basis=
                (
                    "Natural Earth country label point "
                    "(existing map)"

                    if latitude
                    is not None

                    else None
                ),

            coordinate_precision=
                (
                    "country_approximation"

                    if latitude
                    is not None

                    else None
                ),
        )


        return result


    # =====================================================
    # 4. INSTITUTIONAL EVENT ORIGIN FALLBACK
    # =====================================================
    #
    # Runs ONLY when no explicit article geography was
    # established above.
    #
    # Example:
    #
    # Divided Fed holds interest rates steady...
    #
    # → institution = Federal Reserve
    # → event_country = United States
    #
    # This does not claim a physical incident location.
    # =====================================================

    institutional_candidates = (
        _institutional_origin_candidates(
            article
        )
    )


    institutional_countries = list(
        dict.fromkeys(
            candidate[
                "country"
            ]

            for candidate
            in institutional_candidates
        )
    )


    if len(
        institutional_countries
    ) != 1:

        result[
            "evidence"
        ] = (
            institutional_candidates
            if institutional_candidates
            else candidates
        )

        return result


    country = (
        institutional_countries[0]
    )


    (
        latitude,
        longitude,
    ) = _country_coordinates(
        country
    )


    result.update(
        event_country=
            country,

        event_region=
            None,

        event_city=
            None,

        latitude=
            latitude,

        longitude=
            longitude,

        location_basis=
            "institutional_event_origin",

        location_confidence=
            (
                "Current event attributed to a "
                "country-linked policy institution; "
                "not a claimed physical incident site"
            ),

        coordinate_basis=
            (
                "Natural Earth country label point "
                "(institutional origin map anchor)"

                if latitude
                is not None

                else None
            ),

        evidence=
            institutional_candidates,

        coordinate_precision=
            (
                "country_approximation"

                if latitude
                is not None

                else None
            ),
    )


    return result
