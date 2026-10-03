import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.live_content import classify_live_content, build_outlook_record
from src.news.live_runner import LiveRunner, live_intake_allow
from src.news.live_config import LiveConfig
from src.news.v3_config import Config
from src.news.v3_validation import prefilter
from src.news.product_scores import outlook_attention, decorate, attention
from src.news.ui_api import read_product_intelligence

CASES={
 'skip':['Apple TV: The 16 Best Sci-Fi Shows to Stream Right Now','EA Sports FC review','India vs West Indies cricket','Celebrity interview','Best movies to watch this weekend','Cricket preview','What to watch on Apple TV'],
 'outlook':['Wall St Week Ahead — Jobs report, inflation data to test US rate path','Investors await CPI report next week','Microsoft earnings set for Thursday','Nvidia earnings preview: AI demand in focus','Fed meeting ahead as markets watch rate guidance','What to watch: CPI due next week'],
 'event':['Federal Reserve holds interest rates unchanged','US CPI rose 3.2%, data showed','AWS outage disrupts services','Nvidia faces new export controls','Tanker hit in Strait of Hormuz','TSMC expands advanced packaging capacity','Apple supplier halts production','Fed holds rates unchanged after markets awaited decision','Microsoft reports earnings after investors awaited results']}

def article(headline):
    return {'article_id':'test','headline':headline,'source':'fixture','published_at':'2026-09-27T00:00:00Z'}

class OutlookTests(unittest.TestCase):
    def test_required_classification_cases(self):
        for expected,headlines in CASES.items():
            for headline in headlines:
                with self.subTest(headline=headline):
                    a=article(headline);self.assertEqual(classify_live_content(a,prefilter(a))['content_type'],expected)
    def test_legacy_gate_unchanged_behavior(self):
        for headline in CASES['outlook'][:2]+CASES['skip'][:3]:
            a=article(headline);self.assertFalse(live_intake_allow(a,prefilter(a)))
        for headline in CASES['event'][:7]:
            a=article(headline)
            # Explicit three-way improvements need not depend on an old surface pass.
            self.assertEqual(classify_live_content(a,{'state':'background'})['content_type'],'event')
    def test_frozen_reject_always_wins(self):
        self.assertEqual(classify_live_content(article('Microsoft earnings preview'),{'state':'reject'})['content_type'],'skip')
    def test_future_clause_not_actual_event(self):
        for headline in ['Fed may cut rates next week','Microsoft reports earnings Thursday','Microsoft reports Thursday','Nvidia earnings preview: investors expect reports next week']:
            a=article(headline);self.assertEqual(classify_live_content(a,prefilter(a))['content_type'],'outlook')
    def test_preview_not_promoted_by_historical_body(self):
        a={**article('Investors await CPI report next week'),'body':'US CPI rose 3.2% last month.'}
        self.assertEqual(classify_live_content(a,prefilter(a))['content_type'],'outlook')
    def test_schema_no_date_geography_or_event_qualification(self):
        a=article('Microsoft earnings set for Thursday');decision=classify_live_content(a,prefilter(a));r=build_outlook_record(a,decision,'2026-09-27T00:00:00Z')
        self.assertIsNone(r['outlook']['scheduled_at_utc']);self.assertEqual(r['outlook']['expected_window'],'Thursday')
        self.assertIsNone(r['event']);self.assertIsNone(r['geography']);self.assertEqual(r['ticker_analysis'],[])
        self.assertEqual(r['outlook']['related_tickers'][0]['ticker'],'MSFT')
        self.assertEqual(r['severity']['level'],'N/A — Upcoming')
        for evidence in r['outlook']['source_basis']:
            self.assertEqual(a[evidence['source_field']][evidence['start']:evidence['end']],evidence['quote'])
    def test_mention_only_not_catalyst_subject(self):
        a=article('CPI preview: Microsoft investors await inflation report')
        r=build_outlook_record(a,{},'2026-09-27T00:00:00Z')
        self.assertEqual(r['outlook']['related_tickers'],[])
    def test_exact_timestamp_only(self):
        a=article('Microsoft earnings scheduled for 2026-10-01T20:00:00Z')
        r=build_outlook_record(a,{},'2026-09-27T00:00:00Z')
        self.assertEqual(r['outlook']['scheduled_at_utc'],'2026-10-01T20:00:00+00:00')
        score=outlook_attention(r,'2026-09-27T00:00:00Z');self.assertNotIn('urgency',score)
        self.assertEqual(score['watch_priority']['components']['resolved_upcoming_week_bonus'],10)
    def test_event_scores_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        raw=json.loads((root/'data/news/research/stress_test_v1_v316_final_replay.json').read_text())
        decorated=decorate(raw)
        for a,b in zip(raw['articles'],decorated['articles']): self.assertEqual(b['product_scores'],attention(a,raw['generated_at']))
    def test_outlook_skip_no_pipeline_or_gemini_and_durable_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);c=LiveConfig(enabled=True,state_dir=root/'state',output=root/'news_research_live_current.json')
            rows=[{'articleId':str(i),'title':h} for i,h in enumerate([CASES['outlook'][0],CASES['outlook'][2],CASES['skip'][0]])]
            from src.news.research_v3 import build_research_output_v3
            def empty_only(articles,*args,**kwargs):
                self.assertEqual(articles,[]);return build_research_output_v3(articles,*args,**kwargs)
            with patch('src.news.live_runner.build_research_output_v3',side_effect=empty_only),patch('src.news.llm.analyzer.Analyzer.analyze_article',side_effect=AssertionError('No Gemini')):
                runner=LiveRunner(c,Config(),fetch=lambda *args:rows)
                first=runner.cycle();second=runner.cycle()
            self.assertEqual((first['event_count'],first['outlook_count'],first['skip_count']),(0,2,1))
            self.assertEqual(second['duplicate_count'],3);self.assertEqual(first['gemini_calls_this_cycle'],0)
            p,status=read_product_intelligence(root,c.output,c);self.assertEqual(status,200)
            self.assertEqual(len(p['articles']),2);self.assertEqual(p['articles'][0]['content_type'],'outlook')
            self.assertIn('watch_priority',p['articles'][0]['product_scores'])
