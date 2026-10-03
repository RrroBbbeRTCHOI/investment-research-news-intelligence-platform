import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from app import app
from src.news.ui_api import DEFAULT_OUTPUT,read_product_intelligence
from src.news.live_config import LiveConfig
from src.news.llm.analyzer import atomic_json

ROOT=Path(__file__).resolve().parents[2]

class ProductApiTests(unittest.TestCase):
    def test_browser_polling_never_calls_providers(self):
        with patch.dict(app.config,{'NEWS_INTELLIGENCE_OUTPUT_PATH':str(ROOT/DEFAULT_OUTPUT)}), \
             patch('src.news.llm.analyzer.Analyzer.analyze_article',side_effect=AssertionError('Network forbidden')), \
             patch('requests.get',side_effect=AssertionError('Network forbidden')), \
             patch('src.data.yahoo_provider.history',side_effect=AssertionError('Network forbidden')):
            client=app.test_client()
            for _ in range(3):
                response=client.get('/api/news/intelligence');self.assertEqual(response.status_code,200)
                self.assertIn('product_scores',response.get_json()['articles'][0])
                self.assertEqual(client.get('/api/news/markets').status_code,200)
    def test_stale_status_without_snapshot_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=LiveConfig(enabled=True,state_dir=Path(tmp))
            atomic_json(config.state_dir/'status.json',{'pipeline_status':'live','generated_at_utc':'2000-01-01T00:00:00+00:00','secret':'never expose'})
            payload,status=read_product_intelligence(ROOT,DEFAULT_OUTPUT,config)
            self.assertEqual(status,200);self.assertEqual(payload['operational']['pipeline_status'],'stale')
            self.assertNotIn('secret',payload['operational'])
    def test_demo_mode(self):
        payload,status=read_product_intelligence(ROOT,DEFAULT_OUTPUT,LiveConfig())
        self.assertEqual(payload['operational']['pipeline_status'],'demo');self.assertEqual(status,200)
