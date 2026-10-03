"""Read-only Flask integration tests; analysis is never invoked."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import app

ROOT=Path(__file__).resolve().parents[2]

class NewsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'current.json'
        self.data=json.loads((ROOT/'data/news/research/mag7_live_sample21_run2_legal_fix.json').read_text())
        self.old=app.config['NEWS_INTELLIGENCE_OUTPUT_PATH'];app.config['NEWS_INTELLIGENCE_OUTPUT_PATH']=str(self.path)
        self.client=app.test_client()
    def tearDown(self):
        app.config['NEWS_INTELLIGENCE_OUTPUT_PATH']=self.old;self.tmp.cleanup()
    def request(self, data=None):
        self.path.write_text(json.dumps(self.data if data is None else data))
        return self.client.get('/api/news/intelligence')
    def test_real_batch(self):
        response=self.request();self.assertEqual(response.status_code,200)
        x=response.get_json();self.assertEqual(set(x),{'schema_version','generated_at','summary','queue','articles'})
        self.assertEqual(len(x['articles']),21);self.assertEqual(x['queue'],[])
        self.assertEqual(sum(a['gate']['is_event'] for a in x['articles']),4)
        self.assertTrue(all(a['ticker_analysis']==[] for a in x['articles']))
        self.assertTrue(all(a['direction']=='Analyst judgment required' for a in x['articles']))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_missing(self):
        r=self.client.get('/api/news/intelligence');self.assertEqual(r.status_code,503);self.assertIn('error',r.get_json())
        self.assertNotIn(str(self.path),r.get_data(as_text=True))
    def test_empty(self):
        self.data['articles']=[];self.data['research_queue']=[]
        self.assertEqual(self.request().get_json()['articles'],[])
    def test_malformed(self):
        for data in [[],{},dict(self.data,articles=[{'article_id':'bad'}]),dict(self.data,research_queue={})]:
            self.assertEqual(self.request(data).status_code,503)
        self.path.write_text('{broken');self.assertEqual(self.client.get('/api/news/intelligence').status_code,503)
    def test_real_ticker_fields_preserved(self):
        data=json.loads((ROOT/'data/news/research/relevance_qa_round2_run2.json').read_text())
        out=self.request(data).get_json()
        for original,row in zip(data['articles'],out['articles']):
            self.assertEqual(row['ticker_analysis'],original['ticker_analysis'])
            self.assertEqual(row['direction'],original['direction'])
        self.assertEqual(out['queue'],data['research_queue'])
    def test_news_page_opens(self):
        r=self.client.get('/news');self.assertEqual(r.status_code,200);self.assertIn(b'BACKEND SNAPSHOT',r.data)
    def test_no_file_selection_from_request(self):
        self.request()
        r=self.client.get('/api/news/intelligence?path=/etc/passwd')
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.get_json()['articles']),21)
