"""Canonical balance schema tests, using isolated synthetic transport responses."""
from copy import deepcopy
import json
import unittest
from support import Replay, TICKERS
from test_balance_coverage import available_response, ENDPOINT
from test_financial_interpretation import dataset
from src.analysis.financial_statement_bridges import FIELDS, BALANCE_ALIASES, normalize
from src.analysis.financial_statement_diagnostics import interpret
from src.services.financial_interpretation_service import build_financial_interpretation


class BalanceAliasTests(unittest.TestCase):
    def test_every_equivalent_alias_for_every_ticker_and_both_years(self):
        for ticker in (*TICKERS,'ACME'):
            for name,aliases in BALANCE_ALIASES.items():
                for alias in aliases:
                    with self.subTest(ticker=ticker,field=name,alias=alias):
                        rows=dataset()
                        for values in rows.values():
                            for row in values:row['symbol']=ticker
                        primary=FIELDS['balance'][name]
                        for row in rows['balance']:row[alias]=row.pop(primary)
                        out=interpret(ticker,normalize(ticker,rows))['balance_sheet']['metrics'][name]
                        self.assertEqual(out['availability'],'available')
                        for side,index in [('current',0),('prior',1)]:
                            f=out[side+'_fact']
                            self.assertEqual(out[side],rows['balance'][index][alias])
                            self.assertEqual(f['source_field'],alias)
                            self.assertEqual(f['normalized_from'],alias)
                            self.assertEqual(f['canonical_field'],name)
                            self.assertEqual(f['source'],'FMP')
                            self.assertEqual(f['period'],rows['balance'][index]['date'])

    def test_seven_and_arbitrary_ticker_transport_cache_and_normalization(self):
        for ticker in (*TICKERS,'ACME'):
            with self.subTest(ticker=ticker),Replay() as r:
                rows=available_response(r,ticker)
                expected=interpret(ticker,normalize(ticker,rows))
                for row in r.raw['fmp'][f'{ticker}:{ENDPOINT}:5']:
                    for name,primary in FIELDS['balance'].items():
                        row[BALANCE_ALIASES[name][0]]=row.pop(primary)
                first=build_financial_interpretation(ticker)
                for name in FIELDS['balance']:
                    for side in ('current','prior','change','growth_pct'):
                        self.assertEqual(first['balance_sheet']['metrics'][name][side],expected['balance_sheet']['metrics'][name][side])
                self.assertEqual(first['balance_sheet']['liquidity'],expected['balance_sheet']['liquidity'])
                for name in ('receivables','inventory','payables','deferred_revenue'):
                    self.assertEqual(first['balance_sheet']['working_capital'][name]['growth_gap_pp'],expected['balance_sheet']['working_capital'][name]['growth_gap_pp'])
                path=r.fmp._build_cache_path(ENDPOINT,ticker,5)
                self.assertEqual(json.loads(path.read_text())['data'],r.raw['fmp'][f'{ticker}:{ENDPOINT}:5'])
                self.assertEqual(r.calls.count(('fmp',ticker,ENDPOINT)),1)
                r.calls.clear();self.assertEqual(first,build_financial_interpretation(ticker))
                self.assertFalse(r.calls)

    def test_valid_primary_including_zero_retains_precedence(self):
        for v in (0,42):
            d=dataset();d['balance'][0].update(cashAndCashEquivalents=v,cash=999)
            m=interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']
            self.assertEqual(m['current'],v)
            self.assertEqual(m['current_fact']['source_field'],'cashAndCashEquivalents')

    def test_unusable_primary_falls_back_to_valid_alias(self):
        for v in (None,True,'N/A',float('nan'),float('inf')):
            d=dataset();d['balance'][0].update(cashAndCashEquivalents=v,cash=42)
            m=interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']
            self.assertEqual(m['current'],42)

    def test_conflicting_fallback_aliases_are_not_arbitrarily_chosen(self):
        d=dataset();d['balance'][0].update(cashAndCashEquivalents=None,cash=42,cashAndEquivalents=43)
        m=interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']
        self.assertIsNone(m['current'])
        self.assertEqual(m['current_fact']['reason'],'conflicting_balance_aliases')
        d['balance'][0]['cashAndEquivalents']=42
        self.assertEqual(interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']['current'],42)

    def test_alias_does_not_bypass_metadata_validation(self):
        for field,v in [('reportedCurrency',None),('period','Q4'),('symbol','WRONG'),('unit','millions')]:
            d=dataset();d['balance'][0].update(cashAndCashEquivalents=None,cash=42)
            d['balance'][0][field]=v
            self.assertIsNone(interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']['current'])
        d=dataset();d['balance'][0].update(cashAndCashEquivalents=None,cash=42,fiscalYear='2023')
        self.assertIsNone(interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['cash']['change'])

    def test_broader_totals_and_components_are_not_aliases(self):
        # Total equity includes minority interests; cash+investments is not cash.
        for name,broad in [('cash','cashAndShortTermInvestments'),('equity','totalEquity'),
                           ('payables','totalPayables'),('receivables','accountsReceivables'),
                           ('debt','longTermDebt'),('deferred_revenue','deferredRevenueNonCurrent')]:
            d=dataset();d['balance'][0].pop(FIELDS['balance'][name]);d['balance'][0][broad]=123
            self.assertIsNone(interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics'][name]['current'])

    def test_no_matching_value_stays_unknown(self):
        d=dataset();d['balance'][0].pop('netReceivables')
        m=interpret('TEST',normalize('TEST',d))['balance_sheet']['metrics']['receivables']
        self.assertIsNone(m['current'])
        self.assertEqual(m['current_fact']['reason'],'missing_value')
