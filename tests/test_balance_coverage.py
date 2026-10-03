"""Supplemental synthetic provider cases: never replace recorded golden data."""
from copy import deepcopy
from unittest.mock import patch
import json
import unittest
from support import Replay, TICKERS, ROOT
from test_financial_interpretation import dataset
from src.services.financial_interpretation_service import build_financial_interpretation
from src.analysis.financial_statement_bridges import FIELDS, normalize
from src.analysis.financial_statement_diagnostics import interpret

ENDPOINT = 'balance-sheet-statement'


def available_response(replay, ticker):
    """Synthetic values with explicit metadata, used ONLY in isolated tests."""
    rows = dataset()
    for kind in rows:
        for row in rows[kind]:
            row['symbol'] = ticker
    for kind, endpoint in [('income', 'income-statement'), ('balance', ENDPOINT),
                           ('cash', 'cash-flow-statement')]:
        replay.raw['fmp'][f'{ticker}:{endpoint}:5'] = deepcopy(rows[kind])
    return rows


class BalanceCoverageTests(unittest.TestCase):
    def test_each_ticker_cache_miss_fetch_cache_reuse_and_provenance(self):
        for ticker in TICKERS:
            with self.subTest(ticker=ticker), Replay() as r:
                rows = available_response(r,ticker)
                path = r.fmp._build_cache_path(ENDPOINT,ticker,5)
                self.assertFalse(path.exists())
                first = build_financial_interpretation(ticker)
                self.assertTrue(path.exists())
                self.assertEqual(json.loads(path.read_text())['data'], rows['balance'])
                self.assertEqual(r.calls.count(('fmp',ticker,ENDPOINT)),1)
                for name,field in FIELDS['balance'].items():
                    m=first['balance_sheet']['metrics'][name]
                    self.assertEqual(m['availability'],'available')
                    self.assertEqual(m['current'],rows['balance'][0][field])
                    self.assertEqual(m['prior'],rows['balance'][1][field])
                    for f in (m['current_fact'],m['prior_fact']):
                        self.assertEqual(f['source'],'FMP')
                        self.assertEqual(f['source_field'],field)
                        self.assertEqual(f['ticker'],ticker)
                        self.assertEqual(f['currency'],'USD')
                        self.assertEqual(f['period_type'],'FY')
                        self.assertIn(ENDPOINT,f['source_url'])
                liq=first['balance_sheet']['liquidity']
                for name,expected in [('current_ratio',650/300),('quick_ratio',500/300),
                                      ('cash_debt',300/250),('debt_equity',250/900),('net_cash',55)]:
                    self.assertAlmostEqual(liq[name]['current'],expected)
                for k in ('receivables','inventory','payables','deferred_revenue'):
                    self.assertAlmostEqual(first['balance_sheet']['working_capital'][k]['growth_gap_pp'],0)
                for k in ('debt','cash'):
                    self.assertNotEqual(first['trend_context'][k]['state'],'unknown')
                r.calls.clear()
                # New request scope: this must exercise disk reuse, not only in-request memoization.
                second=build_financial_interpretation(ticker)
                self.assertEqual(first,second)
                self.assertFalse(r.calls)

    def test_amzn_actual_route_uses_available_balance_response(self):
        from bs4 import BeautifulSoup
        with Replay() as r:
            available_response(r,'AMZN')
            page=r.app_module.app.test_client().get('/research?ticker=AMZN&tab=financials')
            self.assertEqual(page.status_code,200)
            section=BeautifulSoup(page.data,'html.parser').select_one('#moat2-balance')
            self.assertIn('Current Ratio: 2.17',section.get_text(' ',strip=True))
            self.assertIn('FMP',section.get_text())

    def test_aapl_recorded_response_and_diagnostics_unchanged(self):
        with Replay() as r:
            actual=build_financial_interpretation('AAPL')
            rows={kind:r.raw['fmp'][f'AAPL:{endpoint}:5'] for kind,endpoint in
                  [('income','income-statement'),('balance',ENDPOINT),('cash','cash-flow-statement')]}
            expected=interpret('AAPL',normalize('AAPL',rows))
            self.assertEqual(actual,expected)

    def test_missing_each_field_never_becomes_zero(self):
        for name,field in FIELDS['balance'].items():
            with self.subTest(field=field),Replay() as r:
                available_response(r,'AMZN')
                r.raw['fmp'][f'AMZN:{ENDPOINT}:5'][0].pop(field)
                out=build_financial_interpretation('AMZN')
                m=out['balance_sheet']['metrics'][name]
                self.assertIsNone(m['current'])
                self.assertEqual(m['availability'],'unknown')
                self.assertEqual(m['current_fact']['reason'],'missing_value')
                if name=='short_investments':self.assertIsNone(out['balance_sheet']['liquidity']['quick_ratio']['current'])

    def test_mismatched_year_currency_and_quarter_remain_unknown(self):
        for field,value in [('date','2025-09-30'),('fiscalYear','2023'),
                            ('period','Q4'),('reportedCurrency','EUR')]:
            with self.subTest(field=field),Replay() as r:
                available_response(r,'AMZN')
                r.raw['fmp'][f'AMZN:{ENDPOINT}:5'][0][field]=value
                out=build_financial_interpretation('AMZN')
                self.assertIsNone(out['balance_sheet']['metrics']['cash']['change'])
                self.assertIsNone(out['balance_sheet']['working_capital']['receivables']['growth_gap_pp'])

    def test_failure_does_not_cache_fabricated_empty_balance_and_retry_works(self):
        with Replay() as r:
            first=build_financial_interpretation('AMZN')
            self.assertTrue(any('balance: FMP returned HTTP 503' in x for x in first['limitations']))
            self.assertFalse(r.fmp._build_cache_path(ENDPOINT,'AMZN',5).exists())
            # Supply a matching synthetic response only after the unavailable attempt.
            income=r.raw['fmp']['AMZN:income-statement:5']
            rows=[]
            for source in income:
                row=deepcopy(dataset()['balance'][0])
                for k in ('symbol','date','fiscalYear','period','reportedCurrency'):row[k]=source[k]
                rows.append(row)
            r.raw['fmp'][f'AMZN:{ENDPOINT}:5']=rows
            second=build_financial_interpretation('AMZN')
            self.assertIsNotNone(second['balance_sheet']['metrics']['assets']['current'])

    def test_missing_key_reason_and_valid_cache_without_credentials(self):
        with Replay() as r:
            available_response(r,'AMZN')
            with patch.object(r.fmp,'FINANCIAL_API_KEY',None):
                out=build_financial_interpretation('AMZN')
                self.assertTrue(any('balance: FMP API key is not configured' in s for s in out['limitations']))
                self.assertFalse(r.calls)
            expected=build_financial_interpretation('AMZN')
            r.calls.clear()
            with patch.object(r.fmp,'FINANCIAL_API_KEY',None):
                self.assertEqual(build_financial_interpretation('AMZN'),expected)
                self.assertFalse(r.calls)

    def test_expired_and_corrupt_balance_cache_refetch(self):
        import os
        for mode in ('expired','corrupt'):
            with self.subTest(mode=mode),Replay() as r:
                available_response(r,'AMZN');build_financial_interpretation('AMZN')
                path=r.fmp._build_cache_path(ENDPOINT,'AMZN',5)
                if mode=='expired':os.utime(path,(r.now-r.fmp.HISTORICAL_CACHE_SECONDS-1,)*2)
                else:path.write_text('bad json')
                r.calls.clear();out=build_financial_interpretation('AMZN')
                self.assertEqual(r.calls.count(('fmp','AMZN',ENDPOINT)),1)
                self.assertIsNotNone(out['balance_sheet']['metrics']['cash']['current'])

    def test_empty_provider_response_stays_unknown_and_reuses_existing_policy(self):
        with Replay() as r:
            available_response(r,'AMZN');r.raw['fmp'][f'AMZN:{ENDPOINT}:5']=[]
            out=build_financial_interpretation('AMZN')
            self.assertIsNone(out['balance_sheet']['metrics']['assets']['current'])
            r.calls.clear();build_financial_interpretation('AMZN')
            self.assertFalse(r.calls)

    def test_generic_code_and_no_untrusted_error_details(self):
        from src.services.financial_interpretation_service import _history_failure
        code=(ROOT/'src/services/financial_interpretation_service.py').read_text()
        for ticker in TICKERS:self.assertNotIn(ticker,code)
        self.assertNotIn('secret-token',_history_failure('balance',RuntimeError('secret-token')))

    def test_available_balance_does_not_change_legacy_cards_scores_or_ratings(self):
        from baseline import route_result
        from src.services.earnings_quality_service import get_scoring_summary
        for ticker in TICKERS:
            with self.subTest(ticker=ticker),Replay() as r:
                before=route_result(r,ticker,'financials')['context']['company']
                before.pop('financial_interpretation')
                quality=deepcopy(get_scoring_summary(ticker))
                rows=[]
                for source in r.raw['fmp'][f'{ticker}:income-statement:5']:
                    row=deepcopy(dataset()['balance'][0])
                    for k in ('symbol','date','fiscalYear','period','reportedCurrency'):row[k]=source[k]
                    rows.append(row)
                r.raw['fmp'][f'{ticker}:{ENDPOINT}:5']=rows
                r.clear_caches()
                after=route_result(r,ticker,'financials')['context']['company']
                after.pop('financial_interpretation')
                self.assertEqual(before,after)
                self.assertEqual(quality,get_scoring_summary(ticker))
