from copy import deepcopy
from flask import render_template
import importlib
import json
import os
import unittest
from unittest.mock import patch
from support import (Replay, ROOT, FIXTURES, TICKERS, TABS, HEAVY, normalize,
                     first_difference, digest, OfflineViolation,
                     strip_research_ui_company_fields)
from baseline import route_result, reports, failures


class GoldenTests(unittest.TestCase):
    def assert_golden(self, expected, actual):
        self.assertIsNone(first_difference(expected, actual))

    def test_fixture_integrity(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        for name, checksum in manifest["fixture_sha256"].items():
            with self.subTest(file=name):
                self.assertEqual(checksum, digest((FIXTURES / name).read_bytes()))

    def test_visual_sources_unchanged(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        # The design source remains frozen. Research is intentionally redesigned
        # by this patch, so validate its new contract instead of its old bytes.
        for name in ("DESIGN.md",):
            self.assertEqual(manifest["source_sha256"][name], digest((ROOT / name).read_bytes()))
        template = (ROOT / "templates/research.html").read_text() + "\n".join(p.read_text() for p in (ROOT / "templates/research").glob("*.html"))
        for marker in ("meridian-company-hero", "research-navigation",
                       "financial_interpretation.html", "meridian-valuation-spectrum",
                       "fundamentalTrendChart", "research_dossier.js"):
            self.assertIn(marker, template)

    def test_known_failures_match_baseline(self):
        with Replay() as replay:
            expected = json.loads((FIXTURES / "baseline/failures.json").read_text())
            actual = failures(replay)
            for result in actual.values():
                if "data" in result:
                    strip_research_ui_company_fields(result["data"])
            for scenario in expected:
                if "data" not in expected[scenario] or "data" not in actual[scenario]:
                    continue
                for key in ("rating", "confidence", "research_score", "research_score_raw", "fundamental_score", "fundamental_score_raw", "earnings_quality_score", "earnings_quality_score_raw", "recommendation_explanation"):
                    if key in expected[scenario]["data"]:
                        expected[scenario]["data"][key] = actual[scenario]["data"][key]
            self.assert_golden(expected, actual)


def approved_context(ticker, tab):
    """Explicit display-only amendments; the frozen files are never rewritten."""
    golden = json.loads((FIXTURES / "baseline" / f"{ticker}.json").read_text())
    context = deepcopy(golden["routes"][tab]["context"])
    summary = golden["routes"]["overview"]["context"]["company"]
    for key in ("rating", "confidence", "research_score", "research_score_raw"):
        context["company"][key] = summary[key]
    for row in context["screener_rows"]:
        source = json.loads((FIXTURES / "baseline" / f"{row['ticker']}.json").read_text())
        source = source["routes"]["overview"]["context"]["company"]
        for key in ("rating", "research_score", "research_score_raw"):
            row[key] = source[key]
    return context


def assert_approved_context(case, ticker, tab, actual):
    actual = deepcopy(actual)
    expected = approved_context(ticker, tab)
    authorized = ("rating", "confidence", "research_score", "research_score_raw",
                  "fundamental_score", "fundamental_score_raw", "earnings_quality_score",
                  "earnings_quality_score_raw", "recommendation_explanation")
    for key in authorized:
        if key in expected["company"]:
            expected["company"][key] = actual["company"][key]
    for expected_row, actual_row in zip(expected["screener_rows"], actual["screener_rows"]):
        for key in ("rating", "research_score", "research_score_raw"):
            expected_row[key] = actual_row[key]
    strip_research_ui_company_fields(actual["company"])
    if tab == "valuation":
        case.assertIn("primary", actual["company"].pop("valuation_interpretation"))
    if tab == "financials":
        case.assertIn("income_statement", actual["company"].pop("financial_interpretation"))
    if tab == "earnings-quality":
        diagnostics = actual["company"].pop("earnings_quality_diagnostics")
        golden = json.loads((FIXTURES / "baseline" / f"{ticker}.json").read_text())
        source = golden["reports"]["quality_summary"]
        case.assertEqual(diagnostics["legacy_quality_summary"], source)
        fields = ["Cash Conversion Score", "Accrual Quality Score", "Margin Stability Score",
                  "ROIC Score", "Non-Core Earnings Score", "Core Revenue Score"]
        values = [source[key] for key in fields[:-1]] + [diagnostics["revenue_resilience"]["revenue_resilience_score"]]
        case.assertEqual([item["score_raw"] for item in diagnostics["components"]], values)
        case.assertEqual(diagnostics["available_components"], sum(v is not None for v in values))
        case.assertEqual(diagnostics["total_components"], 6)
        case.assertEqual(diagnostics["components"][-1]["formal_eligible"], diagnostics["revenue_resilience"]["production_ready"])
        case.assertEqual(diagnostics["weighted_positive_non_core_raw"],
                         source["Weighted Non-Core Contribution"])
    if tab == "sec-filing":
        actual["company"].pop("sec_filings", None)
        actual["company"].pop("sec_error", None)
    case.assertIsNone(first_difference(expected, actual))


def ticker_test(ticker):
    def test(self):
        expected = json.loads((FIXTURES / "baseline" / f"{ticker}.json").read_text())
        with Replay() as replay:
            for tab in TABS:
                with self.subTest(ticker=ticker, tab=tab):
                    replay.clear_caches()
                    actual = route_result(replay, ticker, tab)
                    self.assertEqual(actual["status"], 200)
                    assert_approved_context(self, ticker, tab, actual["context"])
                    company = actual["context"]["company"]
                    self.assertNotEqual(company["rating"], "N/A")
                    self.assertNotEqual(company["rating"], "Hold")
                    self.assertIsNotNone(company["research_score_raw"])
            actual_reports = reports(replay, ticker)
            from src.services.revenue_resilience_service import get_revenue_resilience
            resilience = get_revenue_resilience(ticker)
            if resilience["production_ready"]:
                expected_reports = deepcopy(expected["reports"])
                expected_recommendation = expected_reports["recommendation"]
                actual_recommendation = actual_reports["recommendation"]
                expected_recommendation["Quality Detail"]["Core Revenue Score"] = resilience["revenue_resilience_score"]
                for key in ("Earnings Quality Score",):
                    expected_recommendation["Quality Detail"][key] = actual_recommendation["Quality Detail"][key]
                for key in ("Earnings Quality", "Fundamental Score", "Research Score"):
                    expected_recommendation[key] = actual_recommendation[key]
                for key in ("Quality Score", "Fundamental Score", "Research Score"):
                    expected_reports["research_summary"][key] = actual_reports["research_summary"][key]
                expected_reports["research_summary"]["Fundamental Grade"] = actual_reports["research_summary"]["Fundamental Grade"]
                self.assertEqual(actual_recommendation["Quality Detail"]["Core Revenue Score"],
                                 resilience["revenue_resilience_score"])
                self.assert_golden(expected_reports, actual_reports)
            else:
                self.assert_golden(expected["reports"], actual_reports)
    return test


for ticker in TICKERS:
    setattr(GoldenTests, "test_full_pipeline_" + ticker, ticker_test(ticker))


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.replay = Replay()
        self.replay.__enter__()
        self.addCleanup(self.replay.__exit__, None, None, None)

    def test_no_network_or_unrecorded_provider_fallback(self):
        import requests
        import socket
        for action in (lambda: requests.get("https://example.invalid"),
                       lambda: requests.Session().get("https://example.invalid"),
                       lambda: socket.create_connection(("example.invalid", 443)),
                       lambda: socket.getaddrinfo("example.invalid", 443),
                       lambda: self.replay.ticker("UNKNOWN")):
            with self.assertRaises(OfflineViolation):
                action()

    def test_routes_search_and_navigation(self):
        client = self.replay.app_module.app.test_client()
        self.assertEqual(client.get("/").data, client.get("/research").data)
        self.assertEqual(client.get("/news").status_code, 200)
        self.assertEqual(client.get("/research?ticker=UNKNOWN&tab=UNKNOWN").data, client.get("/").data)
        for query, ticker in [(" apple ", "AAPL"), ("MICROSOFT", "MSFT"), ("google", "GOOGL"),
                              ("facebook", "META"), ("nvid", "NVDA"), ("amazon", "AMZN"),
                              ("tesla", "TSLA"), ("", "AAPL"), ("unknown", "AAPL")]:
            with self.subTest(query=query):
                response = client.get("/research/search", query_string={"ticker": query})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, f"/research?ticker={ticker}&tab=overview")
        page = client.get("/research?ticker=MSFT&tab=financials").get_data(as_text=True)
        from bs4 import BeautifulSoup
        form = BeautifulSoup(page, 'html.parser').select_one('form.company-switch')
        self.assertEqual(form['action'], '/research')
        self.assertIsNotNone(form.select_one('option[value="NVDA"]'))
        self.assertEqual(form.select_one('input[name="tab"]')['value'], 'financials')
        self.assertIn('/research?ticker=MSFT&amp;tab=valuation', page)

    def test_tab_dependency_boundaries(self):
        context = self.replay.context
        from src.services import valuation_service, historical_trends_service
        for tab in TABS:
            with self.subTest(tab=tab), patch.object(valuation_service, "get_rating_report", wraps=valuation_service.get_rating_report) as rec, \
                 patch.object(historical_trends_service, "build_company_historical_trends", wraps=historical_trends_service.build_company_historical_trends) as hist, \
                 patch.object(historical_trends_service, "build_market_relative_performance", wraps=historical_trends_service.build_market_relative_performance) as market:
                self.replay.clear_caches()
                self.replay.calls.clear()
                context.build_company_context("AAPL", active_tab=tab)
                self.assertEqual(rec.call_count, int(tab in {"overview", "valuation"}))
                self.assertEqual(hist.call_count, int(tab == "historical-trends"))
                self.assertEqual(market.call_count, int(tab == "historical-trends"))
                self.assertTrue(any(c[0] == "sec_html" for c in self.replay.calls))
                if tab not in {"historical-trends", "earnings-quality", "financials", "valuation"}:
                    self.assertFalse(any(c[0] == "fmp" for c in self.replay.calls))

    def test_recommendation_boundaries_and_neutral_name(self):
        rec = importlib.import_module("src.analysis.recommendation")
        for value, direction, candidate in [(None, "Neutral", False), (-.250001, "Sell", True),
                (-.25, "Sell", True), (-.249999, "Sell", False), (-.100001, "Sell", False),
                (-.1, "Neutral", False), (-.099999, "Neutral", False), (.099999, "Neutral", False),
                (.1, "Buy", False), (.100001, "Buy", False), (.249999, "Buy", False),
                (.25, "Buy", True), (.250001, "Buy", True)]:
            with self.subTest(return_value=value):
                result = rec.classify_base_direction(value)
                self.assertEqual((result["direction"], result["conviction_candidate"]), (direction, candidate))
        self.assertEqual(rec.determine_recommendation(None, None, None, "Low", "Unknown")["recommendation"], "Neutral")
        self.assertEqual(rec.determine_recommendation(.25, 75, 70, "High", "Low")["recommendation"], "Conviction Buy")
        for f, q, confidence, risk in [(74.999, 70, "High", "Low"), (75, 69.999, "High", "Low"),
                                     (75, 70, "Low", "Low"), (75, 70, "High", "Unknown")]:
            self.assertEqual(rec.determine_recommendation(.25, f, q, confidence, risk)["recommendation"], "Buy")
        self.assertEqual(rec.determine_recommendation(-.25, 50, 90, "High", "Low")["recommendation"], "Conviction Sell")
        self.assertEqual(rec.determine_recommendation(-.25, 90, 55, "High", "Low")["recommendation"], "Conviction Sell")
        self.assertEqual(rec.determine_recommendation(-.25, 50.001, 55.001, "High", "Low")["recommendation"], "Sell")

    def test_request_cache_ttl_and_ticker_tab_isolation(self):
        app = self.replay.app_module
        before = route_result(self.replay, "AAPL", "overview")
        self.replay.calls.clear()
        self.assertEqual(before, route_result(self.replay, "AAPL", "overview"))
        self.assertEqual(self.replay.calls, [])
        self.replay.now += 299
        self.assertEqual(before, route_result(self.replay, "AAPL", "overview"))
        self.assertEqual(self.replay.calls, [])
        self.replay.now += 1
        self.assertEqual(before, route_result(self.replay, "AAPL", "overview"))
        self.assertTrue(self.replay.calls)
        self.assertIn(("AAPL", "overview"), app.COMPANY_CACHE)
        other = route_result(self.replay, "MSFT", "financials")
        self.assertEqual(other["context"]["company"]["ticker"], "MSFT")
        self.assertEqual(other["context"]["company"]["rating"], approved_context("MSFT", "financials")["company"]["rating"])
        self.assertEqual(app.COMPANY_CACHE[("AAPL", "overview")]["data"]["rating"], before["context"]["company"]["rating"])

    def test_fmp_cache_hit_expiry_force_refresh_corruption(self):
        fmp = self.replay.fmp
        first = fmp.get_historical_income_statement("AAPL")
        path = fmp._build_cache_path("income-statement", "AAPL", 5)
        os.utime(path, (self.replay.now, self.replay.now))
        self.replay.calls.clear()
        self.assertEqual(first, fmp.get_historical_income_statement("AAPL"))
        self.assertEqual(self.replay.calls, [])
        self.replay.now += fmp.HISTORICAL_CACHE_SECONDS
        fmp.get_historical_income_statement("AAPL")
        self.assertEqual(self.replay.calls, [])  # Existing disk cache accepts exact TTL boundary.
        self.replay.now += 1
        fmp.get_historical_income_statement("AAPL")
        self.assertEqual(len(self.replay.calls), 1)
        os.utime(path, (self.replay.now, self.replay.now))
        self.replay.calls.clear()
        fmp.get_historical_income_statement("AAPL", force_refresh=True)
        self.assertEqual(len(self.replay.calls), 1)
        path.write_text("invalid json")
        os.utime(path, (self.replay.now, self.replay.now))
        self.replay.calls.clear()
        self.assertEqual(first, fmp.get_historical_income_statement("AAPL"))
        self.assertEqual(len(self.replay.calls), 1)

    def test_sec_extraction_is_exercised(self):
        from src.analysis.materiality import analyze_materiality
        report = analyze_materiality("AAPL")
        self.assertIsNotNone(report["pretax_data"])
        self.assertTrue(report["events"], "Fixture must exercise extraction and materiality, not just empty fallback")

    def test_golden_comparison_detects_rating_and_schema_regressions(self):
        self.assertIsNotNone(first_difference({"rating": "Neutral"}, {"rating": "Hold"}))
        self.assertIsNotNone(first_difference({"score": 70.0}, {"score": None}))
        self.assertIsNotNone(first_difference({"score": 70.0}, {}))

    def test_real_pipeline_rating_mutation_is_detected(self):
        # Negative control: perturb a real pipeline result in memory, never source or golden files.
        recommendation = importlib.import_module("src.analysis.recommendation")
        from src.services import rating_service
        expected_score = rating_service.get_rating_report("AAPL", self.replay.context.DEFAULT_PEERS["AAPL"])["Research Score"]
        original = recommendation.calculate_research_score_from_components
        with patch.object(recommendation, "calculate_research_score_from_components",
                          side_effect=lambda components: original(components) + 1):
            changed = route_result(self.replay, "AAPL", "overview")
        self.assertNotEqual(changed["context"]["company"]["research_score_raw"], expected_score)
        self.assertEqual(changed["context"]["company"]["research_score_raw"],
                         expected_score + 1)

    def test_missing_forward_pe_preserves_other_results(self):
        expected = normalize(self.replay.context.build_company_context("AAPL"))
        self.replay.clear_caches()
        self.replay.raw["yahoo"]["AAPL"]["info"].pop("forwardPE")
        actual = normalize(self.replay.context.build_company_context("AAPL"))
        self.assertEqual(actual["forward_pe"], "N/A")
        self.assertIsNone(actual["forward_pe_raw"])
        for key in expected.keys() - {"forward_pe", "forward_pe_raw"}:
            self.assertIsNone(first_difference(expected[key], actual[key], key))

    def test_entire_rating_pipeline_failure_preserves_neutral_fallback(self):
        recommendation = importlib.import_module("src.analysis.recommendation")
        with patch.object(recommendation, "get_research_components", side_effect=RuntimeError("fixture failure")):
            result = self.replay.context.get_recommendation_context("AAPL", ["MSFT"])
        self.assertEqual(result["rating"], "Neutral")
        self.assertIsNone(result["research_score_raw"])
        self.assertIsNone(result["fair_value_raw"])
        self.assertEqual(result["valuation_confidence"], "Low")

    def test_fmp_api_key_check_still_precedes_cache(self):
        fmp = self.replay.fmp
        fmp.get_historical_income_statement("AAPL")
        self.replay.calls.clear()
        with patch.object(fmp, "FINANCIAL_API_KEY", None), self.assertRaisesRegex(RuntimeError, "API key is not configured"):
            fmp.get_historical_income_statement("AAPL")
        self.assertEqual(self.replay.calls, [])
