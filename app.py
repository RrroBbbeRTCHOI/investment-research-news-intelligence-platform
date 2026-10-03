from flask import g
from src.data.reuse import data_scope, state
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
)

import time

from src.ui.research_context import (
    build_company_context,
    build_screener_context,
)


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)
from src.ui.research_dossier import build_research_dossier_context, compact
app.jinja_env.filters['compact'] = compact

@app.before_request
def begin_data_scope():
    g.research_scope = data_scope(persistent=True)
    g.research_scope.__enter__()

@app.teardown_request
def end_data_scope(error):
    scope = g.pop('research_scope', None)
    if scope is not None:
        scope.__exit__(None, None, None)

def cache_timestamp():
    current = state()
    return current['oldest'] if current is not None else time.time()



# =========================================================
# CACHE CONFIGURATION
# =========================================================

CACHE_TTL_SECONDS = 300

SCREENER_CACHE_TTL_SECONDS = 300


# =========================================================
# IN-MEMORY CACHE
# =========================================================

# IMPORTANT:
#
# Company cache is now:
#
#   (ticker, tab)
#
# instead of only:
#
#   ticker
#
# because different tabs load different datasets.

COMPANY_CACHE = {}


# Lightweight screener company cache.
#
# This deliberately does NOT contain the heavy
# recommendation / valuation / historical models.

SCREENER_COMPANY_CACHE = {}


SCREENER_CACHE = {

    "data":
        None,

    "timestamp":
        0,
}


# =========================================================
# RESEARCH UNIVERSE
# =========================================================

RESEARCH_UNIVERSE = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
]


VALID_TABS = {
    "overview",
    "financials",
    "valuation",
    "historical-trends",
    "earnings-quality",
    "financial-health",
    "sec-filing",
    "relevant-events",
}


# =========================================================
# COMPANY DISPLAY NAMES
# =========================================================

COMPANY_NAMES = {

    "AAPL":
        "Apple Inc.",

    "MSFT":
        "Microsoft Corp.",

    "GOOGL":
        "Alphabet Inc.",

    "NVDA":
        "NVIDIA Corp.",

    "AMZN":
        "Amazon.com Inc.",

    "META":
        "Meta Platforms Inc.",

    "TSLA":
        "Tesla Inc.",
}


# =========================================================
# SECTOR MAPPING
# =========================================================

SECTOR_MAP = {

    "AAPL":
        "technology",

    "MSFT":
        "technology",

    "NVDA":
        "technology",

    "GOOGL":
        "communication-services",

    "META":
        "communication-services",

    "AMZN":
        "consumer-cyclical",

    "TSLA":
        "consumer-cyclical",
}


# =========================================================
# SEARCH ALIASES
# =========================================================

SEARCH_ALIASES = {

    "AAPL": "AAPL",
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "APPLE INC.": "AAPL",

    "MSFT": "MSFT",
    "MICROSOFT": "MSFT",
    "MICROSOFT CORP": "MSFT",
    "MICROSOFT CORPORATION": "MSFT",

    "GOOGL": "GOOGL",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "ALPHABET INC": "GOOGL",
    "ALPHABET INC.": "GOOGL",

    "NVDA": "NVDA",
    "NVIDIA": "NVDA",
    "NVIDIA CORP": "NVDA",
    "NVIDIA CORPORATION": "NVDA",

    "AMZN": "AMZN",
    "AMAZON": "AMZN",
    "AMAZON.COM": "AMZN",
    "AMAZON.COM INC": "AMZN",

    "META": "META",
    "META PLATFORMS": "META",
    "META PLATFORMS INC": "META",
    "FACEBOOK": "META",

    "TSLA": "TSLA",
    "TESLA": "TSLA",
    "TESLA INC": "TSLA",
    "TESLA INC.": "TSLA",
}


# =========================================================
# CACHE HELPERS
# =========================================================

def is_cache_fresh(
    timestamp,
    ttl=CACHE_TTL_SECONDS
):

    if not timestamp:
        return False

    age = (
        time.time()
        -
        timestamp
    )

    return (
        age
        <
        ttl
    )


# =========================================================
# COMPANY CONTEXT CACHE
# =========================================================

def get_company_context_cached(
    ticker,
    active_tab
):

    cache_key = (
        ticker,
        active_tab,
    )

    cached_item = (
        COMPANY_CACHE.get(
            cache_key
        )
    )

    if (
        cached_item
        and
        is_cache_fresh(
            cached_item[
                "timestamp"
            ]
        )
    ):

        print(
            f"[CACHE HIT] "
            f"Company: {ticker} "
            f"| Tab: {active_tab}"
        )

        return (
            cached_item[
                "data"
            ]
        )

    print(
        f"[CACHE MISS] "
        f"Company: {ticker} "
        f"| Tab: {active_tab}"
    )

    data = (
        build_company_context(
            ticker=ticker,
            active_tab=active_tab,
        )
    )

    COMPANY_CACHE[
        cache_key
    ] = {

        "data":
            data,

        "timestamp":
            cache_timestamp(),
    }

    return data


# =========================================================
# LIGHTWEIGHT SCREENER COMPANY CACHE
# =========================================================

def get_screener_company_cached(
    ticker
):

    cached_item = (
        SCREENER_COMPANY_CACHE.get(
            ticker
        )
    )

    if (
        cached_item
        and
        is_cache_fresh(
            cached_item[
                "timestamp"
            ]
        )
    ):

        print(
            f"[CACHE HIT] "
            f"Screener Company: {ticker}"
        )

        return (
            cached_item[
                "data"
            ]
        )

    print(
        f"[CACHE MISS] "
        f"Screener Company: {ticker}"
    )

    data = (
        build_screener_context(
            ticker
        )
    )

    SCREENER_COMPANY_CACHE[
        ticker
    ] = {

        "data":
            data,

        "timestamp":
            cache_timestamp(),
    }

    return data


# =========================================================
# BUILD SCREENER
# =========================================================

def build_screener_rows():

    rows = []

    for ticker in (
        RESEARCH_UNIVERSE
    ):

        try:

            data = (
                get_screener_company_cached(
                    ticker
                )
            )

            rows.append({

                # -----------------------------------------
                # Identity
                # -----------------------------------------

                "ticker":
                    ticker,

                "name":
                    data.get(
                        "company_name",
                        COMPANY_NAMES.get(
                            ticker,
                            ticker
                        )
                    ),

                "sector":
                    SECTOR_MAP.get(
                        ticker,
                        "other"
                    ),

                # -----------------------------------------
                # Market Cap
                # -----------------------------------------

                "market_cap":
                    data.get(
                        "market_cap",
                        "N/A"
                    ),

                "market_cap_raw":
                    data.get(
                        "market_cap_raw"
                    ),

                # -----------------------------------------
                # Revenue Growth
                # -----------------------------------------

                "revenue_growth":
                    data.get(
                        "revenue_growth",
                        "N/A"
                    ),

                "revenue_growth_raw":
                    data.get(
                        "revenue_growth_raw"
                    ),

                # -----------------------------------------
                # ROE
                # -----------------------------------------

                "roe":
                    data.get(
                        "roe",
                        "N/A"
                    ),

                "roe_raw":
                    data.get(
                        "roe_raw"
                    ),

                # -----------------------------------------
                # ROIC
                # -----------------------------------------

                "roic":
                    data.get(
                        "roic",
                        "N/A"
                    ),

                "roic_raw":
                    data.get(
                        "roic_raw"
                    ),

                # -----------------------------------------
                # Operating Margin
                # -----------------------------------------

                "operating_margin":
                    data.get(
                        "operating_margin",
                        "N/A"
                    ),

                "operating_margin_raw":
                    data.get(
                        "operating_margin_raw"
                    ),

                # -----------------------------------------
                # P/E
                # -----------------------------------------

                "pe":
                    data.get(
                        "pe",
                        "N/A"
                    ),

                "pe_raw":
                    data.get(
                        "pe_raw"
                    ),

                # -----------------------------------------
                # Research Score
                #
                # Heavy recommendation model is not
                # executed for screener construction.
                # -----------------------------------------

                "research_score":
                    data.get(
                        "research_score",
                        "N/A"
                    ),

                "research_score_raw":
                    data.get(
                        "research_score_raw"
                    ),

                # -----------------------------------------
                # Rating
                # -----------------------------------------

                "rating":
                    data.get(
                        "rating",
                        "N/A"
                    ),
            })

        except Exception as error:

            print(
                f"Screener failed for "
                f"{ticker}: {error}"
            )

            rows.append({

                "ticker":
                    ticker,

                "name":
                    COMPANY_NAMES.get(
                        ticker,
                        ticker
                    ),

                "sector":
                    SECTOR_MAP.get(
                        ticker,
                        "other"
                    ),

                "market_cap":
                    "N/A",

                "market_cap_raw":
                    None,

                "revenue_growth":
                    "N/A",

                "revenue_growth_raw":
                    None,

                "roe":
                    "N/A",

                "roe_raw":
                    None,

                "roic":
                    "N/A",

                "roic_raw":
                    None,

                "operating_margin":
                    "N/A",

                "operating_margin_raw":
                    None,

                "pe":
                    "N/A",

                "pe_raw":
                    None,

                "research_score":
                    "N/A",

                "research_score_raw":
                    None,

                "rating":
                    "N/A",
            })

    return rows


# =========================================================
# SCREENER CACHE
# =========================================================

def get_screener_rows_cached():

    if (
        SCREENER_CACHE[
            "data"
        ]
        is not None
        and
        is_cache_fresh(
            SCREENER_CACHE[
                "timestamp"
            ],
            ttl=SCREENER_CACHE_TTL_SECONDS
        )
    ):

        print(
            "[CACHE HIT] Screener"
        )

        return (
            SCREENER_CACHE[
                "data"
            ]
        )

    print(
        "[CACHE MISS] Screener"
    )

    rows = (
        build_screener_rows()
    )

    SCREENER_CACHE[
        "data"
    ] = rows

    SCREENER_CACHE[
        "timestamp"
    ] = cache_timestamp()

    return rows


# =========================================================
# RESEARCH MODE
# =========================================================

@app.route("/")
@app.route("/research")
def research():

    ticker = (
        request.args.get(
            "ticker",
            "AAPL"
        )
        .upper()
        .strip()
    )

    tab = (
        request.args.get(
            "tab",
            "overview"
        )
        .lower()
        .strip()
    )

    # -----------------------------------------------------
    # Validation
    # -----------------------------------------------------

    if (
        ticker
        not in
        RESEARCH_UNIVERSE
    ):

        ticker = "AAPL"

    if (
        tab
        not in
        VALID_TABS
    ):

        tab = "overview"

    # -----------------------------------------------------
    # Selected Company
    #
    # Important:
    # active_tab is now passed into the context builder.
    # -----------------------------------------------------

    # Build the complete dossier once. Legacy context is retained for downstream
    # integrations, but does not select which sections render.
    dossier = build_research_dossier_context(ticker)
    try:
        company = get_company_context_cached(ticker=ticker, active_tab=tab)
    except Exception:
        app.logger.warning("Legacy Research context unavailable for %s", ticker)
        company = dossier["company"]

    # -----------------------------------------------------
    # Lightweight Screener
    # -----------------------------------------------------

    try:
        screener_rows = get_screener_rows_cached()
    except Exception:
        screener_rows = [{"ticker": symbol} for symbol in RESEARCH_UNIVERSE]

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    return render_template(

        "research.html",

        company=company,

        selected_ticker=ticker,

        active_tab=tab,

        screener_rows=screener_rows,
        dossier=dossier,
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/research/search")
def research_search():

    query = (
        request.args.get(
            "ticker",
            ""
        )
        .upper()
        .strip()
    )

    ticker = (
        SEARCH_ALIASES.get(
            query
        )
    )

    # -----------------------------------------------------
    # Partial Company Name Search
    # -----------------------------------------------------

    if ticker is None:

        for (
            alias,
            mapped_ticker
        ) in (
            SEARCH_ALIASES.items()
        ):

            if (
                query
                and
                query in alias
            ):

                ticker = (
                    mapped_ticker
                )

                break

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    if ticker is None:

        ticker = "AAPL"

    return redirect(

        url_for(

            "research",

            ticker=ticker,

            tab="overview",
        )
    )


# =========================================================
# NEWS MODE
# =========================================================

# News-only snapshot configuration; no provider calls or analytical changes.
import os
from flask import jsonify
from src.news.ui_api import DEFAULT_OUTPUT, read_intelligence
from src.news.ui_api import read_product_intelligence
from src.news.live_config import LiveConfig
news_product_config = LiveConfig.from_env()
app.config['NEWS_INTELLIGENCE_OUTPUT_PATH'] = os.environ.get('NEWS_INTELLIGENCE_OUTPUT_PATH', str(news_product_config.output) if news_product_config.enabled else DEFAULT_OUTPUT)

@app.get('/api/news/intelligence')
def news_intelligence_api():
    payload, status = read_product_intelligence(app.root_path, app.config['NEWS_INTELLIGENCE_OUTPUT_PATH'], news_product_config)
    response = jsonify(payload)
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/api/news/markets')
def news_markets_api():
    from src.news.market_snapshot import read_market_snapshot
    response = jsonify(read_market_snapshot(app.root_path, news_product_config))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.route("/news")
def news():

    return render_template(
        "news.html"
    )


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000,
    )
