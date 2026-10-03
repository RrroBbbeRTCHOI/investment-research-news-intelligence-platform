import math
import pandas as pd

from src.data.financial_data import (
    get_revenue,
    get_net_income,
    get_operating_income,
    get_total_debt,
    get_equity,
    get_free_cash_flow,
)

from src.data.market_data import (
    get_company_info,
    get_current_price,
    get_market_cap,
)

from src.analysis.fundamentals import (
    calculate_roic,
)

from src.analysis.recommendation import (
    analyze_recommendation,
)


# =========================================================
# DEFAULT PEER SETS
# =========================================================

DEFAULT_PEERS = {

    "AAPL": [
        "MSFT",
        "GOOGL",
        "NVDA",
        "AMZN",
    ],

    "MSFT": [
        "AAPL",
        "GOOGL",
        "AMZN",
        "NVDA",
    ],

    "GOOGL": [
        "META",
        "MSFT",
        "AMZN",
    ],

    "NVDA": [
        "AMD",
        "AVGO",
        "INTC",
    ],

    "AMZN": [
        "GOOGL",
        "MSFT",
        "META",
    ],

    "META": [
        "GOOGL",
        "AMZN",
        "MSFT",
    ],

    "TSLA": [
        "GM",
        "F",
    ],
}


# =========================================================
# SAFE HELPERS
# =========================================================

def safe_float(value):

    try:

        if value is None:
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except Exception:
        return None


def latest_value(data):

    if data is None:
        return None

    if isinstance(
        data,
        (int, float)
    ):

        return safe_float(
            data
        )

    if isinstance(
        data,
        pd.Series
    ):

        clean = (
            data
            .dropna()
        )

        if clean.empty:
            return None

        return safe_float(
            clean.iloc[0]
        )

    if isinstance(
        data,
        pd.DataFrame
    ):

        clean = (
            data
            .stack()
            .dropna()
        )

        if clean.empty:
            return None

        return safe_float(
            clean.iloc[0]
        )

    return None


def latest_two_values(data):

    if isinstance(
        data,
        pd.Series
    ):

        clean = (
            data
            .dropna()
        )

        if len(clean) < 2:
            return None, None

        return (
            safe_float(
                clean.iloc[0]
            ),
            safe_float(
                clean.iloc[1]
            )
        )

    if isinstance(
        data,
        pd.DataFrame
    ):

        clean = (
            data
            .stack()
            .dropna()
        )

        if len(clean) < 2:
            return None, None

        return (
            safe_float(
                clean.iloc[0]
            ),
            safe_float(
                clean.iloc[1]
            )
        )

    return None, None


# =========================================================
# FORMATTERS
# =========================================================

def format_percent(
    value,
    decimals=1
):

    value = safe_float(
        value
    )

    if value is None:
        return "N/A"

    return (
        f"{value * 100:.{decimals}f}%"
    )


def format_price(value):

    value = safe_float(
        value
    )

    if value is None:
        return "N/A"

    return (
        f"${value:,.2f}"
    )


def format_multiple(
    value,
    decimals=1
):

    value = safe_float(
        value
    )

    if value is None:
        return "N/A"

    return (
        f"{value:.{decimals}f}x"
    )


def format_score(
    value,
    decimals=1
):

    value = safe_float(
        value
    )

    if value is None:
        return "N/A"

    return (
        f"{value:.{decimals}f}"
    )


def format_market_cap(value):

    value = safe_float(
        value
    )

    if value is None:
        return "N/A"

    if value >= 1_000_000_000_000:

        return (
            f"${value / 1_000_000_000_000:.2f}T"
        )

    if value >= 1_000_000_000:

        return (
            f"${value / 1_000_000_000:.1f}B"
        )

    if value >= 1_000_000:

        return (
            f"${value / 1_000_000:.1f}M"
        )

    return (
        f"${value:,.0f}"
    )


# =========================================================
# BASIC FUNDAMENTAL CALCULATIONS
# =========================================================

def calculate_revenue_growth(
    revenue
):

    current, previous = (
        latest_two_values(
            revenue
        )
    )

    if (
        current is None
        or previous is None
        or previous == 0
    ):

        return None

    return (
        current - previous
    ) / abs(
        previous
    )


def calculate_roe(
    net_income,
    equity
):

    ni = (
        latest_value(
            net_income
        )
    )

    eq = (
        latest_value(
            equity
        )
    )

    if (
        ni is None
        or eq is None
        or eq == 0
    ):

        return None

    return (
        ni / eq
    )


def calculate_operating_margin(
    operating_income,
    revenue
):

    op_income = (
        latest_value(
            operating_income
        )
    )

    rev = (
        latest_value(
            revenue
        )
    )

    if (
        op_income is None
        or rev is None
        or rev == 0
    ):

        return None

    return (
        op_income / rev
    )


def calculate_fcf_margin(
    free_cash_flow,
    revenue
):

    fcf = (
        latest_value(
            free_cash_flow
        )
    )

    rev = (
        latest_value(
            revenue
        )
    )

    if (
        fcf is None
        or rev is None
        or rev == 0
    ):

        return None

    return (
        fcf / rev
    )


def calculate_debt_to_equity(
    debt,
    equity
):

    debt_value = (
        latest_value(
            debt
        )
    )

    equity_value = (
        latest_value(
            equity
        )
    )

    if (
        debt_value is None
        or equity_value is None
        or equity_value == 0
    ):

        return None

    return (
        debt_value
        / equity_value
    )


# =========================================================
# RECOMMENDATION CONTEXT
# =========================================================

def get_recommendation_context(
    ticker,
    peer_tickers
):

    try:

        report = (
            analyze_recommendation(
                ticker=ticker,
                peer_tickers=peer_tickers
            )
        )

    except Exception as error:

        print(
            f"Recommendation analysis failed "
            f"for {ticker}: {error}"
        )

        return {

            "rating":
                "N/A",

            "base_direction":
                "N/A",

            "conviction":
                False,

            "fundamental_score_raw":
                None,

            "fundamental_score":
                "N/A",

            "research_score_raw":
                None,

            "research_score":
                "N/A",

            "earnings_quality_score_raw":
                None,

            "earnings_quality_score":
                "N/A",

            "fair_value_low_raw":
                None,

            "fair_value_low":
                "N/A",

            "fair_value_raw":
                None,

            "fair_value":
                "N/A",

            "fair_value_high_raw":
                None,

            "fair_value_high":
                "N/A",

            "expected_return_raw":
                None,

            "expected_return":
                "N/A",

            "valuation_confidence":
                "N/A",

            "confidence":
                "N/A",

            "expectation_level":
                "N/A",

            "expectation_risk":
                "N/A",

            "implied_fcff_growth_raw":
                None,

            "implied_fcff_growth":
                "N/A",

            "market_premium_raw":
                None,

            "market_premium":
                "N/A",

            "recommendation_explanation":
                "Recommendation unavailable.",

            "conviction_gate":
                None,
        }

    # -----------------------------------------------------
    # RAW OUTPUTS
    # -----------------------------------------------------

    fundamental_score = (
        report.get(
            "Fundamental Score"
        )
    )

    research_score = (
        report.get(
            "Research Score"
        )
    )

    earnings_quality = (
        report.get(
            "Earnings Quality"
        )
    )

    fair_value_low = (
        report.get(
            "Fair Value Low"
        )
    )

    fair_value_base = (
        report.get(
            "Fair Value Base"
        )
    )

    fair_value_high = (
        report.get(
            "Fair Value High"
        )
    )

    expected_return = (
        report.get(
            "Expected Return"
        )
    )

    implied_fcff_growth = (
        report.get(
            "Implied FCFF Growth"
        )
    )

    market_premium = (
        report.get(
            "Market Premium vs Base DCF"
        )
    )

    valuation_confidence = (
        report.get(
            "Valuation Confidence"
        )
        or "N/A"
    )

    # -----------------------------------------------------
    # UI OUTPUT
    # -----------------------------------------------------

    return {

        # Recommendation
        "rating":
            (
                report.get(
                    "Recommendation"
                )
                or "N/A"
            ),

        "base_direction":
            (
                report.get(
                    "Base Direction"
                )
                or "N/A"
            ),

        "conviction":
            bool(
                report.get(
                    "Conviction",
                    False
                )
            ),

        # Fundamental Score
        "fundamental_score_raw":
            fundamental_score,

        "fundamental_score":
            format_score(
                fundamental_score
            ),

        # Research Score
        "research_score_raw":
            research_score,

        "research_score":
            format_score(
                research_score
            ),

        # Earnings Quality
        "earnings_quality_score_raw":
            earnings_quality,

        "earnings_quality_score":
            format_score(
                earnings_quality
            ),

        # Fair Value Range
        "fair_value_low_raw":
            fair_value_low,

        "fair_value_low":
            format_price(
                fair_value_low
            ),

        "fair_value_raw":
            fair_value_base,

        "fair_value":
            format_price(
                fair_value_base
            ),

        "fair_value_high_raw":
            fair_value_high,

        "fair_value_high":
            format_price(
                fair_value_high
            ),

        # Expected Return
        "expected_return_raw":
            expected_return,

        "expected_return":
            format_percent(
                expected_return,
                1
            ),

        # Confidence
        #
        # IMPORTANT:
        # Current model exposes
        # Valuation Confidence.
        #
        # We use the same value in the
        # current UI "confidence" slot.
        #
        # This is NOT renamed internally.
        #
        "valuation_confidence":
            valuation_confidence,

        "confidence":
            valuation_confidence,

        # Expectations
        "expectation_level":
            (
                report.get(
                    "Expectation Level"
                )
                or "N/A"
            ),

        "expectation_risk":
            (
                report.get(
                    "Expectation Risk"
                )
                or "N/A"
            ),

        # Implied Growth
        "implied_fcff_growth_raw":
            implied_fcff_growth,

        "implied_fcff_growth":
            format_percent(
                implied_fcff_growth,
                1
            ),

        # Market Premium
        "market_premium_raw":
            market_premium,

        "market_premium":
            format_percent(
                market_premium,
                1
            ),

        # Explanation
        "recommendation_explanation":
            (
                report.get(
                    "Explanation"
                )
                or "N/A"
            ),

        # Conviction Detail
        "conviction_gate":
            report.get(
                "Conviction Gate"
            ),
    }


# =========================================================
# COMPANY CONTEXT
# =========================================================

def build_company_context(
    ticker,
    peer_tickers=None
):

    ticker = (
        ticker
        .upper()
        .strip()
    )

    # -----------------------------------------------------
    # PEERS
    # -----------------------------------------------------

    if peer_tickers is None:

        peer_tickers = (
            DEFAULT_PEERS.get(
                ticker,
                []
            )
        )

    # -----------------------------------------------------
    # COMPANY INFO
    # -----------------------------------------------------

    info = (
        get_company_info(
            ticker
        )
        or {}
    )

    company_name = (
        info.get(
            "longName"
        )
        or info.get(
            "shortName"
        )
        or ticker
    )

    exchange = (
        info.get(
            "exchange"
        )
        or "N/A"
    )

    # -----------------------------------------------------
    # MARKET DATA
    # -----------------------------------------------------

    price_raw = (
        safe_float(
            get_current_price(
                ticker
            )
        )
    )

    market_cap_raw = (
        safe_float(
            get_market_cap(
                ticker
            )
        )
    )

    pe_raw = (
        safe_float(
            info.get(
                "trailingPE"
            )
        )
    )

    forward_pe_raw = (
        safe_float(
            info.get(
                "forwardPE"
            )
        )
    )

    # -----------------------------------------------------
    # FINANCIAL DATA
    # -----------------------------------------------------

    revenue = (
        get_revenue(
            ticker
        )
    )

    net_income = (
        get_net_income(
            ticker
        )
    )

    operating_income = (
        get_operating_income(
            ticker
        )
    )

    total_debt = (
        get_total_debt(
            ticker
        )
    )

    equity = (
        get_equity(
            ticker
        )
    )

    free_cash_flow = (
        get_free_cash_flow(
            ticker
        )
    )

    # -----------------------------------------------------
    # BASIC FUNDAMENTALS
    # -----------------------------------------------------

    revenue_growth_raw = (
        calculate_revenue_growth(
            revenue
        )
    )

    roe_raw = (
        calculate_roe(
            net_income,
            equity
        )
    )

    operating_margin_raw = (
        calculate_operating_margin(
            operating_income,
            revenue
        )
    )

    fcf_margin_raw = (
        calculate_fcf_margin(
            free_cash_flow,
            revenue
        )
    )

    debt_to_equity_raw = (
        calculate_debt_to_equity(
            total_debt,
            equity
        )
    )

    # -----------------------------------------------------
    # ROIC
    # -----------------------------------------------------

    try:

        roic_raw = (
            calculate_roic(
                ticker
            )
        )

    except Exception as error:

        print(
            f"ROIC calculation failed "
            f"for {ticker}: {error}"
        )

        roic_raw = None

    # -----------------------------------------------------
    # FINAL RESEARCH / RECOMMENDATION ENGINE
    # -----------------------------------------------------

    recommendation = (
        get_recommendation_context(
            ticker,
            peer_tickers
        )
    )

    # -----------------------------------------------------
    # BASE CONTEXT
    # -----------------------------------------------------

    context = {

        # Identity
        "ticker":
            ticker,

        "company_name":
            company_name,

        "exchange":
            exchange,

        "peers":
            peer_tickers,

        # Market
        "price_raw":
            price_raw,

        "price":
            format_price(
                price_raw
            ),

        "market_cap_raw":
            market_cap_raw,

        "market_cap":
            format_market_cap(
                market_cap_raw
            ),

        # Revenue Growth
        "revenue_growth_raw":
            revenue_growth_raw,

        "revenue_growth":
            format_percent(
                revenue_growth_raw
            ),

        # ROE
        "roe_raw":
            roe_raw,

        "roe":
            format_percent(
                roe_raw
            ),

        # ROIC
        "roic_raw":
            roic_raw,

        "roic":
            format_percent(
                roic_raw
            ),

        # Operating Margin
        "operating_margin_raw":
            operating_margin_raw,

        "operating_margin":
            format_percent(
                operating_margin_raw
            ),

        # FCF Margin
        "fcf_margin_raw":
            fcf_margin_raw,

        "fcf_margin":
            format_percent(
                fcf_margin_raw
            ),

        # Debt / Equity
        "debt_to_equity_raw":
            debt_to_equity_raw,

        "debt_to_equity":
            format_multiple(
                debt_to_equity_raw,
                2
            ),

        # P/E
        "pe_raw":
            pe_raw,

        "pe":
            format_multiple(
                pe_raw
            ),

        # Forward P/E
        "forward_pe_raw":
            forward_pe_raw,

        "forward_pe":
            format_multiple(
                forward_pe_raw
            ),
    }

    # -----------------------------------------------------
    # ADD FINAL MODEL OUTPUT
    # -----------------------------------------------------

    context.update(
        recommendation
    )

    return context