"""Collectors execute real production routes, formulas and report builders."""
import importlib
from flask import template_rendered
from support import normalize, digest


def route_result(replay, ticker, tab):
    app = replay.app_module.app
    seen = []
    def capture(sender, template, context, **extra):
        seen.append({key: context[key] for key in ("company", "selected_ticker", "active_tab", "screener_rows")})
    with template_rendered.connected_to(capture, app):
        response = app.test_client().get("/research", query_string={"ticker": ticker, "tab": tab})
    if response.status_code != 200 or len(seen) != 1:
        raise AssertionError(f"Route {ticker}/{tab}: status={response.status_code}, render_count={len(seen)}")
    return {"status": response.status_code, "context": normalize(seen[0]), "html_sha256": digest(response.data)}


def reports(replay, ticker):
    peers = replay.context.DEFAULT_PEERS[ticker]
    def call(module, function, *args):
        return getattr(importlib.import_module("src." + module), function)(*args)
    return normalize({
        "recommendation": call("analysis.recommendation", "analyze_recommendation", ticker, peers),
        "research_summary": call("analysis.rating", "get_research_summary", ticker, peers),
        "quality_summary": call("analysis.quality", "get_quality_summary", ticker),
        "valuation": call("models.valuation_engine", "analyze_valuation", ticker, peers),
        "dcf_summary": call("models.dcf_model", "get_dcf_summary", ticker),
        "dcf_scenarios": call("models.dcf_model", "get_dcf_scenarios", ticker),
        "market_expectations": call("models.dcf_analysis", "get_market_expectation_summary", ticker),
        "fcff": call("models.fcff_model", "get_fcff_summary", ticker),
        "fundamentals": call("analysis.fundamentals", "get_fundamental_summary", ticker),
        "materiality": call("analysis.materiality", "analyze_materiality", ticker),
        "non_core": call("analysis.non_core_earnings", "analyze_non_core_earnings", ticker),
        "sec_summary": call("data.sec_filings", "get_filing_summary", ticker),
        "sec_classification": call("analysis.filing_classifier", "classify_sec_filing", ticker),
        "historical_financials": call("analysis.historical_trends", "build_company_historical_trends", ticker),
    })


def failures(replay):
    cases = {}
    for kind in ("financials", "sec_html", "fmp", "history"):
        replay.failures.add((kind, "AAPL"))
        tab = "historical-trends" if kind == "fmp" else "overview"
        try:
            try:
                cases[kind] = {"data": normalize(replay.context.build_company_context("AAPL", active_tab=tab))}
            except Exception as error:
                cases[kind] = {"exception": type(error).__name__, "message": str(error)}
        finally:
            replay.failures.clear()
    return cases
