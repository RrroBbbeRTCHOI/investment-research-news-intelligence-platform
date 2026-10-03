"""Focused V3.1.1 grounding and qualitative-confidence regression tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.news.v3_validation import ground_summary
from src.news.v3_config import Config
from src.news.research_v3 import build_research_output_v3
from src.news.ui_api import read_intelligence

ROOT=Path(__file__).resolve().parents[2]


def nvidia_replay():
    before=json.loads((ROOT/'docs/v3_1/nvidia_after.json').read_text())
    articles=json.loads((ROOT/'data/news/normalized/v3_gemini_nvidia_test.json').read_text())['articles']
    class RecordedAnalyzer:
        calls=0
        def analyze_article(self, article):
            return deepcopy(before['articles'][0]['enrichment'])
    # Replay the supplied response, never call or write an enrichment cache.
    after=build_research_output_v3(articles,[],config=Config(),analyzer=RecordedAnalyzer(),now=before['generated_at'])
    return before,after


class GroundingTests(unittest.TestCase):
    def check(self,summary,quotes,body=None):
        body=body or ' '.join(quotes)
        citations=[{'field':'summary_full','source_field':'body','quote':q} for q in quotes]
        return ground_summary(summary,citations,{'body':body})

    def test_supported_paraphrase(self):
        source='Nvidia chief executive Jensen Huang rejected AI warnings.'
        summary='Nvidia CEO Jensen Huang dismissed AI warnings.'
        result=self.check(summary,[source])
        self.assertEqual(result['value'],summary)
        audit=result['sentence_validation'][0]
        self.assertEqual(audit['supporting_quotes'],[source])
        self.assertEqual(audit['source_fields'],['body'])
        self.assertTrue(audit['reason'])

    def test_new_fact_wrong_actor_and_changed_number_rejected(self):
        source='Huang said revenue increased 10%.'
        for summary in ('Huang said revenue increased 20%.',
                        'Altman said revenue increased 10%.',
                        'Huang said revenue increased 10% and profit doubled.'):
            with self.subTest(summary=summary):
                self.assertIsNone(self.check(summary,[source])['value'])

    def test_negation_and_conditional_not_dropped(self):
        for summary,source in [
            ('Nvidia stopped production.','Nvidia did not stop production.'),
            ('Production stopped.','Officials denied that production stopped.'),
            ('Nvidia stopped production.','Nvidia stopped production only if supplies ran out.'),
            ('Nvidia stopped production.','Rumors that Nvidia stopped production were denied.'),
            ('AI will cause extinction.','AI could cause extinction.')]:
            with self.subTest(source=source):
                self.assertIsNone(self.check(summary,[source])['value'])

    def test_multiple_spans_jointly_support_compressed_sentence(self):
        quotes=['Nvidia halted production.','Nvidia delayed shipments.']
        summary='Nvidia stopped production and postponed shipments.'
        result=self.check(summary,quotes)
        self.assertEqual(result['value'],summary)
        self.assertEqual(result['sentence_validation'][0]['supporting_quotes'],quotes)

    def test_clipped_citation_cannot_hide_attribution_or_negation(self):
        for source in ['Officials denied that production stopped.',
                       'Huang said production stopped.', 'Huang says production stopped.', 'There are fears that production stopped.']:
            self.assertIsNone(self.check('production stopped.',['production stopped.'],source)['value'])

    def test_clipped_citation_cannot_hide_conditional_suffix(self):
        self.assertIsNone(self.check('Nvidia stopped production.', ['Nvidia stopped production'],
            'Nvidia stopped production only if supplies ran out.')['value'])

    def test_false_citation_or_changed_quoted_claim_rejected(self):
        self.assertIsNone(self.check('Nvidia stopped production.',['Nvidia stopped production.'],'Nvidia discussed production.')['value'])
        self.assertIsNone(self.check('Huang called warnings "fiction".',['Huang described warnings as "doomsday narratives".'])['value'])

    def test_numeric_level_is_not_growth_amount(self):
        self.assertIsNone(self.check('Revenue increased 10%.',['Revenue increased to 10%.'])['value'])

    def test_added_non_latin_entity_is_not_discarded(self):
        self.assertIsNone(self.check('Nvidia stopped production 東京.', ['Nvidia stopped production.'])['value'])

    def test_comparison_direction_and_currency_not_discarded(self):
        for summary,quote in [('Revenue > 10.', 'Revenue < 10.'),('Revenue £10.', 'Revenue €10.')]:
            self.assertIsNone(self.check(summary,[quote])['value'])

    def test_supported_quote_with_scraper_prefix(self):
        quote='Huang rejected AI warnings.'
        self.assertEqual(self.check(quote,[quote],'Reporter Getty Images'+quote)['value'],quote)


class ConfidenceAndReplayTests(unittest.TestCase):
    def test_bbc_normalized_high(self):
        for source in ('BBC',' bBc ','  BBC  '):
            self.assertEqual(Config().source_tier(source),'High')
        self.assertEqual(Config(source_quality={' bbc ':'Medium'}).source_tier('BBC'),'Medium')

    def test_unknown_source_and_no_numeric_policy(self):
        self.assertEqual(Config().source_tier('Unlisted publisher'),'Unknown')
        self.assertEqual(Config(source_quality={}).source_tier('BBC'),'Unknown')
        with self.assertRaisesRegex(ValueError,'numeric weights'):
            Config(source_quality={'BBC':.9})

    def test_api_converts_old_composite_to_components_without_writing_snapshot(self):
        before,_=nvidia_replay()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old_snapshot.json';p.write_text(json.dumps(before));original=p.read_bytes()
            with patch.dict('os.environ',{'NEWS_SOURCE_QUALITY_JSON':'{"bbc":"High"}'}):
                response,status=read_intelligence(tmp,p)
            self.assertEqual(status,200)
            confidence=response['articles'][0]['ticker_analysis'][0]['quantitative']['confidence']
            self.assertIsNone(confidence['value'])
            self.assertEqual(confidence['source_quality'],'High')
            self.assertEqual(confidence['extraction_self_assessment'],.95)
            self.assertEqual(confidence['relationship_evidence_quality'],'Moderate')
            self.assertNotIn('0.5985',json.dumps(confidence))
            self.assertEqual(p.read_bytes(),original)

    def test_nvidia_recorded_response_replay(self):
        before,after=nvidia_replay();old=before['articles'][0];new=after['articles'][0]
        self.assertIsNone(old['article_summary']['summary_full'])
        for field in ('summary_short','summary_full'):
            self.assertTrue(new['article_summary'][field])
            self.assertTrue(new['semantic_validation']['summary_validation'][field]['sentence_validation'][0]['accepted'])
        self.assertEqual(new['geography']['event_country'],None)
        self.assertEqual(new['severity'],old['severity']);self.assertEqual(new['severity']['level'],'Low')
        self.assertEqual(len(new['ticker_analysis']),1)
        t=new['ticker_analysis'][0];prior=old['ticker_analysis'][0]
        for key in ('ticker','qualification','relationship_type','evidence','financial_materiality','research_priority','direction'):
            self.assertEqual(t[key],prior[key])
        self.assertEqual(t['ticker'],'NVDA')
        self.assertEqual(t['quantitative']['relevance'],prior['quantitative']['relevance'])
        self.assertEqual(t['quantitative']['relevance']['value'],.45)
        self.assertEqual(t['quantitative']['time_decay'],prior['quantitative']['time_decay'])
        self.assertEqual(t['quantitative']['impact'],prior['quantitative']['impact'])
        self.assertIsNone(t['quantitative']['impact']['value'])
        self.assertEqual(t['quantitative']['confidence']['source_quality'],'High')
        self.assertIsNone(t['quantitative']['confidence']['value'])
        self.assertEqual(after['summary']['llm_calls'],0)
