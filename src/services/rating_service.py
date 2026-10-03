import logging
from src.data.reuse import scoped
from src.services.cache import cached


@scoped
def build_research_components(ticker, peer_tickers):
    from src.analysis.rating import (
        calculate_growth_score,
        get_quality_summary,
        calculate_financial_health_score,
        calculate_six_month_momentum,
        score_momentum,
        calculate_annualised_volatility,
        score_risk_from_volatility,
        calculate_fundamental_score_from_components,
        analyze_valuation,
        score_valuation_expected_return,
    )

    from src.services.earnings_quality_service import get_scoring_summary
    get_quality_summary = get_scoring_summary

    ticker = ticker.upper().strip()
    growth = calculate_growth_score(ticker)
    quality_summary = get_quality_summary(ticker)
    quality = quality_summary.get("Earnings Quality Score")
    if quality is None:
        quality = quality_summary.get("Score")
    balance_sheet = calculate_financial_health_score(ticker)
    momentum_raw = calculate_six_month_momentum(ticker)
    momentum = score_momentum(momentum_raw)
    volatility = calculate_annualised_volatility(ticker)
    risk = score_risk_from_volatility(volatility)
    components = {
        "Growth": growth,
        "Quality": quality,
        "Balance Sheet": balance_sheet,
        "Momentum": momentum,
        "Risk": risk,
        "Six Month Momentum": momentum_raw,
        "Annualised Volatility": volatility,
        "Quality Details": quality_summary,
    }
    fundamental_score = calculate_fundamental_score_from_components(components)
    components["Fundamental Score"] = fundamental_score
    valuation_detail = {}
    try:
        valuation_detail = analyze_valuation(ticker=ticker, peer_tickers=peer_tickers)
    except Exception as error:
        logging.getLogger(__name__).exception(
            "Valuation analysis failed for %s", ticker
        )
        valuation_detail = {}
    expected_return = valuation_detail.get("expected_return_base")
    valuation_score = score_valuation_expected_return(expected_return)
    components["Valuation"] = valuation_score
    components["Expected Return"] = expected_return
    components["Valuation Confidence"] = valuation_detail.get("valuation_confidence")
    components["Expectation Level"] = valuation_detail.get("expectation_level")
    components["Expectation Risk"] = valuation_detail.get("expectation_risk")
    components["Valuation Details"] = valuation_detail
    return components


@scoped
def build_recommendation(
    ticker,
    peer_tickers,
    get_research_components,
    calculate_research_score_from_components,
):
    from src.analysis.recommendation import (
        determine_recommendation,
        generate_recommendation_explanation,
    )

    ticker = ticker.upper().strip()
    try:
        components = get_research_components(ticker, peer_tickers)
    except Exception as error:
        logging.getLogger(__name__).exception(
            "Research component pipeline failed for %s", ticker
        )
        components = {}
    fundamental_score = components.get("Fundamental Score")
    research_score = calculate_research_score_from_components(components)
    quality_summary = components.get("Quality Details", {}) or {}
    quality_score = components.get("Quality")
    if quality_score is None:
        quality_score = quality_summary.get("Earnings Quality Score")
    if quality_score is None:
        quality_score = quality_summary.get("Score")
    valuation = components.get("Valuation Details", {}) or {}
    expected_return = valuation.get("expected_return_base")
    if expected_return is None:
        expected_return = components.get("Expected Return")
    valuation_confidence = (
        valuation.get("valuation_confidence")
        or components.get("Valuation Confidence")
        or "Low"
    )
    expectation_level = (
        valuation.get("expectation_level")
        or components.get("Expectation Level")
        or "Unknown"
    )
    expectation_risk = (
        valuation.get("expectation_risk")
        or components.get("Expectation Risk")
        or "Unknown"
    )
    recommendation_result = determine_recommendation(
        expected_return=expected_return,
        fundamental_score=fundamental_score,
        quality_score=quality_score,
        valuation_confidence=valuation_confidence,
        expectation_risk=expectation_risk,
    )
    final_recommendation = recommendation_result["recommendation"]
    explanation = generate_recommendation_explanation(
        expected_return=expected_return,
        fundamental_score=fundamental_score,
        research_score=research_score,
        quality_score=quality_score,
        valuation_confidence=valuation_confidence,
        expectation_level=expectation_level,
        expectation_risk=expectation_risk,
    )
    report = {
        "Ticker": ticker,
        "Recommendation": final_recommendation,
        "Base Direction": recommendation_result["base_direction"],
        "Conviction": recommendation_result["conviction"],
        "Fundamental Score": fundamental_score,
        "Earnings Quality": quality_score,
        "Research Score": research_score,
        "Current Price": valuation.get("current_price"),
        "Fair Value Low": valuation.get("fair_value_low"),
        "Fair Value Base": valuation.get("fair_value_base"),
        "Fair Value High": valuation.get("fair_value_high"),
        "Expected Return": expected_return,
        "Valuation Confidence": valuation_confidence,
        "Implied FCFF Growth": valuation.get("implied_fcff_growth"),
        "Expectation Level": expectation_level,
        "Expectation Risk": expectation_risk,
        "Market Premium vs Base DCF": valuation.get("market_premium_vs_base_dcf"),
        "Conviction Gate": recommendation_result["conviction_gate"],
        "Explanation": explanation,
        "Valuation Detail": valuation,
        "Quality Detail": quality_summary,
    }
    return report


@scoped
def get_rating_report(ticker, peers):
    from src.analysis.recommendation import analyze_recommendation

    return cached(
        ("rating", ticker, tuple(peers)),
        lambda: analyze_recommendation(ticker, peers),
        acceptable=lambda result: result.get("Research Score") is not None,
    )
