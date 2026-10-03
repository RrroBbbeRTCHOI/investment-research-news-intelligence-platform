"""Offline Live Intake Policy V1 contracts and minimal Research lane wiring."""
import json
import tempfile
import unittest
from pathlib import Path
from src.news.live_intake_policy import classify_live_intake, is_investment_editorial
from src.news.live_content import classify_live_content, display_type
from src.news.live_runner import LiveRunner
from src.news.live_config import LiveConfig
from src.news.v3_config import Config
from src.news.v3_validation import prefilter
from .test_v3 import FakeProvider

CASES = {
    'event': [
        'Fed cuts rates by 25 basis points',
        'Nvidia raises revenue guidance',
        'Apple supplier halts production',
        'FTC opens investigation into Meta',
        'EU fines Apple',
        'Saudi Arabia ramps up oil shipments through Strait of Hormuz',
        'Microsoft announces acquisition of cybersecurity company',
        'Congress passes AI law', 'FTC opens AI probe',
        'Import ban imposed on Apple devices',
        'CPI released above expectations',
        'Microsoft to buy cybersecurity company for $5 billion',
    ],
    'outlook': [
        'Microsoft earnings set for Thursday',
        'Nvidia earnings preview: AI demand in focus',
        'Fed meeting ahead as markets watch rate guidance',
        'Micron reports earnings Wednesday',
        'Regulatory ruling expected next week',
        'CPI release tomorrow',
        'Apple may face import ban',
        'Nvidia reports Wednesday',
        'Microsoft product launch scheduled for Thursday',
    ],
    'research': [
        'India ranks in low category in AI adoption curve despite high search interest',
        'Bill Gates calls for stronger AI safeguards and legislation',
        'Bill Gates joins calls for AI safeguards, including legislation',
        'AI adoption remains uneven across emerging markets',
        'Semiconductor packaging remains a structural bottleneck',
        'US-China fragile truce highlights long-term trade uncertainty',
        'Lawmakers urge regulation',
        'Nvidia CEO discusses AI safety and existing strategy',
    ],
    'skip': [
        'TSMC Stock: An AI Technology Leader Trading At Just 0.7x PEG',
        'Top Three S&P 500 Stocks to Watch This Week: Micron, Accenture, Tesla',
        'Is Nvidia Stock a Buy?',
        'Amazon Technical Analysis: Key Support Levels',
        'Top 5 AI Stocks to Buy Now', 'Why I Bought Nvidia',
        'Meta Stock: Bull Case and Bear Case',
        'Stocks investors should watch this week',
        'Top five stocks for the week ahead',
        'General market outlook for next week',
    ],
}


class IntakePolicyTests(unittest.TestCase):
    def decision(self, headline, **extra):
        article = {'headline': headline, **extra}
        return classify_live_intake(article, prefilter(article))

    def check_group(self, kind):
        for headline in CASES[kind]:
            with self.subTest(headline=headline):
                self.assertEqual(self.decision(headline)['content_type'], kind)

    def test_events(self): self.check_group('event')
    def test_outlooks(self): self.check_group('outlook')
    def test_research(self): self.check_group('research')
    def test_skips(self): self.check_group('skip')

    def test_audit_and_wrapper_are_deterministic(self):
        for headlines in CASES.values():
            for h in headlines:
                a = {'headline': h}; p = prefilter(a)
                expected = classify_live_intake(a, p)
                self.assertEqual(classify_live_content(a, p), expected)
                self.assertEqual(classify_live_intake(a, p), expected)
                self.assertEqual(expected['policy_version'], 'live_intake_v1')
                self.assertIsInstance(expected['reason'], str)
                self.assertTrue(expected['reason'])
                self.assertTrue(expected['signals'])
                self.assertTrue(all(isinstance(s, str) for s in expected['signals']))

    def test_actual_event_and_outlook_override_editorial(self):
        cases = {
            'Opinion: Fed cuts rates by 50 basis points': 'event',
            'Commentary: Nvidia raises revenue guidance': 'event',
            'Opinion: Microsoft earnings set for Thursday': 'outlook',
            'Nvidia earnings preview: valuation in focus': 'outlook',
            'Top Stocks Today: Tesla reports quarterly earnings': 'event',
        }
        for h, expected in cases.items():
            with self.subTest(headline=h):
                self.assertEqual(self.decision(h, article_url='https://example.com/opinion/story')['content_type'], expected)

    def test_editorial_path_is_not_domain_reputation(self):
        h = 'AI adoption remains uneven across emerging markets'
        for domain in ['example.com', 'unknown.test']:
            d = self.decision(h, article_url=f'https://{domain}/opinion/story')
            self.assertEqual(d['content_type'], 'research')
            self.assertIn('editorial_path', d['signals'])
        h = 'There wasn’t much to Xi: A red carpet, a fragile truce and the search for US-China stability'
        self.assertEqual(self.decision(h, article_url='https://example.com/opinion/et-commentary/story')['content_type'], 'skip')

    def test_bare_words_do_not_make_editorial(self):
        for h in ['Microsoft to buy cybersecurity company for $5 billion',
                  'Apple to sell new devices', 'Stocks rise after Fed decision',
                  'Investors watch Fed as meeting begins', 'Apple price update']:
            with self.subTest(headline=h):
                self.assertFalse(is_investment_editorial({'headline': h}))
                self.assertFalse(set(self.decision(h)['signals']) & {'valuation', 'stock_picking', 'stock_listicle', 'technical_analysis'})

    def test_noise_and_reject_still_win(self):
        a = {'headline': 'Fed cuts rates by 25 basis points'}
        self.assertEqual(classify_live_intake(a, {'state': 'reject'})['content_type'], 'skip')
        self.assertEqual(self.decision('Celebrity interview: Microsoft earnings set for Thursday')['content_type'], 'skip')

    def test_listicle_summary_does_not_manufacture_outlook(self):
        d = self.decision('Top three stocks to watch this week', summary='Microsoft earnings set for Thursday')
        self.assertEqual(d['content_type'], 'skip')

    def test_research_is_not_a_dumping_ground(self):
        self.assertEqual(self.decision('Why I bought Nvidia', summary='AI adoption remains uneven')['content_type'], 'skip')
        self.assertEqual(self.decision('Generic opinion on life')['content_type'], 'skip')

    def test_modal_and_historical_context(self):
        self.assertEqual(self.decision('Microsoft may announce acquisition; valuation looks expensive')['content_type'], 'skip')
        self.assertEqual(self.decision('US imposes import ban after Apple faced months of legal threat')['content_type'], 'event')
        self.assertEqual(self.decision('Investors await CPI report next week', body='US CPI rose 3.2% last month')['content_type'], 'outlook')

    def test_legacy_eligibility_is_research_not_event_confirmation(self):
        d = classify_live_intake({'headline': 'Company business discussion'}, {'state': 'surface'})
        self.assertEqual(d['content_type'], 'research')
        self.assertEqual(d['signals'], ['legacy_eligibility'])

    def test_research_reuses_existing_pipeline_and_final_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = LiveConfig(enabled=True, state_dir=root/'state', output=root/'news_research_live_current.json')
            llm = Config(provider='gemini', model='test', api_key='fake', cache_dir=root/'llm')
            provider = FakeProvider()
            raw = {'articleId': 'research-1', 'title': 'Nvidia CEO discusses AI safety',
                   'content': 'Nvidia CEO discusses AI safety and existing strategy.',
                   'source': {'domain': 'example.com'}, 'pubDate': '2026-09-27T00:00:00Z',
                   'url': 'https://example.com/article/research-1'}
            result = LiveRunner(c, llm, fetch=lambda *args: [raw], provider=provider).cycle()
            record = json.loads(c.output.read_text())['articles'][0]
            self.assertEqual(provider.calls, 1)
            self.assertEqual(result['event_count'], 1)  # Existing processing counter.
            self.assertEqual(record['intake']['content_type'], 'research')
            self.assertEqual(record['intake']['policy_version'], 'live_intake_v1')
            self.assertEqual(record['content_type'], 'event')  # Compatible backend lane.
            self.assertFalse(record['gate']['is_event'])
            self.assertEqual(record['display_type'], 'research')
            self.assertEqual(display_type({'content_type': 'event', 'gate': {'is_event': True}}), 'event')
