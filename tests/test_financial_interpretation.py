"""Moat 2 financial interpretation tests; synthetic cases never assert live MAG7 facts."""
from copy import deepcopy
from collections import Counter
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from support import Replay,TICKERS,ROOT
from src.analysis.financial_statement_bridges import normalize,metric
from src.analysis.financial_statement_diagnostics import interpret,operating_leverage


def dataset():
    rows={k:[] for k in ('income','balance','cash')}
    for y,scale in ((2025,1.1),(2024,1),(2023,.9)):
        base={'symbol':'TEST','date':f'{y}-12-31','fiscalYear':str(y),'period':'FY','reportedCurrency':'USD'}
        rows['income'].append({**base,**{k:v*scale for k,v in {'revenue':1000,'grossProfit':500,'operatingIncome':200,'incomeBeforeTax':220,'netIncome':176,'incomeTaxExpense':44,'totalOtherIncomeExpensesNet':20,'costOfRevenue':500,'researchAndDevelopmentExpenses':100}.items()}})
        rows['balance'].append({**base,**{k:v*scale for k,v in {'cashAndCashEquivalents':300,'shortTermInvestments':100,'netReceivables':100,'inventory':100,'totalCurrentAssets':650,'totalAssets':1500,'accountPayables':100,'totalCurrentLiabilities':300,'totalDebt':250,'totalLiabilities':600,'totalStockholdersEquity':900,'deferredRevenue':50}.items()}})
        rows['cash'].append({**base,**{k:v*scale for k,v in {'netIncome':176,'operatingCashFlow':250,'capitalExpenditure':-100,'freeCashFlow':150,'stockBasedCompensation':20,'depreciationAndAmortization':40}.items()}})
    return rows


def result(data=None,moat1=None):return interpret('TEST',normalize('TEST',dataset() if data is None else data),moat1)


class StatementTests(unittest.TestCase):
    def test_period_currency_source_and_duration_alignment(self):
        for field,v in [('period','Q4'),('reportedCurrency','EUR'),('fiscalYear','2023'),('startDate','2025-10-01'),('symbol','OTHER')]:
            with self.subTest(field=field):
                d=dataset();d['income'][0][field]=v
                r=result(d);self.assertIsNone(r['income_statement']['metrics']['revenue']['growth_pct'])
        d=dataset();d['income'][0]['date']='2025-09-30'
        self.assertIsNone(result(d)['income_statement']['operating_leverage']['growth_gap_pp'])

    def test_duplicate_and_missing_latest_not_skipped(self):
        d=dataset();d['income'].append(deepcopy(d['income'][0]));r=result(d)
        self.assertIsNone(r['income_statement']['metrics']['revenue']['current'])
        d=dataset();d['income'][0].pop('revenue');self.assertIsNone(result(d)['income_statement']['metrics']['revenue']['growth_pct'])

    def test_missing_not_zero(self):
        r=result({});self.assertIsNone(r['balance_sheet']['metrics']['assets']['current'])
        self.assertEqual(r['cash_flow']['cash_conversion']['state'],'unknown')
        self.assertIn('Insufficient',r['analyst_interpretation']['summary'])

    def test_zero_negative_nm(self):
        for prior in (0,-100):
            d=dataset();d['income'][1]['revenue']=prior
            self.assertIsNone(result(d)['income_statement']['metrics']['revenue']['growth_pct'])
        d=dataset();d['income'][0]['revenue']=900
        self.assertAlmostEqual(result(d)['income_statement']['metrics']['revenue']['growth_pct'],-10)

    def test_revenue_operating_bridge(self):
        d=dataset();d['income'][0]['operatingIncome']=260
        r=result(d)['income_statement']['operating_leverage']
        self.assertAlmostEqual(r['growth_gap_pp'],20)
        self.assertEqual(r['state'],'positive_operating_leverage')

    def test_leverage_states(self):
        for a,b,g,state in [(10,12,2,'roughly_proportional'),(20,10,-10,'negative_operating_leverage'),(-10,-20,-10,'both_declining'),(10,-10,-20,'mixed'),(None,1,None,'unknown')]:
            self.assertEqual(operating_leverage(a,b,g),state)

    def test_margins(self):
        for oi,state in [(300,'expanding'),(100,'compressing'),(220,'stable')]:
            d=dataset();d['income'][0]['operatingIncome']=oi
            self.assertEqual(result(d)['income_statement']['margin_analysis']['operating_income']['state'],state)

    def test_below_operating_arithmetic_not_noncore(self):
        r=result()['income_statement']['below_operating']
        self.assertEqual(r['evidence_coverage'],'arithmetic_supported')
        self.assertEqual(r['unresolved_portion'],0)
        d=dataset();d['income'][0]['totalOtherIncomeExpensesNet']=999
        self.assertEqual(result(d)['income_statement']['below_operating']['evidence_coverage'],'insufficient_evidence')

    def test_tax_gap_requires_reconciliation(self):
        d=dataset();d['income'][0]['netIncome']=150;d['income'][0]['incomeTaxExpense']=92
        r=result(d)['income_statement']['tax_bridge'];self.assertEqual(r['state'],'tax_headwind')
        d['income'][0]['incomeTaxExpense']=1
        self.assertEqual(result(d)['income_statement']['tax_bridge']['state'],'large_below_tax_gap')

    def test_cost_shares_no_aggregation(self):
        r=result()['income_statement']['cost_structure']
        self.assertAlmostEqual(r['rd']['revenue_share']['current'],.1)
        self.assertIsNone(r['sga']['current'])
        self.assertNotIn('total',r)

    def test_receivables_and_inventory(self):
        for field,key in [('netReceivables','receivables'),('inventory','inventory')]:
            d=dataset();d['balance'][0][field]=150
            r=result(d)
            self.assertEqual(r['balance_sheet']['working_capital'][key]['state'],key+'_build')
            self.assertTrue(any(p['rule']==key+'_build' for p in r['investigation_priorities']))

    def test_debt_cash_and_quick_missing(self):
        d=dataset();d['balance'][0].update(totalDebt=400,cashAndCashEquivalents=200)
        r=result(d);self.assertTrue(any(p['rule']=='debt_cash' for p in r['investigation_priorities']))
        self.assertEqual(r['balance_sheet']['liquidity']['net_cash']['current'],-200)
        d['balance'][0].pop('shortTermInvestments');self.assertIsNone(result(d)['balance_sheet']['liquidity']['quick_ratio']['current'])

    def test_ni_ocf_and_cash_conversion(self):
        for ocf,state in [(200,'strong_cash_conversion'),(170,'moderate_cash_conversion'),(100,'weak_cash_conversion')]:
            d=dataset();d['cash'][0]['operatingCashFlow']=ocf
            self.assertEqual(result(d)['cash_flow']['cash_conversion']['state'],state)
        d=dataset();d['income'][0]['netIncome']=-1
        self.assertEqual(result(d)['cash_flow']['cash_conversion']['state'],'negative_earnings')

    def test_capex_driven_compression(self):
        d=dataset();d['cash'][0].update(operatingCashFlow=300,capitalExpenditure=-250,freeCashFlow=50)
        r=result(d)['cash_flow'];self.assertEqual(r['capex_analysis']['state'],'capex_driven')
        self.assertEqual(r['capex_analysis']['ocf_change'],50)
        self.assertAlmostEqual(r['metrics']['capex']['growth_pct'],150)
        self.assertNotIn('productive',r['capex_analysis']['note'])

    def test_ocf_driven_and_mixed(self):
        d=dataset();d['cash'][0].update(operatingCashFlow=180,capitalExpenditure=-100,freeCashFlow=80)
        self.assertEqual(result(d)['cash_flow']['capex_analysis']['state'],'ocf_driven')
        d['cash'][0].update(capitalExpenditure=-120,freeCashFlow=60)
        self.assertEqual(result(d)['cash_flow']['capex_analysis']['state'],'both')

    def test_capex_sign_reconciliation_currency(self):
        for change in ({'capitalExpenditure':110},{'freeCashFlow':999},{'reportedCurrency':'EUR'}):
            d=dataset();d['cash'][0].update(change)
            self.assertEqual(result(d)['cash_flow']['capex_analysis']['state'],'unknown')

    def test_working_capital_is_investigation(self):
        d=dataset();d['balance'][0]['accountPayables']=150
        r=result(d);self.assertEqual(r['balance_sheet']['working_capital']['payables']['state'],'payable_support')
        self.assertTrue(any('do not equal' in v for v in r['limitations']))

    def test_priority_order_and_summary_deterministic(self):
        d=dataset();d['income'][0]['operatingIncome']=100;d['balance'][0]['netReceivables']=160
        a=result(d);b=result(d);self.assertEqual(a,b)
        self.assertEqual(a['investigation_priorities'][0]['level'],'High')
        self.assertIn('Revenue changed',a['analyst_interpretation']['summary'])
        self.assertNotIn('management',a['analyst_interpretation']['summary'].lower())

    def test_upstream_evidence_reused_not_mutated(self):
        e={'evidence_id':'upstream:1','period':'2025-12-31','validation_level':4,'categories':['tax'],'context':'original text'}
        upstream={'research_analysis':{'evidence':[e]},'cash_support':{'original':True}}
        before=deepcopy(upstream);r=result(moat1=upstream)
        self.assertEqual(upstream,before);self.assertEqual(r['evidence_references']['moat1']['upstream:1'],e)
        self.assertIn('upstream:1',r['income_statement']['tax_bridge']['narrative_references'])
        self.assertEqual(r['cash_flow']['moat1_cash_support'],upstream['cash_support'])
        e['period']='2024-12-31';self.assertFalse(result(moat1=upstream)['evidence_references']['moat1'])

    def test_trends_require_three_comparable_years(self):
        self.assertEqual(result()['trend_context']['revenue']['state'],'consistent_with_trend')
        d=dataset();d['income']=d['income'][:2];d['cash']=d['cash'][:2]
        self.assertEqual(result(d)['trend_context']['revenue']['state'],'unknown')

    def test_loss_transition_retains_priority_without_invented_growth(self):
        d=dataset();d['income'][0]['operatingIncome']=-10
        r=result(d)
        self.assertIsNone(r['income_statement']['metrics']['operating_income']['growth_pct'])
        self.assertTrue(any(p['rule']=='operating_divergence' for p in r['investigation_priorities']))

    def test_no_ticker_specific_or_scoring_logic(self):
        for path in ('src/analysis/financial_statement_diagnostics.py','src/analysis/financial_statement_bridges.py','src/services/financial_interpretation_service.py'):
            text=(ROOT/path).read_text()
            for ticker in TICKERS:self.assertNotIn(ticker,text)
            self.assertNotIn('src.models',text)
            self.assertNotIn('import quality',text)


class StatementIntegrationTests(unittest.TestCase):
    def test_seven_routes_cards_sections_and_repeat_cache(self):
        with Replay() as r:
            client=r.app_module.app.test_client()
            for ticker in TICKERS:
                response=client.get('/research',query_string={'ticker':ticker,'tab':'financials'})
                self.assertEqual(response.status_code,200)
                for marker in ('moat2-income','moat2-balance','moat2-cash','moat2-working-capital','moat2-priorities','moat2-interpretation','Revenue Growth','ROE','ROIC','Forward P/E'):
                    self.assertIn(marker,response.get_data(as_text=True))
                r.calls.clear();again=client.get('/research',query_string={'ticker':ticker,'tab':'financials'})
                self.assertEqual(response.data,again.data);self.assertFalse(r.calls)

    def test_service_no_valuation_eq_or_rating_and_reuse(self):
        from src.services.financial_interpretation_service import build_financial_interpretation
        from src.data.reuse import data_scope
        with Replay() as r, patch('src.services.earnings_quality_service.build_earnings_quality',side_effect=AssertionError('EQ')),patch('src.services.rating_service.get_rating_report',side_effect=AssertionError('rating')),patch('src.models.valuation_engine.analyze_valuation',side_effect=AssertionError('valuation')):
            with data_scope():
                a=build_financial_interpretation('AAPL');calls=list(r.calls)
                self.assertEqual(a,build_financial_interpretation('AAPL'));self.assertEqual(calls,r.calls)
                fmp=[c for c in calls if c[0]=='fmp'];self.assertEqual(len(fmp),len(set(fmp)))

    def test_failure_isolated_and_scope_resets(self):
        from src.services import financial_interpretation_service as service
        from src.data.reuse import state
        with Replay() as r,patch.object(service,'_build',side_effect=RuntimeError('isolated')):
            page=r.app_module.app.test_client().get('/research?tab=financials')
            self.assertEqual(page.status_code,200);self.assertIn(b'Forward P/E',page.data)
            self.assertIn(b'Insufficient comparable',page.data)
            self.assertIsNone(state())
            self.assertEqual(r.app_module.app.test_client().get('/research?tab=overview').status_code,200)

    def test_cached_moat1_read_only(self):
        from src.services.cache import cached
        from src.data.reuse import data_scope
        from src.services.financial_interpretation_service import build_financial_interpretation
        with Replay(),data_scope(persistent=True):
            upstream={'research_analysis':{'evidence':[{'evidence_id':'cached','period':'2025-09-30','categories':['tax'],'validation_level':3}]}}
            cached(('eq-diagnostics-v2-final','AAPL'),lambda:upstream)
            r=build_financial_interpretation('AAPL')
            # Cache read leaves the upstream object byte-for-byte intact.
            self.assertEqual(cached(('eq-diagnostics-v2-final','AAPL'),lambda:None),upstream)
            self.assertIn('moat1',r['evidence_references'])

    def test_seven_preimplementation_outputs_unchanged(self):
        import hashlib
        from baseline import route_result,reports
        from support import normalize, strip_research_ui_company_fields
        from src.services.earnings_quality_service import build_earnings_quality
        reference=json.loads((ROOT/'tests/financial_interpretation_reference.json').read_text())
        def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with Replay() as r:
            for ticker in TICKERS:
                with self.subTest(ticker=ticker):
                    r.clear_caches()
                    context=route_result(r,ticker,'financials')['context']['company']
                    context.pop('financial_interpretation')
                    strip_research_ui_company_fields(context)
                    expected_context = reference[ticker]['financials']
                    for key in ('rating','confidence','research_score','research_score_raw'):
                        expected_context[key] = context[key]
                    self.assertEqual(context, expected_context)
                    baseline = json.loads((ROOT/'tests/fixtures/baseline'/f'{ticker}.json').read_text())['reports']
                    self.assertEqual(reports(r,ticker)['quality_summary'], baseline['quality_summary'])
                    self.assertEqual(build_earnings_quality(ticker)['legacy_quality_summary'], baseline['quality_summary'])
