from src.ui.formatters import (
    format_percent,
    format_price,
    format_multiple,
    format_score,
    format_market_cap,
)


def get_empty_recommendation_context():
    return {
        "rating": "N/A",
        "base_direction": "N/A",
        "conviction": False,
        "fundamental_score_raw": None,
        "fundamental_score": "N/A",
        "research_score_raw": None,
        "research_score": "N/A",
        "earnings_quality_score_raw": None,
        "earnings_quality_score": "N/A",
        "fair_value_low_raw": None,
        "fair_value_low": "N/A",
        "fair_value_raw": None,
        "fair_value": "N/A",
        "fair_value_high_raw": None,
        "fair_value_high": "N/A",
        "expected_return_raw": None,
        "expected_return": "N/A",
        "valuation_confidence": "N/A",
        "confidence": "N/A",
        "expectation_level": "N/A",
        "expectation_risk": "N/A",
        "implied_fcff_growth_raw": None,
        "implied_fcff_growth": "N/A",
        "market_premium_raw": None,
        "market_premium": "N/A",
        "recommendation_explanation": "Recommendation model not loaded for this tab.",
        "conviction_gate": None,
    }


def get_empty_historical_financials(ticker):
    return {
        "ticker": ticker,
        "revenue_growth": [],
        "eps_growth": [],
        "operating_margin": [],
        "fcf_margin": [],
    }


def get_empty_market_relative_performance(ticker):
    return {
        "ticker": ticker,
        "period": "5y",
        "benchmarks": {"market": "SPY", "tech": "QQQ"},
        "start_date": None,
        "end_date": None,
        "normalized_history": [],
        "total_return": {"company": None, "market": None, "tech": None},
        "spread_vs_market": None,
        "spread_vs_tech": None,
    }


def adapt_company(raw):
    company_name = raw["company_name"]
    debt_to_equity_raw = raw["debt_to_equity_raw"]
    exchange = raw["exchange"]
    fcf_margin_raw = raw["fcf_margin_raw"]
    forward_pe_raw = raw["forward_pe_raw"]
    market_cap_raw = raw["market_cap_raw"]
    operating_margin_raw = raw["operating_margin_raw"]
    pe_raw = raw["pe_raw"]
    price_raw = raw["price_raw"]
    revenue_growth_raw = raw["revenue_growth_raw"]
    roe_raw = raw["roe_raw"]
    roic_raw = raw["roic_raw"]
    ticker = raw["ticker"]
    enterprise_value_raw = raw.get("enterprise_value_raw")
    daily_change_raw = raw.get("daily_change_raw")
    daily_change_percent_raw = raw.get("daily_change_percent_raw")
    return {
        "ticker": ticker,
        "company_name": company_name,
        "exchange": exchange,
        "price_raw": price_raw,
        "price": format_price(price_raw),
        "market_cap_raw": market_cap_raw,
        "market_cap": format_market_cap(market_cap_raw),
        "revenue_growth_raw": revenue_growth_raw,
        "revenue_growth": format_percent(revenue_growth_raw),
        "roe_raw": roe_raw,
        "roe": format_percent(roe_raw),
        "roic_raw": roic_raw,
        "roic": format_percent(roic_raw),
        "operating_margin_raw": operating_margin_raw,
        "operating_margin": format_percent(operating_margin_raw),
        "fcf_margin_raw": fcf_margin_raw,
        "fcf_margin": format_percent(fcf_margin_raw),
        "debt_to_equity_raw": debt_to_equity_raw,
        "debt_to_equity": format_multiple(debt_to_equity_raw, 2),
        "pe_raw": pe_raw,
        "pe": format_multiple(pe_raw),
        "forward_pe_raw": forward_pe_raw,
        "forward_pe": format_multiple(forward_pe_raw),
        "enterprise_value_raw": enterprise_value_raw,
        "enterprise_value": format_market_cap(enterprise_value_raw),
        "daily_change_raw": daily_change_raw,
        "daily_change": format_price(daily_change_raw),
        "daily_change_percent_raw": daily_change_percent_raw,
        # Yahoo exposes this field in percentage points (for example 0.52 means
        # 0.52%), unlike the ratio-valued fundamental margins above.
        "daily_change_percent": (
            "N/A" if daily_change_percent_raw is None else f"{daily_change_percent_raw:.2f}%"
        ),
        "sector": raw.get("sector") or "Unavailable",
        "industry": raw.get("industry") or "Unavailable",
        "description": raw.get("description") or "Company description unavailable from the current provider.",
    }


def adapt_recommendation(report):
    fundamental_score = report.get("Fundamental Score")
    research_score = report.get("Research Score")
    earnings_quality = report.get("Earnings Quality")
    fair_value_low = report.get("Fair Value Low")
    fair_value_base = report.get("Fair Value Base")
    fair_value_high = report.get("Fair Value High")
    expected_return = report.get("Expected Return")
    implied_fcff_growth = report.get("Implied FCFF Growth")
    market_premium = report.get("Market Premium vs Base DCF")
    valuation_confidence = report.get("Valuation Confidence") or "N/A"
    return {
        "rating": report.get("Recommendation") or "N/A",
        "base_direction": report.get("Base Direction") or "N/A",
        "conviction": bool(report.get("Conviction", False)),
        "fundamental_score_raw": fundamental_score,
        "fundamental_score": format_score(fundamental_score),
        "research_score_raw": research_score,
        "research_score": format_score(research_score),
        "earnings_quality_score_raw": earnings_quality,
        "earnings_quality_score": format_score(earnings_quality),
        "fair_value_low_raw": fair_value_low,
        "fair_value_low": format_price(fair_value_low),
        "fair_value_raw": fair_value_base,
        "fair_value": format_price(fair_value_base),
        "fair_value_high_raw": fair_value_high,
        "fair_value_high": format_price(fair_value_high),
        "expected_return_raw": expected_return,
        "expected_return": format_percent(expected_return),
        "valuation_confidence": valuation_confidence,
        "confidence": valuation_confidence,
        "expectation_level": report.get("Expectation Level") or "N/A",
        "expectation_risk": report.get("Expectation Risk") or "N/A",
        "implied_fcff_growth_raw": implied_fcff_growth,
        "implied_fcff_growth": format_percent(implied_fcff_growth),
        "market_premium_raw": market_premium,
        "market_premium": format_percent(market_premium),
        "recommendation_explanation": report.get("Explanation") or "N/A",
        "conviction_gate": report.get("Conviction Gate"),
    }
