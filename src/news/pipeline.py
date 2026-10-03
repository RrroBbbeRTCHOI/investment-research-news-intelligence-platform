"""Offline backend: python3 -m src.news.pipeline (never invokes a provider)."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .channel_generator import generate_channels
from .event_extractor import extract_event
from .event_gate import evaluate_gate
from .exposure_matcher import (
    load_exposure_edges,
    match_exposures,
    parse_time,
)


ROOT = Path(__file__).resolve().parents[2]


# =========================================================
# FILE OUTPUT
# =========================================================

def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)


# =========================================================
# HISTORICAL SNAPSHOT DETECTION
# =========================================================

def _is_historical_snapshot(article: dict) -> bool:
    """
    Return True only for deliberately curated historical replay inputs.

    These inputs must explicitly confirm that:
    - they are historical validation snapshots
    - later information has been excluded
    - the snapshot was constructed from event-time source facts

    This prevents normal articles without fetched_at from silently using
    published_at as if the currently stored full-text version were known
    at publication time.
    """

    return (
        article.get("historical_snapshot") is True
        and article.get("later_context_excluded") is True
        and article.get("snapshot_method")
        == "manual_factual_snapshot_from_event_time_source"
    )


# =========================================================
# PREDICTION TIME
# =========================================================

def _resolve_prediction_time(
    article: dict,
    explicit_prediction_time: str | None = None,
):
    """
    Determine the point-in-time timestamp used for exposure eligibility.

    Priority:

    1. Explicit --prediction-time
       Only allowed if it does not precede observable article information.

    2. Historical curated snapshot
       Use published_at as the research replay time.

    3. Normal live / ingested article
       Use max(published_at, fetched_at), but only if fetched_at exists.

    This distinction prevents look-ahead bias while still allowing
    deliberately curated historical validation cases.
    """

    published = None
    fetched = None

    if article.get("published_at"):
        published = parse_time(article["published_at"], end_of_day=True)

    if article.get("fetched_at"):
        fetched = parse_time(article["fetched_at"], end_of_day=True)

    observed = [
        value
        for value in (published, fetched)
        if value is not None
    ]

    # -----------------------------------------------------
    # Explicit replay time
    # -----------------------------------------------------

    if explicit_prediction_time:
        prediction = parse_time(explicit_prediction_time)

        if prediction is None:
            raise ValueError("Invalid prediction_time")

        if observed and prediction < max(observed):
            raise ValueError(
                "prediction_time precedes article availability; "
                "cannot replay future article text"
            )

        return prediction

    # -----------------------------------------------------
    # Historical validation snapshot
    # -----------------------------------------------------

    if _is_historical_snapshot(article):

        if published is None:
            return None

        return published

    # -----------------------------------------------------
    # Normal provider/live article
    # -----------------------------------------------------

    # Full article content is not safely point-in-time usable unless
    # fetched_at exists.
    if fetched is None:
        return None

    if observed:
        return max(observed)

    return None


# =========================================================
# PIPELINE
# =========================================================

def run_pipeline(
    root: Path = ROOT,
    *,
    input_path: Path | None = None,
    exposure_workbook: Path | None = None,
    prediction_time: str | None = None,
) -> dict:

    root = Path(root)

    path = (
        input_path
        or root
        / "data/news/normalized/freenewsapi_articles_normalized.json"
    )

    # -----------------------------------------------------
    # LOAD NORMALIZED ARTICLES
    # -----------------------------------------------------

    normalized = json.loads(
        path.read_text(encoding="utf-8")
    )

    articles = normalized.get("articles")

    if (
        not isinstance(articles, list)
        or any(not isinstance(a, dict) for a in articles)
    ):
        raise ValueError(
            "Normalized input must contain an articles list of objects"
        )

    ids = [
        article.get("article_id")
        for article in articles
    ]

    if (
        any(not article_id for article_id in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError(
            "Normalized articles require unique nonempty article_id values"
        )

    if (
        prediction_time
        and parse_time(prediction_time) is None
    ):
        raise ValueError("Invalid prediction_time")

    # -----------------------------------------------------
    # INITIALIZE
    # -----------------------------------------------------

    now = datetime.now(timezone.utc).isoformat()

    edges, knowledge = load_exposure_edges(
        root,
        exposure_workbook,
    )

    events = []
    rejected = []
    matches = []
    all_channels = []
    exclusions = []

    # -----------------------------------------------------
    # PROCESS ARTICLES
    # -----------------------------------------------------

    for article in articles:

        # =================================================
        # EVENT GATE
        # =================================================

        gate = evaluate_gate(article)

        if not gate["is_event"]:
            rejected.append(gate)
            continue

        # =================================================
        # EVENT EXTRACTION
        # =================================================

        event = extract_event(
            article,
            now=now,
        )

        # =================================================
        # CANDIDATE CHANNELS
        # =================================================

        candidates = generate_channels(event)

        # =================================================
        # POINT-IN-TIME RESOLUTION
        # =================================================

        prediction = _resolve_prediction_time(
            article,
            explicit_prediction_time=prediction_time,
        )

        at = (
            prediction.isoformat()
            if prediction
            else None
        )

        # =================================================
        # EXPOSURE MATCHING
        # =================================================

        pairs, skipped = match_exposures(
            event,
            candidates,
            edges,
            prediction_time=at,
        )

        # =================================================
        # EVENT IDENTITY SAFETY
        # =================================================

        if any(
            existing["event_id"] == event["event_id"]
            for existing in events
        ):
            raise ValueError(
                "Duplicate event identity from "
                "provider_article_id + event_type"
            )

        # =================================================
        # COLLECT OUTPUT
        # =================================================

        events.append(event)
        all_channels.append(candidates)
        matches.extend(pairs)
        exclusions.extend(skipped)

    # =====================================================
    # EVENT OUTPUT
    # =====================================================

    event_output = {
        "_metadata": {
            "schema_version": "event_v1",
            "article_count": len(articles),
            "accepted_event_count": len(events),
            "rejected_article_count": len(rejected),
            "generated_at": now,
        },
        "events": events,
        "rejected": rejected,
    }

    # =====================================================
    # MATCH OUTPUT
    # =====================================================

    match_output = {
        "_metadata": {
            "schema_version": "event_company_match_v1",
            "generated_at": now,
            "exposure_knowledge": knowledge,
            "score_interpretation": (
                "Uncalibrated relevance prior, not probability, "
                "return or impact."
            ),
        },
        "matches": matches,
        "edge_exclusions": exclusions,
    }

    # =====================================================
    # SAVE OUTPUTS
    # =====================================================

    _save(
        root / "data/news/events/events_v1.json",
        event_output,
    )

    _save(
        root / "data/news/events/candidate_channels_v1.json",
        {
            "_metadata": {
                "schema_version": "candidate_channels_v1"
            },
            "events": all_channels,
        },
    )

    _save(
        root / "data/news/matches/event_company_matches_v1.json",
        match_output,
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    top_matches = sorted(
        (
            pair
            for pair in matches
            if pair["matched"]
        ),
        key=lambda pair: -pair["relevance_score"],
    )[:10]

    return {
        "articles": len(articles),
        "accepted": len(events),
        "rejected": len(rejected),
        "candidate_channels": sum(
            len(item["candidate_channels"])
            for item in all_channels
        ),
        "company_matches": sum(
            pair["matched"]
            for pair in matches
        ),
        "pairs": len(matches),
        "exposure_knowledge": knowledge,
        "top_matches": top_matches,
    }


# =========================================================
# CLI
# =========================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--input",
        type=Path,
    )

    parser.add_argument(
        "--exposure-workbook",
        type=Path,
    )

    parser.add_argument(
        "--prediction-time",
        help=(
            "ISO UTC time; cannot precede input availability"
        ),
    )

    args = parser.parse_args()

    try:

        result = run_pipeline(
            input_path=args.input,
            exposure_workbook=args.exposure_workbook,
            prediction_time=args.prediction_time,
        )

    except (
        OSError,
        ValueError,
        TypeError,
    ) as exc:

        parser.exit(
            1,
            f"News pipeline failed: {exc}\n",
        )

    # =====================================================
    # TERMINAL SUMMARY
    # =====================================================

    print(
        "=" * 60
        + "\nNEWS INTELLIGENCE PIPELINE\n"
        + "=" * 60
    )

    for label, key in [
        ("Articles loaded", "articles"),
        ("Events accepted", "accepted"),
        ("Articles rejected", "rejected"),
        ("Candidate channels", "candidate_channels"),
        ("Company matches", "company_matches"),
    ]:
        print(
            f'{label + ":":28}'
            f'{result[key]:>5}'
        )

    print(
        "Exposure knowledge: "
        + result["exposure_knowledge"]["status"]
    )

    print(
        result["exposure_knowledge"]["message"]
    )

    print("\nTop matches:")

    for pair in result["top_matches"]:

        print(
            f"{pair['ticker']} | "
            f"{pair['event_id']} | "
            f"relevance "
            f"{pair['relevance_score']:.2f}"
        )

    if not result["top_matches"]:
        print("(none)")

    print("=" * 60)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()