"""Offline live-intake tests; frozen research is not regraded."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.live_content import classify_live_content, is_live_commentary_or_valuation
from src.news.live_runner import LiveRunner
from src.news.live_config import LiveConfig
from src.news.v3_config import Config
from src.news.v3_validation import prefilter

SKIP = [
    'TSMC Stock: An AI Technology Leader Trading At Just 0.7x PEG',
    'Is Nvidia Stock a Buy?',
    'Apple Stock Looks Undervalued',
    'Tesla Price Target Raised to $300',
    '3 Reasons to Buy Microsoft Stock',
    'Meta Stock: Bull Case and Bear Case',
    'Amazon Technical Analysis: Key Support Levels',
    'Top 5 AI Stocks to Buy Now',
    'Why I Bought Nvidia',
    'GOOGL Valuation Looks Attractive',
    'Apple Shares Trade at 25x Earnings',
    'TSMC Is Cheap At Current Multiples',
    'Microsoft Stock Looks Overvalued',
    'Nvidia Investment Thesis',
]
EVENT = [
    'TSMC expands advanced packaging capacity',
    'TSMC reports quarterly earnings',
    'Nvidia raises revenue guidance',
    'Apple supplier halts production',
    'FTC opens investigation into Meta',
    'EU fines Apple',
    'US imposes import ban on Apple devices',
    'Saudi Arabia ramps up oil shipments through Strait of Hormuz',
    'Microsoft announces acquisition of cybersecurity company',
    'Nvidia reports earnings and trades at 30x forward earnings',
    'Apple announces acquisition; analysts call valuation expensive',
    'TSMC expands capacity despite rich valuation',
    'Microsoft acquires company at a high earnings multiple',
    'Microsoft to buy cybersecurity company for $5 billion',
]
OUTLOOK = [
    'Microsoft earnings set for Thursday',
    'Nvidia earnings preview: AI demand in focus',
    'Microsoft earnings preview: valuation in focus',
    'Nvidia earnings set for Wednesday; valuation remains elevated',
    'Fed meeting ahead as markets watch rate guidance',
]

class CommentaryIntakeTests(unittest.TestCase):
    def check_routes(self, headlines, expected):
        for headline in headlines:
            with self.subTest(headline=headline):
                a = {'headline': headline}
                self.assertEqual(classify_live_content(a, prefilter(a))['content_type'], expected)

    def test_commentary_skips_even_if_prefilter_surfaces_it(self):
        self.check_routes(SKIP, 'skip')
        for headline in SKIP:
            a = {'headline': headline}
            self.assertTrue(is_live_commentary_or_valuation(a))
            self.assertEqual(classify_live_content(a, {'state': 'surface'})['content_type'], 'skip')

    def test_actual_event_override(self):
        self.check_routes(EVENT, 'event')

    def test_outlook_override(self):
        self.check_routes(OUTLOOK, 'outlook')

    def test_no_bare_buy_sell_price_or_target_filter(self):
        for headline in ['Microsoft to buy cybersecurity company for $5 billion',
                         'Apple to sell new devices', 'Nvidia price update',
                         'Microsoft target update']:
            self.assertFalse(is_live_commentary_or_valuation({'headline': headline}))

    def test_frozen_reject_and_hard_noise_still_win(self):
        self.assertEqual(classify_live_content({'headline': EVENT[0]}, {'state': 'reject'})['content_type'], 'skip')
        self.assertEqual(classify_live_content({'headline': 'Celebrity interview: Nvidia reports earnings'}, {'state': 'surface'})['content_type'], 'skip')

    def test_headline_only_not_incidental_body_terms(self):
        a = {'headline': 'Nvidia management discusses AI demand', 'body': 'Analysts debate fair value and P/E.'}
        self.assertFalse(is_live_commentary_or_valuation(a))
        self.assertFalse(is_live_commentary_or_valuation({'headline': None}))

    def test_negated_or_modal_action_is_not_an_override(self):
        for headline in ['Apple could announce acquisition; valuation looks expensive',
                         'Apple has not announced acquisition; valuation in focus']:
            a = {'headline': headline}
            self.assertEqual(classify_live_content(a, {'state': 'surface'})['content_type'], 'skip')

    def test_skip_uses_no_research_or_gemini_and_keeps_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = LiveConfig(enabled=True, state_dir=root/'state',
                                output=root/'news_research_live_current.json')
            rows = [{'articleId': 'valuation-1', 'title': SKIP[0]}]
            with patch('src.news.live_runner.build_research_output_v3', side_effect=AssertionError('No research expected')), \
                 patch('src.news.llm.analyzer.Analyzer.analyze_article', side_effect=AssertionError('No Gemini expected')):
                runner = LiveRunner(config, Config(), fetch=lambda *args: rows)
                first = runner.cycle()
                second = runner.cycle()
            self.assertEqual(first['skip_count'], 1)
            self.assertEqual(first['cheap_reject_count'], 1)
            self.assertEqual(first['gemini_calls_this_cycle'], 0)
            self.assertEqual(first['pending_count'], 0)
            self.assertEqual(first['article_count'], 0)
            self.assertEqual(second['duplicate_count'], 1)
