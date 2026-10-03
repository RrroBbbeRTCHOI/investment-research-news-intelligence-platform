"""V1.5 integration/edge scenarios; golden recordings are never modified."""
from collections import Counter
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from support import Replay, TICKERS, FIXTURES
from test_moat1 import inputs, normalized, evidence, table
from src.data.earnings_quality_inputs import load_eq_inputs, normalize_inputs
from src.analysis.earnings_quality_diagnostics import build_diagnostics, cash_history, growth_decomposition
from src.analysis.earnings_quality_evidence import statement_evidence


class CompletionTests(unittest.TestCase):
    def test_real_recorded_aapl_assets_and_ratios(self):
        with Replay():
            data = load_eq_inputs('AAPL')
            current = cash_history(data)[0]
            self.assertEqual(current['period'], '2025-09-27')
            self.assertEqual(current['inputs']['assets']['value'], 359241000000)
            self.assertEqual(current['inputs']['assets']['source'], 'FMP')
            self.assertAlmostEqual(current['cash_conversion'], 111482 / 112010)
            self.assertAlmostEqual(current['accrual_ratio'], (112010 - 111482) / 359241)

    def test_seven_tickers_existing_growth_and_explicit_missing_balance(self):
        from src.services.earnings_quality_service import build_earnings_quality
        with Replay():
            for ticker in TICKERS:
                with self.subTest(ticker=ticker):
                    result = build_earnings_quality(ticker)
                    for metric in result['growth_decomposition'].values():
                        self.assertEqual(metric['status'], 'normal')
                        self.assertEqual(metric['availability'], 'available')
                    self.assertIsNotNone(result['cash_support']['current']['cash_conversion'])
                    if ticker != 'AAPL':
                        self.assertIsNone(result['cash_support']['current']['accrual_ratio'])
                        self.assertEqual(result['cash_support']['current']['status'], 'Unknown')
                    self.assertEqual(result['non_core_evidence'], result['identified_non_core_items'])
                    self.assertTrue(result['non_core_evidence']['statement_items'])
                    baseline = json.loads((FIXTURES/'baseline'/f'{ticker}.json').read_text())
                    self.assertEqual(result['legacy_quality_summary'], baseline['reports']['quality_summary'])

    def test_seven_tickers_synthetic_aligned_balance_provider_integration(self):
        # Explicit synthetic balances test wiring; these are NOT recorded company assets.
        from src.services.earnings_quality_service import build_earnings_quality
        with Replay() as replay:
            for ticker in TICKERS:
                rows = replay.raw['fmp'][f'{ticker}:income-statement:5']
                replay.raw['fmp'][f'{ticker}:balance-sheet-statement:5'] = [
                    {**{k: r[k] for k in ('symbol', 'date', 'fiscalYear', 'reportedCurrency', 'period')},
                     'totalAssets': 1e12} for r in rows]
                result = build_earnings_quality(ticker)
                for row in result['cash_support']['history']:
                    ni, ocf = row['inputs']['net_income']['value'], row['inputs']['ocf']['value']
                    self.assertAlmostEqual(row['accrual_ratio'], (ni - ocf) / 1e12)
                    self.assertEqual(row['accrual_availability'], 'available')

    def test_existing_historical_cache_reuses_all_three_endpoints(self):
        with Replay() as replay:
            replay.fmp.get_historical_income_statement('AAPL')
            replay.fmp.get_historical_cash_flow_statement('AAPL')
            replay.fmp.get_historical_balance_sheet('AAPL')
            replay.calls.clear()
            load_eq_inputs('AAPL')
            load_eq_inputs('AAPL')
            self.assertEqual([c for c in replay.calls if c[0] == 'fmp'], [])

    def test_partial_growth_does_not_hide_valid_earnings_gap(self):
        i, c, a = inputs(ni=(100, 150))
        c[-1].pop('freeCashFlow')
        r = build_diagnostics(normalize_inputs('TEST', i, c, a), evidence())
        self.assertEqual(r['diagnostics'][1]['severity'], 'concern')
        self.assertIsNone(r['diagnostics'][1]['inputs']['gaps']['fcf_vs_oi'])
        self.assertEqual(r['growth_decomposition']['fcf_growth']['availability'], 'unknown')

    def test_partial_cash_does_not_hide_ni_operating_gap(self):
        i, c, a = inputs(ni=(100, 150))
        c[-1].pop('operatingCashFlow')
        r = build_diagnostics(normalize_inputs('TEST', i, c, a), evidence())
        self.assertEqual(r['diagnostics'][1]['severity'], 'concern')
        self.assertEqual(r['diagnostics'][1]['availability'], 'partial')
        self.assertEqual(r['cash_support']['current']['status'], 'Unknown')

    def test_fcf_lag_and_no_invented_working_capital_cause(self):
        i, c, a = inputs()
        c[-1]['freeCashFlow'] = 50
        r = build_diagnostics(normalize_inputs('TEST', i, c, a), evidence())
        d = r['diagnostics'][3]
        self.assertEqual(d['severity'], 'caution')
        self.assertIn('further review', d['statement'])
        self.assertIn('no causal attribution', d['statement'])
        self.assertTrue(d['evidence'])

    def test_negative_normal_growth_is_retained(self):
        g = growth_decomposition(normalized(ni=(100, 80)))
        self.assertEqual(g['net_income_growth']['status'], 'normal')
        self.assertAlmostEqual(g['net_income_growth']['value'], -.2)

    def test_noncore_statement_amount_ratio_and_overlap_warning(self):
        i, c, a = inputs()
        i[-1]['incomeBeforeTax'] = 120
        i[-1]['totalOtherIncomeExpensesNet'] = 9
        i[-1]['interestIncome'] = 5
        rows = statement_evidence(normalize_inputs('TEST', i, c, a))
        self.assertAlmostEqual(rows[0]['signed_contribution'], 9 / 120)
        self.assertIsNone(rows[1]['signed_contribution'])
        self.assertIn('Do not sum', rows[0]['aggregation'])
        self.assertEqual(rows[0]['evidence']['source_field'], 'totalOtherIncomeExpensesNet')
        for field, value in [('totalOtherIncomeExpensesNet', -9), ('incomeBeforeTax', 0),
                             ('reportedCurrency', 'EUR')]:
            changed = deepcopy(i)
            changed[-1][field] = value
            if field == 'reportedCurrency': changed[-1]['period'] = 'Q4'
            row = statement_evidence(normalize_inputs('TEST', changed, c, a))[0]
            self.assertIsNone(row['signed_contribution'])

    def test_old_sec_material_event_does_not_change_current_interpretation(self):
        e = evidence(table())  # synthetic SEC denominator 1bn, diagnostic denominator 111
        r = build_diagnostics(normalized(), e)
        self.assertEqual(r['interpretation']['sustainability'], 'Unknown / Insufficient Evidence')
        self.assertIn('historical evidence only', r['diagnostics'][2]['statement'])
        self.assertFalse(r['diagnostics'][2]['inputs']['current_period_match'])

    def test_malformed_balance_does_not_use_convenient_yahoo_replacement(self):
        with Replay() as replay:
            rows = replay.raw['fmp']['AAPL:balance-sheet-statement:5']
            rows[0]['reportedCurrency'] = None
            data = load_eq_inputs('AAPL')
            self.assertIsNone(cash_history(data)[0]['accrual_ratio'])
            self.assertEqual(data['periods'][0]['values']['assets']['source'], 'FMP')

    def test_rendered_cash_and_evidence_keep_existing_sections(self):
        from flask import render_template
        from baseline import route_result
        from bs4 import BeautifulSoup
        with Replay() as replay:
            result = route_result(replay, 'AAPL', 'earnings-quality')
            with replay.app_module.app.test_request_context('/research'):
                from src.ui.research_dossier import build_research_dossier_context
                html = render_template('research.html', dossier=build_research_dossier_context('AAPL'), **result['context'])
            page = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
            for text in ('1.00x', '0.15%', 'Other income / expense, net',
                         'Fundamental Score', 'Research Score', 'Core Revenue', 'Unavailable',
                         'reported_statement_observation', 'Insufficient evidence'):
                self.assertIn(text, page)
