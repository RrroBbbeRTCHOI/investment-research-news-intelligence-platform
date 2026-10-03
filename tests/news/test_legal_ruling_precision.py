"""Prospective legal-action QA; no market outcomes or exposure-rule changes."""
import json
from pathlib import Path
from unittest import TestCase
from src.news.event_gate import evaluate_gate
from src.news.event_extractor import extract_event
from .helpers import article


class LegalRulingPrecisionTests(TestCase):
    def check(self, text, accepted):
        a = article(text, headline=text)
        self.assertEqual(evaluate_gate(a)['is_event'], accepted, text)
        event = extract_event(a)
        if accepted:
            self.assertEqual(event['event_type'], 'legal_antitrust', text)
        else:
            self.assertIsNone(event, text)

    def test_exact_full_real_article(self):
        path = Path(__file__).resolve().parents[2] / 'data/news/normalized/mag7_live_sample21_20260921.json'
        rows = json.loads(path.read_text())['articles']
        a = next(a for a in rows if a['headline'] == 'In Washington, temples to Trump’s ego lie ruined. And another is on the way')
        self.assertFalse(evaluate_gate(a)['is_event'])
        self.assertIsNone(extract_event(a))

    def test_court_blocks_technology_rule(self):
        self.check('Federal appeals court blocks enforcement of new technology rule.', True)

    def test_antitrust_ruling(self):
        self.check('Court rules against Google in antitrust case.', True)

    def test_commentary_mention(self):
        self.check('Column: what the court ruling means for Washington politics.', False)

    def test_historical_background(self):
        self.check('The article revisits a court ruling from three years ago.', False)

    def test_connected_legal_actions(self):
        for text in ['The court ruled against Google.', 'A judge ordered a company to comply.',
                     'The appeals court upheld the injunction.', 'The court dismissed the lawsuit.',
                     'The regulator issued a binding compliance order.',
                     'A formal ruling was issued.', 'A regulatory settlement was announced.']:
            with self.subTest(text=text):
                self.check(text, True)

    def test_background_and_unrelated_actions(self):
        for text in ['Scaffolding covers the signage where a court ordered removal of a name.',
                     'The article revisits how the court ruled against a company.',
                     'Column: what it means that the court ruled against the administration.',
                     'The court building is near the road blocked by spectators.',
                     'The court might rule against the company.', 'The court has not ruled.',
                     'The court issued a newsletter about architecture.',
                     'The court ruled against a company three years ago.']:
            with self.subTest(text=text):
                self.check(text, False)

    def test_analysis_does_not_veto_asserted_action(self):
        a = article('The court ruled against Google in an antitrust case. Analysts discuss the implications.',
                    headline='Analysis: implications of the Google case')
        self.assertTrue(evaluate_gate(a)['is_event'])
        self.assertEqual(extract_event(a)['event_subtype'], 'ruling')
