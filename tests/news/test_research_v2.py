import copy
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from src.news.research_v2 import analyze_v2,build_research_output_v2
from src.news.event_geography import geography
from src.news.research_policy import severity
from src.news.ui_api import read_intelligence
from .helpers import article

ROOT=Path(__file__).resolve().parents[2]

def sample(headline):
    return article(headline+' The report describes the company and the current situation.',headline=headline)

class ResearchV2Tests(TestCase):
    def test_direct_commentary(self):
        a=analyze_v2(sample("Nvidia boss rejects AI extinction fears as 'doomsday narratives'"),[])
        self.assertTrue(a['usable']);self.assertFalse(a['gate']['is_event'])
        t=a['ticker_analysis'][0]
        self.assertEqual(t['ticker'],'NVDA');self.assertEqual(t['relationship_type'],'direct_company_subject')
        self.assertEqual(t['relevance']['level'],'High');self.assertEqual(a['severity']['level'],'Low')
        self.assertEqual(t['research_priority']['level'],'Low')
    def test_layoff_headlines(self):
        for h in ['Apple cuts jobs in second layoff round in two months, report says',"Apple Fitness+ Layoffs Reported Ahead of Potential 'Major' Changes"]:
            with self.subTest(headline=h):
                a=analyze_v2(sample(h),[]);t=a['ticker_analysis'][0]
                self.assertEqual(t['ticker'],'AAPL');self.assertEqual(t['relationship_type'],'direct_event_subject')
                self.assertEqual(t['relevance']['level'],'High');self.assertIn(a['severity']['level'],['Low','Medium'])
                self.assertEqual(t['financial_materiality']['level'],'Not yet quantified')
    def test_roundup_is_mention_only(self):
        a=analyze_v2(sample('S&P 500 Future Prediction: Nvidia, CPI, Oil and Fed Rate Hike in Focus'),[])
        t=a['ticker_analysis'][0];self.assertEqual(t['relationship_type'],'direct_mention')
        self.assertEqual(t['relevance']['level'],'Mention only');self.assertEqual(t['research_priority']['level'],'Review')
    def test_pool_cloud_not_computing(self):
        a=analyze_v2(sample('Pool chemical vapor cloud causes hazmat response in Gurnee'),[])
        self.assertEqual(a['ticker_analysis'],[]);self.assertEqual(a['candidate_channels'],[])
        self.assertEqual(a['geography']['event_country'],'United States')
    def test_saudi_global_event(self):
        a=analyze_v2(sample('Saudi oil export disruption interrupts shipments'),[])
        self.assertTrue(a['usable']);self.assertEqual(a['ticker_analysis'],[])
        self.assertEqual(a['geography']['event_country'],'Saudi Arabia');self.assertIsNotNone(a['event']['latitude'])
        self.assertEqual(a['event']['coordinate_precision'],'country_approximation')
    def test_geography_does_not_use_publisher(self):
        a=sample('A company discusses new safety procedures');a.update(source='BBC',countries=['UK'])
        self.assertIsNone(geography(a)['event_country']);self.assertIsNone(geography(a)['latitude'])
    def test_unmatched_general_news_can_map(self):
        a=analyze_v2(sample('Community exhibition opens in Japan'),[])
        self.assertFalse(a['gate']['is_event']);self.assertEqual(a['ticker_analysis'],[])
        self.assertIsNotNone(a['event']['latitude'])
    def test_geography_ambiguous_and_negated(self):
        for text in ['A facility was not in Taiwan.','The company discussed operations in Taiwan and in Japan.']:
            self.assertIsNone(geography(article(text,headline='Location discussion'))['latitude'])
    def test_severity_independent_of_relevance(self):
        a=analyze_v2(sample('Nvidia CEO says AI risks are exaggerated'),[])
        b=analyze_v2(sample('A major fab production halt stopped manufacturing in Taiwan'),[])
        self.assertEqual(a['ticker_analysis'][0]['relevance']['level'],'High');self.assertEqual(a['severity']['level'],'Low')
        self.assertEqual(b['severity']['level'],'High');self.assertEqual(b['ticker_analysis'],[])
    def test_historical_ml_does_not_change_decisions(self):
        a=sample('Regulator fines Meta for data violations')
        with patch('src.news.research_intelligence.context_for',return_value={'status':'available','probability':0}):one=analyze_v2(a,[])
        with patch('src.news.research_intelligence.context_for',return_value={'status':'available','probability':1}):two=analyze_v2(a,[])
        self.assertEqual(one['severity'],two['severity'])
        for key in ['relevance','research_priority','direction','financial_materiality']:
            self.assertEqual(one['ticker_analysis'][0][key],two['ticker_analysis'][0][key])
    def test_returns_fields_ignored(self):
        a=sample('Apple cuts jobs in a restructuring');b=copy.deepcopy(a);b.update(future_return=100,abnormal_return=-.9,ml_prediction=1)
        self.assertEqual(analyze_v2(a,[])['severity'],analyze_v2(b,[])['severity'])
    def test_direction_always_analyst(self):
        a=build_research_output_v2([sample('Nvidia CEO says AI risks are exaggerated')],[])
        for row in a['articles']:
            self.assertEqual(row['direction'],'Analyst judgment required')
            for t in row['ticker_analysis']:self.assertEqual(t['direction'],'Analyst judgment required')
    def test_unusable_and_duplicates(self):
        a=sample('Nvidia CEO says AI risks are exaggerated')
        result=build_research_output_v2([a,a,None,{'headline':'bad'}],[])
        self.assertEqual(result['summary']['usable'],1);self.assertEqual(result['summary']['rejected'],3)
    def test_missing_availability_not_qualified(self):
        a=sample('Nvidia CEO says AI risks are exaggerated');a['fetched_at']=None
        t=analyze_v2(a,[])['ticker_analysis'][0];self.assertEqual(t['qualification'],'candidate_requires_review')
    def test_api_v2_current(self):
        data,code=read_intelligence(ROOT,'data/news/research/news_research_v2_current.json')
        self.assertEqual(code,200);self.assertEqual(data['schema_version'],'news_ui_v2')
        n=next(a for a in data['articles'] if a['headline'].startswith('Nvidia boss'))
        self.assertEqual(n['ticker_analysis'][0]['relevance']['level'],'High')
        self.assertEqual(n['severity']['level'],'Low')
    def test_severity_negated_and_unknown(self):
        self.assertEqual(severity(sample('A major fab production halt was not reported'),'general_news')['level'],'Unknown')
        self.assertEqual(severity(sample('Some industry information is available'),'general_news')['score'],None)

    def test_explicit_historical_subject_not_current(self):
        a=analyze_v2(sample('Apple cuts jobs in 2020'),[])
        self.assertEqual(a['ticker_analysis'][0]['qualification'],'candidate_requires_review')
        self.assertEqual(a['severity']['level'],'Unknown')
    def test_duplicate_edge_ids_rejected(self):
        with self.assertRaises(ValueError):build_research_output_v2([], [{'edge_id':'one'},{'edge_id':'one'}])

    def test_proposed_disruption_not_observed_severity(self):
        self.assertEqual(severity(sample('Officials discuss a nationwide complete shutdown'),'general_news')['level'],'Unknown')
