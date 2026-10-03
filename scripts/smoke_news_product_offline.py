"""Temporary-only end-to-end smoke test; real network is explicitly forbidden."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.news.live_config import LiveConfig
from src.news.live_runner import LiveRunner
from src.news.v3_config import Config
from src.news.llm.analyzer import Analyzer
from tests.news.test_v3 import FakeProvider

def main():
    with tempfile.TemporaryDirectory() as tmp, patch('requests.get',side_effect=AssertionError('Live network forbidden')), patch('urllib.request.urlopen',side_effect=AssertionError('Live network forbidden')):
        folder=Path(tmp)
        config=LiveConfig(enabled=True,state_dir=folder/'state',output=folder/'news_research_live_current.json',max_calls=1)
        llm=Config(provider='gemini',model='offline-test',api_key='test-only',cache_dir=folder/'enrichment')
        article={'articleId':'offline-smoke','title':'Nvidia CEO discusses AI safety','content':'Nvidia CEO discusses AI safety and existing strategy.',
                 'source':{'domain':'offline fixture'},'pubDate':'2026-09-27T00:00:00Z','url':'https://example.invalid/offline'}
        provider=FakeProvider();runner=LiveRunner(config,llm,fetch=lambda *args:[article],provider=provider)
        first=runner.cycle();second=runner.cycle()
        assert first['gemini_calls_this_cycle']==1 and second['duplicate_count']==1 and provider.calls==1
        from app import app
        with patch.dict(app.config,{'NEWS_INTELLIGENCE_OUTPUT_PATH':str(config.output)}), patch('app.news_product_config',config), patch.object(Analyzer,'analyze_article',side_effect=AssertionError('Browser must not enrich')):
            for _ in range(2):
                response=app.test_client().get('/api/news/intelligence')
                assert response.status_code==200 and len(response.get_json()['articles'])==1
        print(json.dumps({'result':'PASS','mock_provider_calls':provider.calls,'second_cycle_duplicates':second['duplicate_count'],
                          'flask_poll_reads':2,'real_news_api_calls':0,'real_gemini_calls':0,'temporary_files_only':True},indent=2))

if __name__=='__main__': main()
