"""Targeted digital-service outage recall and explicit outage geography."""
import json
from pathlib import Path
import unittest
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from .helpers import article

ROOT = Path(__file__).resolve().parents[2]

class ServiceOutageTests(unittest.TestCase):
    def event(self, text, **kwargs):
        return extract_event(article(text, headline=text, **kwargs))

    def test_google_cloud_outage(self):
        e = self.event('Google Cloud suffers global service outage')
        self.assertEqual((e['event_type'],e['event_subtype']),('infrastructure_outage','outage'))

    def test_google_recovery(self):
        e = self.event('Google services restored after global outage')
        self.assertEqual(e['event_type'],'infrastructure_outage')

    def test_facebook_recovery(self):
        e = self.event('Facebook and Instagram back up after global outage')
        self.assertEqual(e['event_type'],'infrastructure_outage')
        self.assertIn('META',e['tickers_mentioned'])

    def test_negation(self):
        self.assertIsNone(self.event('Meta says no outage occurred'))
        self.assertIsNone(self.event('Google services were not down'))

    def test_future_commentary(self):
        for text in ('Analysts discuss risk of future cloud outages',
                     'Google services could become unavailable.',
                     'Google service outage could occur tomorrow.',
                     'Analysts discuss cloud outage risk.',
                     'If Google services went down, customers could suffer.',
                     'Google services went down last year.',
                     'A historical example of Google service outage.'):
            with self.subTest(text=text): self.assertIsNone(self.event(text))

    def test_explicit_germany(self):
        e = self.event('Tesla Germany factory loses power and production stops')
        self.assertIn('Germany',e['affected_countries'])
        self.assertEqual(e['primary_country'],'Germany')

    def test_country_outside_selected_clause(self):
        e = extract_event(article('Tesla factory suffered a power outage.',
                                 headline='Tesla Germany factory halts work'))
        self.assertEqual(e['primary_country'],'Germany')

    def test_country_metadata(self):
        e = self.event('Tesla factory suffered a power outage.',countries=['Germany'])
        self.assertEqual(e['primary_country'],'Germany')
        self.assertEqual(e['evidence_fields']['primary_country']['source_field'],'countries')

    def test_no_city_or_global_inference(self):
        for text in ('Tesla factory near Berlin suffered a power outage.',
                     'Google Cloud suffers global service outage.'):
            with self.subTest(text=text):
                self.assertEqual(self.event(text)['affected_countries'],[])

    def test_factory_interruption_not_service_outage(self):
        e = self.event('TSMC wafer fabrication interruption affects production in Taiwan.')
        self.assertEqual(e['event_type'],'supply_chain')

    def test_service_variants(self):
        for phrase in ('global service outage','technical outage','platform outage',
                       'service disruption','technical disruption','services unavailable',
                       'services went down','services were down','systems went down',
                       'platform went down','service restored',
                       'operations restored after disruption'):
            with self.subTest(phrase=phrase):
                e = self.event('Google '+phrase)
                self.assertIsNotNone(e)
                self.assertEqual(e['event_type'],'infrastructure_outage')

    def test_historical_07_12(self):
        data=json.loads((ROOT/'data/news/normalized/historical_validation_H07_H12.json').read_text())['articles']
        events={a['article_id']:extract_event(a) for a in data}
        self.assertIsNone(events['historical_H07'])
        self.assertIsNone(events['historical_H12'])
        for key in ('historical_H08','historical_H09','historical_H10','historical_H11'):
            self.assertEqual(events[key]['event_type'],'infrastructure_outage')
        self.assertEqual(events['historical_H10']['primary_country'],'Germany')
        self.assertIn('META',events['historical_H11']['tickers_mentioned'])
        channels={c['channel_family'] for c in generate_channels(events['historical_H09'])['candidate_channels']}
        self.assertTrue({'cloud_services','datacenter_infrastructure'}<=channels)
