import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.live_config import LiveConfig
from src.news.live_runner import LiveRunner, normalize, canonical_url
from src.news.llm.analyzer import Analyzer, atomic_json
from src.news.llm.base import ProviderError
from src.news.v3_config import Config
from .test_v3 import FakeProvider

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.c=LiveConfig(enabled=True,state_dir=self.root/'state',output=self.root/'news_research_live_current.json')
        self.llm=Config(provider='gemini',model='test',api_key='test-only',cache_dir=self.root/'cache')
        self.raw={'articleId':'1','title':'Nvidia CEO discusses AI safety','content':'Nvidia CEO discusses AI safety and existing strategy.',
                  'source':{'domain':'test'},'pubDate':'2026-09-26T12:00:00Z','url':'https://example.com/a?utm_source=x'}
        self.provider=FakeProvider()
    def runner(self,fetch=None):
        return LiveRunner(self.c,self.llm,fetch=fetch or (lambda *args:[self.raw]),provider=self.provider)
    def test_duplicate_once_across_restarts(self):
        self.runner().cycle();self.runner().cycle()
        self.assertEqual(self.provider.calls,1)
        self.assertEqual(len(json.loads(self.c.output.read_text())['articles']),1)
    def test_existing_enrichment_cache(self):
        Analyzer(self.llm,self.provider).analyze_article(normalize(self.raw,'2026-09-27T00:00:00+00:00'))
        stats=self.runner().cycle();self.assertEqual(self.provider.calls,1);self.assertEqual(stats['gemini_cache_hits'],1)
    def test_quota_deferred_then_resume(self):
        self.c.max_calls=0;stats=self.runner().cycle()
        self.assertEqual(stats['quota_deferred_count'],1);self.assertEqual(self.provider.calls,0)
        self.assertFalse(self.c.output.exists())
        self.c.max_calls=1;self.runner().cycle();self.assertEqual(self.provider.calls,1)
    def test_retry_counts_against_hard_quota(self):
        self.c.max_calls=1;self.provider=FakeProvider(error=ProviderError('http_429'))
        with patch('src.news.llm.analyzer.time.sleep'):
            stats=self.runner().cycle()
        self.assertEqual(self.provider.calls,1);self.assertEqual(stats['gemini_calls_this_cycle'],1)
    def test_daily_budget_survives_restart(self):
        self.c.daily_calls=1;self.runner().cycle();self.raw={**self.raw,'articleId':'2','url':'https://example.com/b','content':'Nvidia CEO discusses a new research strategy.'}
        stats=self.runner().cycle();self.assertEqual(self.provider.calls,1);self.assertEqual(stats['quota_deferred_count'],1)
    def test_failure_retains_snapshot(self):
        self.runner().cycle();before=self.c.output.read_bytes()
        def fail(*args): raise RuntimeError('secret must not escape')
        stats=self.runner(fail).cycle();self.assertEqual(self.c.output.read_bytes(),before)
        self.assertEqual(stats['pipeline_status'],'degraded');self.assertNotIn('secret',json.dumps(stats))
    def test_noise_no_llm(self):
        self.raw.update(title='Missing cruise passenger found',content='Missing cruise passenger found off Mexico coast.')
        stats=self.runner().cycle();self.assertEqual(self.provider.calls,0);self.assertEqual(stats['cheap_reject_count'],1)
    def test_incremental_fixed_window_pages(self):
        self.c.page_size=1;calls=[]
        def fetch(*args):
            calls.append(args);return [self.raw] if args[3]==0 else []
        r=self.runner(fetch);r.cycle();r.cycle();r.cycle()
        self.assertEqual(calls[0][1:3],calls[1][1:3]);self.assertEqual([x[3] for x in calls],[0,1,0])
    def test_disabled_no_fetch(self):
        self.c.enabled=False
        def fail(*args): self.fail('No network allowed')
        self.assertEqual(self.runner(fail).cycle()['pipeline_status'],'disabled')
    def test_url_identity(self):
        self.assertEqual(canonical_url(self.raw['url']),'https://example.com/a')
    def test_url_alias_duplicate_without_same_provider_id(self):
        alias={**self.raw,'articleId':'2','url':'https://example.com/a?utm_source=other'}
        stats=self.runner(lambda *args:[self.raw,alias]).cycle()
        self.assertEqual(stats['duplicate_count'],1);self.assertEqual(self.provider.calls,1)
    def test_failure_one_article_does_not_block_other(self):
        class Selective(FakeProvider):
            def generate(self,article):
                if article['provider_article_id']=='1': raise ProviderError('invalid_schema')
                return super().generate(article)
        self.provider=Selective()
        other={**self.raw,'articleId':'2','title':'Microsoft CEO discusses cloud strategy','content':'Microsoft CEO discusses the cloud strategy.','url':'https://example.com/b'}
        stats=self.runner(lambda *args:[self.raw,other]).cycle()
        self.assertEqual(stats['pending_count'],1)
        self.assertEqual(len(json.loads(self.c.output.read_text())['articles']),1)
    def test_unusable_article_does_not_get_stuck_pending(self):
        self.raw={'articleId':'empty'}
        stats=self.runner().cycle();self.assertEqual(stats['pending_count'],0);self.assertEqual(self.provider.calls,0)
    def test_atomic_replacement_observers_see_complete_json(self):
        from concurrent.futures import ThreadPoolExecutor
        atomic_json(self.c.output,{'articles':[0]*100})
        def reader():
            for _ in range(100): self.assertEqual(len(json.loads(self.c.output.read_text())['articles']),100)
        with ThreadPoolExecutor() as pool:
            future=pool.submit(reader)
            for n in range(20): atomic_json(self.c.output,{'articles':[n]*100})
            future.result()
