"""Independent bounded ingestion. Flask and browser never invoke this runner."""

import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .live_dedupe import canonicalize_live_url, cross_subdomain_key, usable_text, rebuild_identity_index
from .live_config import LiveConfig
from .llm.analyzer import Analyzer, atomic_json
from .llm.base import ProviderError, content
from .v3_config import Config
from .v3_validation import prefilter
from .research_v3 import build_research_output_v3
from .live_content import classify_live_content, build_outlook_record, display_type


# ============================================================
# JSON HELPERS
# ============================================================


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return deepcopy(default)


# ============================================================
# URL NORMALIZATION
# ============================================================


def canonical_url(value):
    return canonicalize_live_url(value)


# ============================================================
# ARTICLE NORMALIZATION
# ============================================================


def normalize(raw, now):
    source = raw.get("source") or {}

    row = {
        "provider": "perigon",
        "provider_article_id": raw.get("articleId") or raw.get("_id"),
        "headline": raw.get("title") or raw.get("headline") or "",
        "summary": raw.get("description") or raw.get("summary"),
        "body": raw.get("content") or raw.get("body"),
        "source": source.get("domain") if isinstance(source, dict) else source,
        "article_url": raw.get("url") or raw.get("article_url"),
        "published_at": raw.get("pubDate") or raw.get("published_at"),
        "fetched_at": now,
    }

    keys = identities(row)

    row["article_id"] = (
        "live_"
        + hashlib.sha256(keys[0].encode()).hexdigest()[:24]
    )

    return row


# ============================================================
# ARTICLE IDENTITY / DEDUPE
# ============================================================


def identities(article):
    keys = []

    provider_article_id = article.get("provider_article_id")

    if provider_article_id:
        keys.append(
            "id:"
            + article.get("provider", "")
            + ":"
            + str(provider_article_id)
        )

    url = canonical_url(article.get("article_url"))

    if url:
        keys.append("url:" + url)

    # Keep substantive legacy content hashes byte-for-byte. Headline-only rows
    # need URL scope: equal headlines are not evidence of equal articles.
    body_key = "content:" + hashlib.sha256(content(article).encode()).hexdigest()
    if usable_text(article) or not url:
        keys.append(body_key)
    else:
        keys.append("urlcontent:" + hashlib.sha256((url + "\n" + content(article)).encode()).hexdigest())

    cross_key = cross_subdomain_key(article)
    if cross_key:
        keys.append(cross_key)

    fallback = [
        article.get(k)
        for k in (
            "headline",
            "source",
            "published_at",
        )
    ]

    if (
        all(fallback)
        and not article.get("body")
        and not article.get("summary")
        and len(keys) == 1
    ):
        keys.append(
            "fallback:"
            + hashlib.sha256(
                json.dumps(fallback).encode()
            ).hexdigest()
        )

    return keys


# ============================================================
# LIVE PRODUCT INTAKE GATE — V3.2.2
# ============================================================


def live_intake_allow(article, prefilter_result):
    """
    Additive live-product intake gate.

    Frozen V3.1.6 prefilter semantics remain unchanged.

    Purpose:
    Decide whether an article deserves Gemini / full research
    compute.

    This does NOT decide:
    - final event classification
    - geography
    - ticker qualification
    - severity
    - relevance
    - urgency
    - financial impact
    - price direction

    Design:
    - explicit frozen reject -> SKIP
    - entertainment / lifestyle / obvious non-research -> SKIP
    - future preview / expectation / week-ahead content -> SKIP
    - frozen surface -> ALLOW after the above safety filters
    - background -> allow only with narrow research-event evidence
    """

    state = (
        prefilter_result.get("state")
        if isinstance(prefilter_result, dict)
        else None
    )

    # ========================================================
    # FROZEN EXPLICIT REJECT
    # ========================================================

    if state == "reject":
        return False

    # ========================================================
    # SEARCHABLE ARTICLE TEXT
    # ========================================================

    text = " ".join(
        str(article.get(field) or "")
        for field in (
            "headline",
            "summary",
            "body",
        )
    ).lower()

    # ========================================================
    # HARD NON-RESEARCH / ENTERTAINMENT FILTER
    #
    # IMPORTANT:
    # This runs BEFORE accepting frozen surface.
    #
    # Example:
    # "Apple TV: 16 Best Sci-Fi Shows..."
    # may contain Apple and accidentally look company-related,
    # but should never consume research compute.
    # ========================================================

    non_research_signals = (
        "best shows",
        "best movies",
        "best sci-fi",
        "best series",
        "to stream",
        "stream right now",
        "streaming now",
        "what to watch",
        "tv shows",
        "game review",
        "sports review",
        "first odi",
        "test match",
        "cricket",
        "songwriters hall of fame",
        "celebrity",
        "horoscope",
        "recipe",
        "travel guide",
        "gift guide",
    )

    if any(
        signal in text
        for signal in non_research_signals
    ):
        return False

    # ========================================================
    # PREVIEW / EXPECTATION / WEEK-AHEAD FILTER
    #
    # Research Intelligence should prioritize actual events,
    # not generic calendar previews or speculative setup pieces.
    #
    # Examples to skip:
    # - Wall St Week Ahead
    # - investors await CPI
    # - expected to report
    # - inflation data to test rate path
    # ========================================================

    preview_signals = (
        "week ahead",
        "ahead of",
        "expected to",
        "is expected to",
        "forecast",
        "forecasts",
        "investors await",
        "markets await",
        "traders await",
        "to test",
        "could test",
        "may test",
        "preview",
        "what to expect",
        "set to report",
        "due to report",
        "due this week",
        "upcoming",
    )

    if any(
        signal in text
        for signal in preview_signals
    ):
        return False

    # ========================================================
    # EXISTING FROZEN SURFACE
    #
    # Surface remains strong evidence once obvious non-research
    # and preview intent have been filtered.
    # ========================================================

    if state == "surface":
        return True

    # ========================================================
    # DIRECT MAG7 / PLATFORM BUSINESS EVENTS
    #
    # Company mention alone is NOT enough.
    #
    # Require:
    # relevant company/service
    # +
    # meaningful business/operational/financial event signal.
    # ========================================================

    company_signals = (
        "apple",
        "microsoft",
        "nvidia",
        "amazon",
        "alphabet",
        "google",
        "meta",
        "tesla",
        "aws",
        "amazon web services",
        "azure",
    )

    company_event_signals = (
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "forecast cut",
        "guidance cut",
        "guidance raised",
        "layoff",
        "layoffs",
        "job cuts",
        "shutdown",
        "halt",
        "halts",
        "outage",
        "offline",
        "unavailable",
        "launch",
        "recall",
        "investigation",
        "probe",
        "lawsuit",
        "antitrust",
        "regulator",
        "regulatory",
        "export control",
        "export controls",
        "restriction",
        "restrictions",
        "factory",
        "production",
        "capacity",
        "supplier",
        "supply chain",
        "partnership",
        "acquisition",
        "acquires",
        "merger",
        "ban",
        "blocked",
        "approval",
        "approved",
        "orders",
        "shipments",
        "sales",
    )

    if (
        any(
            signal in text
            for signal in company_signals
        )
        and any(
            signal in text
            for signal in company_event_signals
        )
    ):
        return True

    # ========================================================
    # SEMICONDUCTOR INFRASTRUCTURE / CAPACITY
    # ========================================================

    semiconductor_entities = (
        "tsmc",
        "taiwan semiconductor",
        "cowos",
        "advanced packaging",
    )

    semiconductor_event_signals = (
        "capacity",
        "expansion",
        "expand",
        "packaging",
        "factory",
        "fab",
        "plant",
        "production",
        "supply",
        "shortage",
        "constraint",
        "allocation",
        "disruption",
        "shutdown",
    )

    if (
        any(
            signal in text
            for signal in semiconductor_entities
        )
        and any(
            signal in text
            for signal in semiconductor_event_signals
        )
    ):
        return True

    # ========================================================
    # ACTUAL FEDERAL RESERVE / FOMC POLICY ACTION
    #
    # Require actual decision/action wording.
    #
    # "Fed may cut rates" does NOT pass.
    # "Fed holds rates unchanged" does pass.
    # ========================================================

    monetary_institutions = (
        "federal reserve",
        "fomc",
    )

    monetary_action_signals = (
        "holds rates",
        "held rates",
        "rates unchanged",
        "raises rates",
        "raised rates",
        "cuts rates",
        "cut rates",
        "rate decision",
        "policy decision",
    )

    if (
        any(
            signal in text
            for signal in monetary_institutions
        )
        and any(
            signal in text
            for signal in monetary_action_signals
        )
    ):
        return True

    # ========================================================
    # ACTUAL MACRO DATA RELEASE
    #
    # Generic mention of inflation/jobs is NOT enough.
    #
    # Require:
    # macro subject
    # +
    # release/result wording.
    # ========================================================

    macro_data_subjects = (
        "consumer price index",
        "cpi",
        "inflation",
        "payrolls",
        "jobs report",
        "unemployment",
    )

    macro_release_signals = (
        "rose",
        "fell",
        "increased",
        "decreased",
        "came in",
        "was reported",
        "reported",
        "released",
        "data showed",
        "showed",
        "slowed",
        "accelerated",
        "unexpectedly",
    )

    if (
        any(
            signal in text
            for signal in macro_data_subjects
        )
        and any(
            signal in text
            for signal in macro_release_signals
        )
    ):
        return True

    # ========================================================
    # EXPORT CONTROL / ANTITRUST
    #
    # Require policy signal + relevant technology context.
    # ========================================================

    regulatory_signals = (
        "export control",
        "export controls",
        "export restriction",
        "export restrictions",
        "antitrust",
    )

    technology_context = (
        "nvidia",
        "ai chip",
        "ai chips",
        "semiconductor",
        "advanced chip",
        "advanced chips",
        "microsoft",
        "google",
        "alphabet",
        "amazon",
        "meta",
        "apple",
    )

    if (
        any(
            signal in text
            for signal in regulatory_signals
        )
        and any(
            signal in text
            for signal in technology_context
        )
    ):
        return True

    # ========================================================
    # STRAIT OF HORMUZ / CRITICAL SHIPPING DISRUPTION
    #
    # Generic shipping does NOT pass.
    #
    # Require:
    # Strait of Hormuz
    # +
    # physical disruption signal.
    # ========================================================

    if (
        "strait of hormuz" in text
        and any(
            signal in text
            for signal in (
                "blockade",
                "blocked",
                "tanker",
                "attack",
                "attacked",
                "hit",
                "strike",
                "shipping disruption",
                "shipping disrupted",
                "disrupts shipping",
                "closure",
                "closed",
            )
        )
    ):
        return True

    # ========================================================
    # SUPPLY-CHAIN DISRUPTION
    #
    # Require:
    # supply-chain / production disruption
    # +
    # MAG7 / semiconductor context.
    # ========================================================

    supply_chain_signals = (
        "supply chain",
        "factory shutdown",
        "factory halt",
        "production halt",
        "production shutdown",
    )

    relevant_supply_context = (
        "apple",
        "nvidia",
        "microsoft",
        "amazon",
        "google",
        "alphabet",
        "meta",
        "tesla",
        "tsmc",
        "semiconductor",
        "chip",
        "chips",
    )

    if (
        any(
            signal in text
            for signal in supply_chain_signals
        )
        and any(
            signal in text
            for signal in relevant_supply_context
        )
    ):
        return True

    # ========================================================
    # DEFAULT
    # ========================================================

    return False


# ============================================================
# LLM BUDGET
# ============================================================


class Budget:
    """
    Reserve actual requests durably before network I/O,
    including retries.
    """

    def __init__(
        self,
        config,
        state,
        save,
        now,
    ):
        self.config = config
        self.state = state
        self.save = save
        self.now = now
        self.calls = 0

    def reserve(self):
        day = (
            datetime.now(timezone.utc)
            .date()
            .isoformat()
        )

        usage = self.state.setdefault(
            "usage",
            {},
        )

        if (
            self.calls >= self.config.max_calls
            or usage.get(day, 0)
            >= self.config.daily_calls
        ):
            raise ProviderError(
                "quota_deferred"
            )

        usage[day] = (
            usage.get(day, 0)
            + 1
        )

        self.calls += 1

        self.save()


# ============================================================
# BUDGET-AWARE ANALYZER
# ============================================================


class BudgetAnalyzer(Analyzer):

    def __init__(
        self,
        config,
        budget,
        provider=None,
    ):
        self.budget = budget
        self.injected = provider

        super().__init__(
            replace(
                config,
                reprocess=False,
                max_articles=1000,
            )
        )

    def _provider(
        self,
        config,
    ):
        target = (
            self.injected
            or Analyzer._provider(config)
        )

        if target is None:
            return None

        budget = self.budget

        class Guarded:

            def generate(
                self,
                article,
            ):
                budget.reserve()

                return target.generate(
                    article
                )

        return Guarded()


# ============================================================
# LIVE RUNNER
# ============================================================


class LiveRunner:

    def __init__(
        self,
        config,
        llm,
        fetch=None,
        edges=(),
        knowledge=None,
        provider=None,
    ):
        self.config = config
        self.llm = llm
        self.fetch = fetch
        self.edges = edges
        self.knowledge = knowledge
        self.provider = provider

        self.config.state_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Never permit product worker to overwrite frozen output.
        if (
            config.output.name
            != "news_research_live_current.json"
        ):
            raise ValueError(
                "Live output must use its dedicated filename"
            )

    # ========================================================
    # PUBLIC CYCLE
    # ========================================================

    def cycle(
        self,
        now=None,
    ):
        if not self.config.enabled:
            return {
                "pipeline_status": "disabled",
                "gemini_calls_this_cycle": 0,
            }

        lock_path = (
            self.config.state_dir
            / "runner.lock"
        )

        with lock_path.open("a") as lock:

            try:
                fcntl.flock(
                    lock,
                    fcntl.LOCK_EX
                    | fcntl.LOCK_NB,
                )

            except BlockingIOError:
                return {
                    "pipeline_status":
                        "already_running"
                }

            return self._cycle(
                now
                or datetime.now(
                    timezone.utc
                ).isoformat()
            )

    # ========================================================
    # INTERNAL CYCLE
    # ========================================================

    def _cycle(
        self,
        now,
    ):
        c = self.config

        state_path = (
            c.state_dir
            / "state.json"
        )

        state = read_json(
            state_path,
            {
                "seen": {},
                "pending": {},
                "records": {},
                "usage": {},
            },
        )

        save = lambda: atomic_json(
            state_path,
            state,
        )

        stats = {
            "event_count": 0,
            "outlook_count": 0,
            "skip_count": 0,
            "generated_at_utc":
                now,

            "last_successful_fetch_utc":
                state.get(
                    "last_successful_fetch_utc"
                ),

            "provider_fetch_at_utc":
                None,

            "pipeline_status":
                "live",

            "new_article_count":
                0,

            "duplicate_count":
                0,

            "cheap_reject_count":
                0,

            "gemini_cache_hits":
                0,

            "gemini_calls_this_cycle":
                0,

            "quota_deferred_count":
                0,
        }

        # Upgrade alias coverage in place, without a state schema migration.
        stats['duplicate_count'] += rebuild_identity_index(state, identities)
        save()

        # ====================================================
        # CREATE FETCH WINDOW
        # ====================================================

        if not state.get("window"):

            previous = state.get(
                "last_successful_fetch_utc"
            )

            if previous:

                start = (
                    datetime.fromisoformat(
                        previous
                    )
                    - timedelta(
                        seconds=c.overlap
                    )
                )

            else:

                start = (
                    datetime.fromisoformat(
                        now
                    )
                    - timedelta(
                        hours=1
                    )
                )

            state["window"] = {
                "start":
                    start.isoformat(),

                "end":
                    now,

                "page":
                    0,
            }

            save()

        window = (
            state[
                "window"
            ]
        )

        # ====================================================
        # PROVIDER FETCH
        # ====================================================

        try:
            fetch = self.fetch

            if fetch is None:

                from .providers.perigon import (
                    fetch_incremental_page
                )

                fetch = (
                    fetch_incremental_page
                )

            rows = fetch(
                c.query,
                window["start"],
                window["end"],
                window["page"],
                c.page_size,
            )

            if (
                not isinstance(
                    rows,
                    list,
                )
                or any(
                    not isinstance(
                        row,
                        dict,
                    )
                    for row
                    in rows
                )
            ):
                raise ValueError(
                    "Invalid provider page"
                )

            stats[
                "provider_fetch_at_utc"
            ] = now

            # ================================================
            # NORMALIZE + DEDUPE
            # ================================================

            for raw in rows:

                article = normalize(
                    raw,
                    now,
                )

                keys = identities(
                    article
                )

                existing = next(
                    (
                        state[
                            "seen"
                        ][key]

                        for key
                        in keys

                        if key
                        in state[
                            "seen"
                        ]
                    ),
                    None,
                )

                if existing:

                    stats[
                        "duplicate_count"
                    ] += 1

                    for key in keys:
                        state[
                            "seen"
                        ][key] = existing

                    continue

                aid = (
                    article[
                        "article_id"
                    ]
                )

                for key in keys:
                    state[
                        "seen"
                    ][key] = aid

                state[
                    "pending"
                ][aid] = {
                    "article":
                        article,

                    "status":
                        "pending",
                }

                stats[
                    "new_article_count"
                ] += 1

            # ================================================
            # ADVANCE WINDOW
            # ================================================

            if (
                len(rows)
                < c.page_size
            ):

                state[
                    "last_successful_fetch_utc"
                ] = (
                    window[
                        "end"
                    ]
                )

                state[
                    "window"
                ] = None

            else:

                window[
                    "page"
                ] += 1

            save()

            stats[
                "last_successful_fetch_utc"
            ] = (
                state.get(
                    "last_successful_fetch_utc"
                )
            )

        except Exception:

            stats[
                "pipeline_status"
            ] = "degraded"

            stats[
                "reason"
            ] = (
                "Provider unavailable; "
                "showing cached results"
            )

        # ====================================================
        # BUDGET / ANALYZER
        # ====================================================

        budget = Budget(
            c,
            state,
            save,
            now,
        )

        analyzer = BudgetAnalyzer(
            self.llm,
            budget,
            self.provider,
        )

        pending_items = list(
            state[
                "pending"
            ].items()
        )[: c.max_articles]

        # ====================================================
        # PROCESS PENDING ARTICLES
        # ====================================================

        for aid, item in pending_items:

            article = (
                item[
                    "article"
                ]
            )

            try:

                # ============================================
                # LIVE PRODUCT INTAKE GATE
                # ============================================

                prefilter_result = (
                    prefilter(
                        article
                    )
                )

                decision = classify_live_content(article, prefilter_result)
                item['intake'] = decision
                # RESEARCH intake uses the existing backend, not a new schema.
                # Keep its original policy decision in item/record intake audit.
                kind = 'event' if decision['content_type'] == 'research' else decision['content_type']
                stats[kind + '_count'] += 1

                if kind == 'skip':

                    stats[
                        "cheap_reject_count"
                    ] += 1

                    # Identity remains in `seen`.
                    # Therefore skipped articles do not return
                    # repeatedly during overlapping fetches.

                    state[
                        "pending"
                    ].pop(
                        aid,
                        None,
                    )

                    save()

                    continue

                if kind == 'outlook':
                    state['records'][aid] = build_outlook_record(article, decision, now)
                    state['pending'].pop(aid, None)
                    save()
                    continue

                # ============================================
                # FULL V3.1.6 RESEARCH
                # ============================================

                result = (
                    build_research_output_v3(
                        [
                            article
                        ],
                        self.edges,
                        config=(
                            self.llm
                        ),
                        analyzer=(
                            analyzer
                        ),
                        knowledge=(
                            self.knowledge
                        ),
                        now=(
                            now
                        ),
                    )
                )

                record = (
                    result[
                        "articles"
                    ][0]
                )
                record['content_type'] = 'event'
                record['display_type'] = display_type(record)
                record['intake'] = decision

                unusable = (
                    not record.get(
                        "usable",
                        False,
                    )
                )

                enrichment = (
                    record.get(
                        "enrichment"
                    )
                    or {}
                )

                # ============================================
                # ENRICHMENT DEFERRED
                # ============================================

                if (
                    not unusable
                    and enrichment.get(
                        "status"
                    )
                    != "available"
                ):

                    reason = (
                        enrichment.get(
                            "reason"
                        )
                    )

                    if reason in (
                        "quota_deferred",
                        "run_limit",
                    ):

                        item[
                            "status"
                        ] = (
                            "quota_deferred"
                        )

                    else:

                        item[
                            "status"
                        ] = (
                            "enrichment_deferred"
                        )

                    if (
                        item[
                            "status"
                        ]
                        == "quota_deferred"
                    ):

                        stats[
                            "quota_deferred_count"
                        ] += 1

                    stats[
                        "pipeline_status"
                    ] = (
                        "degraded"
                    )

                    state[
                        "pending"
                    ].pop(
                        aid,
                        None,
                    )

                    state[
                        "pending"
                    ][aid] = item

                    continue

                # ============================================
                # CACHE OBSERVABILITY
                # ============================================

                stats[
                    "gemini_cache_hits"
                ] += bool(
                    enrichment.get(
                        "cache_hit"
                    )
                )

                # ============================================
                # STORE COMPLETED RECORD
                # ============================================

                state[
                    "records"
                ][aid] = record

                state[
                    "pending"
                ].pop(
                    aid,
                    None,
                )

                save()

            except Exception:

                # Conservative behavior:
                # keep incomplete record pending and rotate it.

                item[
                    "status"
                ] = (
                    "enrichment_deferred"
                )

                stats[
                    "pipeline_status"
                ] = (
                    "degraded"
                )

                state[
                    "pending"
                ].pop(
                    aid,
                    None,
                )

                state[
                    "pending"
                ][aid] = item

        # ====================================================
        # FINAL CYCLE METRICS
        # ====================================================

        stats[
            "gemini_calls_this_cycle"
        ] = budget.calls

        stats[
            "pending_count"
        ] = len(
            state[
                "pending"
            ]
        )

        # An open pagination window is not an unprocessed-article backlog.
        # Preserve any provider/processing failure status set earlier.
        if stats["pending_count"] or stats["quota_deferred_count"]:

            stats[
                "pipeline_status"
            ] = (
                "degraded"
            )

            stats.setdefault(
                "reason",
                (
                    "Processing backlog; "
                    "showing completed research"
                ),
            )

        save()

        # ====================================================
        # LIVE SNAPSHOT
        # ====================================================

        records = list(
            state[
                "records"
            ].values()
        )[-500:]
        # Compatibility metadata only: do not reclassify existing completed research.
        records = [{**record, 'content_type': record.get('content_type', 'event')} for record in records]

        stats[
            "article_count"
        ] = len(
            records
        )

        atomic_json(
            c.state_dir
            / "status.json",
            stats,
        )

        if records:

            old = read_json(
                c.output,
                {},
            )

            if (
                old.get(
                    "articles"
                )
                != records
            ):

                result = (
                    build_research_output_v3(
                        [],
                        self.edges,
                        config=(
                            Config()
                        ),
                        knowledge=(
                            self.knowledge
                        ),
                        now=(
                            now
                        ),
                    )
                )

                result[
                    "articles"
                ] = records

                # ============================================
                # RESEARCH QUEUE
                # ============================================

                result[
                    "research_queue"
                ] = [
                    {
                        "article_id":
                            record[
                                "article_id"
                            ],

                        "ticker":
                            ticker[
                                "ticker"
                            ],

                        "qualification":
                            ticker.get(
                                "qualification"
                            ),
                    }

                    for record
                    in records

                    for ticker
                    in record.get(
                        "ticker_analysis",
                        [],
                    )
                ]

                # ============================================
                # SUMMARY
                # ============================================

                result[
                    "summary"
                ] = {
                    "event_count": sum(r['content_type'] == 'event' for r in records),
                    "outlook_count": sum(r['content_type'] == 'outlook' for r in records),
                    "articles":
                        len(
                            records
                        ),

                    "surface":
                        sum(
                            record.get(
                                "feed",
                                {},
                            ).get(
                                "state"
                            )
                            == "surface"

                            for record
                            in records
                        ),

                    "noise_rejected":
                        sum(
                            record.get(
                                "feed",
                                {},
                            ).get(
                                "state"
                            )
                            == "reject"

                            for record
                            in records
                        ),

                    "qualified_pairs":
                        sum(
                            str(
                                ticker.get(
                                    "qualification",
                                    "",
                                )
                            ).startswith(
                                "qualified_"
                            )

                            for record
                            in records

                            for ticker
                            in record.get(
                                "ticker_analysis",
                                [],
                            )
                        ),

                    "review_candidates":
                        sum(
                            ticker.get(
                                "qualification"
                            )
                            == (
                                "candidate_"
                                "requires_review"
                            )

                            for record
                            in records

                            for ticker
                            in record.get(
                                "ticker_analysis",
                                [],
                            )
                        ),
                }

                result[
                    "live"
                ] = (
                    stats
                )

                atomic_json(
                    c.output,
                    result,
                )

        return stats


# ============================================================
# CLI ENTRYPOINT
# ============================================================


def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--once",
        action="store_true",
    )

    args = (
        parser.parse_args()
    )

    config = (
        LiveConfig.from_env()
    )

    # ========================================================
    # OPTIONAL MARKET WORKER
    # ========================================================

    if config.market_enabled:

        from threading import (
            Thread,
            Event,
        )

        from .market_snapshot import (
            run_market_loop
        )

        stop = Event()

        if args.once:

            from .market_snapshot import (
                refresh_markets
            )

            refresh_markets(
                config
            )

        else:

            Thread(
                target=(
                    run_market_loop
                ),
                args=(
                    config,
                    stop,
                ),
                daemon=True,
            ).start()

    # ========================================================
    # LIVE NEWS DISABLED
    # ========================================================

    if not config.enabled:

        print(
            "Live ingestion disabled; "
            "frozen/demo mode remains available."
        )

        if (
            config.market_enabled
            and not args.once
        ):

            while True:

                time.sleep(
                    config.market_interval
                )

        return

    # ========================================================
    # EXPOSURE KNOWLEDGE
    # ========================================================

    from .exposure_matcher import (
        load_exposure_edges
    )

    from .pipeline import ROOT

    edges, knowledge = (
        load_exposure_edges(
            ROOT,
            None,
        )
    )

    runner = LiveRunner(
        config,
        Config.from_env(),
        edges=edges,
        knowledge=knowledge,
    )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while True:

        try:

            print(
                json.dumps(
                    runner.cycle()
                )
            )

        except (
            ValueError,
            OSError,
        ):

            print(
                "Live operation unavailable; "
                "last snapshot retained."
            )

        if args.once:
            break

        time.sleep(
            config.interval
        )


if __name__ == "__main__":
    main()
