import json
import time

import requests

from src.config import (
    CACHE_DIR,
    FINANCIAL_API_KEY,
    HISTORICAL_TREND_YEARS,
)


# =========================================================
# Configuration
# =========================================================

FMP_BASE_URL = "https://financialmodelingprep.com/stable"

HISTORICAL_CACHE_DIR = (
    CACHE_DIR
    / "historical_financials"
)

# Historical annual statements change slowly.
# Cache for 7 days.
HISTORICAL_CACHE_SECONDS = 7 * 24 * 60 * 60


# =========================================================
# Cache Setup
# =========================================================

def _ensure_cache_directory():
    """
    Ensure historical cache directory exists.
    """

    HISTORICAL_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def _build_cache_path(
    endpoint,
    ticker,
    years
):
    """
    Build cache path.

    Example:
        AAPL_income_statement_5y.json
    """

    ticker = ticker.upper().strip()

    endpoint_name = (
        endpoint
        .replace("-", "_")
        .replace("/", "_")
    )

    filename = (
        f"{ticker}_"
        f"{endpoint_name}_"
        f"{years}y.json"
    )

    return (
        HISTORICAL_CACHE_DIR
        / filename
    )


# =========================================================
# Cache Read
# =========================================================

def _load_cache(
    endpoint,
    ticker,
    years,
    max_age_seconds=HISTORICAL_CACHE_SECONDS
):
    """
    Load valid cache.

    Returns:
        list -> valid cached data
        None -> missing / expired / invalid
    """

    _ensure_cache_directory()

    cache_path = _build_cache_path(
        endpoint,
        ticker,
        years
    )

    if not cache_path.exists():
        return None

    try:

        file_age = (
            time.time()
            - cache_path.stat().st_mtime
        )

    except OSError:
        return None

    if file_age > max_age_seconds:
        return None

    try:

        with open(
            cache_path,
            "r",
            encoding="utf-8"
        ) as file:

            payload = json.load(file)

    except (
        OSError,
        json.JSONDecodeError
    ):
        return None

    if not isinstance(
        payload,
        dict
    ):
        return None

    data = payload.get("data")

    if not isinstance(
        data,
        list
    ):
        return None

    print(
        f"[CACHE HIT] "
        f"{ticker.upper()} "
        f"{endpoint} "
        f"{years}Y"
    )

    return data


# =========================================================
# Cache Write
# =========================================================

def _save_cache(endpoint, ticker, years, data):
    """Preserve the cache payload and TTL, replacing complete JSON atomically."""
    import os
    import tempfile
    from pathlib import Path
    _ensure_cache_directory()
    cache_path = _build_cache_path(endpoint, ticker, years)
    payload = {'ticker': ticker.upper().strip(), 'endpoint': endpoint,
               'years': years, 'cached_at': int(time.time()), 'data': data}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=cache_path.parent, suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
            json.dump(payload, file, indent=2, ensure_ascii=False)
        os.replace(temporary, cache_path)
    except OSError as error:
        print(f'[CACHE WARNING] Could not save cache: {error}')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# =========================================================
# FMP Request Helper
# =========================================================

def _fmp_get(
    endpoint,
    ticker,
    years,
    force_refresh=False
):
    """
    Cache-first FMP request.

    Order:
        1. Read local cache
        2. If valid, return cached data
        3. Otherwise call FMP
        4. Save response to cache
    """

    ticker = ticker.upper().strip()

    if not FINANCIAL_API_KEY:

        raise RuntimeError(
            "FMP API key is not configured. "
            "Check FINANCIAL_API_KEY in .env."
        )

    # -----------------------------------------------------
    # Cache First
    # -----------------------------------------------------

    if not force_refresh:

        cached_data = _load_cache(
            endpoint,
            ticker,
            years
        )

        if cached_data is not None:
            return cached_data

    # -----------------------------------------------------
    # API Fetch
    # -----------------------------------------------------

    print(
        f"[API FETCH] "
        f"{ticker} "
        f"{endpoint} "
        f"{years}Y"
    )

    url = (
        f"{FMP_BASE_URL}/"
        f"{endpoint}"
    )

    params = {
        "symbol":
            ticker,

        "period":
            "annual",

        "limit":
            years,

        "apikey":
            FINANCIAL_API_KEY,
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

    except requests.RequestException:

        raise RuntimeError(
            f"FMP request failed for "
            f"{ticker} / {endpoint}."
        )

    if response.status_code != 200:

        raise RuntimeError(
            f"FMP returned HTTP "
            f"{response.status_code} "
            f"for {ticker} / {endpoint}."
        )

    try:

        data = response.json()

    except ValueError:

        raise RuntimeError(
            f"FMP returned invalid JSON "
            f"for {ticker} / {endpoint}."
        )

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            f"Unexpected FMP response "
            f"for {ticker} / {endpoint}."
        )

    _save_cache(
        endpoint,
        ticker,
        years,
        data
    )

    return data


# =========================================================
# Raw Historical Statements
# =========================================================

def get_historical_income_statement(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Historical annual income statement.
    """

    return _fmp_get(
        endpoint="income-statement",
        ticker=ticker,
        years=years,
        force_refresh=force_refresh
    )


def get_historical_cash_flow_statement(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Historical annual cash flow statement.
    """

    return _fmp_get(
        endpoint="cash-flow-statement",
        ticker=ticker,
        years=years,
        force_refresh=force_refresh
    )


def get_historical_balance_sheet(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Historical annual balance sheet.
    """

    return _fmp_get(
        endpoint="balance-sheet-statement",
        ticker=ticker,
        years=years,
        force_refresh=force_refresh
    )


# =========================================================
# Simplified Income History
# =========================================================

def get_income_history(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Simplified income statement history.
    """

    raw_data = (
        get_historical_income_statement(
            ticker,
            years=years,
            force_refresh=force_refresh
        )
    )

    result = []

    for row in raw_data:

        result.append(
            {
                "year":
                    row.get("fiscalYear"),

                "date":
                    row.get("date"),

                "revenue":
                    row.get("revenue"),

                "operating_income":
                    row.get("operatingIncome"),

                "net_income":
                    row.get("netIncome"),

                "eps":
                    row.get("eps"),
            }
        )

    return result


# =========================================================
# Simplified Cash Flow History
# =========================================================

def get_cash_flow_history(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Simplified cash flow history.
    """

    raw_data = (
        get_historical_cash_flow_statement(
            ticker,
            years=years,
            force_refresh=force_refresh
        )
    )

    result = []

    for row in raw_data:

        operating_cash_flow = row.get(
            "operatingCashFlow"
        )

        capital_expenditure = row.get(
            "capitalExpenditure"
        )

        free_cash_flow = row.get(
            "freeCashFlow"
        )

        # FMP normally stores CapEx as negative.
        # If freeCashFlow is missing:
        #
        # FCF = OCF + CapEx

        if (
            free_cash_flow is None
            and operating_cash_flow is not None
            and capital_expenditure is not None
        ):

            free_cash_flow = (
                operating_cash_flow
                + capital_expenditure
            )

        result.append(
            {
                "year":
                    row.get("fiscalYear"),

                "date":
                    row.get("date"),

                "operating_cash_flow":
                    operating_cash_flow,

                "capital_expenditure":
                    capital_expenditure,

                "free_cash_flow":
                    free_cash_flow,
            }
        )

    return result


# =========================================================
# Simplified Balance Sheet History
# =========================================================

def get_balance_sheet_history(
    ticker,
    years=HISTORICAL_TREND_YEARS,
    force_refresh=False
):
    """
    Simplified historical balance sheet.

    Important:
    FMP totalDebt uses the provider's own definition.

    Do not directly use total_debt for:
    - ROIC
    - Net Debt
    - Invested Capital

    until accounting definitions are standardized.
    """

    raw_data = (
        get_historical_balance_sheet(
            ticker,
            years=years,
            force_refresh=force_refresh
        )
    )

    result = []

    for row in raw_data:

        result.append(
            {
                "year":
                    row.get("fiscalYear"),

                "date":
                    row.get("date"),

                "cash":
                    row.get(
                        "cashAndCashEquivalents"
                    ),

                "total_assets":
                    row.get(
                        "totalAssets"
                    ),

                "equity":
                    row.get(
                        "totalStockholdersEquity"
                    ),

                "total_debt":
                    row.get(
                        "totalDebt"
                    ),
            }
        )

    return result


# =========================================================
# Cache Utilities
# =========================================================

def clear_historical_cache(
    ticker=None
):
    """
    Clear historical financial cache.

    ticker="AAPL":
        clear only AAPL

    ticker=None:
        clear all historical cache
    """

    _ensure_cache_directory()

    if ticker is None:

        files = list(
            HISTORICAL_CACHE_DIR.glob(
                "*.json"
            )
        )

    else:

        ticker = (
            ticker
            .upper()
            .strip()
        )

        files = list(
            HISTORICAL_CACHE_DIR.glob(
                f"{ticker}_*.json"
            )
        )

    removed = 0

    for file_path in files:

        try:

            file_path.unlink()
            removed += 1

        except OSError:
            pass

    return removed


# =========================================================
# Cache Test
# =========================================================

def test_cache():

    print("\n")
    print("=" * 70)
    print(
        "HISTORICAL CACHE TEST"
    )
    print("=" * 70)

    print(
        "\nCache directory:"
    )

    print(
        HISTORICAL_CACHE_DIR
    )

    print(
        "\nCache lifetime:"
    )

    print(
        f"{HISTORICAL_CACHE_SECONDS} seconds"
    )

    print(
        "(7 days)"
    )


# =========================================================
# Income Statement Test
# =========================================================

def test_income_statement():

    ticker = "AAPL"

    print("\n")
    print("=" * 70)

    print(
        f"{ticker} HISTORICAL "
        f"INCOME STATEMENT TEST"
    )

    print("=" * 70)

    history = get_income_history(
        ticker
    )

    print(
        "\nRecords returned:"
    )

    print(
        len(history)
    )

    for row in history:

        print("\n" + "-" * 70)

        print(
            "Year:",
            row["year"]
        )

        print(
            "Date:",
            row["date"]
        )

        print(
            "Revenue:",
            row["revenue"]
        )

        print(
            "Operating Income:",
            row[
                "operating_income"
            ]
        )

        print(
            "Net Income:",
            row[
                "net_income"
            ]
        )

        print(
            "EPS:",
            row["eps"]
        )


# =========================================================
# Cash Flow Test
# =========================================================

def test_cash_flow():

    ticker = "AAPL"

    print("\n")
    print("=" * 70)

    print(
        f"{ticker} HISTORICAL "
        f"CASH FLOW TEST"
    )

    print("=" * 70)

    history = get_cash_flow_history(
        ticker
    )

    print(
        "\nRecords returned:"
    )

    print(
        len(history)
    )

    for row in history:

        print("\n" + "-" * 70)

        print(
            "Year:",
            row["year"]
        )

        print(
            "Date:",
            row["date"]
        )

        print(
            "Operating Cash Flow:",
            row[
                "operating_cash_flow"
            ]
        )

        print(
            "Capital Expenditure:",
            row[
                "capital_expenditure"
            ]
        )

        print(
            "Free Cash Flow:",
            row[
                "free_cash_flow"
            ]
        )


# =========================================================
# Balance Sheet Test
# =========================================================

def test_balance_sheet():

    ticker = "AAPL"

    print("\n")
    print("=" * 70)

    print(
        f"{ticker} HISTORICAL "
        f"BALANCE SHEET TEST"
    )

    print("=" * 70)

    history = get_balance_sheet_history(
        ticker
    )

    print(
        "\nRecords returned:"
    )

    print(
        len(history)
    )

    for row in history:

        print("\n" + "-" * 70)

        print(
            "Year:",
            row["year"]
        )

        print(
            "Date:",
            row["date"]
        )

        print(
            "Cash:",
            row["cash"]
        )

        print(
            "Total Assets:",
            row[
                "total_assets"
            ]
        )

        print(
            "Equity:",
            row["equity"]
        )

        print(
            "Total Debt:",
            row[
                "total_debt"
            ]
        )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    test_cache()

    test_income_statement()

    test_cash_flow()

    test_balance_sheet()
