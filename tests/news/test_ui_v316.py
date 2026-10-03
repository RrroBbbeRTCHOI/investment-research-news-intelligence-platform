"""Read-only frozen V3.1.6 presentation contracts."""
import hashlib
import json
import unittest
from pathlib import Path
from src.news.ui_api import DEFAULT_OUTPUT, read_intelligence

ROOT = Path(__file__).resolve().parents[2]


class FrozenUIContracts(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / DEFAULT_OUTPUT
        self.raw = self.path.read_bytes()
        self.source = json.loads(self.raw)
        self.payload, self.status = read_intelligence(ROOT, DEFAULT_OUTPUT)

    def article(self, case):
        return next(a for a in self.payload['articles'] if f'_{case}_' in a['article_id'])

    def test_default_frozen_summary(self):
        self.assertEqual(self.status, 200)
        self.assertEqual(len(self.payload['articles']), 12)
        states = [a['feed']['state'] for a in self.payload['articles']]
        self.assertEqual(states.count('surface'), 11)
        self.assertEqual(states.count('reject'), 1)
        self.assertEqual(self.payload['summary'], self.source['summary'])

    def test_final_fields_and_provenance_preserved(self):
        for old, new in zip(self.source['articles'], self.payload['articles']):
            for field in ('geography', 'severity', 'classification', 'feed', 'research_priority'):
                self.assertEqual(old.get(field), new.get(field))
            if old.get('event'):
                for field in ('event_type', 'event_subtype', 'evidence_fields'):
                    self.assertEqual(old['event'].get(field), new['event'].get(field))
            for before, after in zip(old['ticker_analysis'], new['ticker_analysis']):
                for field in ('qualification', 'relationship_type', 'financial_materiality', 'relevance'):
                    self.assertEqual(before.get(field), after.get(field))

    def test_aws_qualified_and_review_are_separate(self):
        tickers = {t['ticker']: t for t in self.article('ST07')['ticker_analysis']}
        self.assertEqual(tickers['AMZN']['qualification'], 'qualified_direct_event_subject')
        self.assertEqual(tickers['AAPL']['qualification'], 'candidate_requires_review')

    def test_fed_and_hormuz_geography(self):
        fed = self.article('ST01')
        self.assertEqual(fed['severity']['level'], 'Unknown')
        self.assertEqual(fed['geography']['location_basis'], 'institutional_event_origin')
        for case in ('ST09', 'ST10'):
            article = self.article(case)
            self.assertIsNone(article['geography']['event_country'])
            self.assertEqual(article['geography']['event_region'], 'Strait of Hormuz')
            self.assertEqual(article['severity']['level'], 'High')
            self.assertEqual(article['ticker_analysis'], [])

    def test_snapshot_never_rewritten(self):
        self.assertEqual(hashlib.sha256(self.raw).digest(), hashlib.sha256(self.path.read_bytes()).digest())

