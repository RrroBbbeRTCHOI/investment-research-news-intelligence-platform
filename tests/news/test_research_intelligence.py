import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.news.research_intelligence import build_research_output, run_research, DIRECTION
from src.news.event_extractor import extract_event
from .helpers import article, edge, normalized, workbook

NOW='2026-09-21T00:00:00Z'

class ResearchIntelligenceTests(unittest.TestCase):
    def build(self, articles=None, edges=None, **kwargs):
        return build_research_output(articles or [article()], edges if edges is not None else [edge()], now=NOW, **kwargs)

    def test_indirect_relationship_without_company_mention(self):
        x=self.build()['articles'][0]['ticker_analysis'][0]
        self.assertEqual(x['ticker'],'NVDA')
        self.assertEqual(x['relationship_type'],'indirect_exposure_match')
        self.assertEqual(x['relevance_score'],.60)
        self.assertEqual(x['legacy_relevance_score'],.80)
        self.assertEqual(x['direction'],DIRECTION)
        self.assertEqual(x['economic_channels'],['supply_chain'])
        self.assertEqual(x['evidence'][0]['source_locator'],'Synthetic test evidence, not real exposure')

    def test_direct_mention_is_only_a_review_candidate(self):
        x=self.build([article('A regulator fined a bank. Analysts compared the issue with Meta.',headline='Regulator fines a bank')],[])['articles'][0]
        self.assertEqual(x['status'],'no_qualified_match')
        t=x['ticker_analysis'][0]
        self.assertEqual(t['qualification'],'candidate_requires_review')
        self.assertEqual(t['relevance_score'],.15)
        self.assertEqual(t['research_priority']['level'],'Review')
        self.assertEqual(t['economic_channels'],[])

    def test_named_qualified_exposure_separate_from_mention(self):
        a=article('An earthquake struck Taiwan. NVIDIA reported the news.')
        x=self.build([a])['articles'][0]['ticker_analysis'][0]
        self.assertEqual(x['relationship_type'],'direct_exposure_match')
        self.assertEqual(x['relevance_score'],.75)

    def test_unsupported_indirect_relationship_not_invented(self):
        out=self.build(edges=[edge(country='Japan')])
        self.assertEqual(out['research_queue'],[])
        self.assertEqual(out['articles'][0]['status'],'no_qualified_match')

    def test_future_expired_blocked_unknown_time_fail_closed(self):
        for e in [edge(known_at_utc='2027-01-01'),edge(valid_to='2026-08-01'),edge(evidence_status='blocked'),edge(source_url=None)]:
            with self.subTest(e=e):
                out=self.build(edges=[e])
                self.assertEqual(out['research_queue'],[])
                self.assertTrue(out['articles'][0]['edge_exclusions'])
        self.assertEqual(self.build([article(fetched_at=None)])['research_queue'],[])

    def test_explicit_replay_cannot_precede_article(self):
        with self.assertRaises(ValueError):self.build(prediction_time='2025-01-01')

    def test_temporal_status_is_metadata_not_independent_verification(self):
        t=self.build()['articles'][0]['ticker_analysis'][0]['temporal_status']
        self.assertEqual(t['status'],'eligible_by_record_metadata')
        self.assertFalse(t['source_dates_independently_verified'])
        self.assertEqual(t['as_of'],'2026-09-17T09:00:00+00:00')

    def test_multiple_tickers_and_multiple_edges_no_pair_inflation(self):
        out=self.build(edges=[edge(),edge(edge_id='2'),edge(edge_id='3',ticker='AAPL')])
        self.assertEqual({r['ticker'] for r in out['research_queue']},{'AAPL','NVDA'})
        self.assertEqual(len(out['research_queue']),2)
        self.assertEqual(out['summary']['qualified_pairs'],2)
        self.assertTrue(all(r['relevance_score']==.60 for r in out['research_queue']))

    def test_duplicate_edges_and_articles_rejected(self):
        with self.assertRaises(ValueError):self.build(edges=[edge(),edge()])
        with self.assertRaises(ValueError):self.build([article(),article()])
        with self.assertRaises(ValueError):self.build([article(),article(article_id='other')])

    def test_evidence_and_priority_separate_from_relevance(self):
        a=self.build()['articles'][0]['ticker_analysis'][0]
        b=self.build(edges=[edge(evidence_status='partial')])['articles'][0]['ticker_analysis'][0]
        self.assertEqual(a['relevance_score'],b['relevance_score'])
        self.assertNotEqual(a['legacy_relevance_score'],b['legacy_relevance_score'])
        self.assertEqual(a['evidence_strength']['relationship_level'],'Strong (curated)')
        self.assertEqual(b['evidence_strength']['relationship_level'],'Partial')
        self.assertEqual(a['research_priority']['level'],'High')
        self.assertEqual(b['research_priority']['level'],'Medium')
        self.assertFalse(a['evidence_strength']['independently_verified'])
        self.assertIsNone(a['evidence_strength']['article_source_quality'])

    def test_severity_does_not_become_relevance_or_materiality(self):
        event=extract_event(article(),now=NOW)
        event['severity_score']=1.0
        with patch('src.news.research_intelligence.extract_event',return_value=event):out=self.build()
        x=out['articles'][0]['ticker_analysis'][0]
        self.assertEqual(x['relevance_score'],.60)
        self.assertEqual(x['materiality']['level'],'Unknown')
        self.assertEqual(x['materiality']['factors']['event_severity'],1.0)

    def test_historical_probability_never_changes_eligibility_priority_direction(self):
        a=self.build()
        for p in [0.,1.]:
            with patch('src.news.research_intelligence.context_for',return_value={'probability':p,'status':'test_only'}):
                b=self.build()
                self.assertEqual(a['research_queue'],b['research_queue'])
                aa=deepcopy(a['articles'][0]['ticker_analysis'][0]);bb=deepcopy(b['articles'][0]['ticker_analysis'][0])
                aa.pop('historical_reaction');bb.pop('historical_reaction');self.assertEqual(aa,bb)
                self.assertEqual(self.build(edges=[])['research_queue'],[])

    def test_rejected_event_cannot_get_tickers_or_historical_context(self):
        with patch('src.news.research_intelligence.context_for') as lookup:
            x=self.build([article('TSMC announces an employee training initiative.',headline='Employee training')])
        lookup.assert_not_called()
        self.assertEqual(x['research_queue'],[])
        self.assertIsNone(x['articles'][0]['event'])
        self.assertEqual(x['summary']['rejected'],1)

    def test_no_input_mutation(self):
        a=[article()];e=[edge()];old=deepcopy([a,e]);self.build(a,e)
        self.assertEqual([a,e],old)

    def test_recency_breaks_ties_without_changing_priority(self):
        older=article(article_id='old',provider_article_id='old',published_at='2026-09-16T08:00:00Z')
        newer=article(article_id='new',provider_article_id='new')
        q=self.build([older,newer])['research_queue']
        self.assertEqual([r['article_id'] for r in q],['new','old'])

    def test_cli_output_preserves_original_files_and_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);normalized(root,[article()]);workbook(root,[edge()]);old=root/'data/news/events/events_v1.json';old.parent.mkdir(parents=True);old.write_text('frozen sentinel')
            result=run_research(root)
            self.assertEqual(result['summary']['qualified_pairs'],1)
            self.assertEqual(old.read_text(),'frozen sentinel')
            json.dumps(result,allow_nan=False)
            with self.assertRaises(FileExistsError):run_research(root)

    def test_empty_input(self):
        x=build_research_output([],[],now=NOW)
        self.assertEqual(x['summary']['articles'],0)
        self.assertEqual(x['research_queue'],[])
