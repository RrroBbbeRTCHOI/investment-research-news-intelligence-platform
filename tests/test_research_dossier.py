"""Continuous dossier contracts; frozen analytical outputs remain exact."""
import json
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
from flask import template_rendered
from support import Replay, FIXTURES, ROOT, normalize, first_difference
from src.data.reuse import data_scope
from src.ui import research_dossier as module

class DossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replay = Replay()
        cls.replay.__enter__()
        cls.data = {}
        cls.pages = {}
        for ticker in ("AAPL", "NVDA", "MSFT"):
            with data_scope(persistent=True):
                cls.data[ticker] = module.build_research_dossier_context(ticker)
            response = cls.replay.app_module.app.test_client().get("/research", query_string={"ticker":ticker, "tab":"valuation", "event":"qa-event"})
            assert response.status_code == 200
            cls.pages[ticker] = BeautifulSoup(response.data, "html.parser")

    @classmethod
    def tearDownClass(cls):
        cls.replay.__exit__(None, None, None)

    def test_all_eight_sections_and_legacy_target_for_each_company(self):
        for ticker, page in self.pages.items():
            with self.subTest(ticker=ticker):
                sections = page.select("[data-research-section]")
                self.assertEqual([s.get("data-section-id", s["id"]) for s in sections], [x[0] for x in module.SECTIONS])
                self.assertEqual(page.body["data-initial-section"], "valuation")
                self.assertEqual(page.select_one("#company-switch option[selected]")["value"], ticker)
                self.assertFalse(self.data[ticker]["errors"])
                ids = [el["id"] for el in page.select("[id]")]
                self.assertEqual(len(ids), len(set(ids)), "No duplicate IDs in the continuous dossier")

    def test_company_values_stay_frozen_except_authorized_integrated_rating(self):
        for ticker, dossier in self.data.items():
            expected = json.loads((FIXTURES / "baseline" / (ticker+".json")).read_text())["routes"]["overview"]["context"]["company"]
            for key in ("price_raw","market_cap_raw","revenue_growth_raw","roe_raw","roic_raw","operating_margin_raw","fcf_margin_raw",
                        "pe_raw","forward_pe_raw","fair_value_low_raw","fair_value_raw","fair_value_high_raw",
                        "expected_return_raw"):
                with self.subTest(ticker=ticker, field=key):
                    self.assertEqual(dossier["company"][key], expected[key])
            report = module.rating_service.get_rating_report(ticker, module.DEFAULT_PEERS.get(ticker, []))
            self.assertEqual(dossier["company"]["fundamental_score_raw"], report["Fundamental Score"])
            self.assertEqual(dossier["company"]["research_score_raw"], report["Research Score"])

    def test_six_quality_components_preserve_five_goldens_and_use_v14_resilience(self):
        fields = ["Cash Conversion Score","Accrual Quality Score","Margin Stability Score","ROIC Score","Non-Core Earnings Score"]
        for ticker, dossier in self.data.items():
            golden = json.loads((FIXTURES / "baseline" / (ticker+".json")).read_text())["reports"]["quality_summary"]
            quality = dossier["earnings_quality"]
            components = quality["components"]
            self.assertEqual([c["score_raw"] for c in components[:5]], [golden[k] for k in fields])
            self.assertEqual(quality["legacy_quality_summary"], golden)
            resilience = quality["revenue_resilience"]
            self.assertEqual(components[-1]["score_raw"], resilience["revenue_resilience_score"])
            self.assertEqual(resilience["model_version"], "REVENUE-RESILIENCE-V1.4")
            self.assertEqual(components[-1]["formal_eligible"], resilience["production_ready"])
            self.assertEqual(components[-1]["effective_weight"] is not None, resilience["production_ready"])
            if resilience["production_ready"]:
                self.assertNotEqual(quality["score_raw"], golden["Earnings Quality Score"])
            else:
                self.assertEqual(quality["score_raw"], golden["Earnings Quality Score"])
            self.assertEqual(len(self.pages[ticker].select("[data-quality-component]")), 6)
            self.assertIsNotNone(self.pages[ticker].select_one('[data-quality-component="revenue_resilience"] meter'))

    def test_financial_modes_preserve_exact_service_values_and_interpretation(self):
        for ticker, dossier in self.data.items():
            fi = dossier["financials"]["interpretation"]
            modes = dossier["financials"]["modes"]
            self.assertEqual([m["key"] for m in modes], ["income","cash","balance"])
            for mode, source, key in zip(modes, ["income_statement","cash_flow","balance_sheet"], ["revenue","ocf","cash"]):
                row = next(r for r in mode["rows"] if r["key"] == key)
                self.assertEqual(row["raw"], fi[source]["metrics"][key])
                panel = self.pages[ticker].select_one('[data-statement-panel="'+mode["key"]+'"]')
                self.assertIn(row["current"], panel.get_text())
            income = {row["key"]: row for row in modes[0]["rows"]}
            self.assertIn(income["revenue"]["direction"], ("positive","negative","neutral"))
            self.assertNotEqual(income["eps"]["change"], "—")
            self.assertIn(income["eps"]["direction"], ("positive","negative","neutral"))
            self.assertNotEqual(income["revenue_growth"]["change"], "—")
            balance = {row["key"]: row for row in modes[2]["rows"]}
            debt_change = balance["debt"]["raw"]["change"]
            self.assertEqual(balance["debt"]["direction"], "neutral" if debt_change is None or debt_change == 0 else "positive" if debt_change < 0 else "negative")
            narrative = self.pages[ticker].select_one(".narrative").get_text()
            self.assertIn(dossier["financials"]["analyst_summary"]["text"], narrative)
            self.assertNotIn("arithmetic_supported", narrative)
            self.assertNotIn("Unknown: no supported", narrative)
            for marker in ("moat2-margins","moat2-trends","moat2-working-capital","moat2-priorities","moat2-interpretation"):
                self.assertIsNotNone(self.pages[ticker].select_one("#"+marker))
            self.assertTrue(any(r["key"] == "eps" for r in modes[0]["rows"]))

    def test_chart_payload_equals_production_histories(self):
        for ticker, page in self.pages.items():
            payload = json.loads(page.select_one("#research-chart-data").string)
            self.assertIsNone(first_difference(normalize(self.data[ticker]["historical_trends"]), payload["historical"]))
            self.assertIsNone(first_difference(normalize(self.data[ticker]["financials"]["modes"]), payload["financials"]))
            self.assertTrue(payload["historical"]["market_relative_performance"]["normalized_history"])
            self.assertTrue(payload["historical"]["financials"]["roic"])
            self.assertTrue(payload["historical"]["financials"]["roe"])
            for row in payload["historical"]["financials"]["roe"]:
                self.assertIsNotNone(row["roe"])

    def test_valuation_positions_and_raw_values_are_backend_bound(self):
        for ticker, dossier in self.data.items():
            company = dossier["company"]
            detail = json.loads((FIXTURES / "baseline" / (ticker+".json")).read_text())["reports"]["valuation"]
            expected = [company["fair_value_low_raw"], company["fair_value_raw"], detail["dcf_base"],
                        company["fair_value_high_raw"], company["price_raw"]]
            self.assertEqual([p["raw"] for p in dossier["valuation"]["spectrum"]], expected)
            self.assertEqual([float(n["data-value"]) for n in self.pages[ticker].select(".spectrum-marker")], expected)
            self.assertEqual([p["label"] for p in dossier["valuation"]["spectrum"]],
                             ["Low","Composite fair value","Base DCF","High","Current price"])
            self.assertIn("Premium vs Base DCF", self.pages[ticker].select_one(".valuation-metrics").get_text())

    def test_rating_hierarchy_and_debt_provenance_are_truthful(self):
        for ticker, dossier in self.data.items():
            self.assertEqual([p["label"] for p in dossier["rating"]["profiles"]],
                             ["Fundamental","Valuation","Momentum"])
            methodology = {item["label"]: item for item in dossier["rating"]["methodology"]}
            self.assertEqual(methodology["Profitability"]["display"], "Not separately scored")
            page = self.pages[ticker]
            self.assertIn("55% Fundamental + 30% Valuation + 15% Momentum",
                          page.select_one(".rating-methodology").get_text(" ",strip=True))
            debt = dossier["financial_health"]["balance_sheet"]["metrics"]["debt"]
            fact = debt["current_fact"]
            self.assertEqual(dossier["financial_health_meta"]["debt"]["source"], fact["source"] if fact else "FMP")
            self.assertEqual(dossier["financial_health_meta"]["debt"]["field"], fact["source_field"] if fact else "totalDebt")
            tooltip = page.select_one("#debt-definition").get_text(" ",strip=True)
            self.assertIn("debt-like liabilities beyond SEC term debt", tooltip)
            self.assertIn("No like-for-like SEC debt reconciliation", tooltip)
            resilience = page.select_one('[data-quality-component="revenue_resilience"]')
            self.assertIn("Revenue Resilience", resilience.get_text(" ",strip=True))
            self.assertIn("Diversification", resilience.get_text(" ",strip=True))

    def test_sec_metadata_and_bidirectional_context(self):
        for ticker, dossier in self.data.items():
            page = self.pages[ticker]
            self.assertTrue(dossier["sec_filings"])
            for filing in dossier["sec_filings"]:
                self.assertIn(filing["accession_number"], page.select_one("#sec-filings").get_text())
                self.assertIsNotNone(page.select_one('#sec-filings a[href="'+filing["url"]+'"]'))
            self.assertEqual(page.select_one("#relevant-events")["data-ticker"], ticker)
            self.assertTrue(any("ticker="+ticker in a["href"] and "event=qa-event" in a["href"] for a in page.select('a[href^="/news"]')))
        news_js = (ROOT / "static/js/news_ui.js").read_text()
        self.assertIn("/research?ticker=", news_js)

    def test_no_figma_mock_values_in_rendered_dossier(self):
        forbidden = ("SEDOL","ISIN","12M Outperform","$980","$875.28","$60.92B","$27.02B","32.4x fwd P/E","48.2x","84%+ hyperscale","Multi-Stage DCF","analyst consensus")
        for ticker, page in self.pages.items():
            primary = page.select_one("#research-dossier").get_text(" ", strip=True)
            for value in forbidden:
                self.assertNotIn(value, primary, (ticker, value))

    def test_cached_section_switches_do_not_reload_providers(self):
        client = self.replay.app_module.app.test_client()
        for tab in ("financials","historical-trends","sec-filing","earnings-quality","financial-health","relevant-events"):
            self.replay.calls.clear()
            response = client.get("/research?ticker=AAPL&tab="+tab)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.replay.calls, [], tab)
            soup = BeautifulSoup(response.data, "html.parser")
            self.assertEqual(soup.body["data-initial-section"], "sec-filings" if tab == "sec-filing" else tab)
            self.assertEqual(len(soup.select("[data-research-section]")), 8)

    def test_formatter_missing_negative_and_percentage_points(self):
        self.assertEqual(module.compact(None), "Unavailable")
        self.assertEqual(module.compact(416161000000), "$416.16B")
        self.assertEqual(module.compact(-12715000000), "$-12.71B")
        self.assertEqual(module.compact(.0157,"pp"), "+1.6 pp")
        self.assertEqual(module.compact(-0.00001,"pp"), "0.0 pp")
        self.assertEqual(module.compact(float("nan")), "Unavailable")

class DossierFailureTests(unittest.TestCase):
    def test_analytical_news_vendor_and_globe_sources_remain_byte_identical(self):
        import ast
        import hashlib
        manifest = json.loads((ROOT / "tests/research_dossier_locked_hashes.json").read_text())
        body_hash = manifest.pop("__historical_loader_body__")
        for path, expected in manifest.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)
        source = ast.parse((ROOT / "src/services/historical_trends_service.py").read_text())
        loader = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "_build_historical_trends")
        self.assertEqual(hashlib.sha256(ast.dump(ast.Module(body=loader.body, type_ignores=[])).encode()).hexdigest(), body_hash)
        sec = ast.parse((ROOT / "src/services/sec_filing_service.py").read_text())
        loader = next(n for n in sec.body if isinstance(n, ast.FunctionDef) and n.name == "_build_sec_filing")
        self.assertEqual(hashlib.sha256(ast.dump(ast.Module(body=loader.body, type_ignores=[])).encode()).hexdigest(),
                         "42f1bdb9c7ed5ac8478b58862a2d35936ae294eaed0b372e2370bc0666878162")

    def test_each_section_failure_preserves_other_sections(self):
        targets = [
            ("financials",module,"build_financial_interpretation"),
            ("valuation",module,"build_valuation_interpretation"),
            ("historical-trends",module.historical_trends_service,"build_historical_trends"),
            ("earnings-quality",module,"build_earnings_quality"),
            ("sec-filings",module.sec_filing_service,"build_sec_filing"),
        ]
        with Replay() as replay:
            for key, owner, method in targets:
                with self.subTest(section=key), patch.object(owner,method,side_effect=RuntimeError("isolated test failure")):
                    # Non-persistent scope ensures an earlier dossier cannot hide failure.
                    with data_scope():
                        dossier = module.build_research_dossier_context("AAPL")
                    self.assertIn(key, dossier["errors"])
                    self.assertEqual(dossier["company"]["ticker"],"AAPL")
                    from flask import render_template
                    with replay.app_module.app.test_request_context("/research?ticker=AAPL"):
                        html = render_template("research.html",dossier=dossier,company=dossier["company"],selected_ticker="AAPL",active_tab="overview",screener_rows=[{"ticker":"AAPL"}])
                    self.assertEqual(len(BeautifulSoup(html,"html.parser").select("[data-research-section]")),8)

    def test_legacy_context_failure_does_not_break_route(self):
        with Replay() as replay, patch.object(replay.app_module, "get_company_context_cached",side_effect=RuntimeError("legacy failure")):
            response = replay.app_module.app.test_client().get("/research?ticker=MSFT")
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(BeautifulSoup(response.data,"html.parser").select("[data-research-section]")),8)
