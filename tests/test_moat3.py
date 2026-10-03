"""Moat 3 reproducible finance tests. Synthetic values are never production caches."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from support import Replay,TICKERS,ROOT,normalize as json_normalize
from src.data.valuation_inputs import normalize_valuation_inputs,dated_assumption
from src.analysis.valuation_cash_flows import (calculate_nopat,calculate_fcff,calculate_fcfe,
    calculate_operating_nwc,calculate_delta_operating_nwc,calculate_normalized_tax_rate,
    calculate_net_borrowing,build_cash_flows)
from src.analysis.cost_of_capital import calculate_cost_of_equity,calculate_cost_of_debt,calculate_wacc
from src.analysis.reverse_dcf import (calculate_terminal_value,calculate_fcff_dcf_value,
    calculate_fcfe_dcf_value,solve_implied_fcff_growth,solve_implied_fcfe_growth,build_sensitivity_matrix)
from src.analysis.valuation_interpretation import build_interpretation,consistency


def config():
    c=json.loads((ROOT/'data/valuation_assumptions.json').read_text())
    for key,value in [('erp',.05),('risk_free_fallback',.04),('terminal_growth',.02)]:
        c[key].update(value=value,stale=False,kind='External Assumption')
    return c


def raw(ticker='TEST'):
    out={'income':[],'cash':[],'balance':[]}
    for year in range(2025,2019,-1):
        base={'symbol':ticker,'date':f'{year}-12-31','fiscalYear':str(year),'period':'FY','reportedCurrency':'USD'}
        factor=1.1**(year-2020)
        out['income'].append({**base,'revenue':1000*factor,'grossProfit':500*factor,
            'operatingIncome':200*factor,'incomeBeforeTax':190*factor,'incomeTaxExpense':38*factor,
            'netIncome':152*factor,'interestExpense':10*factor,'totalOtherIncomeExpensesNet':-10*factor})
        out['balance'].append({**base,'totalCurrentAssets':500*factor,'cashAndCashEquivalents':100*factor,
            'shortTermInvestments':50*factor,'totalCurrentLiabilities':300*factor,'shortTermDebt':50*factor,
            'capitalLeaseObligationsCurrent':10*factor,'longTermDebt':150*factor,'capitalLeaseObligations':30*factor,
            'totalDebt':230*factor,'totalAssets':1000*factor,'totalStockholdersEquity':500*factor,
            'preferredStock':0,'minorityInterest':0,'netReceivables':100*factor,'inventory':100*factor,
            'accountPayables':100*factor,'deferredRevenue':50*factor})
        out['cash'].append({**base,'netIncome':152*factor,'depreciationAndAmortization':30*factor,
            'capitalExpenditure':-50*factor,'operatingCashFlow':220*factor,'freeCashFlow':170*factor,
            'netDebtIssuance':10*factor})
    return out


def inputs(ticker='TEST'):
    from src.analysis.financial_statement_diagnostics import interpret
    d=raw(ticker);p=normalize_valuation_inputs(ticker,d)
    market={k:{'value':v,'currency':'USD','source':'synthetic-test','observation_date':'2026-01-15'}
            for k,v in [('market_cap',5000),('enterprise_value',5100),('price',100),('pe',25),('forward_pe',22)]}
    return {'ticker':ticker,'periods':p,'market':market,'config':config(),
            'risk_free':{'value':.04,'kind':'External Assumption','source':'test','observation_date':'2026-01-15'},
            'beta':{'value':1.2,'kind':'Calculated','source':'test','window':'5Y monthly'},
            'historical_pe':{'median':20,'observations':[],'method':'Synthetic test','status':'Proxy','note':'Test only'},
            'moat1':None,'moat2':interpret(ticker,p),'errors':[],'retrieved_at':'2026-01-15'}


class CashFlowTests(unittest.TestCase):
    def test_nopat_fcff_fcfe_exact_formulas(self):
        self.assertEqual(calculate_nopat(200,.2),160)
        self.assertEqual(calculate_fcff(200,.2,30,50,10),130)
        self.assertEqual(calculate_fcfe(150,30,50,10,20),140)
        self.assertEqual(calculate_fcff(200,.2,30,50,-10),150)

    def test_missing_and_capex_da_signs(self):
        for index in range(5):
            args=[200,.2,30,50,10];args[index]=None;self.assertIsNone(calculate_fcff(*args))
        for index in range(5):
            args=[150,30,50,10,20];args[index]=None;self.assertIsNone(calculate_fcfe(*args))
        self.assertIsNone(calculate_fcff(200,.2,-1,50,10))
        self.assertIsNone(calculate_fcfe(150,30,-50,10,20))

    def test_preferred_nwc_exclusions_and_delta(self):
        p=inputs()['periods'];c,past=p[0]['values'],p[1]['values']
        n=calculate_operating_nwc(c);factor=1.1**5
        self.assertAlmostEqual(n['value'],(500-100-50-(300-50-10))*factor)
        d=calculate_delta_operating_nwc(c,past)
        self.assertAlmostEqual(d['value'],110*(1.1**5-1.1**4))

    def test_lease_overlap_is_not_added_twice(self):
        c=inputs()['periods'][0]['values'];c['debt']['value']=c['short_debt']['value']+c['long_debt']['value']
        self.assertIsNone(calculate_operating_nwc(c)['value'])

    def test_nwc_component_fallback_requires_all_components(self):
        data=raw();row=data['balance'][0];row.pop('totalCurrentAssets')
        row.update(otherOperatingCurrentAssets=20,accruedOperatingLiabilities=30,otherOperatingCurrentLiabilities=40)
        c=normalize_valuation_inputs('TEST',data)[0]['values'];n=calculate_operating_nwc(c)
        self.assertEqual(n['method'],'Explicit operating components')
        c['other_operating_assets']['availability']='unknown'
        self.assertIsNone(calculate_operating_nwc(c)['value'])

    def test_nwc_period_and_currency_mismatch(self):
        p=inputs()['periods'];p[1]['values']['cash']['currency']='EUR'
        self.assertIsNone(calculate_delta_operating_nwc(p[0]['values'],p[1]['values'])['value'])

    def test_three_year_tax_median_and_two_year_fallback(self):
        p=inputs()['periods']
        for row,rate in zip(p,[.1,.3,.2]):row['values']['income_tax']['value']=rate*row['values']['pretax_income']['value']
        self.assertAlmostEqual(calculate_normalized_tax_rate(p,config())['value'],.2)
        p[0]['values']['pretax_income']['value']=-1
        self.assertEqual(calculate_normalized_tax_rate(p,config())['method'],'2-observation median fallback')

    def test_invalid_tax_and_unusual_evidence(self):
        p=inputs()['periods'];e=[{'period':p[0]['period'],'validation_level':3,'categories':['tax']}]
        t=calculate_normalized_tax_rate(p,config(),e)
        self.assertEqual(len(t['excluded']),1)
        p[1]['values']['income_tax']['value']=999999
        self.assertIsNone(calculate_normalized_tax_rate(p,config(),e)['value'])

    def test_statutory_tax_fallback_must_be_documented(self):
        c=config();c['statutory_tax_fallback']={'value':.25}
        self.assertIsNone(calculate_normalized_tax_rate([],c)['value'])
        c['statutory_tax_fallback'].update(source='test',observation_date='2026-01-01',version='test',method='blended reference',stale=False)
        self.assertEqual(calculate_normalized_tax_rate([],c)['value'],.25)

    def test_net_borrowing_hierarchy_and_proxy(self):
        d=raw();d['cash'][0].update(debtIssuance=100,debtRepayment=30)
        p=normalize_valuation_inputs('TEST',d);a,b=p[0]['values'],p[1]['values']
        self.assertEqual(calculate_net_borrowing(a,b)['value'],70)
        a.pop('debt_issued');a.pop('debt_repaid')
        self.assertEqual(calculate_net_borrowing(a,b)['method'],'Reported signed net debt issuance')
        a.pop('net_borrowing');out=calculate_net_borrowing(a,b)
        self.assertEqual(out['method'],'BALANCE-SHEET PROXY')
        self.assertAlmostEqual(out['value'],200*(1.1**5-1.1**4))

    def test_fcfe_missing_does_not_remove_fcff(self):
        data=inputs();c=data['periods'][0]['values']
        c['net_borrowing']['availability']='unknown'
        from src.analysis.valuation_cash_flows import result
        with patch('src.analysis.valuation_cash_flows.calculate_net_borrowing',return_value=result(reason='No reliable borrowing source')):
            r=build_interpretation(data)
        self.assertEqual(r['primary']['status'],'converged')
        self.assertIsNone(r['cross_check']['growth'])

    def test_reported_fcf_is_not_fcff(self):
        data=inputs();r=build_cash_flows(data['periods'],config())['current']
        self.assertNotEqual(r['fcff'],r['reported_fcf']['value'])
        self.assertNotEqual(r['fcfe'],r['reported_fcf']['value'])


class CapitalTests(unittest.TestCase):
    def test_capm(self):
        self.assertAlmostEqual(calculate_cost_of_equity(.04,1.2,.05),.10)
        self.assertIsNone(calculate_cost_of_equity(.04,None,.05))

    def test_debt_cost_market_and_accounting_proxy(self):
        p=inputs()['periods'];a,b=p[0]['values'],p[1]['values']
        r=calculate_cost_of_debt(a,b)
        self.assertEqual(r['confidence'],'Proxy')
        self.assertAlmostEqual(r['value'],10*1.1**5/(200*(1.1**5+1.1**4)/2))
        q={'value':.05,'source':'test market','observation_date':'2026-01-01','stale':False}
        self.assertEqual(calculate_cost_of_debt(a,b,q)['confidence'],'Market')

    def test_wacc_market_weights_and_tax(self):
        r=calculate_wacc(800,200,.1,.05,.25,preferred=0)
        self.assertAlmostEqual(r['value'],.8*.1+.2*.05*.75)
        self.assertEqual(r['equity_weight'],.8)

    def test_zero_debt_and_missing_cost(self):
        self.assertEqual(calculate_wacc(100,0,.1,None,None,preferred=0)['value'],.1)
        self.assertIsNone(calculate_wacc(100,10,.1,None,.2)['value'])
        self.assertIsNone(calculate_wacc(100,10,.1,.05,.2,preferred=10)['value'])

    def test_dated_external_assumption_validation(self):
        with patch('src.data.valuation_inputs.today',return_value=date(2026,9,11)):
            item={'value':.04,'source':'test','observation_date':'2026-09-01','method':'external','version':'1','max_age_days':62}
            self.assertEqual(dated_assumption(item)['value'],.04)
            item['observation_date']='2025-01-01';self.assertTrue(dated_assumption(item)['stale'])
            item['observation_date']='2027-01-01';self.assertIsNone(dated_assumption(item)['value'])

    def test_missing_beta_fallback_is_explicit(self):
        from src.data.valuation_inputs import load_valuation_inputs
        with Replay(),patch('src.data.valuation_inputs.get_company_info',return_value={'currency':'USD'}),patch('src.data.valuation_inputs.get_price_history',return_value=None):
            r=load_valuation_inputs('AAPL')
            self.assertEqual(r['beta']['value'],1)
            self.assertEqual(r['beta']['kind'],'Fallback Assumption')
            self.assertEqual(r['beta']['confidence'],'Low Confidence')


class SolverTests(unittest.TestCase):
    def test_terminal_value_and_invalid_rates(self):
        self.assertAlmostEqual(calculate_terminal_value(100,.1,.02),1275)
        self.assertIsNone(calculate_terminal_value(100,.02,.02))
        self.assertIsNone(calculate_terminal_value(100,.01,.02))

    def test_known_growth_positive_negative_and_high(self):
        for g in (.12,-.25,1.5):
            for model,solver in [(calculate_fcff_dcf_value,solve_implied_fcff_growth),(calculate_fcfe_dcf_value,solve_implied_fcfe_growth)]:
                target=model(100,g,.1,.02);r=solver(target,100,.1,.02)
                self.assertEqual(r['status'],'converged')
                self.assertAlmostEqual(r['growth'],g,places=8)
                self.assertLess(abs(r['residual']),target*1e-9)
                self.assertEqual(r,solver(target,100,.1,.02))

    def test_no_solution_bad_cash_flow_missing(self):
        self.assertEqual(solve_implied_fcff_growth(1e20,1,.1,.02)['status'],'no_solution_in_bounds')
        self.assertEqual(solve_implied_fcff_growth(100,-1,.1,.02)['status'],'invalid_inputs')
        self.assertEqual(solve_implied_fcff_growth(100,None,.1,.02)['status'],'insufficient_evidence')

    def test_discount_rate_matching(self):
        data=inputs();r=build_interpretation(data)
        self.assertEqual(r['primary']['discount_rate'],r['cost_of_capital']['wacc']['value'])
        self.assertEqual(r['cross_check']['discount_rate'],r['cost_of_capital']['cost_of_equity'])
        self.assertEqual(r['primary']['target'],r['enterprise_value']['value'])
        self.assertEqual(r['cross_check']['target'],r['snapshot']['market_cap']['value'])

    def test_sensitivity_monotonicity_and_invalid_cells(self):
        s=build_sensitivity_matrix(2000,100,.1,.02,config())
        self.assertEqual(len(s['rows']),5)
        self.assertGreater(s['rows'][-1]['cells'][1]['growth'],s['rows'][0]['cells'][1]['growth'])
        self.assertLess(s['rows'][2]['cells'][-1]['growth'],s['rows'][2]['cells'][0]['growth'])
        s=build_sensitivity_matrix(2000,100,.025,.02,config())
        self.assertIsNone(s['rows'][0]['cells'][-1]['growth'])

    def test_cross_check_never_averaged(self):
        r=consistency({'growth':.3},{'growth':.1},10)
        self.assertEqual(r['status'],'FCFF / FCFE Reconciliation Required')
        self.assertAlmostEqual(r['gap_pp'],20)
        self.assertNotIn('average',r)


class InterpretationTests(unittest.TestCase):
    def test_snapshot_premium_not_overvaluation(self):
        r=build_interpretation(inputs())
        self.assertEqual(r['snapshot']['historical_premium'],.25)
        self.assertNotIn('Sell',json.dumps(r))
        self.assertIn('Under the stated assumptions',r['risk_summary']['priced_in'])

    def test_ev_does_not_deduct_cash_again(self):
        r=build_interpretation(inputs())
        self.assertEqual(r['enterprise_value']['value'],5100)
        self.assertIn('No independent cash deduction',r['enterprise_value']['cash_treatment'])

    def test_currency_mismatch_disables_targets(self):
        d=inputs();d['market']['market_cap']['currency']='EUR';r=build_interpretation(d)
        self.assertIsNone(r['primary']['growth']);self.assertIsNone(r['cross_check']['growth'])

    def test_upstream_results_unchanged(self):
        d=inputs();before=deepcopy(d);r=build_interpretation(d)
        self.assertEqual(d,before)
        self.assertEqual(r['fundamentals']['moat2_interpretation'],d['moat2']['analyst_interpretation'])
        json.dumps(r,allow_nan=False)

    def test_tax_evidence_read_only_and_period_specific(self):
        d=inputs();d['moat1']={'research_analysis':{'evidence':[{'period':'2025-12-31','validation_level':3,'categories':['tax']}]}}
        before=deepcopy(d);r=build_interpretation(d)
        self.assertEqual(len(r['cost_of_capital']['tax']['excluded']),1)
        self.assertEqual(d,before)

    def test_no_ticker_specific_formula_code(self):
        for name in ('valuation_cash_flows','cost_of_capital','reverse_dcf','valuation_interpretation'):
            code=(ROOT/f'src/analysis/{name}.py').read_text()
            for ticker in TICKERS:self.assertNotIn(ticker,code)


class IntegrationTests(unittest.TestCase):
    def test_all_seven_routes_complete_data_and_cache(self):
        from src.services import valuation_interpretation_service as service
        with Replay() as r:
            for ticker in TICKERS:
                with self.subTest(ticker=ticker),patch.object(service,'load_valuation_inputs',return_value=inputs(ticker)):
                    response=r.app_module.app.test_client().get(f'/research?ticker={ticker}&tab=valuation')
                    self.assertEqual(response.status_code,200)
                    for marker in ('moat3-snapshot','moat3-history','moat3-expectations','moat3-gaps','moat3-sensitivity','moat3-risk','moat3-methodology'):
                        self.assertIn(marker,response.get_data(as_text=True))
                    from bs4 import BeautifulSoup
                    soup=BeautifulSoup(response.data,'html.parser')
                    self.assertFalse(soup.select_one('#moat3-methodology').has_attr('open'))
                    r.calls.clear();again=r.app_module.app.test_client().get(f'/research?ticker={ticker}&tab=valuation')
                    self.assertEqual(response.data,again.data);self.assertFalse(r.calls)

    def test_service_failure_isolated(self):
        with Replay() as r,patch('src.services.valuation_interpretation_service.load_valuation_inputs',side_effect=ValueError('test')):
            page=r.app_module.app.test_client().get('/research?ticker=AAPL&tab=valuation')
            self.assertEqual(page.status_code,200);self.assertIn(b'moat3-unavailable',page.data)
            from bs4 import BeautifulSoup
            spectrum = BeautifulSoup(page.data, 'html.parser').select_one('.meridian-valuation-spectrum')
            self.assertIsNotNone(spectrum)
            self.assertEqual(len(spectrum.select('[data-value]')), 5)
            self.assertEqual([node['data-marker'] for node in spectrum.select('[data-value]')],
                             ['Low','Composite fair value','Base DCF','High','Current price'])

    def test_no_legacy_model_dependency(self):
        from src.services.valuation_interpretation_service import build_valuation_interpretation
        with patch('src.services.valuation_interpretation_service.load_valuation_inputs',return_value=inputs()),patch('src.services.rating_service.get_rating_report',side_effect=AssertionError('rating')),patch('src.models.dcf_model.calculate_wacc',side_effect=AssertionError('legacy WACC')):
            self.assertEqual(build_valuation_interpretation('TEST')['primary']['status'],'converged')

    def test_all_seven_legacy_reports_and_moat1_moat2_unchanged(self):
        from baseline import route_result,reports
        from support import strip_research_ui_company_fields
        from src.services.earnings_quality_service import build_earnings_quality
        from src.services.financial_interpretation_service import build_financial_interpretation
        reference=json.loads((ROOT/'tests/moat3_legacy_reference.json').read_text())
        def digest(v):return hashlib.sha256(json.dumps(json_normalize(v),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with Replay() as r:
            for ticker in TICKERS:
                with self.subTest(ticker=ticker):
                    r.clear_caches();company=route_result(r,ticker,'valuation')['context']['company'];company.pop('valuation_interpretation');strip_research_ui_company_fields(company)
                    self.assertEqual(company['ticker'], ticker)
                    baseline = json.loads((ROOT/'tests/fixtures/baseline'/f'{ticker}.json').read_text())['reports']
                    self.assertEqual(reports(r,ticker)['quality_summary'], baseline['quality_summary'])
                    self.assertEqual(build_earnings_quality(ticker)['legacy_quality_summary'], baseline['quality_summary'])
                    self.assertEqual(digest(build_financial_interpretation(ticker)),reference[ticker]['moat2'])


class TransportTests(unittest.TestCase):
    def test_complete_provider_path_for_all_seven_and_no_duplicate_calls(self):
        from src.services.valuation_interpretation_service import build_valuation_interpretation
        from src.data.reuse import data_scope
        from collections import Counter
        for ticker in TICKERS:
            with self.subTest(ticker=ticker),Replay() as r,patch('src.data.valuation_inputs.load_assumptions',return_value=config()):
                rows=raw(ticker)
                for kind,endpoint in [('income','income-statement'),('balance','balance-sheet-statement'),('cash','cash-flow-statement')]:
                    r.raw['fmp'][f'{ticker}:{endpoint}:5']=rows[kind]
                r.raw['yahoo'][ticker]['info'].update(currency='USD',marketCap=5000,enterpriseValue=5100,currentPrice=100)
                with data_scope(persistent=True):
                    first=build_valuation_interpretation(ticker)
                    self.assertEqual(first['primary']['status'],'converged')
                    self.assertEqual(first['cross_check']['status'],'converged')
                    calls=list(r.calls)
                    self.assertEqual(first,build_valuation_interpretation(ticker))
                    self.assertEqual(calls,r.calls)
                    fmp=[c for c in calls if c[0]=='fmp']
                    self.assertEqual(len(fmp),3);self.assertEqual(len(set(fmp)),3)
                self.assertEqual(first['enterprise_value']['method'],'Provider market-EV proxy')
                self.assertTrue(all(row['cells'] for row in first['sensitivity']['rows']))

    def test_reported_zero_interest_is_not_free_debt(self):
        p=inputs()['periods'];p[0]['values']['interest_expense']['value']=0
        self.assertIsNone(calculate_cost_of_debt(p[0]['values'],p[1]['values'])['value'])

    def test_historical_fcff_uses_valid_recent_window_with_explicit_years(self):
        out=build_interpretation(inputs())
        row=next(r for r in out['expectation_gaps'] if r['comparison']=='fcff CAGR')
        self.assertIsNotNone(row['observed'])
        self.assertEqual(row['history']['years'],3)
        self.assertEqual(row['history']['prior_period'],'2022-12-31')

    def test_preferred_capital_without_common_income_allocation_blocks_crosscheck(self):
        d=inputs();d['periods'][0]['values']['preferred_book']['value']=10
        r=build_interpretation(d)
        self.assertIsNone(r['primary']['growth']);self.assertIsNone(r['cross_check']['growth'])

    def test_source_period_conflict_cannot_support_nwc_or_fcff(self):
        d=raw();d['balance'][0]['date']='2025-09-30'
        i=inputs();i['periods']=normalize_valuation_inputs('TEST',d)
        self.assertIsNone(build_interpretation(i)['primary']['growth'])


    def test_future_annual_statement_is_not_observed_financial_data(self):
        d=raw();d['income'][0]['date']='2099-12-31'
        p=normalize_valuation_inputs('TEST',d)
        self.assertEqual(p[0]['values']['operating_income']['availability'],'unknown')
        self.assertEqual(p[0]['values']['operating_income']['reason'],'future_statement_period')
