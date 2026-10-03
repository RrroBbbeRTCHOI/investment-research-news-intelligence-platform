"""Operational wording regressions; no exposure-matcher changes required."""
import json
from pathlib import Path
import unittest

from src.news.event_gate import evaluate_gate, event_evidence
from .helpers import article


class OperationalGateTests(unittest.TestCase):
    def check_text(self, text, accepted):
        value = article(body='', headline=text)
        self.assertEqual(evaluate_gate(value)['is_event'], accepted, text)
        if accepted:
            self.assertEqual(event_evidence(value)['event_type'], 'supply_chain')

    def test_production_interruption(self):
        self.check_text('A production interruption affects output at the manufacturer.', True)

    def test_wafer_fabrication_interruption(self):
        self.check_text('TSMC wafer fabrication interruption affects advanced chip production in Taiwan', True)

    def test_packaging_disruption(self):
        for text in (
            'TSMC CoWoS packaging disruption delays advanced AI chip packaging',
            'Advanced packaging disruption delays orders.',
            'A temporary interruption affected CoWoS operations.',
        ):
            with self.subTest(text=text):
                self.check_text(text, True)

    def test_general_operational_vocabulary(self):
        for phrase in (
            'production halt', 'production suspension', 'manufacturing interruption',
            'fabrication interruption', 'packaging interruption', 'capacity disruption',
            'assembly interruption', 'shipment disruption', 'operational disruption',
        ):
            with self.subTest(phrase=phrase):
                self.check_text(f'A supplier reported a {phrase} today.', True)

    def test_verbal_actions(self):
        for text in ('An equipment issue interrupted wafer fabrication.',
                     'The supplier suspended assembly.',
                     'Packaging was disrupted by an equipment failure.'):
            with self.subTest(text=text):
                self.check_text(text, True)

    def test_production_continued_normally(self):
        self.check_text('Production continued normally.', False)
        self.check_text('Wafer fabrication continued operating normally.', False)

    def test_cowos_unaffected(self):
        self.check_text('CoWoS was not affected.', False)

    def test_negated_disruption_evidence(self):
        for text in ('Wafer fabrication was not interrupted.',
                     'CoWoS packaging was not disrupted.',
                     'There was no packaging disruption.',
                     'The announcement did not involve production interruptions or packaging disruptions.',
                     'Officials denied a fabrication interruption.',
                     'There is no evidence of a capacity disruption.'):
            with self.subTest(text=text):
                self.check_text(text, False)

    def test_hypothetical_and_historical_events(self):
        for text in ('Packaging could be disrupted.',
                     'A potential fabrication interruption threatens output.',
                     'A production interruption occurred last year.'):
            with self.subTest(text=text):
                self.check_text(text, False)

    def test_employee_training(self):
        self.check_text('TSMC announces employee training initiative in Taiwan', False)

    def test_generic_company_announcements(self):
        for text in ('TSMC announces a corporate initiative.',
                     'TSMC announces a hiring program for fabrication staff.',
                     'TSMC announces employee training for packaging operations.',
                     'An executive interview discusses manufacturing strategy.',
                     'TSMC discusses its long-term outlook for advanced packaging.'):
            with self.subTest(text=text):
                self.check_text(text, False)

    def test_positive_clause_with_independent_negation(self):
        value = article(headline='', body=(
            'Wafer fabrication was interrupted. CoWoS was not affected.'))
        evidence = event_evidence(value)
        self.assertIsNotNone(evidence)
        self.assertIn('fabrication', evidence['clause'])
        self.assertNotIn('CoWoS', evidence['clause'])

    def test_specificity_fixture(self):
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root / 'data/news/normalized/tsmc_specificity_test.json').read_text())
        results = {a['article_id']: evaluate_gate(a)['is_event'] for a in data['articles']}
        self.assertEqual(results, {
            'tsmc_spec_001': True, 'tsmc_spec_002': True, 'tsmc_spec_003': False,
        })
