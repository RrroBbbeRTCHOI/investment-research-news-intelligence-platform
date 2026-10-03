"""Real historical financial wording; frozen schema and matcher remain unchanged."""
import json
from pathlib import Path
import unittest
from src.news.event_gate import evaluate_gate
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.exposure_matcher import load_exposure_edges, match_exposures
from src.news.pipeline import _resolve_prediction_time
from .helpers import article

ROOT = Path(__file__).resolve().parents[2]

class FinancialWordingTests(unittest.TestCase):
    def event(self, text):
        return extract_event(article(text, headline=text))

    def test_production_reductions(self):
        for phrase in ('cuts production', 'cut production', 'reduced production',
                       'reduce production', 'production reduction', 'trimmed output',
                       'cuts output', 'reduced output'):
            with self.subTest(phrase=phrase):
                e = self.event(f'Tesla {phrase} at Shanghai factory.')
                self.assertIsNotNone(e)
                self.assertEqual(e['event_type'], 'supply_chain')
                self.assertEqual(e['event_subtype'], 'production_interruption')

    def test_no_production_cut(self):
        for text in ('No production cut occurred.', 'Tesla did not cut production.',
                     'Tesla production reduction was not confirmed.'):
            with self.subTest(text=text):
                self.assertIsNone(self.event(text))

    def test_forecasts_and_discussion_are_not_events(self):
        for text in ('Analysts forecast Tesla cuts production at Shanghai factory.',
                     'Tesla could reduce production at Shanghai factory.',
                     'Tesla plans to reduce production at Shanghai factory.',
                     'Tesla discusses production reduction at Shanghai factory.',
                     'An opinion on industry production reduction.',
                     'Tesla production cuts are expected by analysts.'):
            with self.subTest(text=text):
                self.assertIsNone(self.event(text))

    def test_export_curb_geography(self):
        e = self.event('U.S. updates export curbs on AI chips to China.')
        self.assertEqual((e['event_type'], e['event_subtype']),
                         ('trade_export_control', 'export_controls'))
        self.assertEqual(set(e['affected_countries']), {'United States', 'China'})
        self.assertEqual(e['primary_country'], 'United States')
        self.assertIs(e['export_restriction'], True)
        self.assertIs(e['regulatory_channel'], True)
        self.assertIn('regulatory_export', {c['channel_family'] for c in generate_channels(e)['candidate_channels']})

    def test_export_wording_variants(self):
        for text in ('The United States updated export curbs on chips to China.',
                     'The United States revised export restrictions on chips to China.',
                     'The United States restricted exports of chips to China.',
                     'The United States restricts exports of chips to China.',
                     'The United States tightens export rules on chips to China.',
                     'Additional licensing requirements were imposed on Nvidia AI-chip exports.',
                     'Nvidia disclosed expanded licensing requirements affecting chip exports.',
                     'The United States imposed an export licensing requirement on chips.'):
            with self.subTest(text=text):
                e = self.event(text)
                self.assertIsNotNone(e)
                self.assertEqual(e['event_type'], 'trade_export_control')
                self.assertIs(e['export_restriction'], True)

    def test_generic_regulation_stays_generic(self):
        e = self.event('The government introduced new licensing requirements for domestic businesses.')
        self.assertEqual((e['event_type'], e['event_subtype']), ('government_policy', 'regulation'))
        self.assertIsNone(e['export_restriction'])

    def test_export_negations_and_forecasts(self):
        for text in ('The U.S. did not update export curbs on chips to China.',
                     'No additional licensing requirements were imposed on chip exports.',
                     'The U.S. could tighten export rules on chips.',
                     'Analysts forecast the U.S. updates export curbs on chips.'):
            with self.subTest(text=text):
                self.assertIsNone(self.event(text))

    def test_no_invented_middle_east_country(self):
        e = self.event('The U.S. imposed additional licensing requirements affecting Nvidia chip exports to some Middle East countries.')
        self.assertEqual(e['affected_countries'], ['United States'])
        self.assertEqual(e['event_type'], 'trade_export_control')

    def test_historical_fixtures(self):
        edges, status = load_exposure_edges(ROOT)
        self.assertEqual(status['status'], 'loaded')
        expected = {
            'historical_H01': ('natural_disaster', set()),
            'historical_H02': ('trade_export_control', {('NVDA', '5')}),
            'historical_H03': ('infrastructure_outage', {('AMZN', '17')}),
            'historical_H04': ('supply_chain', {('TSLA', '23')}),
            'historical_H05': ('trade_export_control', {('NVDA', '5')}),
            'historical_H06': ('trade_export_control', set()),
        }
        for filename in ('historical_validation_H01_H03.json', 'historical_validation_H04_H06.json'):
            for a in json.loads((ROOT / 'data/news/normalized' / filename).read_text())['articles']:
                with self.subTest(article=a['article_id']):
                    e = extract_event(a)
                    self.assertIsNotNone(e)
                    kind, matches = expected[a['article_id']]
                    self.assertEqual(e['event_type'], kind)
                    pairs, _ = match_exposures(e, generate_channels(e), edges,
                        prediction_time=_resolve_prediction_time(a).isoformat())
                    actual = {(p['ticker'], str(edge['edge_id'])) for p in pairs for edge in p['matched_edges']}
                    self.assertEqual(actual, matches)
                    if a['article_id'] in ('historical_H05', 'historical_H06'):
                        self.assertIs(e['export_restriction'], True)
                        self.assertIs(e['regulatory_channel'], True)
