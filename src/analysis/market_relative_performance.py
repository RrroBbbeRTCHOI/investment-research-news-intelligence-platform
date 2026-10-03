import pandas as pd

from src.config import (
    DEFAULT_BENCHMARK,
    DEFAULT_TECH_BENCHMARK,
)

from src.data.market_data import (
    get_price_history,
)


# =========================================================
# Configuration
# =========================================================

DEFAULT_PERIOD = "5y"

DEFAULT_MARKET_BENCHMARK = DEFAULT_BENCHMARK
DEFAULT_TECH_BENCHMARK = DEFAULT_TECH_BENCHMARK


# =========================================================
# Helpers
# =========================================================

def _prepare_price_series(
    price_history
):
    """
    Convert price history into a clean pandas Series.

    Expected:
        pandas DataFrame returned from the existing
        get_price_history() market-data function.

    Preferred column:
        Close

    Returns:
        pandas Series
    """

    if price_history is None:
        return pd.Series(dtype=float)

    if not isinstance(
        price_history,
        pd.DataFrame
    ):
        return pd.Series(dtype=float)

    if price_history.empty:
        return pd.Series(dtype=float)

    # -----------------------------------------------------
    # Prefer Adjusted Close if available
    # -----------------------------------------------------

    if "Adj Close" in price_history.columns:

        series = price_history[
            "Adj Close"
        ].copy()

    elif "Close" in price_history.columns:

        series = price_history[
            "Close"
        ].copy()

    else:

        return pd.Series(dtype=float)

    # -----------------------------------------------------
    # Clean Series
    # -----------------------------------------------------

    series = pd.to_numeric(
        series,
        errors="coerce"
    )

    series = series.dropna()

    series = series.sort_index()

    return series


def _normalize_to_100(
    series
):
    """
    Rebase a price series to 100.

    Formula:

        normalized_t
        =
        price_t / first_price * 100
    """

    if series is None:
        return pd.Series(dtype=float)

    if series.empty:
        return pd.Series(dtype=float)

    first_value = series.iloc[0]

    if (
        first_value is None
        or first_value == 0
    ):
        return pd.Series(dtype=float)

    return (
        series
        / first_value
        * 100
    )


def _calculate_total_return(
    series
):
    """
    Calculate total return across the full series.

    Formula:

        ending_price / starting_price - 1
    """

    if series is None:
        return None

    if series.empty:
        return None

    if len(series) < 2:
        return None

    first_value = series.iloc[0]
    last_value = series.iloc[-1]

    if first_value in (
        None,
        0
    ):
        return None

    return (
        last_value
        / first_value
    ) - 1


def _align_series(
    company_series,
    market_series,
    tech_series
):
    """
    Align company, SPY and QQQ by common trading dates.

    This ensures all three normalized lines start on
    exactly the same date.
    """

    combined = pd.concat(
        [
            company_series.rename(
                "company"
            ),
            market_series.rename(
                "market"
            ),
            tech_series.rename(
                "tech"
            ),
        ],
        axis=1,
        join="inner"
    )

    combined = combined.dropna()

    combined = combined.sort_index()

    return combined


# =========================================================
# Relative Performance Builder
# =========================================================

def build_market_relative_performance(
    ticker,
    period=DEFAULT_PERIOD,
    market_benchmark=DEFAULT_MARKET_BENCHMARK,
    tech_benchmark=DEFAULT_TECH_BENCHMARK
):
    """
    Build company vs SPY vs QQQ historical performance.

    Returns:
        {
            ticker,
            period,
            benchmarks,
            start_date,
            end_date,
            normalized_history,
            total_return,
            spread_vs_market,
            spread_vs_tech
        }
    """

    ticker = (
        ticker
        .upper()
        .strip()
    )

    market_benchmark = (
        market_benchmark
        .upper()
        .strip()
    )

    tech_benchmark = (
        tech_benchmark
        .upper()
        .strip()
    )

    # -----------------------------------------------------
    # Load Price History
    # -----------------------------------------------------

    company_raw = get_price_history(
        ticker,
        period=period
    )

    market_raw = get_price_history(
        market_benchmark,
        period=period
    )

    tech_raw = get_price_history(
        tech_benchmark,
        period=period
    )

    # -----------------------------------------------------
    # Prepare Price Series
    # -----------------------------------------------------

    company_series = (
        _prepare_price_series(
            company_raw
        )
    )

    market_series = (
        _prepare_price_series(
            market_raw
        )
    )

    tech_series = (
        _prepare_price_series(
            tech_raw
        )
    )

    # -----------------------------------------------------
    # Validate
    # -----------------------------------------------------

    if company_series.empty:

        raise ValueError(
            f"No valid price history "
            f"for {ticker}."
        )

    if market_series.empty:

        raise ValueError(
            f"No valid price history "
            f"for {market_benchmark}."
        )

    if tech_series.empty:

        raise ValueError(
            f"No valid price history "
            f"for {tech_benchmark}."
        )

    # -----------------------------------------------------
    # Align Trading Dates
    # -----------------------------------------------------

    aligned = _align_series(
        company_series,
        market_series,
        tech_series
    )

    if aligned.empty:

        raise ValueError(
            "No overlapping trading dates "
            "between company and benchmarks."
        )

    # -----------------------------------------------------
    # Normalize All Three to 100
    # -----------------------------------------------------

    company_normalized = (
        _normalize_to_100(
            aligned["company"]
        )
    )

    market_normalized = (
        _normalize_to_100(
            aligned["market"]
        )
    )

    tech_normalized = (
        _normalize_to_100(
            aligned["tech"]
        )
    )

    # -----------------------------------------------------
    # Total Returns
    # -----------------------------------------------------

    company_return = (
        _calculate_total_return(
            aligned["company"]
        )
    )

    market_return = (
        _calculate_total_return(
            aligned["market"]
        )
    )

    tech_return = (
        _calculate_total_return(
            aligned["tech"]
        )
    )

    # -----------------------------------------------------
    # Relative Spreads
    # -----------------------------------------------------

    if (
        company_return is None
        or market_return is None
    ):

        spread_vs_market = None

    else:

        spread_vs_market = (
            company_return
            - market_return
        )

    if (
        company_return is None
        or tech_return is None
    ):

        spread_vs_tech = None

    else:

        spread_vs_tech = (
            company_return
            - tech_return
        )

    # -----------------------------------------------------
    # Chart-Friendly History
    # -----------------------------------------------------

    normalized_history = []

    for date in aligned.index:

        normalized_history.append(
            {
                "date":
                    date.strftime(
                        "%Y-%m-%d"
                    ),

                "company":
                    float(
                        company_normalized.loc[
                            date
                        ]
                    ),

                "market":
                    float(
                        market_normalized.loc[
                            date
                        ]
                    ),

                "tech":
                    float(
                        tech_normalized.loc[
                            date
                        ]
                    ),
            }
        )

    # -----------------------------------------------------
    # Final Result
    # -----------------------------------------------------

    return {
        "ticker":
            ticker,

        "period":
            period,

        "benchmarks":
            {
                "market":
                    market_benchmark,

                "tech":
                    tech_benchmark,
            },

        "start_date":
            aligned.index[
                0
            ].strftime(
                "%Y-%m-%d"
            ),

        "end_date":
            aligned.index[
                -1
            ].strftime(
                "%Y-%m-%d"
            ),

        "normalized_history":
            normalized_history,

        "total_return":
            {
                "company":
                    company_return,

                "market":
                    market_return,

                "tech":
                    tech_return,
            },

        "spread_vs_market":
            spread_vs_market,

        "spread_vs_tech":
            spread_vs_tech,
    }


# =========================================================
# Formatting Helpers
# =========================================================

def _format_percent(
    value
):
    """
    Decimal -> percentage string.
    """

    if value is None:
        return "N/A"

    return (
        f"{value * 100:.2f}%"
    )


def _format_pp(
    value
):
    """
    Decimal spread -> percentage points.
    """

    if value is None:
        return "N/A"

    return (
        f"{value * 100:+.2f} pp"
    )


# =========================================================
# Test
# =========================================================

def test_market_relative_performance():

    ticker = "AAPL"

    result = (
        build_market_relative_performance(
            ticker,
            period="5y"
        )
    )

    print("\n")
    print("=" * 75)
    print(
        f"{ticker} MARKET RELATIVE PERFORMANCE TEST"
    )
    print("=" * 75)

    print(
        "\nPeriod:"
    )

    print(
        result[
            "period"
        ]
    )

    print(
        "\nStart Date:"
    )

    print(
        result[
            "start_date"
        ]
    )

    print(
        "\nEnd Date:"
    )

    print(
        result[
            "end_date"
        ]
    )

    print(
        "\nBenchmarks:"
    )

    print(
        result[
            "benchmarks"
        ]
    )

    print(
        "\nTOTAL RETURN"
    )

    print("-" * 75)

    print(
        ticker,
        ":",
        _format_percent(
            result[
                "total_return"
            ][
                "company"
            ]
        )
    )

    print(
        result[
            "benchmarks"
        ][
            "market"
        ],
        ":",
        _format_percent(
            result[
                "total_return"
            ][
                "market"
            ]
        )
    )

    print(
        result[
            "benchmarks"
        ][
            "tech"
        ],
        ":",
        _format_percent(
            result[
                "total_return"
            ][
                "tech"
            ]
        )
    )

    print(
        "\nRELATIVE SPREAD"
    )

    print("-" * 75)

    print(
        f"{ticker} vs "
        f"{result['benchmarks']['market']}:",
        _format_pp(
            result[
                "spread_vs_market"
            ]
        )
    )

    print(
        f"{ticker} vs "
        f"{result['benchmarks']['tech']}:",
        _format_pp(
            result[
                "spread_vs_tech"
            ]
        )
    )

    print(
        "\nNORMALIZED HISTORY"
    )

    print("-" * 75)

    history = result[
        "normalized_history"
    ]

    print(
        "Records:",
        len(history)
    )

    if history:

        print(
            "\nFirst Record:"
        )

        print(
            history[0]
        )

        print(
            "\nLast Record:"
        )

        print(
            history[-1]
        )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    test_market_relative_performance()