"""V2 research scenarios are synthetic unless explicitly using frozen Replay data."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from support import Replay, TICKERS, FIXTURES
from test_moat1 import inputs, normalized, evidence, table
from src.analysis import filing_classifier as classifier
from src.analysis.earnings_quality_narrative_evidence import narrative_evidence
from src.analysis.earnings_quality_research_evidence import normalize_evidence, group_families, load_rules
from src.analysis.earnings_quality_attribution import fcf_attribution, build_attribution
from src.analysis.earnings_quality_research import build_research, roic_trend
from src.data.earnings_quality_inputs import normalize_inputs

FILING = {'form': '10-K', 'accession_number': 'synthetic-accession',
          'url': 'https://www.sec.gov/Archives/synthetic.htm',
          'report_date': '2025-12-31', 'filing_date': '2026-02-01'}


def source(text, data=None):
    data = data or normalized()
    e = narrative_evidence(data['ticker'], classifier.classify_filing_text(text), FILING, text)
    e['validated_events'] = []
    e['statement_items'] = []
    return e


def research(text='', data=None):
    data = data or normalized()
    return build_research(data, source(text, data))


class EvidenceV2Tests(unittest.TestCase):
    def test_policy_is_not_event_even_with_amount_and_year(self):
        r = research('For fiscal year 2025, equity investment gains are recorded in other income under our accounting policy in USD $20 million.')
        self.assertFalse(r['event_families'])
        self.assertTrue(all(e['validation_level'] <= 1 for e in r['evidence']))

    def test_hypothetical_and_negated_are_not_actual(self):
        for text in ('We may record a $20 million equity investment gain in fiscal year 2025 (USD).',
                     'We did not recognize a $20 million equity investment gain in fiscal year 2025 (USD).'):
            self.assertFalse(research(text)['event_families'])

    def test_aapl_prior_year_tax_event_not_filing_year(self):
        text = 'In fiscal year 2024, we recorded a $20 million one-time tax charge in net income (USD).'
        r = research(text)
        tax = next(e for e in r['evidence'] if 'tax' in e['categories'])
        self.assertEqual(tax['event_fiscal_year'], 2024)
        self.assertEqual(tax['period'], '2024-12-31')
        self.assertEqual(tax['filing_date'], '2026-02-01')
        self.assertEqual(tax['amount'], -20e6)
        self.assertEqual(tax['validation_level'], 4)
        self.assertEqual(r['event_families'][0]['recurrence_status'], 'explicitly one-off')
        self.assertNotIn(tax['evidence_id'], r['core_revenue']['evidence'])

    def test_deferred_tax_actual_event_upgrade_does_not_change_legacy_classifier(self):
        text = 'For fiscal year 2025, we recorded a $20 million valuation allowance charge against deferred tax assets in net income (USD).'
        legacy = classifier.classify_context('tax_unusual_items', 'tax', 2, text)
        self.assertLessEqual(legacy['final_level'], 1)
        tax = next(e for e in research(text)['evidence'] if 'tax' in e['categories'])
        self.assertGreaterEqual(tax['validation_level'], 3)
        self.assertEqual(tax['validation_status'], 'actual_event_result')

    def test_missing_fiscal_year_and_ambiguous_amount_not_inferred(self):
        text = 'We recorded a gain on equity securities while revenue increased by $20 million and costs increased by $10 million (USD).'
        for e in research(text)['evidence']:
            self.assertIsNone(e['amount'])
            self.assertIsNone(e['event_fiscal_year'])
            self.assertLessEqual(e['validation_level'], 2)

    def test_quarter_event_not_assigned_to_annual_statement(self):
        text = 'For the first quarter of fiscal year 2025, we recorded a $20 million tax charge (USD).'
        tax = next(e for e in research(text)['evidence'] if 'tax' in e['categories'])
        self.assertEqual(tax['event_fiscal_year'], 2025)
        self.assertIsNone(tax['period'])
        self.assertIsNone(tax['amount'])
        self.assertEqual(tax['validation_level'], 2)

    def test_currency_and_unlinked_amount_remain_unknown(self):
        for text in ('In fiscal year 2025, we recorded a $20 million equity investment gain.',
                     'In fiscal year 2025, we recorded a gain on equity securities while revenue increased by $20 million (USD).'):
            self.assertTrue(all(e['amount'] is None for e in research(text)['evidence']))

    def test_structured_amount_match_reaches_stage_five_without_sum(self):
        data = normalized()
        e = source('For fiscal year 2025, we recorded a $20 million equity securities valuation gain (USD).', data)
        e['validated_events'] = evidence(table('20'))['validated_events']
        items = normalize_evidence(data, e)
        self.assertTrue(any(i['validation_level'] == 5 for i in items if i['evidence_type'] == 'narrative'))
        result = build_research(data, e)
        self.assertNotIn('total_non_core_amount', result)
        self.assertNotIn('non_core_share', result)

    def test_msft_named_recapitalization_and_dilution_group(self):
        text = ('For fiscal year 2025, we recorded a $30 million dilution gain from the OpenAI Recapitalization (USD). '
                'For fiscal year 2025, we recognized a gain related to the OpenAI Recapitalization in other income.')
        families = research(text)['event_families']
        self.assertEqual(len(families), 1)
        self.assertEqual(len(families[0]['source_evidence']), 2)
        self.assertIn('dilution_gain', families[0]['topics'])
        self.assertIn('recapitalization', families[0]['topics'])
        self.assertIsNone(families[0]['validated_amount'])

    def test_conflicting_named_transaction_amounts_not_combined(self):
        text = ('For fiscal year 2025, we recorded a $30 million dilution gain from the Acme Recapitalization (USD). '
                'For fiscal year 2025, we recorded a $40 million dilution gain from the Acme Recapitalization (USD).')
        families = research(text)['event_families']
        self.assertEqual(len(families), 1)
        self.assertIsNone(families[0]['validated_amount'])

    def test_tsla_bitcoin_and_multi_year_fx(self):
        text = ('In fiscal year 2024, we recorded a $2 million foreign exchange gain (USD). '
                'In fiscal year 2025, we recorded a $3 million foreign exchange loss (USD). '
                'In fiscal year 2025, we recorded a $5 million bitcoin gain from fair value remeasurement (USD).')
        families = research(text)['event_families']
        fx = [f for f in families if 'foreign_exchange' in f['topics']]
        self.assertEqual(len(fx), 2)
        self.assertTrue(all(f['recurrence_status'] == 'volatile recurring' for f in fx))
        self.assertTrue(any('digital_assets' in f['topics'] for f in families))

    def test_generic_net_income_topic_cannot_create_false_recurrence(self):
        text = ('In fiscal year 2024, we recorded a $2 million foreign exchange gain in net income (USD). '
                'In fiscal year 2025, we recorded a $3 million tax charge in net income (USD).')
        self.assertTrue(all(f['recurrence_status'] not in ('historically recurring', 'volatile recurring') for f in research(text)['event_families']))

    def test_repeated_keywords_one_source_event(self):
        text = 'For fiscal year 2025, we recorded a $20 million regulatory credit revenue benefit from automotive regulatory credits in net income (USD).'
        r = research(text)
        self.assertEqual(len(r['event_families']), 1)
        self.assertEqual(r['core_revenue']['status'], 'caution')
        self.assertIsNone(r['core_revenue']['score'])


class AttributionV2Tests(unittest.TestCase):
    def test_amzn_capex_driven_fcf_without_complete_wc(self):
        i, c, a = inputs(ocf=(100, 120))
        c[0].update(freeCashFlow=80, capitalExpenditure=-20)
        c[1].update(freeCashFlow=20, capitalExpenditure=-100)
        c[1].pop('inventory')
        data = normalize_inputs('TEST', i, c, a)
        r = fcf_attribution(data)
        self.assertEqual(r['status'], 'capex_increase')
        self.assertEqual(r['changes'], {'ocf': 20, 'capex': -80, 'fcf': -60})
        self.assertEqual(r['attribution'], 'supported')
        self.assertNotIn('productive', r['summary'])

    def test_ocf_weakness_mixed_and_bad_sign(self):
        for ocf, capex, expected in [(50, -20, 'ocf_weakness'), (50, -40, 'mixed'), (130, -20, 'not_declining'), (100, 20, 'incomplete')]:
            i, c, a = inputs(ocf=(100, ocf))
            c[0].update(capitalExpenditure=-20, freeCashFlow=80)
            c[1].update(capitalExpenditure=capex, freeCashFlow=ocf+capex)
            self.assertEqual(fcf_attribution(normalize_inputs('TEST', i, c, a))['status'], expected)

    def test_unreconciled_fcf_cannot_claim_capex_cause(self):
        i, c, a = inputs()
        c[-1]['freeCashFlow'] = 999
        self.assertEqual(fcf_attribution(normalize_inputs('TEST', i, c, a))['attribution'], 'unknown')

    def test_meta_tax_bridge_and_ni_divergence_survives_strong_cash(self):
        i, c, a = inputs(ni=(100, 80), oi=(100, 120), ocf=(120, 150))
        i[0].update(incomeBeforeTax=110, incomeTaxExpense=10)
        i[1].update(incomeBeforeTax=132, incomeTaxExpense=52)
        r = research(data=normalize_inputs('TEST', i, c, a))
        tax = r['attribution']['bridges'][2]
        self.assertAlmostEqual(tax['gap_pp'], -40)
        self.assertEqual(tax['attribution'], 'supported')
        self.assertEqual(r['interpretation']['state'], 'Concern')
        self.assertTrue(r['interpretation']['strengths'])
        self.assertTrue(any('pretax_income → net_income' in s for s in r['interpretation']['concerns']))

    def test_googl_below_operating_growth_not_automatic_investment_cause(self):
        i, c, a = inputs(oi=(100, 110))
        i[0]['incomeBeforeTax'] = 100
        i[1]['incomeBeforeTax'] = 150
        r = research(data=normalize_inputs('TEST', i, c, a))
        b = r['attribution']['bridges'][1]
        self.assertEqual(b['attribution'], 'unknown')
        self.assertAlmostEqual(b['gap_pp'], 40)
        self.assertIn('No validated causal', b['summary'])

    def test_statement_other_income_reconciles_without_component_double_count(self):
        i, c, a = inputs()
        for row in i:
            row['totalOtherIncomeExpensesNet'] = row['incomeBeforeTax'] - row['operatingIncome']
            row['interestIncome'] = 10
        r = research(data=normalize_inputs('TEST', i, c, a))
        b = r['attribution']['bridges'][1]
        self.assertEqual(b['attribution'], 'supported')
        self.assertNotIn('interest_income', b['arithmetic']['history'][0]['inputs'])

    def test_nvda_missing_assets_stay_unknown(self):
        i, c, a = inputs()
        data = normalize_inputs('TEST', i, c, [])
        from src.analysis.earnings_quality_diagnostics import cash_history
        self.assertIsNone(cash_history(data)[0]['accrual_ratio'])
        self.assertEqual(cash_history(data)[0]['status'], 'Unknown')

    def test_margin_comparison(self):
        self.assertEqual(research(data=normalized(oi=(100, 150)))['margin_quality']['status'], 'margin_expansion_investigation')
        self.assertEqual(research(data=normalized(oi=(100, 80)))['margin_quality']['status'], 'operating_deterioration_investigation')

    def test_roic_trend_and_missing_period(self):
        rules = load_rules()
        for values, state in [([.2,.15,.1], 'improving'), ([.1,.15,.2], 'deteriorating'), ([.15,.1,.2], 'volatile'), ([.1,.1,.1], 'stable')]:
            rows = [{'period': f'{y}-12-31', 'value': v} for y, v in zip((2025,2024,2023), values)]
            self.assertEqual(roic_trend(rows, rules)['status'], state)
        self.assertEqual(roic_trend([{'period':'2025-12-31','value':.2}],rules)['status'], 'unavailable')

    def test_empty_evidence_is_not_clean(self):
        r = research()
        self.assertEqual(r['core_revenue']['status'], 'unknown')
        self.assertIn('Unknown', r['interpretation']['state'])
        self.assertFalse(r['event_families'])


class IntegrationV2Tests(unittest.TestCase):
    def test_seven_tickers_frozen_scores_and_independent_research(self):
        from src.services.earnings_quality_service import build_earnings_quality
        with Replay() as replay:
            with patch('src.models.valuation_engine.analyze_valuation', side_effect=AssertionError('valuation dependency')), \
                 patch('src.services.rating_service.get_rating_report', side_effect=AssertionError('rating dependency')):
                for ticker in TICKERS:
                    with self.subTest(ticker=ticker):
                        result = build_earnings_quality(ticker)
                        baseline = json.loads((FIXTURES/'baseline'/f'{ticker}.json').read_text())['reports']
                        self.assertEqual(result['legacy_quality_summary'], baseline['quality_summary'])
                        self.assertEqual(result['non_core_evidence']['legacy_report'], baseline['non_core'])
                        resilience = result['revenue_resilience']
                        self.assertEqual(result['components'][-1]['score_raw'], resilience['revenue_resilience_score'])
                        self.assertEqual(result['components'][-1]['formal_eligible'], resilience['production_ready'])
                        self.assertIn('research_analysis', result)
                        json.dumps(result, allow_nan=False)

    def test_all_seven_routes_show_new_sections_and_reuse_cache(self):
        from collections import Counter
        from baseline import route_result
        with Replay() as replay:
            for ticker in TICKERS:
                response = replay.app_module.app.test_client().get(f'/research?ticker={ticker}&tab=earnings-quality')
                self.assertEqual(response.status_code,200)
                for name in (b'eq2-attribution',b'eq2-core-revenue',b'eq2-families',b'eq2-fcf',b'eq2-operating-quality'):
                    self.assertIn(name,response.data)
            replay.calls.clear()
            replay.app_module.app.test_client().get('/research?ticker=AAPL&tab=earnings-quality')
            self.assertEqual(replay.calls,[])
