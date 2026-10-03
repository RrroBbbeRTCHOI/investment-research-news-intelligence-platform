"""Narrative integration tests. All disclosure examples here are synthetic."""
from copy import deepcopy
from collections import Counter
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from support import Replay, TICKERS, FIXTURES
from test_moat1 import evidence, table
from src.analysis import filing_classifier as classifier
from src.analysis.earnings_quality_narrative_evidence import narrative_evidence
from src.analysis.financial_line_extractor import FINANCIAL_LINE_PATTERNS

FILING = {'form': '10-K', 'accession_number': 'test-accession',
          'url': 'https://www.sec.gov/Archives/test.htm', 'report_date': '2025-12-31'}
DISCLOSURE = 'For fiscal year 2025, we recorded a $20 million benefit from regulatory credits in net income.'


def build(text, filing=FILING):
    return narrative_evidence('TEST', classifier.classify_filing_text(text), filing, text)


class NarrativeTests(unittest.TestCase):
    def test_expanded_topic_bypasses_structured_row_gate(self):
        self.assertNotIn('regulatory_credits', FINANCIAL_LINE_PATTERNS)
        result = build(DISCLOSURE)
        self.assertTrue(result['narrative_events'])
        event = result['narrative_events'][0]
        self.assertIn('regulatory_credits', event['topics'])
        self.assertEqual(event['evidence_status'], 'validated_narrative')
        self.assertEqual(event['fiscal_year'], 2025)
        self.assertIsNone(event['event_amount'])
        self.assertIsNone(event['materiality'])

    def test_hypothetical_risk_policy_and_negation_rejected(self):
        cases = [
            'We may record a $20 million benefit from regulatory credits in net income.',
            'Risk factors: regulatory credits could result in a $20 million change in net income.',
            'The company recognizes regulatory credits under its accounting policy for the year ended 2025.',
            'We did not record regulatory credits in net income for fiscal year 2025.',
            'We recorded a $20 million profit with no regulatory credits in net income.',
            'We have not recognized a $20 million benefit from regulatory credits in net income.',
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(build(text)['narrative_events'], [])

    def test_actual_financial_result_and_keyword_deduplication(self):
        text = 'For fiscal year 2025, regulatory credits increased by $20 million and automotive regulatory credits increased net income.'
        r = build(text)
        self.assertEqual(len(r['narrative_events']), 1)
        self.assertGreater(len(r['narrative_events'][0]['matched_keywords']), 1)

    def test_different_disclosures_not_over_deduplicated(self):
        text = DISCLOSURE + ' Separately, we recorded a $9 million benefit from regulatory credits in another jurisdiction.'
        self.assertEqual(len(build(text)['narrative_events']), 2)

    def test_ambiguous_amounts_and_missing_year_not_inferred(self):
        text = 'We recorded a benefit from regulatory credits in net income while revenue increased by $20 million and costs increased by $8 million.'
        event = build(text)['narrative_events'][0]
        self.assertGreaterEqual(len(event['detected_amounts']), 2)
        self.assertIsNone(event['event_amount'])
        self.assertIsNone(event['fiscal_year'])
        self.assertIsNone(event['period'])
        self.assertIsNone(event['materiality'])
        self.assertEqual(event['amount_linkage'], 'unverified')

    def test_missing_source_metadata_and_no_evidence_remain_unknown(self):
        for field in ('form', 'accession_number', 'url'):
            f = dict(FILING); f.pop(field)
            self.assertEqual(build(DISCLOSURE, f)['narrative_events'], [])
        self.assertEqual(build('No pertinent disclosure.')['narrative_availability'], 'insufficient_evidence')

    def test_unrelated_adjacent_actual_event_does_not_validate_keyword(self):
        text = 'Regulatory credits are described in our accounting policy. We recorded a $20 million gain on an unrelated sale in net income.'
        r = build(text)
        self.assertFalse(any('regulatory_credits' in e['topics'] for e in r['narrative_events']))

    def test_structured_validator_unchanged(self):
        r = evidence(table())
        self.assertEqual(len(r['validated_events']), 1)
        self.assertAlmostEqual(r['validated_ratio'], .2)
        self.assertNotIn('narrative_events', r)  # Pure table validator stays pure.

    def test_deferred_tax_policy_and_actual_event_audit(self):
        cases = [
            'Deferred tax assets are reduced by a valuation allowance when realization is not likely.',
            'For fiscal year 2025, we recorded a $20 million valuation allowance charge against deferred tax assets in net income.',
        ]
        for text in cases:
            r = classifier.classify_context('tax_unusual_items', 'tax', 2, text)
            self.assertLessEqual(r['final_level'], 1)
            self.assertIn('deferred_tax_not_operating_event', r['reasons'])
            self.assertEqual(build(text)['narrative_events'], [])

    def test_wrong_year_event_still_enters_legacy_weighted_score(self):
        from src.analysis.materiality import analyze_financial_line_materiality
        from src.analysis.non_core_earnings import calculate_weighted_non_core_events
        line = {'topic': 'equity_security_gains', 'latest_year': 2024,
                'latest_value': {'usd_value': 200}, 'classification_level': 3}
        event = analyze_financial_line_materiality(line, {'pretax_income': 1000, 'fiscal_year': 2025})
        self.assertFalse(event['year_match'])
        weighted = calculate_weighted_non_core_events({'events': [event]})
        self.assertEqual(weighted['positive_events'][0]['weighted_amount'], 200)

    def test_all_seven_wrong_year_audit_matches_frozen_reports(self):
        from src.analysis.non_core_earnings import calculate_weighted_non_core_events
        for t in TICKERS:
            r = json.loads((FIXTURES/'baseline'/f'{t}.json').read_text())['reports']
            before = calculate_weighted_non_core_events(r['materiality'])
            filtered = deepcopy(r['materiality'])
            filtered['events'] = [e for e in filtered.get('events', []) if e.get('year_match')]
            after = calculate_weighted_non_core_events(filtered)
            # Audit records whether filtered results differ; does not alter production.
            self.assertEqual(before['positive_events'], r['non_core']['positive_events'])
            self.assertIsInstance(after['positive_events'], list)

    def test_mag7_pipeline_score_isolation_and_no_duplicate_sec_requests(self):
        from src.services.earnings_quality_service import build_earnings_quality
        from src.data.reuse import data_scope
        from src.analysis.earnings_quality_narrative_evidence import load_narrative_evidence
        for t in TICKERS:
            with self.subTest(ticker=t), Replay() as replay:
                with data_scope():
                    result = build_earnings_quality(t)
                    before = len(replay.calls)
                    load_narrative_evidence(t)
                    self.assertEqual(len(replay.calls), before)
                counts = Counter(c for c in replay.calls if c[0].startswith('sec_'))
                self.assertTrue(all(n == 1 for n in counts.values()))
                baseline = json.loads((FIXTURES/'baseline'/f'{t}.json').read_text())['reports']
                self.assertEqual(result['legacy_quality_summary'], baseline['quality_summary'])
                self.assertEqual(result['non_core_evidence']['legacy_report'], baseline['non_core'])
                self.assertIn('statement_items', result['non_core_evidence'])
                self.assertIn('rejected_narrative_events', result['non_core_evidence'])

    def test_actual_narrative_reaches_rendered_ui_without_changing_scores(self):
        from src.analysis.earnings_quality_narrative_evidence import load_narrative_evidence
        from src.services.earnings_quality_service import build_earnings_quality
        from src.data.reuse import data_scope
        from flask import render_template
        with Replay() as replay:
            baseline = build_earnings_quality('AAPL')
            replay.clear_caches()
            # Synthetic qualifying paragraph alongside original fixture HTML.
            replay.raw['sec']['AAPL']['html'] += '<p>' + DISCLOSURE + '</p>'
            result = build_earnings_quality('AAPL')
            self.assertTrue(result['non_core_evidence']['narrative_events'])
            self.assertEqual(result['score_raw'], baseline['score_raw'])
            self.assertEqual(result['non_core_evidence']['legacy_report'], baseline['non_core_evidence']['legacy_report'])
            context = replay.context.build_company_context('AAPL', active_tab='earnings-quality')
            # Render via actual route, preserving the existing full template contract.
            response = replay.app_module.app.test_client().get('/research?ticker=AAPL&tab=earnings-quality')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'validated_narrative', response.data)
            self.assertIn(b'not included in legacy EQ scoring', response.data)

    def test_tables_not_promoted_into_narrative(self):
        from src.analysis.earnings_quality_narrative_evidence import load_narrative_evidence
        with Replay() as replay:
            replay.raw['sec']['AAPL']['html'] = '<table><tr><td>' + DISCLOSURE + '</td></tr></table>'
            self.assertEqual(load_narrative_evidence('AAPL')['narrative_events'], [])

    def test_other_new_topics_can_flow_without_new_financial_line_patterns(self):
        for topic, keyword in [('inventory_reserve_movements', 'inventory provision'),
                               ('supplier_financing', 'supplier financing'),
                               ('receivable_financing', 'sale of receivables')]:
            with self.subTest(topic=topic):
                text = f'For fiscal year 2025, we recorded a $20 million charge related to {keyword} in net income.'
                self.assertNotIn(topic, FINANCIAL_LINE_PATTERNS)
                self.assertTrue(any(topic in e['topics'] for e in build(text)['narrative_events']))

    def test_multi_year_discussion_does_not_assign_single_event_year(self):
        text = 'For fiscal year 2025, we recorded a $20 million benefit from regulatory credits compared with 2024 in net income.'
        self.assertIsNone(build(text)['narrative_events'][0]['fiscal_year'])

    def test_narrative_changes_neither_full_context_nor_diagnostic_rules(self):
        from src.services.earnings_quality_service import build_earnings_quality
        for ticker in TICKERS:
            with self.subTest(ticker=ticker), Replay() as replay:
                before = replay.context.build_company_context(ticker, active_tab='overview')
                eq_before = build_earnings_quality(ticker)
                replay.clear_caches()
                payload = build(DISCLOSURE)
                with patch('src.analysis.earnings_quality_narrative_evidence.load_narrative_evidence', return_value=payload):
                    after = replay.context.build_company_context(ticker, active_tab='overview')
                    eq_after = build_earnings_quality(ticker)
                self.assertEqual(before, after)
                self.assertEqual(eq_before['legacy_quality_summary'], eq_after['legacy_quality_summary'])
                self.assertEqual(eq_before['diagnostics'], eq_after['diagnostics'])
                self.assertEqual(eq_before['interpretation'], eq_after['interpretation'])
