"""Moat 1 behavior scenarios; synthetic inputs, not regenerated golden outputs."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from support import Replay, FIXTURES, TICKERS
from src.data.earnings_quality_inputs import normalize_inputs, fact
from src.analysis.earnings_quality_diagnostics import build_diagnostics, growth_decomposition, cash_history, working_capital
from src.analysis.earnings_quality_evidence import validate_non_core, parse_signed_cell


def inputs(ni=(100, 112), oi=(100, 111), ocf=(120, 134.4)):
    income, cash, assets = [], [], []
    for i, year in enumerate((2024, 2025)):
        meta = {'date': f'{year}-12-31', 'symbol': 'TEST', 'fiscalYear': str(year), 'period': 'FY', 'reportedCurrency': 'USD'}
        income.append({**meta, 'revenue': (1000, 1100)[i], 'operatingIncome': oi[i],
                       'incomeBeforeTax': (100, 111)[i], 'netIncome': ni[i]})
        wc = ocf[i] - ni[i] - 10
        cash.append({**meta, 'netIncome': ni[i], 'operatingCashFlow': ocf[i], 'freeCashFlow': ocf[i]-20,
                     'capitalExpenditure': -20, 'changeInWorkingCapital': wc,
                     'accountsReceivables': wc, 'inventory': 0, 'accountsPayables': 0, 'otherWorkingCapital': 0,
                     'depreciationAndAmortization': 10, 'stockBasedCompensation': 0, 'deferredIncomeTax': 0,
                     'otherNonCashItems': 0})
        assets.append(fact('TEST', {**meta, 'Total Assets': 1000}, 'Total Assets', 'Yahoo', 'balance_sheet'))
    return income, cash, assets


def normalized(**kwargs):
    i, c, a = inputs(**kwargs)
    return normalize_inputs('TEST', i, c, a)


def filing():
    return {'report_date': '2025-12-31', 'form': '10-K', 'accession_number': 'test-accession',
            'url': 'https://www.sec.gov/Archives/test-document.htm'}


def pretax(value=1000):
    return {'value': value, 'start': '2025-01-01', 'end': '2025-12-31', 'form': '10-K',
            'accession': 'test-accession', 'fiscal_year': 2025, 'fact_name': 'PretaxTest'}


def table(amount='200', topic='gain (loss) on equity securities, net', year=2025, unit='millions', extra=''):
    return f'<table><caption>Years ended · USD in {unit}</caption><tr><th>Item</th><th>2024</th><th>{year}</th></tr><tr><td>{topic}</td><td>1</td><td>{amount}</td></tr>{extra}</table>'


def evidence(html=None, legacy=None, denominator=1e9, **kwargs):
    return validate_non_core(legacy or {}, html, filing(), pretax(denominator), **kwargs)


class FoundationTests(unittest.TestCase):
    def test_six_growth_metrics_and_reported_fcf(self):
        g = growth_decomposition(normalized())
        self.assertEqual(len(g), 6)
        self.assertAlmostEqual(g['net_income_growth']['value'], .12)
        self.assertAlmostEqual(g['operating_income_growth']['value'], .11)
        self.assertEqual(g['fcf_growth']['current']['source_field'], 'freeCashFlow')
        self.assertEqual(g['net_income_growth']['current']['currency'], 'USD')
        self.assertTrue(all(v['evidence'] for v in g.values()))

    def test_missing_period_and_duplicate_period(self):
        for mode in ('missing', 'duplicate', 'wrong_date', 'missing_year', 'wrong_ticker', 'unit'):
            with self.subTest(mode=mode):
                i, c, a = inputs()
                if mode == 'missing': c.pop()
                if mode == 'duplicate': c.append(deepcopy(c[-1]))
                if mode == 'wrong_date': c[-1]['date'] = '2025-09-30'
                if mode == 'missing_year': c[-1].pop('fiscalYear')
                if mode == 'wrong_ticker': c[-1]['symbol'] = 'OTHER'
                if mode == 'unit': c[-1]['unit'] = 'millions'
                r = build_diagnostics(normalize_inputs('TEST', i, c, a), evidence())
                self.assertEqual(r['diagnostics'][1]['inputs']['comparisons']['ni_vs_ocf']['availability'], 'unknown')

    def test_nonadjacent_year_and_currency_mismatch(self):
        i, c, a = inputs()
        i[0]['fiscalYear'] = '2023'
        self.assertEqual(growth_decomposition(normalize_inputs('TEST', i, c, a))['net_income_growth']['availability'], 'unknown')
        i, c, a = inputs()
        c[-1]['reportedCurrency'] = 'EUR'
        self.assertEqual(cash_history(normalize_inputs('TEST', i, c, a))[0]['status'], 'Unknown')

    def test_zero_negative_and_turnaround_growth(self):
        for series, status in [((0, 1), 'not_meaningful'), ((-10, -5), 'not_meaningful'),
                               ((-10, 5), 'turned_profitable'), ((10, -5), 'turned_loss_making')]:
            with self.subTest(series=series):
                r = growth_decomposition(normalized(ni=series))['net_income_growth']
                self.assertEqual(r['status'], status)
                self.assertIsNone(r['value'])

    def test_cash_ratios_and_loss_not_support(self):
        current = cash_history(normalized())[0]
        self.assertEqual(current['status'], 'Supported')
        self.assertAlmostEqual(current['cash_conversion'], 1.2)
        self.assertAlmostEqual(current['accrual_ratio'], -.0224)
        self.assertEqual(cash_history(normalized(ni=(100, 0)))[0]['status'], 'Unknown')
        self.assertEqual(cash_history(normalized(ni=(100, -100), ocf=(120, -120)))[0]['status'], 'Unknown')
        self.assertEqual(cash_history(normalized(ocf=(120, 70)))[0]['status'], 'Concern')
        self.assertEqual(cash_history(normalized(ocf=(120, 105)))[0]['status'], 'Mixed')

    def test_asset_period_missing_and_negative_assets(self):
        i, c, a = inputs()
        a[-1]['period'] = '2025-09-30'
        self.assertIsNone(cash_history(normalize_inputs('TEST', i, c, a))[0]['accrual_ratio'])
        i, c, a = inputs()
        a[-1]['value'] = -1000
        self.assertEqual(cash_history(normalize_inputs('TEST', i, c, a))[0]['status'], 'Unknown')

    def test_complete_working_capital_bridge(self):
        wc = working_capital(normalized())
        self.assertEqual(wc['reconciliation'], 'matched')
        self.assertAlmostEqual(wc['changes']['fcf'], 14.4)
        self.assertAlmostEqual(wc['changes']['working_capital'], 2.4)

    def test_partial_receivables_does_not_become_full_bridge(self):
        i, c, a = inputs()
        c[-1].pop('changeInWorkingCapital')
        wc = working_capital(normalize_inputs('TEST', i, c, a))
        self.assertEqual(wc['reconciliation'], 'incomplete')
        self.assertIsNone(wc['changes'])

    def test_positive_capex_and_unreconciled_ocf(self):
        for field, value in [('capitalExpenditure', 20), ('otherNonCashItems', 1e6)]:
            i, c, a = inputs()
            c[-1][field] = value
            self.assertEqual(working_capital(normalize_inputs('TEST', i, c, a))['reconciliation'], 'incomplete')


class EvidenceTests(unittest.TestCase):
    def test_signed_cells(self):
        for value, expected in [('(1,200)', -1200), ('-200', -200), ('−300', -300), ('+20', 20), ('0', 0), ('—', None), ('20(a)', None)]:
            self.assertEqual(parse_signed_cell(value), expected)

    def test_no_events_unknown_not_clean(self):
        for html in (None, '<html>No candidate tables</html>', table('0')):
            r = evidence(html)
            self.assertNotEqual(r['coverage'], 'reconciled_nonoperating_scope')
            self.assertIsNone(r['validated_ratio'])
            self.assertEqual(build_diagnostics(normalized(), r)['diagnostics'][2]['availability'], 'unknown')

    def test_validated_positive_negative_and_legacy_unchanged(self):
        legacy = {'score': 100, 'positive_events': [{'event_amount': 12}], 'negative_events': [], 'ignored_events': []}
        before = deepcopy(legacy)
        html = table('200') + table('-30', 'foreign currency exchange gain (loss), net')
        r = evidence(html, legacy)
        self.assertEqual(r['legacy_report'], before)
        self.assertEqual(legacy, before)
        self.assertAlmostEqual(r['validated_ratio'], .2)
        self.assertEqual(r['validated_events'][1]['event_amount'], -30e6)
        self.assertEqual(r['validated_events'][0]['materiality'], 'Highly Material')
        self.assertTrue(r['validated_events'][0]['evidence']['url'])

    def test_wrong_year_and_wrong_accession(self):
        self.assertEqual(evidence(table(year=2023))['validated_events'], [])
        p = pretax(1e9);p['accession'] = 'different'
        self.assertEqual(validate_non_core({}, table(), filing(), p)['validated_events'], [])

    def test_zero_negative_or_short_pretax_period(self):
        for value in (0, -1):
            self.assertEqual(evidence(table(), denominator=value)['validated_events'], [])
        p = pretax(1e9);p['start'] = '2025-10-01'
        self.assertEqual(validate_non_core({}, table(), filing(), p)['validated_events'], [])

    def test_unit_and_currency_unknown(self):
        for html in (table(unit='unknown'), table().replace('USD', 'EUR'), table().replace('Years ended', 'Nine months ended')):
            r = evidence(html)
            self.assertEqual(r['validated_events'], [])
            self.assertTrue(r['rejected_events'])

    def test_duplicate_and_conflicting_extraction(self):
        r = evidence(table() + table())
        self.assertEqual(len(r['validated_events']), 1)
        self.assertEqual(len(r['duplicates']), 1)
        self.assertEqual(r['validated_amount'], 200e6)
        r = evidence(table('200') + table('300'))
        self.assertEqual(r['validated_events'], [])
        self.assertIsNone(r['validated_amount'])

    def test_partial_extraction_and_unknown_category(self):
        r = evidence(table() + table('bad', 'income (loss) from equity method investments, net'))
        self.assertEqual(r['coverage'], 'incomplete')
        self.assertEqual(len(r['validated_events']), 1)
        r = evidence(table('300', 'interest income'))
        self.assertIsNone(r['validated_ratio'])
        self.assertIsNone(r['validated_events'][0]['weight'])

    def test_scoped_reconciliation_not_full_core_attribution(self):
        extra = '<tr><td>other income (expense), net</td><td>1</td><td>1</td></tr>'
        p = pretax(100e6);op = {**p, 'value': 99e6}
        r = validate_non_core({}, table('1', extra=extra), filing(), p, op)
        self.assertEqual(r['coverage'], 'reconciled_nonoperating_scope')
        self.assertIn('excludes unusual items', r['reason'])
        r = validate_non_core({}, table('1', extra=extra), filing(), p, {**op, 'value': 98e6})
        self.assertEqual(r['coverage'], 'incomplete')


class InterpretationTests(unittest.TestCase):
    def test_four_families_deterministic_auditable(self):
        a = build_diagnostics(normalized(), evidence())
        self.assertEqual(a, build_diagnostics(normalized(), evidence()))
        self.assertEqual(len(a['diagnostics']), 4)
        for d in a['diagnostics']:
            for key in ('rule_id', 'rule_version', 'type', 'severity', 'statement', 'inputs', 'evidence', 'availability', 'confidence', 'reason'):
                self.assertIn(key, d)

    def test_growth_gap_investigation_not_causality(self):
        r = build_diagnostics(normalized(ni=(100, 122), oi=(100, 108), ocf=(120, 128.4)), evidence(table()))
        self.assertEqual(r['diagnostics'][1]['severity'], 'concern')
        self.assertIn('do not establish', r['diagnostics'][1]['statement'])
        self.assertEqual(r['interpretation']['sustainability'], 'Concern')

    def test_gap_boundary_and_no_cross_provider_supported_claim(self):
        for ni, expected in [(129.999, 'observation'), (130, 'concern'), (130.001, 'concern')]:
            r = build_diagnostics(normalized(ni=(100, ni), oi=(100, 120), ocf=(120, 156)), evidence())
            self.assertEqual(r['diagnostics'][1]['severity'], expected)
        extra = '<tr><td>other income (expense), net</td><td>1</td><td>1</td></tr>'
        p = pretax(100e6)
        e = validate_non_core({}, table('1', extra=extra), filing(), p, {**p, 'value': 99e6})
        self.assertNotEqual(build_diagnostics(normalized(), e)['interpretation']['sustainability'], 'Supported')

    def test_small_gap_no_clean_conclusion_without_evidence(self):
        r = build_diagnostics(normalized(), evidence())
        self.assertEqual(r['interpretation']['sustainability'], 'Unknown / Insufficient Evidence')
        self.assertTrue(r['interpretation']['strengths'])

    def test_supported_only_with_scoped_reconciliation(self):
        extra = '<tr><td>other income (expense), net</td><td>1</td><td>0.000001</td></tr>'
        p = pretax(112)
        e = validate_non_core({}, table('0.000001', extra=extra), filing(), p, {**p, 'value': 111})
        i, c, a = inputs()
        i[-1]['incomeBeforeTax'] = 112
        data = normalize_inputs('TEST', i, c, a)
        r = build_diagnostics(data, e)
        self.assertEqual(r['interpretation']['sustainability'], 'Supported')
        e['coverage'] = 'incomplete'
        self.assertNotEqual(build_diagnostics(data, e)['interpretation']['sustainability'], 'Supported')

    def test_fcf_gap_partial_bridge_caution(self):
        i, c, a = inputs(ocf=(120, 200))
        c[-1].pop('inventory')
        r = build_diagnostics(normalize_inputs('TEST', i, c, a), evidence())
        self.assertEqual(r['diagnostics'][3]['severity'], 'caution')
        self.assertIn('bridge is incomplete', r['diagnostics'][3]['statement'])


class IntegrationTests(unittest.TestCase):
    def test_seven_tickers_independent_and_golden_scores(self):
        with Replay() as replay:
            from src.services.earnings_quality_service import build_earnings_quality
            with patch('src.services.valuation_service.build_valuation', side_effect=AssertionError('valuation dependency')), \
                 patch('src.models.valuation_engine.analyze_valuation', side_effect=AssertionError('DCF dependency')), \
                 patch('src.services.rating_service.get_rating_report', side_effect=AssertionError('rating dependency')):
                for ticker in TICKERS:
                    with self.subTest(ticker=ticker):
                        result = build_earnings_quality(ticker)
                        baseline = json.loads((FIXTURES/'baseline'/f'{ticker}.json').read_text())
                        self.assertEqual(result['legacy_quality_summary'], baseline['reports']['quality_summary'])
                        self.assertEqual(result['identified_non_core_items']['legacy_report'], baseline['reports']['non_core'])
                        self.assertEqual(len(result['growth_decomposition']), 6)
                        self.assertEqual(len(result['diagnostics']), 4)
                        json.dumps(result, allow_nan=False)

    def test_rating_and_eq_share_scoring_once(self):
        with Replay() as replay:
            from src.services import earnings_quality_service as service
            from src.data.reuse import data_scope
            with patch.object(service.quality, 'get_quality_components', wraps=service.quality.get_quality_components) as build:
                with data_scope(persistent=True):
                    replay.context.build_company_context('AAPL', active_tab='overview')
                with data_scope(persistent=True):
                    service.build_earnings_quality('AAPL')
                self.assertEqual(build.call_count, 1)

    def test_fmp_failure_still_returns_legacy_scores_and_unknown(self):
        with Replay() as replay:
            replay.failures.add(('fmp', 'AAPL'))
            from src.services.earnings_quality_service import build_earnings_quality
            r = build_earnings_quality('AAPL')
            self.assertIsNotNone(r['score_raw'])
            self.assertEqual(r['diagnostics'][1]['availability'], 'unknown')
