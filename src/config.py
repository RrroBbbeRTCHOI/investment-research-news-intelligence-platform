import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# Load Environment Variables
# =========================================================

load_dotenv()


# =========================================================
# Project Paths
# =========================================================

# Project root directory
# Example:
# /Users/choisiuhang/Documents/Python Practice/Stock Screener

BASE_DIR = Path(__file__).resolve().parent.parent

# Main data directory
DATA_DIR = BASE_DIR / "data"

# Cache directory
CACHE_DIR = DATA_DIR / "cache"

# Stock database
STOCK_DATABASE_PATH = DATA_DIR / "stocks.csv"

# Watchlist database
WATCHLIST_PATH = DATA_DIR / "watchlist.csv"


# =========================================================
# Environment
# =========================================================

APP_ENV = os.getenv(
    "APP_ENV",
    "development"
)


# =========================================================
# Market Data Configuration
# =========================================================

# Used mainly for:
# - current price
# - market cap
# - historical price
# - SPY / QQQ benchmark performance

MARKET_DATA_PROVIDER = os.getenv(
    "MARKET_DATA_PROVIDER",
    "yfinance"
)

MARKET_API_KEY = os.getenv(
    "MARKET_API_KEY"
)


# =========================================================
# Financial Data Configuration
# =========================================================

# Current plan:
# - FMP for standardized historical financial statements
# - SEC for official filing verification
# - derived ratios calculated internally

FINANCIAL_DATA_PROVIDER = os.getenv(
    "FINANCIAL_DATA_PROVIDER",
    "fmp"
)

FINANCIAL_API_KEY = os.getenv(
    "FINANCIAL_API_KEY"
)


# =========================================================
# News Data Configuration
# =========================================================

NEWS_DATA_PROVIDER = os.getenv(
    "NEWS_DATA_PROVIDER",
    "news_api"
)

NEWS_API_KEY = os.getenv(
    "NEWS_API_KEY"
)


# =========================================================
# SEC Configuration
# =========================================================

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "robertchoi0203@gmail.com"
)


# =========================================================
# Benchmark Configuration
# =========================================================

# Broad market benchmark
DEFAULT_BENCHMARK = os.getenv(
    "DEFAULT_BENCHMARK",
    "SPY"
)

# Technology-heavy benchmark
DEFAULT_TECH_BENCHMARK = os.getenv(
    "DEFAULT_TECH_BENCHMARK",
    "QQQ"
)


# =========================================================
# Historical Trends Configuration
# =========================================================

# Default number of annual periods shown
HISTORICAL_TREND_YEARS = int(
    os.getenv(
        "HISTORICAL_TREND_YEARS",
        "5"
    )
)

# Supported research universe for first version
RESEARCH_UNIVERSE = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
]


# =========================================================
# Rating Model Configuration
# =========================================================

RATING_WEIGHTS = {
    "growth": 0.25,
    "profitability": 0.20,
    "quality": 0.20,
    "valuation": 0.25,
    "financial_health": 0.10,
}


# =========================================================
# Valuation Model Configuration
# =========================================================

VALUATION_WEIGHTS = {
    "historical": 0.30,
    "peer": 0.30,
    "dcf": 0.40,
}


# =========================================================
# News Relevance Configuration
# =========================================================

NEWS_RELEVANCE_THRESHOLD = 0.60

NEWS_HIGH_RELEVANCE_THRESHOLD = 0.80

NEWS_RATING_REVIEW_THRESHOLD = 0.85


# =========================================================
# News Radar Time Windows
# =========================================================

NEWS_RECENT_HOURS = 1

NEWS_ACTIVE_HOURS = 6


# =========================================================
# Cache Configuration
# =========================================================

CACHE_ENABLED = True

MARKET_DATA_CACHE_SECONDS = 300

FINANCIAL_DATA_CACHE_SECONDS = 3600

NEWS_DATA_CACHE_SECONDS = 300


# =========================================================
# Display Configuration
# =========================================================

APP_NAME = "Investment Research Platform"

APP_ICON = "📊"

DEFAULT_PAGE_LAYOUT = "wide"


# =========================================================
# Utility
# =========================================================

def ensure_directories():
    """
    Create required project directories if they do not exist.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# =========================================================
# Configuration Validation
# =========================================================

def validate_financial_api():
    """
    Validate financial data provider configuration.

    Does not make an external API request.
    """

    provider = FINANCIAL_DATA_PROVIDER.lower()

    if provider == "fmp" and not FINANCIAL_API_KEY:
        return False

    return True


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ensure_directories()

    print("=" * 60)
    print("CONFIGURATION TEST")
    print("=" * 60)

    print("\nApplication:")
    print(APP_NAME)

    print("\nEnvironment:")
    print(APP_ENV)

    print("\nProject directory:")
    print(BASE_DIR)

    print("\nData directory:")
    print(DATA_DIR)

    print("\nCache directory:")
    print(CACHE_DIR)

    print("\nStock database:")
    print(STOCK_DATABASE_PATH)

    print("\nMarket data provider:")
    print(MARKET_DATA_PROVIDER)

    print("\nFinancial data provider:")
    print(FINANCIAL_DATA_PROVIDER)

    print("\nFinancial API configured:")
    print(validate_financial_api())

    print("\nDefault benchmark:")
    print(DEFAULT_BENCHMARK)

    print("\nTechnology benchmark:")
    print(DEFAULT_TECH_BENCHMARK)

    print("\nHistorical trend years:")
    print(HISTORICAL_TREND_YEARS)

    print("\nResearch universe:")
    print(RESEARCH_UNIVERSE)

    print("\nRating weights:")
    print(RATING_WEIGHTS)

    print("\nValuation weights:")
    print(VALUATION_WEIGHTS)