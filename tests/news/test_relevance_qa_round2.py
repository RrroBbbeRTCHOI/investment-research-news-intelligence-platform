"""Prospective semantic QA; no stock-price labels or historical-model tuning."""
import json
from pathlib import Path
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from src.news.research_intelligence import build_research_output,DIRECTION
from src.news.event_extractor import extract_event,technology_affirmed
from src.news.channel_generator import generate_channels
from src.news.exposure_matcher import load_exposure_edges
from .helpers import article

ROOT=Path(__file__).resolve().parents[2]

class Round2Tests(TestCase):
    def run_text(self,text):
        return build_research_output([article(text,headline=text)],[])['articles'][0]

    def test_direct_event_participants_without_exposure(self):
        for text,ticker in [('Regulator fines Meta over data violations.','META'),
                            ('Competition authority opened an investigation into Nvidia.','NVDA'),
                            ('Tesla recalled vehicles over a safety defect.','TSLA'),
                            ('Apple raised prices by 10%.','AAPL'),
                            ('Microsoft announced layoffs affecting employees.','MSFT')]:
            with self.subTest(text=text):
                r=self.run_text(text);self.assertIsNotNone(r['event'])
                t=next(t for t in r['ticker_analysis'] if t['ticker']==ticker)
                self.assertEqual(t['qualification'],'qualified_direct_event_subject')
                self.assertEqual(t['relationship_type'],'direct_event_subject')
                self.assertEqual(t['evidence'],[])
                self.assertEqual(t['relevance_score'],.15) # Existing weights; no invented edge.
                self.assertEqual(t['direction'],DIRECTION)
                self.assertEqual(t['materiality']['level'],'Unknown')
                self.assertEqual(t['research_priority']['level'],'Medium')
                self.assertTrue(t['direct_event_evidence']['evidence'])

    def test_background_company_does_not_qualify(self):
        for tail in ['Analysts compared the issue with Meta.',
                     'Apple was mentioned in background context.',
                     'Meta was not fined.',
                     'Meta may be fined.',
                     'Meta was fined in 2020.']:
            r=self.run_text('Regulator fines Microsoft. '+tail)
            others=[t for t in r['ticker_analysis'] if t['ticker']!='MSFT']
            self.assertTrue(all(t['qualification']=='candidate_requires_review' for t in others))

    def test_direct_subject_requires_available_article_time(self):
        r=build_research_output([article('Regulator fines Meta.',headline='Regulator fines Meta.',fetched_at=None)],[])
        self.assertEqual(r['summary']['qualified_pairs'],0)

    def test_unaffected_wording_scoped_to_its_technology(self):
        for phrase in ['continued normally','were reported as continuing normally','remained operational',
                       'were operating normally','were not affected','were not disrupted',
                       'were not interrupted','were unaffected','reported no disruption','experienced no impact']:
            text='TSMC CoWoS packaging disruption in Taiwan. Wafer fabrication operations '+phrase+'.'
            with self.subTest(phrase=phrase):
                event=extract_event(article(text,headline='TSMC CoWoS packaging disruption in Taiwan'))
                families={c['channel_family'] for c in generate_channels(event)['candidate_channels']}
                self.assertIn('advanced_packaging',families);self.assertNotIn('advanced_semiconductors',families)

    def test_positive_fabrication_still_active(self):
        event=extract_event(article('TSMC wafer fabrication was disrupted in Taiwan.',headline='TSMC wafer fabrication disruption'))
        self.assertIn('advanced_semiconductors',{c['channel_family'] for c in generate_channels(event)['candidate_channels']})

    def test_local_technology_scope_both_orders(self):
        for text,term,expected in [
                ('CoWoS disrupted; wafer fabrication continued normally','CoWoS',True),
                ('wafer fabrication was not affected; CoWoS disrupted','CoWoS',True),
                ('CoWoS disrupted, wafer fabrication continued normally','CoWoS',True),
                ('wafer fabrication was not affected and CoWoS disrupted','CoWoS',True),
                ('no disruption to wafer fabrication','wafer fabrication',False),
                ('the outage did not affect wafer fabrication','wafer fabrication',False)]:
            start=text.index(term)
            self.assertEqual(technology_affirmed(text,start,start+len(term)),expected,text)

    def test_export_action_variants(self):
        for obj in ['export controls','export restrictions','export-license restrictions',
                    'export licensing restrictions','export license requirements',
                    'new export license rule','restrictions on semiconductor exports']:
            text='The US government announced '+obj+' on advanced chips sold to China.'
            with self.subTest(obj=obj):
                e=extract_event(article(text,headline=text))
                self.assertIsNotNone(e);self.assertEqual(e['event_type'],'trade_export_control')
                self.assertIs(e['export_restriction'],True)

    def test_export_speculation_and_commentary_rejected(self):
        for text in ['Analysts discuss whether export restrictions might be expanded.',
                     'Possible future export restrictions are being discussed.',
                     'Commentary on the history of export controls.',
                     'The US government proposed export-license restrictions on chips.',
                     'The government did not expand export-license restrictions on chips.']:
            self.assertIsNone(extract_event(article(text,headline=text)),text)

    def test_exact_supplied_round2(self):
        articles=json.loads((ROOT/'data/news/normalized/relevance_engine_qa_round2.json').read_text())['articles']
        edges,_=load_exposure_edges(ROOT)
        out=build_research_output(articles,edges)
        self.assertEqual(out['summary'],dict(articles=4,accepted=4,rejected=0,qualified_pairs=3,review_candidates=0))
        one,two,three,four=out['articles']
        self.assertEqual(one['ticker_analysis'][0]['relationship_type'],'direct_event_subject')
        self.assertEqual([t['ticker'] for t in two['ticker_analysis']],['NVDA'])
        self.assertEqual([e['edge_id'] for e in two['ticker_analysis'][0]['evidence']],['2'])
        self.assertEqual(three['ticker_analysis'],[])
        self.assertEqual(four['ticker_analysis'][0]['relationship_type'],'direct_event_subject')
        self.assertIs(four['event']['export_restriction'],True)

    def test_ml_extremes_do_not_change_direct_qualification(self):
        a=[article('Regulator fines Meta.',headline='Regulator fines Meta.')]
        baseline=build_research_output(a,[],now='2026-09-21T00:00:00Z')
        for p in [0.,1.]:
            with patch('src.news.research_intelligence.context_for',return_value={'probability':p}):
                other=build_research_output(a,[],now='2026-09-21T00:00:00Z')
            self.assertEqual(baseline['research_queue'],other['research_queue'])
            self.assertEqual(other['articles'][0]['ticker_analysis'][0]['direction'],DIRECTION)
