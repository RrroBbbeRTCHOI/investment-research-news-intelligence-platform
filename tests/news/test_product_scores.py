import json
import unittest
from copy import deepcopy
from pathlib import Path
from src.news.product_scores import attention, relevance, decorate

class ProductScoreTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((Path(__file__).resolve().parents[2]/'data/news/research/stress_test_v1_v316_final_replay.json').read_text())
    def article(self,n): return next(a for a in self.raw['articles'] if '_'+n+'_' in a['article_id'])
    def score(self,n): return attention(self.article(n),self.raw['generated_at'])
    def test_hormuz_no_invented_relevance(self):
        s=self.score('ST09');self.assertEqual(s['relevance']['score'],0);self.assertGreater(s['urgency']['score'],0)
    def test_qualified_above_review(self):
        tickers={t['ticker']:relevance(t) for t in self.article('ST07')['ticker_analysis']}
        self.assertGreater(tickers['AMZN']['score'],tickers['AAPL']['score'])
        self.assertEqual(tickers['AAPL']['level'],'Review')
    def test_commentary_lower_urgency(self):
        self.assertGreater(self.score('ST03')['urgency']['score'],self.score('ST11')['urgency']['score'])
    def test_no_frozen_mutation(self):
        before=deepcopy(self.raw);decorate(self.raw);self.assertEqual(before,self.raw)
    def test_noise_cannot_gain_urgency(self):
        a=deepcopy(self.article('ST12'));a['severity']={'level':'Critical'}
        self.assertEqual(attention(a,self.raw['generated_at'])['urgency']['score'],0)
    def test_review_cannot_use_direct_type_to_promote(self):
        self.assertLess(relevance({'qualification':'candidate_requires_review','relationship_type':'direct_event_subject','quantitative':{'relevance':{'value':1}}})['score'],60)
