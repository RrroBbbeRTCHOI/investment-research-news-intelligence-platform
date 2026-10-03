"""Offline final-status regression; processing and pagination remain unchanged."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.live_config import LiveConfig
from src.news.live_runner import LiveRunner
from src.news.v3_config import Config
from .test_v3 import FakeProvider


class LiveStatusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.config = LiveConfig(enabled=True, page_size=1, state_dir=root/'state',
                                 output=root/'news_research_live_current.json')
        self.llm = Config(provider='gemini', model='test', api_key='fake', cache_dir=root/'llm')
        self.provider = FakeProvider()
        self.raw = {'articleId': '1', 'title': 'Nvidia CEO discusses AI safety',
                    'content': 'Nvidia CEO discusses AI safety and existing strategy.',
                    'source': {'domain': 'example.com'}, 'pubDate': '2026-09-27T00:00:00Z',
                    'url': 'https://example.com/article/1'}

    def cycle(self, rows=None, fetch=None):
        return LiveRunner(self.config, self.llm,
                          fetch=fetch if fetch is not None else lambda *args: rows,
                          provider=self.provider).cycle()

    def state(self):
        return json.loads((self.config.state_dir/'state.json').read_text())

    def assert_success(self, stats):
        self.assertEqual(stats['pending_count'], 0)
        self.assertEqual(stats['quota_deferred_count'], 0)
        self.assertEqual(stats['pipeline_status'], 'live')
        self.assertNotIn('backlog', stats.get('reason', '').lower())
        stored = json.loads((self.config.state_dir/'status.json').read_text())
        self.assertEqual(stored['pipeline_status'], 'live')
        self.assertNotIn('backlog', stored.get('reason', '').lower())

    def test_full_page_completed_is_live_with_open_window(self):
        stats = self.cycle([self.raw])
        self.assert_success(stats)
        self.assertEqual(stats['article_count'], 1)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.state()['window']['page'], 1)
        self.assertIsNone(stats['last_successful_fetch_utc'])
        self.assertIsNotNone(stats['provider_fetch_at_utc'])

    def test_quota_deferred_remains_degraded(self):
        self.config.max_calls = 0
        stats = self.cycle([self.raw])
        self.assertEqual(stats['pending_count'], 1)
        self.assertEqual(stats['quota_deferred_count'], 1)
        self.assertEqual(stats['pipeline_status'], 'degraded')
        self.assertIn('backlog', stats['reason'].lower())
        self.assertEqual(self.provider.calls, 0)

    def test_unprocessed_pending_without_quota_defer_is_backlog(self):
        self.config.page_size = 3
        self.config.max_articles = 1
        other = {**self.raw, 'articleId': '2', 'url': 'https://example.com/article/2',
                 'content': 'Nvidia CEO discusses AI safety and a different company strategy.'}
        stats = self.cycle([self.raw, other])
        self.assertEqual(stats['pending_count'], 1)
        self.assertEqual(stats['quota_deferred_count'], 0)
        self.assertEqual(stats['pipeline_status'], 'degraded')
        self.assertIn('backlog', stats['reason'].lower())

    def test_provider_failure_preserves_snapshot_and_reason(self):
        self.cycle([self.raw])
        snapshot = self.config.output.read_bytes()
        def fail(*args):
            raise RuntimeError('mock provider failure')
        stats = self.cycle(fetch=fail)
        self.assertEqual(stats['pending_count'], 0)
        self.assertEqual(stats['quota_deferred_count'], 0)
        self.assertEqual(stats['pipeline_status'], 'degraded')
        self.assertEqual(stats['reason'], 'Provider unavailable; showing cached results')
        self.assertEqual(self.config.output.read_bytes(), snapshot)
        self.assertEqual(self.provider.calls, 1)

    def test_successful_empty_fetch_is_live(self):
        stats = self.cycle([])
        self.assert_success(stats)
        self.assertEqual(stats['article_count'], 0)
        self.assertIsNone(self.state()['window'])
        self.assertIsNotNone(stats['last_successful_fetch_utc'])
        self.assertEqual(self.provider.calls, 0)

    def test_full_page_skips_without_records_is_live(self):
        stats = self.cycle([{**self.raw, 'title': 'Is Nvidia Stock a Buy?'}])
        self.assert_success(stats)
        self.assertEqual(stats['article_count'], 0)
        self.assertEqual(stats['skip_count'], 1)
        self.assertEqual(self.state()['window']['page'], 1)
        self.assertEqual(self.provider.calls, 0)

    def test_processing_failure_remains_degraded(self):
        with patch('src.news.live_runner.build_research_output_v3', side_effect=RuntimeError('mock processing failure')):
            stats = self.cycle([self.raw])
        self.assertEqual(stats['pending_count'], 1)
        self.assertEqual(stats['pipeline_status'], 'degraded')
        self.assertIn('backlog', stats['reason'].lower())

    def test_pagination_still_advances_to_completed_watermark(self):
        self.cycle([self.raw])
        window = self.state()['window'].copy()
        calls = []
        def fetch(*args):
            calls.append(args)
            return []
        stats = self.cycle(fetch=fetch)
        self.assert_success(stats)
        self.assertEqual(calls[0][1:4], (window['start'], window['end'], 1))
        self.assertEqual(stats['last_successful_fetch_utc'], window['end'])
        self.assertIsNone(self.state()['window'])
