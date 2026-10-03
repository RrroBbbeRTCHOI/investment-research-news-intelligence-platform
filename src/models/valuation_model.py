from src.analysis.valuation import (
    get_current_price,
    calculate_pe,
    calculate_historical_pe_median,
    calculate_peer_median
)


# =========================================================
# Relative Valuation Inputs
# =========================================================

def prepare_relative_valuation_inputs(
    ticker,
    peer_tickers
):
    """
    Prepare shared relative-valuation inputs ONCE.

    Reused by:
        Historical Fair Value
        Peer Fair Value
        Combined Fair Value
    """

    ticker = (
        ticker
        .upper()
        .strip()
    )

    current_price = (
        get_current_price(
            ticker
        )
    )

    current_pe = (
        calculate_pe(
            ticker
        )
    )

    historical_pe = (
        calculate_historical_pe_median(
            ticker
        )
    )

    peer_pe = (
        calculate_peer_median(
            peer_tickers,
            "P/E"
        )
    )

    return {

        "Ticker":
            ticker,

        "Current Price":
            current_price,

        "Current P/E":
            current_pe,

        "Historical Median P/E":
            historical_pe,

        "Peer Median P/E":
            peer_pe
    }


# =========================================================
# Historical Implied Fair Value
# =========================================================

def calculate_historical_fair_value(
    ticker,
    inputs=None
):
    """
    Fair Value =
    Current Price × Historical Median P/E
    ÷ Current P/E
    """

    if inputs is None:

        inputs = (
            prepare_relative_valuation_inputs(
                ticker,
                []
            )
        )

    current_price = (
        inputs.get(
            "Current Price"
        )
    )

    current_pe = (
        inputs.get(
            "Current P/E"
        )
    )

    historical_pe = (
        inputs.get(
            "Historical Median P/E"
        )
    )

    if (
        current_price is None
        or current_pe is None
        or historical_pe is None
    ):
        return None

    if current_pe == 0:
        return None

    return (
        current_price
        * historical_pe
        / current_pe
    )


# =========================================================
# Peer Implied Fair Value
# =========================================================

def calculate_peer_fair_value(
    ticker,
    peer_tickers,
    inputs=None
):
    """
    Fair Value =
    Current Price × Peer Median P/E
    ÷ Current P/E
    """

    if inputs is None:

        inputs = (
            prepare_relative_valuation_inputs(
                ticker,
                peer_tickers
            )
        )

    current_price = (
        inputs.get(
            "Current Price"
        )
    )

    current_pe = (
        inputs.get(
            "Current P/E"
        )
    )

    peer_pe = (
        inputs.get(
            "Peer Median P/E"
        )
    )

    if (
        current_price is None
        or current_pe is None
        or peer_pe is None
    ):
        return None

    if current_pe == 0:
        return None

    return (
        current_price
        * peer_pe
        / current_pe
    )


# =========================================================
# Combined Fair Value
# =========================================================

def calculate_combined_fair_value(
    ticker,
    peer_tickers,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_relative_valuation_inputs(
                ticker,
                peer_tickers
            )
        )

    historical_value = (
        calculate_historical_fair_value(
            ticker,
            inputs=inputs
        )
    )

    peer_value = (
        calculate_peer_fair_value(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    available_values = []

    if historical_value is not None:

        available_values.append(
            historical_value
        )

    if peer_value is not None:

        available_values.append(
            peer_value
        )

    if not available_values:
        return None

    return (
        sum(
            available_values
        )
        / len(
            available_values
        )
    )


# =========================================================
# Upside / Downside
# =========================================================

def calculate_upside(
    ticker,
    peer_tickers,
    inputs=None
):

    if inputs is None:

        inputs = (
            prepare_relative_valuation_inputs(
                ticker,
                peer_tickers
            )
        )

    current_price = (
        inputs.get(
            "Current Price"
        )
    )

    fair_value = (
        calculate_combined_fair_value(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    if (
        current_price is None
        or fair_value is None
        or current_price == 0
    ):
        return None

    return (
        fair_value
        - current_price
    ) / current_price


# =========================================================
# Valuation Signal
# =========================================================

def get_valuation_signal(
    ticker,
    peer_tickers,
    inputs=None
):

    upside = (
        calculate_upside(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    if upside is None:
        return None

    if upside >= 0.20:
        return "Significantly Undervalued"

    elif upside >= 0.10:
        return "Undervalued"

    elif upside > -0.10:
        return "Fairly Valued"

    elif upside > -0.20:
        return "Overvalued"

    return "Significantly Overvalued"


# =========================================================
# Valuation Model Summary
# =========================================================

def get_valuation_model_summary(
    ticker,
    peer_tickers
):

    inputs = (
        prepare_relative_valuation_inputs(
            ticker,
            peer_tickers
        )
    )

    historical_fair_value = (
        calculate_historical_fair_value(
            ticker,
            inputs=inputs
        )
    )

    peer_fair_value = (
        calculate_peer_fair_value(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    combined_fair_value = (
        calculate_combined_fair_value(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    upside = (
        calculate_upside(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    signal = (
        get_valuation_signal(
            ticker,
            peer_tickers,
            inputs=inputs
        )
    )

    return {

        "Ticker":
            ticker.upper(),

        "Current Price":
            inputs.get(
                "Current Price"
            ),

        "Current P/E":
            inputs.get(
                "Current P/E"
            ),

        "Historical Median P/E":
            inputs.get(
                "Historical Median P/E"
            ),

        "Peer Median P/E":
            inputs.get(
                "Peer Median P/E"
            ),

        "Historical Fair Value":
            historical_fair_value,

        "Peer Fair Value":
            peer_fair_value,

        "Combined Fair Value":
            combined_fair_value,

        "Upside / Downside":
            upside,

        "Valuation Signal":
            signal
    }


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    ticker = "AAPL"

    peers = [
        "MSFT",
        "GOOGL",
        "NVDA",
        "AMZN"
    ]

    print("\n==============================")
    print(
        f"VALUATION MODEL: "
        f"{ticker}"
    )
    print("==============================")

    summary = (
        get_valuation_model_summary(
            ticker,
            peers
        )
    )

    for metric, value in (
        summary.items()
    ):

        if value is None:

            print(
                f"{metric}: N/A"
            )

        elif metric == "Ticker":

            print(
                f"{metric}: {value}"
            )

        elif metric in [
            "Current Price",
            "Historical Fair Value",
            "Peer Fair Value",
            "Combined Fair Value"
        ]:

            print(
                f"{metric}: "
                f"${value:,.2f}"
            )

        elif metric == "Upside / Downside":

            print(
                f"{metric}: "
                f"{value:.2%}"
            )

        elif metric == "Valuation Signal":

            print(
                f"{metric}: {value}"
            )

        else:

            print(
                f"{metric}: "
                f"{value:.2f}x"
            )