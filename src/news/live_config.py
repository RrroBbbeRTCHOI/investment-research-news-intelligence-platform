"""Product-operation settings, separate from frozen research configuration."""

from dataclasses import dataclass
import os
from pathlib import Path


LIVE_OUTPUT = "data/news/research/news_research_live_current.json"


@dataclass
class LiveConfig:
    # =========================================================
    # LIVE NEWS
    # =========================================================

    enabled: bool = False

    # Worker loop interval
    interval: int = 600

    # Incremental fetch overlap window
    overlap: int = 120

    # Maximum articles processed through research per cycle
    max_articles: int = 20

    # Maximum actual LLM requests per cycle
    max_calls: int = 6

    # Maximum actual LLM requests per UTC day
    daily_calls: int = 60

    # Provider page size
    page_size: int = 50

    # Browser Flask polling interval
    poll: int = 45

    # =========================================================
    # MARKET DATA
    # =========================================================

    market_interval: int = 180
    market_enabled: bool = False

    # =========================================================
    # STORAGE
    # =========================================================

    state_dir: Path = Path(
        "data/news/live"
    )

    output: Path = Path(
        LIVE_OUTPUT
    )

    # =========================================================
    # DEFAULT LIVE NEWS QUERY
    #
    # Intentionally narrower than the old version:
    #
    #   Apple OR Microsoft OR Nvidia OR Amazon OR Alphabet
    #   OR Meta OR Tesla OR semiconductor OR economy OR shipping
    #
    # The old "economy" / "shipping" terms were too broad and
    # pulled unrelated sports, politics, entertainment and other
    # general-news stories into the live intake.
    #
    # This query is ONLY the provider intake layer.
    #
    # It does NOT determine:
    # - final event classification
    # - ticker qualification
    # - severity
    # - relevance
    # - urgency
    # - price direction
    #
    # Those remain backend-authoritative.
    # =========================================================

    query: str = (
        "Apple "
        "OR Microsoft "
        "OR Nvidia "
        "OR Amazon "
        "OR Alphabet "
        "OR Google "
        "OR Meta "
        "OR Tesla "
        "OR AWS "
        "OR Azure "
        "OR TSMC "
        "OR semiconductor "
        'OR "AI chip" '
        'OR "export control" '
        'OR "cloud outage" '
        'OR "supply chain" '
        'OR "Federal Reserve" '
        "OR inflation "
        "OR antitrust "
        'OR "Strait of Hormuz"'
    )

    # =========================================================
    # VALIDATION
    # =========================================================

    def __post_init__(self):

        positive_fields = (
            "interval",
            "max_articles",
            "page_size",
            "poll",
            "market_interval",
        )

        for name in positive_fields:

            value = getattr(
                self,
                name,
            )

            if value <= 0:
                raise ValueError(
                    "Positive operation limit required"
                )

        if (
            min(
                self.max_calls,
                self.daily_calls,
                self.overlap,
            ) < 0
        ):
            raise ValueError(
                "Invalid quota or overlap"
            )

        if self.page_size > 100:
            raise ValueError(
                "Invalid quota or page size"
            )

        if (
            self.output.name
            != "news_research_live_current.json"
        ):
            raise ValueError(
                "Live output must use its dedicated filename"
            )

    # =========================================================
    # ENVIRONMENT CONFIG
    # =========================================================

    @classmethod
    def from_env(cls):

        from dotenv import (
            load_dotenv
        )

        load_dotenv(
            override=False
        )

        defaults = cls()

        # -----------------------------------------------------
        # INTEGER ENVIRONMENT VARIABLES
        # -----------------------------------------------------

        mapping = {
            "interval":
                "NEWS_LIVE_INTERVAL_SECONDS",

            "overlap":
                "NEWS_LIVE_OVERLAP_SECONDS",

            "max_articles":
                "NEWS_MAX_ARTICLES_PER_CYCLE",

            "max_calls":
                "NEWS_MAX_LLM_CALLS_PER_CYCLE",

            "daily_calls":
                "NEWS_MAX_LLM_CALLS_PER_DAY",

            "page_size":
                "NEWS_LIVE_PAGE_SIZE",

            "poll":
                "NEWS_UI_POLL_SECONDS",

            "market_interval":
                "NEWS_MARKET_INTERVAL_SECONDS",
        }

        values = {}

        for field_name, env_name in mapping.items():

            default_value = getattr(
                defaults,
                field_name,
            )

            raw_value = os.getenv(
                env_name,
                str(
                    default_value
                ),
            )

            values[
                field_name
            ] = int(
                raw_value
            )

        # -----------------------------------------------------
        # BOOLEANS
        # -----------------------------------------------------

        enabled = (
            os.getenv(
                "NEWS_LIVE_ENABLED",
                "false",
            )
            .strip()
            .lower()
            == "true"
        )

        market_enabled = (
            os.getenv(
                "NEWS_MARKET_ENABLED",
                "false",
            )
            .strip()
            .lower()
            == "true"
        )

        # -----------------------------------------------------
        # PATHS
        # -----------------------------------------------------

        state_dir = Path(
            os.getenv(
                "NEWS_LIVE_STATE_DIR",
                str(
                    defaults.state_dir
                ),
            )
        )

        output = Path(
            os.getenv(
                "NEWS_LIVE_OUTPUT",
                LIVE_OUTPUT,
            )
        )

        # -----------------------------------------------------
        # PROVIDER QUERY
        #
        # NEWS_LIVE_QUERY overrides the built-in query.
        # If the env variable is absent, use the safer default.
        # -----------------------------------------------------

        query = os.getenv(
            "NEWS_LIVE_QUERY",
            defaults.query,
        ).strip()

        if not query:
            query = (
                defaults.query
            )

        # -----------------------------------------------------
        # BUILD CONFIG
        # -----------------------------------------------------

        return cls(
            **values,

            enabled=enabled,

            market_enabled=(
                market_enabled
            ),

            state_dir=(
                state_dir
            ),

            output=(
                output
            ),

            query=(
                query
            ),
        )