"""Fabrication and packaging evidence stay separate through real workbook matching."""
import copy
import json
from pathlib import Path
import unittest

from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.exposure_matcher import load_exposure_edges, match_exposures
from .helpers import article

ROOT = Path(__file__).resolve().parents[2]


def families(event):
    return {c['channel_family'] for c in generate_channels(event)['candidate_channels']}


class ChannelSpecificityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs = json.loads((ROOT / 'data/news/normalized/tsmc_specificity_test.json').read_text())['articles']
        cls.fab, cls.packaging, cls.training = [extract_event(a) for a in inputs]
        cls.edges, status = load_exposure_edges(ROOT)
        assert status['status'] == 'loaded'

    def matches(self, event):
        pairs, _ = match_exposures(event, generate_channels(event), self.edges,
                                  prediction_time='2026-09-18T09:00:00Z')
        return {(p['ticker'], str(e['edge_id'])) for p in pairs for e in p['matched_edges']}

    def test_01_fabrication_channel(self):
        self.assertIn('advanced_semiconductors', families(self.fab))

    def test_02_fabrication_production_flag(self):
        self.assertIs(self.fab['production_disruption'], True)

    def test_03_unaffected_packaging_is_not_positive(self):
        self.assertNotIn('advanced_packaging', families(self.fab))
        self.assertNotIn('advanced packaging', self.fab['technologies_mentioned'])
        self.assertNotIn('CoWoS', self.fab['technologies_mentioned'])

    def test_04_packaging_channel(self):
        self.assertIn('advanced_packaging', families(self.packaging))

    def test_05_normal_fabrication_is_not_positive(self):
        self.assertNotIn('advanced_semiconductors', families(self.packaging))
        self.assertNotIn('wafer fabrication', self.packaging['technologies_mentioned'])

    def test_06_fab_nvda_edge_1(self):
        self.assertIn(('NVDA', '1'), self.matches(self.fab))

    def test_07_fab_aapl_edge_6(self):
        self.assertIn(('AAPL', '6'), self.matches(self.fab))

    def test_08_fab_excludes_packaging_edge_2(self):
        self.assertNotIn(('NVDA', '2'), self.matches(self.fab))

    def test_09_packaging_nvda_edge_2(self):
        self.assertIn(('NVDA', '2'), self.matches(self.packaging))

    def test_10_packaging_excludes_fab_edges(self):
        self.assertEqual(self.matches(self.packaging), {('NVDA', '2')})

    def test_training_still_rejected(self):
        self.assertIsNone(self.training)

    def test_fab_aliases_are_not_company_specific(self):
        for term in ('wafer fabrication', 'logic wafers', 'leading-edge logic',
                     'semiconductor fabrication', 'foundry production', 'fab production',
                     '3nm process', '4nm process', '5nm process'):
            with self.subTest(term=term):
                text = f'A manufacturer reported a production interruption in Taiwan affecting {term}.'
                event = extract_event(article(text, headline=text))
                self.assertIn('advanced_semiconductors', families(event))
                self.assertNotIn('advanced_packaging', families(event))

    def test_packaging_aliases(self):
        for term in ('CoWoS', 'CoWoS-L', 'CoWoS-S', 'advanced packaging',
                     'chip packaging', 'packaging capacity'):
            with self.subTest(term=term):
                text = f'A supplier reported a packaging disruption in Taiwan affecting {term}.'
                event = extract_event(article(text, headline=text))
                self.assertIn('advanced_packaging', families(event))
                self.assertNotIn('advanced_semiconductors', families(event))

    def test_production_flag_positive_wording(self):
        for text in ('Production interruption affects Taiwan output.',
                     'Wafer fabrication interruption affects Taiwan output.',
                     'Fab production halt affects Taiwan output.'):
            with self.subTest(text=text):
                event = extract_event(article(text, headline=text))
                self.assertIs(event['production_disruption'], True)

    def test_production_flag_negative_and_unknown(self):
        for text in ('Wafer fabrication was not interrupted.',
                     'Production was not disrupted.',
                     'Wafer fabrication continued operating normally.'):
            with self.subTest(text=text):
                event = extract_event(article('An earthquake struck Taiwan. ' + text))
                self.assertIs(event['production_disruption'], False)
        self.assertIsNone(extract_event(article('An earthquake struck Taiwan.'))['production_disruption'])

    def test_generator_rechecks_negated_technology_evidence(self):
        event = copy.deepcopy(self.packaging)
        event['technologies_mentioned'] = ['wafer fabrication']
        event['evidence_fields']['technologies_mentioned'] = {
            'evidence': 'Wafer fabrication continued operating normally.'}
        self.assertNotIn('advanced_semiconductors', families(event))

    def test_provenance_contains_actual_positive_technology(self):
        snippets = self.fab['evidence_fields']['technologies_mentioned']['supporting_snippets']
        self.assertTrue(any('wafer fabrication interruption' in s['evidence'] for s in snippets))
        self.assertFalse(any('not affected' in s['evidence'] for s in snippets))

    def test_specific_packaging_cannot_be_refined_to_fab(self):
        text = 'TSMC production interruption affects CoWoS packaging capacity in Taiwan.'
        event = extract_event(article(text, headline=text))
        self.assertIs(event['production_disruption'], True)
        self.assertEqual(self.matches(event), {('NVDA', '2')})
