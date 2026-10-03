"""Contracts for the in-place Level-5 Research presentation patch."""
import hashlib
import unittest

from bs4 import BeautifulSoup

from support import Replay, ROOT


LOCKED_NEWS_ASSETS = {
    "templates/news.html": "555c01dfe6c2fe281e6da016f65e654ab3cb81b540eece6670be6e639d694396",
    "static/css/news.css": "274640a0ed5f4a77ada03f486eb25dae3c59e0c1d8420219153b9ff5b4b730e4",
    "static/js/news_ui.js": "2b3db50946cfb5825da3499ad56af8611e014aeedbf2c8a8a7ae46d603cb35a7",
    "static/js/news_globe.js": "3d093cbcd25b22f9d47cc857b9266f6f50a0a2f0003eaf31be75552d7bd8cd5f",
    "static/vendor/three/three.module.js": "c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a",
    "static/vendor/three/three.core.js": "eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20",
    "static/vendor/three/OrbitControls.js": "b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c",
}


class ResearchLevel5UITests(unittest.TestCase):
    def test_required_symbols_and_sections_render(self):
        tabs = ("overview", "financials", "valuation", "historical-trends",
                "earnings-quality", "financial-health", "sec-filing",
                "relevant-events")
        with Replay() as replay:
            client = replay.app_module.app.test_client()
            for ticker in ("AAPL", "NVDA", "MSFT"):
                for tab in tabs:
                    with self.subTest(ticker=ticker, tab=tab):
                        page = client.get("/research", query_string={"ticker": ticker, "tab": tab})
                        self.assertEqual(page.status_code, 200)
                        soup = BeautifulSoup(page.data, "html.parser")
                        self.assertEqual(soup.select_one("#company-title").get_text(strip=True),
                                         replay.raw["yahoo"][ticker]["info"]["longName"])
                        nav = soup.select_one("[data-component='research-navigation']")
                        self.assertEqual(nav["data-active-tab"], tab)
                        self.assertEqual(len(nav.select("a")), 8)
                        for link in nav.select("a"):
                            self.assertIn(f"ticker={ticker}", link["href"])

    def test_company_hero_represents_backend_values(self):
        with Replay() as replay:
            company = replay.context.build_company_context("AAPL", active_tab="overview")
            page = replay.app_module.app.test_client().get(
                "/research?ticker=AAPL&tab=overview")
            hero = BeautifulSoup(page.data, "html.parser").select_one(".meridian-company-hero")
            hero_text = hero.get_text(" ", strip=True)
            for field in ("company_name", "ticker", "exchange", "sector", "industry",
                          "description", "price", "market_cap", "enterprise_value",
                          "revenue_growth", "operating_margin", "fcf_margin", "roic"):
                with self.subTest(field=field):
                    self.assertIn(str(company[field]), hero_text)
            fixture = replay.raw["yahoo"]["AAPL"]["info"]
            self.assertEqual(company["enterprise_value_raw"], fixture["enterpriseValue"])
            self.assertEqual(company["market_cap_raw"], fixture["marketCap"])

    def test_editorial_shell_and_real_interactions(self):
        with Replay() as replay:
            client = replay.app_module.app.test_client()
            financial_context = replay.context.build_company_context(
                "AAPL", active_tab="financials")
            financials = BeautifulSoup(client.get(
                "/research?ticker=AAPL&tab=financials").data, "html.parser")
            self.assertIsNotNone(financials.select_one(".meridian-company-hero"))
            self.assertEqual(len(financials.select("[data-statement-target]")), 3)
            self.assertEqual(len(financials.select("[data-statement-panel]")), 3)
            self.assertIsNotNone(financials.select_one("script[src*='research_dossier.js']"))
            interpretation = financial_context["financial_interpretation"]
            checks = (("income", interpretation["income_statement"]["metrics"]["revenue"]["current"]),
                      ("cash", interpretation["cash_flow"]["metrics"]["ocf"]["current"]),
                      ("balance", interpretation["balance_sheet"]["metrics"]["cash"]["current"]))
            for mode, value in checks:
                panel = financials.select_one(f"[data-statement-panel='{mode}']")
                self.assertIsNotNone(panel)
                from src.ui.research_dossier import compact
                self.assertIn(compact(value),
                              panel.get_text(" ", strip=True))
            for restored in ("#moat2-margins", "#moat2-trends", "#moat2-working-capital",
                             "#moat2-priorities", "#moat2-interpretation"):
                self.assertIsNotNone(financials.select_one(restored))
            deep_text = financials.select_one("details.meridian-deep-evidence").get_text(" ", strip=True)
            for evidence_label in ("Effective tax rate", "FCF attribution",
                                   "Margin and cost structure", "Compact annual trend context"):
                self.assertIn(evidence_label, deep_text)

            valuation_context = replay.context.build_company_context(
                "NVDA", active_tab="valuation")
            valuation = BeautifulSoup(client.get(
                "/research?ticker=NVDA&tab=valuation").data, "html.parser")
            spectrum = valuation.select_one(".meridian-valuation-spectrum")
            self.assertIsNotNone(spectrum)
            spectrum_text = spectrum.get_text(" ", strip=True)
            for field in ("price", "fair_value_low", "fair_value", "fair_value_high",
                          "expected_return"):
                self.assertIn(valuation_context[field], spectrum_text)

            quality_context = replay.context.build_company_context(
                "MSFT", active_tab="earnings-quality")["earnings_quality_diagnostics"]
            quality = BeautifulSoup(client.get(
                "/research?ticker=MSFT&tab=earnings-quality").data, "html.parser")
            components = quality.select("[data-quality-component]")
            self.assertEqual(len(components), 6)
            self.assertEqual([node["data-quality-component"] for node in components],
                             [item["key"] for item in quality_context["components"]])
            for node, expected in zip(components, quality_context["components"]):
                text = node.get_text(" ", strip=True)
                self.assertIn(expected["label"], text)
                self.assertIn(expected["score"], text)
            evidence = quality.select_one("details.meridian-quality-evidence")
            self.assertIsNotNone(evidence)
            self.assertFalse(evidence.has_attr("open"))

    def test_financial_interpretation_partial_is_live_and_complete(self):
        research = (ROOT / "templates/research/_financials.html").read_text()
        partial = ROOT / "templates/financial_interpretation.html"
        self.assertTrue(partial.is_file())
        self.assertIn("{% include 'financial_interpretation.html' %}", research)
        source = partial.read_text()
        for contract in ("income_statement", "cash_flow", "balance_sheet",
                         "margin_analysis", "cost_structure", "tax_bridge",
                         "trend_context", "evidence_references", "limitations"):
            self.assertIn(contract, source)

    def test_research_news_context_links_remain_ticker_scoped(self):
        with Replay() as replay:
            client = replay.app_module.app.test_client()
            page = BeautifulSoup(client.get(
                "/research?ticker=NVDA&tab=relevant-events").data, "html.parser")
            self.assertEqual(page.select_one("#relevant-events")["data-ticker"], "NVDA")
            self.assertIn("ticker=NVDA", page.select_one("noscript a")["href"])
            news = client.get("/news?ticker=NVDA")
            self.assertEqual(news.status_code, 200)

    def test_figma_mock_values_are_not_in_production_research_sources(self):
        sources = "\n".join((ROOT / path).read_text() for path in (
            "templates/research.html", "templates/financial_interpretation.html",
            "templates/valuation_interpretation.html", "static/js/research_ui.js",
            "static/js/research_events.js", "static/js/research_dossier.js")) + "\n".join(p.read_text() for p in (ROOT / "templates/research").glob("*.html"))
        figma_only = ("$875.28", "$60.92B", "$27.02B", "$10.99B",
                      "32.4x fwd P/E", "48.2x", "83.3% of Total Rev",
                      "1,570 bps", "3 Correlated Global Events Affecting NVDA Fundamentals Today",
                      "Gross Margin Defense", "Capital Efficiency Moat",
                      "Organic Cash Conversion")
        for value in figma_only:
            with self.subTest(value=value):
                self.assertNotIn(value, sources)

    def test_news_globe_three_and_bloomberg_assets_are_byte_locked(self):
        for path, expected in LOCKED_NEWS_ASSETS.items():
            with self.subTest(path=path):
                actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)
        news = BeautifulSoup((ROOT / "templates/news.html").read_text(), "html.parser")
        self.assertIsNotNone(news.select_one(".right-panel > .bloomberg-live"))
        self.assertIsNotNone(news.select_one("#globe"))


if __name__ == "__main__":
    unittest.main()
