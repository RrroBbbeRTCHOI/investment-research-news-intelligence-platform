"""Additional migration checks. Phase 1 golden snapshots remain authoritative."""
from copy import deepcopy
from bs4 import BeautifulSoup
from test_regression import assert_approved_context
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import unittest
from unittest.mock import patch
from support import Replay, FIXTURES, normalize
from baseline import route_result
from src.data.reuse import data_scope, state, reuse
from src.services import cache


class RefactorTests(unittest.TestCase):
    def setUp(self):
        self.replay = Replay()
        self.replay.__enter__()
        self.addCleanup(self.replay.__exit__, None, None, None)

    def test_each_raw_company_dataset_fetched_once_per_scope(self):
        from src.services.company_service import get_company_data
        with data_scope():
            left = get_company_data('AAPL')
            right = get_company_data('AAPL')
        self.assertEqual(left, right)
        counts = Counter(c[0] for c in self.replay.calls)
        self.assertEqual(counts, {'info': 1, 'history': 1, 'financials': 1,
                                  'balance_sheet': 1, 'cashflow': 1})

    # Keep the legacy provider-budget assertion intact by isolating the newly added
    # producer. Actual Moat 3 transport/cache budgets are checked in test_moat3.
    @patch("src.services.valuation_service.build_valuation_interpretation",
           new=lambda *args, **kwargs: {"primary": {}, "error": "Isolated legacy dependency test"})
    def test_cross_tab_reuses_rating_without_changing_context(self):
        route_result(self.replay, 'AAPL', 'overview')
        self.replay.calls.clear()
        actual = route_result(self.replay, 'AAPL', 'valuation')
        expected = json.loads((FIXTURES/'baseline/AAPL.json').read_text())['routes']['valuation']
        assert_approved_context(self, "AAPL", actual["context"]["active_tab"], actual["context"])
        self.assertEqual(self.replay.calls, [])
        actual = route_result(self.replay, 'AAPL', 'earnings-quality')
        expected = json.loads((FIXTURES/'baseline/AAPL.json').read_text())['routes']['earnings-quality']
        assert_approved_context(self, "AAPL", actual["context"]["active_tab"], actual["context"])
        self.assertEqual(self.replay.calls, [])  # Full dossier already loaded these histories.
        self.replay.calls.clear()
        route_result(self.replay, 'AAPL', 'earnings-quality')
        self.assertEqual(self.replay.calls, [])

    def test_shared_result_cannot_extend_page_freshness(self):
        route_result(self.replay, 'AAPL', 'overview')
        self.replay.now += 200
        route_result(self.replay, 'AAPL', 'valuation')
        self.replay.calls.clear()
        self.replay.now += 100
        route_result(self.replay, 'AAPL', 'valuation')
        self.assertTrue(self.replay.calls, 'Dependent page must expire with its source data')

    def test_request_local_values_are_copied_and_discarded(self):
        from src.data.yahoo_provider import statement
        with data_scope():
            original = statement('AAPL', 'financials')
            original.iloc[0, 0] = -123
            self.assertNotEqual(statement('AAPL', 'financials').iloc[0, 0], -123)
        self.assertIsNone(state())
        self.replay.calls.clear()
        with data_scope():
            statement('AAPL', 'financials')
        self.assertEqual(len(self.replay.calls), 1)

    def test_scope_resets_after_route_exception(self):
        # A section/provider failure now degrades gracefully. Inject an actual
        # unrecoverable rendering failure to retain the teardown-safety contract.
        with patch.dict(self.replay.app_module.app.config, TESTING=True), \
             patch.object(self.replay.app_module, 'render_template', side_effect=RuntimeError('render failure')):
            with self.assertRaisesRegex(RuntimeError, 'render failure'):
                self.replay.app_module.app.test_client().get('/research')
        self.assertIsNone(state())

    def test_transient_failures_are_not_reused(self):
        calls = []
        def load():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError('temporary')
            return 7
        with data_scope():
            with self.assertRaises(ValueError):
                reuse('transient', load)
            self.assertEqual(reuse('transient', load), 7)
        self.assertEqual(len(calls), 2)

    def test_price_definitions_stay_different(self):
        from src.data.market_data import get_current_price as closing
        from src.analysis.valuation import get_current_price as info_price
        with data_scope():
            self.assertNotEqual(closing('AAPL'), info_price('AAPL'))
            self.assertEqual(info_price('AAPL'), self.replay.raw['yahoo']['AAPL']['info']['currentPrice'])

    def test_provider_constructor_and_info_failure_boundaries(self):
        from src.data.market_data import get_company_info as tolerant
        from src.analysis.valuation import get_company_info as strict
        with patch('yfinance.Ticker', side_effect=ValueError('construction')):
            with self.assertRaisesRegex(ValueError, 'construction'):
                tolerant('AAPL')
        self.replay.failures.add(('info', 'AAPL'))
        with data_scope():
            self.assertIsNone(tolerant('AAPL'))
            with self.assertRaises(Exception):
                strict('AAPL')

    def test_service_cache_returns_independent_objects_and_includes_peers(self):
        with data_scope(persistent=True):
            value = cache.cached(('rating', 'AAPL', ('MSFT',)), lambda: {'score': [1]})
            value['score'].append(2)
            self.assertEqual(cache.cached(('rating', 'AAPL', ('MSFT',)), lambda: None), {'score': [1]})
            self.assertEqual(cache.cached(('rating', 'AAPL', ('NVDA',)), lambda: {'score': [3]}), {'score': [3]})

    def test_request_scopes_are_thread_isolated(self):
        barrier = threading.Barrier(2)
        def work(value):
            with data_scope():
                reuse('same-key', lambda: value)
                barrier.wait(timeout=5)
                return reuse('same-key', lambda: -1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(work, [1, 2])), [1, 2])
        self.assertIsNone(state())

    def test_service_cache_coalesces_concurrent_same_key(self):
        barrier = threading.Barrier(4)
        calls = []
        def work(_):
            with data_scope(persistent=True):
                barrier.wait(timeout=5)
                return cache.cached(('concurrent',), lambda: calls.append(1) or {'value': 42})
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(work, range(4)))
        self.assertEqual(values, [{'value': 42}]*4)
        self.assertEqual(len(calls), 1)

    def test_service_cache_bound(self):
        with data_scope(persistent=True):
            for i in range(cache.MAX_ENTRIES + 5):
                cache.cached(('bounded', i), lambda: i)
        self.assertEqual(len(cache._results), cache.MAX_ENTRIES)

    def test_atomic_cache_preserves_previous_file_on_replace_failure(self):
        fmp = self.replay.fmp
        raw = fmp.get_historical_income_statement('AAPL')
        path = fmp._build_cache_path('income-statement', 'AAPL', 5)
        before = path.read_bytes()
        with patch('os.replace', side_effect=OSError('injected replace failure')):
            fmp._save_cache('income-statement', 'AAPL', 5, [])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob('*.tmp')), [])
        self.assertEqual(fmp.get_historical_income_statement('AAPL'), raw)

    def test_quality_service_preserves_report_and_existing_classifications(self):
        from src.services import earnings_quality_service as service
        for classification in ("Very Strong", "Strong", "Moderate", "Weak", "Very Weak", "Unknown"):
            with self.subTest(classification=classification):
                original = {"basic": {}, "recommendation": {"Quality Detail": {
                    "Earnings Quality Score": 0, "Earnings Quality": classification,
                    "Cash Conversion Score": 0, "Core Revenue Score": 99,
                    "Weighted Non-Core Contribution": 0}}}
                before = deepcopy(original)
                result = service.expose_scores(original["recommendation"]["Quality Detail"])
                self.assertEqual(original, before)
                view = self.replay.context.adapt_earnings_quality_diagnostics(result)
                self.assertEqual(view["classification"], classification)
                self.assertEqual(view["score"], "0.0")
                self.assertEqual(view["components"][0]["score"], "0.0")
                self.assertEqual(view["components"][-1]["score"], "Unavailable")
                self.assertEqual(view["available_components"], 1)
                self.assertEqual(view["weighted_positive_non_core"], "0.0%")

    def test_quality_missing_report_is_unavailable(self):
        from src.services import earnings_quality_service as service
        for report in (None, {}, {"Quality Detail": {}}, {"Quality Detail": "invalid"}):
            with self.subTest(report=report):
                result = service.expose_scores((report or {}).get("Quality Detail"))
                view = self.replay.context.adapt_earnings_quality_diagnostics(result)
                self.assertEqual(view["score"], "Unavailable")
                self.assertEqual(view["classification"], "Unknown")
                self.assertEqual(view["available_components"], 0)
                self.assertTrue(all(item["score"] == "Unavailable" for item in view["components"]))
                self.assertEqual(view["weighted_positive_non_core"], "Unavailable")

    # Keep the legacy provider-budget assertion intact by isolating the newly added
    # producer. Actual Moat 3 transport/cache budgets are checked in test_moat3.
    @patch("src.services.valuation_service.build_valuation_interpretation",
           new=lambda *args, **kwargs: {"primary": {}, "error": "Isolated legacy dependency test"})
    def test_quality_adds_no_provider_calls(self):
        counts = []
        for tab in ("valuation", "earnings-quality"):
            self.replay.clear_caches()
            self.replay.calls.clear()
            self.replay.context.build_company_context("AAPL", active_tab=tab)
            counts.append(Counter(self.replay.calls))
        # Approved V1 adds two FMP histories; existing Yahoo/SEC provider work is reused.
        for call in list(counts[1]):
            if call[0] == 'fmp':
                del counts[1][call]
        self.assertEqual(counts[0], counts[1])

    def test_quality_rendered_contract(self):
        from support import TICKERS
        client = self.replay.app_module.app.test_client()
        for ticker in TICKERS:
            with self.subTest(ticker=ticker):
                context = route_result(self.replay, ticker, "earnings-quality")["context"]["company"]
                page = BeautifulSoup(client.get(f"/research?ticker={ticker}&tab=earnings-quality").data, "html.parser")
                section = page.select_one("#earnings-quality")
                self.assertIsNotNone(section)
                self.assertEqual(len(section.select('#moat1-growth tbody tr')), 6)
                self.assertEqual(len(section.select('[data-rule-id]')), 4)
                self.assertIsNotNone(section.select_one('#moat1-interpretation'))
                view = context["earnings_quality_diagnostics"]
                self.assertEqual(section.select_one('[data-quality-field="classification"]').get_text(strip=True), view["classification"])
                for item in view["components"]:
                    card = section.select_one(f'[data-quality-component="{item["key"]}"]')
                    self.assertIn(item["label"], card.get_text())
                    expected = item["score"]
                    self.assertIn(expected, card.select_one('[data-quality-field="component-score"]').get_text())
                self.assertEqual(section.select_one('[data-audit-field="non-core-contribution"]').get_text(strip=True), view["weighted_positive_non_core"])
                for value in (context["fundamental_score"], context["research_score"], context["recommendation_explanation"]):
                    self.assertIn(value, section.get_text())
                self.assertIn("absolute value of pretax income", " ".join(section.get_text().split()))
        self.assertIn('id="earnings-quality-diagnostics"', client.get('/research?tab=overview').get_data(as_text=True))
