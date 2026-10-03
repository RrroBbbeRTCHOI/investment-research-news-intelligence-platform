"""EQ must consume valid recorded history without requiring live credentials."""
import os
import unittest
from unittest.mock import patch

from support import Replay, TICKERS
from src.data.earnings_quality_inputs import load_eq_inputs
from src.analysis.earnings_quality_diagnostics import cash_history, growth_decomposition
from src.analysis.earnings_quality_evidence import statement_evidence


class CacheWiringTests(unittest.TestCase):
    def seed(self, replay, ticker):
        for endpoint in ('income-statement', 'cash-flow-statement',
                         'balance-sheet-statement'):
            key = f'{ticker}:{endpoint}:5'
            if key in replay.raw['fmp']:
                replay.fmp._save_cache(endpoint, ticker, 5, replay.raw['fmp'][key])

    def test_aapl_cached_history_without_api_key_or_provider_calls(self):
        with Replay() as replay:
            self.seed(replay, 'AAPL')
            with patch.object(replay.fmp, 'FINANCIAL_API_KEY', ''), \
                 patch('requests.get', side_effect=AssertionError('Unexpected HTTP')), \
                 patch('yfinance.Ticker', side_effect=AssertionError('Unexpected Yahoo')):
                data = load_eq_inputs(' aapl ')
            self.assertEqual(data['errors'], [])
            self.assertEqual(len(data['periods']), 5)
            self.assertEqual(data['availability'], 'available')
            self.assertTrue(all(m['status'] == 'normal'
                                for m in growth_decomposition(data).values()))
            cash = cash_history(data)[0]
            self.assertAlmostEqual(cash['cash_conversion'], 111482 / 112010)
            self.assertAlmostEqual(cash['accrual_ratio'], 528 / 359241)
            items = statement_evidence(data)
            self.assertEqual(items[0]['amount'], -321000000)
            self.assertEqual(items[0]['period'], '2025-09-27')
            self.assertEqual(items[0]['source'], 'FMP')
            self.assertEqual(replay.calls, [])

    def test_all_seven_cached_growth_histories_without_api_key(self):
        with Replay() as replay:
            for ticker in TICKERS:
                self.seed(replay, ticker)
                with patch.object(replay.fmp, 'FINANCIAL_API_KEY', ''), \
                     patch('src.data.earnings_quality_inputs.get_total_assets', return_value=None), \
                     patch('src.data.earnings_quality_inputs.get_company_info', return_value={}):
                    data = load_eq_inputs(ticker)
                with self.subTest(ticker=ticker):
                    self.assertTrue(all(m['status'] == 'normal'
                                        for m in growth_decomposition(data).values()))
                    self.assertIsNotNone(cash_history(data)[0]['cash_conversion'])
                    if ticker != 'AAPL':
                        self.assertIsNone(cash_history(data)[0]['accrual_ratio'])
                        self.assertEqual(cash_history(data)[0]['status'], 'Unknown')
            self.assertEqual(replay.calls, [])

    def test_expired_or_corrupt_cache_does_not_supply_old_evidence(self):
        for mode in ('expired', 'corrupt'):
            with self.subTest(mode=mode), Replay() as replay:
                self.seed(replay, 'AAPL')
                path = replay.fmp._build_cache_path('income-statement', 'AAPL', 5)
                if mode == 'expired':
                    expired = replay.now - replay.fmp.HISTORICAL_CACHE_SECONDS - 1
                    os.utime(path, (expired, expired))
                else:
                    path.write_text('{invalid json')
                with patch.object(replay.fmp, 'FINANCIAL_API_KEY', ''):
                    data = load_eq_inputs('AAPL')
                self.assertEqual(growth_decomposition(data)['revenue_growth']['availability'],
                                 'unknown')
                self.assertTrue(any(e['source'] == 'income' for e in data['errors']))
                self.assertEqual(replay.calls, [])

    def test_cache_miss_uses_existing_loader_once_per_endpoint(self):
        with Replay() as replay:
            data = load_eq_inputs('AAPL')
            self.assertEqual(data['availability'], 'available')
            self.assertCountEqual(replay.calls, [
                ('fmp', 'AAPL', 'income-statement'),
                ('fmp', 'AAPL', 'cash-flow-statement'),
                ('fmp', 'AAPL', 'balance-sheet-statement'),
            ])

    def test_empty_cached_statements_remain_missing_without_fetching(self):
        with Replay() as replay:
            for endpoint in ('income-statement', 'cash-flow-statement',
                             'balance-sheet-statement'):
                replay.fmp._save_cache(endpoint, 'AAPL', 5, [])
            with patch.object(replay.fmp, 'FINANCIAL_API_KEY', ''):
                data = load_eq_inputs('AAPL')
            self.assertEqual(data['periods'], [])
            self.assertEqual(statement_evidence(data), [])
            self.assertEqual(replay.calls, [])
