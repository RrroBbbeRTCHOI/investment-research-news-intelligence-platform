"""Offline identity and state regression tests; no real providers."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.live_runner import LiveRunner, normalize, identities, canonical_url
from src.news.live_dedupe import cross_subdomain_key, publisher_anchor
from src.news.live_config import LiveConfig
from src.news.v3_config import Config
from .test_v3 import FakeProvider

HEADLINE = 'Bill Gates joins calls for AI safeguards, including legislation'
STAMP = '2026-09-27T21:40:08+05:00'
DAWN = '/news/2033076/bill-gates-joins-calls-for-ai-safeguards-including-legislation'


def raw(host='pass.dawn.com', path=DAWN, pid='a', headline=HEADLINE, timestamp=STAMP):
    return {'articleId': pid, 'url': 'https://' + host + path, 'title': headline,
            'source': {'domain': host}, 'pubDate': timestamp, 'content': headline}


def row(**kw):
    return normalize(raw(**kw), '2026-09-28T00:00:00Z')


class LiveDedupeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = LiveConfig(enabled=True, state_dir=self.root/'state', output=self.root/'news_research_live_current.json')
        self.llm = Config(provider='gemini', model='test', api_key='fake', cache_dir=self.root/'llm')
        self.provider = FakeProvider()

    def cycle(self, rows):
        # Force intake eligibility to isolate dedupe from unrelated editorial rules.
        with patch('src.news.live_runner.classify_live_content', return_value={'content_type': 'event'}):
            return LiveRunner(self.config, self.llm, fetch=lambda *args: rows, provider=self.provider).cycle()

    def state(self):
        return json.loads((self.config.state_dir/'state.json').read_text())

    def test_dawn_same_batch_one_attempt(self):
        result = self.cycle([raw(), raw(host='www.dawn.com', pid='b')])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(result['article_count'], 1)
        self.assertEqual(result['pending_count'], 0)

    def test_www_mobile_canonical_identity(self):
        a = row(host='www.example.com', path='/news/123/story')
        b = row(host='m.example.com', path='/news/123/story', pid='b')
        self.assertEqual(canonical_url(a['article_url']), canonical_url(b['article_url']))
        self.assertTrue(set(identities(a)) & set(identities(b)))

    def test_same_headline_different_paths_are_distinct(self):
        a = row(host='example.com', path='/news/123/story')
        b = row(host='example.com', path='/news/456/story', pid='b')
        self.assertFalse(set(identities(a)) & set(identities(b)))
        result = self.cycle([raw(host='example.com', path='/news/123/story'), raw(host='example.com', path='/news/456/story', pid='b')])
        self.assertEqual(result['duplicate_count'], 0)
        self.assertEqual(result['new_article_count'], 2)
        self.assertEqual(result['article_count'], 2)
        # The unchanged enrichment cache may reuse identical text independently.
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(result['gemini_cache_hits'], 1)

    def test_nonpresentation_news_requires_fallback(self):
        a = row(host='news.example.com', path='/article/555/story')
        b = row(host='www.example.com', path='/article/555/story', pid='b')
        self.assertNotEqual(canonical_url(a['article_url']), canonical_url(b['article_url']))
        self.assertEqual(cross_subdomain_key(a), cross_subdomain_key(b))
        for change in [{'headline': 'A different headline'}, {'published_at': '2026-09-27T16:40:09Z'}, {'published_at': None}]:
            self.assertNotEqual(cross_subdomain_key(a), cross_subdomain_key({**b, **change}))

    def test_different_domains_distinct(self):
        a = row(host='reuters.com', path='/article/123')
        b = row(host='example.com', path='/article/123', pid='b')
        self.assertFalse(set(identities(a)) & set(identities(b)))

    def test_tracking_and_normalization(self):
        self.assertEqual(canonical_url('https://WWW.example.com:443/news/123/story/?utm_source=x&utm_medium=y#section'), 'https://example.com/news/123/story')
        self.assertEqual(canonical_url('http://m.example.com:80/news/123?gclid=x'), 'http://example.com/news/123')
        self.assertEqual(canonical_url('https://amp.example.com:8443/news/123'), 'https://example.com:8443/news/123')
        self.assertEqual(canonical_url('https://mobile.example.com/news/123?edition=&id=123'), 'https://example.com/news/123?edition=&id=123')
        for bad in ['javascript:alert(1)', 'https://example.com:bad/a', 'https://user:pass@example.com/a']:
            self.assertIsNone(canonical_url(bad))

    def test_meaningful_query_not_merged(self):
        a = row(host='example.com', path='/article?id=123')
        b = row(host='example.com', path='/article?id=456', pid='b')
        self.assertFalse(set(identities(a)) & set(identities(b)))
        a = row(host='news.example.com', path='/article?id=123')
        self.assertNotEqual(cross_subdomain_key(a), cross_subdomain_key(b))
        self.assertNotEqual(canonical_url('https://example.com/a?id=1&id=2'), canonical_url('https://example.com/a?id=2&id=1'))

    def test_completed_then_duplicate(self):
        self.cycle([raw()]); result = self.cycle([raw(host='www.dawn.com', pid='b')])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(len(self.state()['records']), 1)
        self.assertEqual(self.state()['pending'], {})

    def test_pending_then_duplicate(self):
        self.config.max_calls = 0
        self.cycle([raw()]); result = self.cycle([raw(host='www.dawn.com', pid='b')])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(len(self.state()['pending']), 1)

    def test_legacy_completed_plus_pending_reconciled_without_processing(self):
        self.cycle([raw()]); state = self.state()
        b = row(host='www.dawn.com', pid='b')
        state['pending'][b['article_id']] = {'article': b, 'status': 'quota_deferred'}
        state['seen'] = {k: v for k, v in state['seen'].items() if not k.startswith('crossurl:')}
        state['seen']['id:perigon:b'] = b['article_id']
        before = state['records'].copy(); usage = state['usage'].copy()
        (self.config.state_dir/'state.json').write_text(json.dumps(state))
        result = self.cycle([])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.state()['records'], before)
        self.assertEqual(self.state()['usage'], usage)
        self.assertEqual(self.state()['pending'], {})

    def test_exact_utc_time_and_normalized_headline(self):
        a = row(); b = row(host='www.dawn.com', pid='b', timestamp='2026-09-27T16:40:08Z', headline=' BILL GATES joins calls for AI safeguards, including legislation ')
        self.assertEqual(cross_subdomain_key(a), cross_subdomain_key(b))
        self.assertIsNone(cross_subdomain_key({**a, 'published_at': '2026-09-27T16:40:08'}))

    def test_unknown_or_shared_domains_fail_closed(self):
        for h in ['news.company.co.zz', 'investor.company.com', 'support.company.com', 'foo.blogspot.com', 'pass.github.io', 'pass.wordpress.com', '127.0.0.1']:
            self.assertIsNone(publisher_anchor(h), h)
        self.assertEqual(publisher_anchor('pass.example.co.uk'), 'example.co.uk')
        self.assertIsNone(publisher_anchor('pass.co.uk'))

    def test_content_and_provider_identity_preserved(self):
        a = {**row(), 'body': 'Substantive supplied article body.'}
        b = {**a, 'article_url': 'https://example.org/another', 'provider_article_id': 'other'}
        self.assertTrue(set(k for k in identities(a) if k.startswith('content:')) & set(identities(b)))
        self.assertEqual(identities(a)[0], 'id:perigon:a')

    def test_seen_only_presentation_alias(self):
        self.config.state_dir.mkdir()
        state = {'seen': {'url:https://www.example.com/news/123': 'old'}, 'pending': {}, 'records': {}, 'usage': {}}
        (self.config.state_dir/'state.json').write_text(json.dumps(state))
        result = self.cycle([raw(host='m.example.com', path='/news/123')])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 0)

    def test_seen_only_cross_alias_survives_restart(self):
        self.cycle([raw()])
        state = self.state(); state['records'] = {}
        (self.config.state_dir/'state.json').write_text(json.dumps(state))
        result = self.cycle([raw(host='www.dawn.com', pid='b')])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.state()['pending'], {})

    def test_legacy_pending_pair_reconciles_before_quota(self):
        self.config.max_calls = 0
        self.cycle([raw()]); state = self.state()
        b = row(host='www.dawn.com', pid='b')
        state['pending'][b['article_id']] = {'article': b, 'status': 'quota_deferred'}
        state['seen'] = {k: v for k, v in state['seen'].items() if not k.startswith('crossurl:')}
        (self.config.state_dir/'state.json').write_text(json.dumps(state))
        result = self.cycle([])
        self.assertEqual(result['duplicate_count'], 1)
        self.assertEqual(len(self.state()['pending']), 1)
        self.assertEqual(self.provider.calls, 0)
