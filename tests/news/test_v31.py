"""V3.1 evidence constraints and provider resilience; no live calls in this suite."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .helpers import article, edge
from .test_v3 import semantic, FakeProvider
from src.news.llm.analyzer import Analyzer
from src.news.llm.base import ProviderError
from src.news.research_v3 import build_research_output_v3
from src.news.v3_config import Config, SOURCE_POLICY_NOTICE
from src.news.v3_validation import validate_semantics, validated_geography
from src.news.ui_api import read_intelligence


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.a=article('Nvidia discussed AI safety. Revenue was not quantified. Management requested public debate.',
                       headline='Nvidia CEO discusses AI safety',source='BBC')

    def validated(self, summary, quotes, field='summary_full'):
        s=semantic(self.a)
        s[field]=summary
        s['citations']=[{'field':field,'quote':q,'source_field':'body'} for q in quotes]
        return validate_semantics(self.a,{'semantic':s},{'classification':'commentary','ticker_analysis':[]})

    def test_sentence_filter_both_fields(self):
        one='Nvidia discussed AI safety.'
        two='The company earned $900 billion.'
        three='Management requested public debate.'
        for field in ('summary_short','summary_full'):
            with self.subTest(field=field):
                v=self.validated(' '.join([one,two,three]),[one,three],field)
                x=v['accepted'][field]
                self.assertEqual(x['value'],one+' '+three)
                self.assertEqual([a['accepted'] for a in x['sentence_validation']],[True,False,True])
                self.assertEqual(x['sentence_validation'][0]['source_field'],'body')
                self.assertIn('exact source support',x['sentence_validation'][1]['reason'])

    def test_all_unsupported_null_and_reason(self):
        v=self.validated('Management raised guidance.', ['Nvidia discussed AI safety.'])
        self.assertNotIn('summary_full',v['accepted'])
        self.assertIsNone(v['summary_validation']['summary_full']['value'])
        self.assertTrue(v['summary_validation']['summary_full']['reason'])
        self.assertTrue(v['rejections'])

    def test_wrong_field_citation_does_not_support_summary(self):
        s=semantic(self.a)
        s['summary_full']=self.a['body']
        s['citations']=[{'field':'summary_short','quote':self.a['body'],'source_field':'body'}]
        v=validate_semantics(self.a,{'semantic':s},{})
        self.assertNotIn('summary_full',v['accepted'])

    def test_do_not_strip_negation_or_attribution(self):
        self.a['body']='Officials denied that production stopped. If production stopped, losses could rise.'
        v=self.validated('Production stopped.', [self.a['body']])
        self.assertIsNone(v['summary_validation']['summary_full']['value'])

    def test_line_wrap_does_not_drop_attribution(self):
        self.a['body']='Officials denied that\nproduction stopped.'
        v=self.validated('production stopped.', [self.a['body']])
        self.assertIsNone(v['summary_validation']['summary_full']['value'])

    def test_quote_ending_sentence_keeps_exact_support(self):
        self.a['body']='Huang said "We need public debate." Nvidia discussed AI safety.'
        v=self.validated(self.a['body'],[self.a['body']])
        self.assertEqual(len(v['summary_validation']['summary_full']['sentence_validation']),2)
        self.assertEqual(v['accepted']['summary_full']['value'],self.a['body'])

    def test_paraphrase_not_entailed_by_shared_words(self):
        v=self.validated('Nvidia guaranteed AI safety.', ['Nvidia discussed AI safety.'])
        self.assertIsNone(v['summary_validation']['summary_full']['value'])

    def test_quote_must_exist_in_named_source(self):
        v=self.validated('Nvidia discussed AI safety.', ['Invented source quotation.'])
        self.assertNotIn('summary_full',v['accepted'])

    def test_contextual_geography(self):
        for sentence in ["CBS News is the BBC's US partner.",
                         'The publisher is in the United States.',
                         'Nvidia is headquartered in the United States.',
                         'An interview in the United States discussed AI safety.',
                         'An American executive discussed AI safety.',
                         'Trump in the United States was referenced in commentary.']:
            with self.subTest(sentence=sentence):
                a={**self.a,'body':sentence}
                s=semantic(a);s['primary_country']='United States'
                s['citations'].append({'field':'primary_country','quote':sentence,'source_field':'body'})
                v=validate_semantics(a,{'semantic':s},{})
                self.assertNotIn('primary_country',v['accepted'])
                self.assertIsNone(validated_geography(a)['event_country'])

    def test_actual_event_geography_still_supported(self):
        a=article('An earthquake struck in Taiwan.',headline='Taiwan earthquake disrupts operations')
        self.assertEqual(validated_geography(a)['event_country'],'Taiwan')


class ResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.c=Config(provider='gemini',model='primary',api_key='test-only',cache_dir=Path(self.tmp.name))
        self.a=article('Nvidia discussed AI safety.',headline='Nvidia CEO discusses AI safety')
        self.sleep=patch('src.news.llm.analyzer.time.sleep').start()
    def tearDown(self):
        patch.stopall();self.tmp.cleanup()
    def provider(self, outcomes):
        f=FakeProvider()
        f.generate=unittest.mock.Mock(side_effect=outcomes)
        return f
    def success(self):return (semantic(self.a),{'input_tokens':2,'output_tokens':3,'total_tokens':5})

    def test_503_then_success(self):
        f=self.provider([ProviderError('http_503'),self.success()]);an=Analyzer(self.c,f)
        r=an.analyze_article(self.a)
        self.assertEqual(r['status'],'available');self.assertEqual(an.calls,2)
        self.assertEqual(r['attempt_count'],2);self.assertEqual(r['retry_count'],1)
        self.assertEqual(r['attempts'][0]['reason'],'http_503');self.assertFalse(r['fallback_used'])
        self.sleep.assert_called_once_with(2)

    def test_transient_allowlist_bounded(self):
        for code in (429,500,502,503,504):
            with self.subTest(code=code):
                c=replace(self.c,model=str(code))
                f=FakeProvider(error=ProviderError('http_'+str(code)));an=Analyzer(c,f)
                r=an.analyze_article(self.a)
                self.assertEqual(f.calls,3);self.assertEqual(an.calls,3)
                self.assertEqual(r['attempt_count'],3);self.assertFalse(r['cache_hit'])
                self.assertFalse(list(c.cache_dir.glob(an._digest(self.a,c.model)+'.json')))

    def test_nontransient_never_retries_or_falls_back(self):
        for reason in ('http_400','http_401','http_403','http_404','unsupported_model','transport_or_json_error','invalid_or_incomplete_response'):
            with self.subTest(reason=reason):
                f=FakeProvider(error=ProviderError(reason))
                an=Analyzer(replace(self.c,model=reason,fallback_model='fallback'),f)
                with patch.object(an,'_provider',side_effect=AssertionError('Unexpected fallback')):
                    r=an.analyze_article(self.a)
                self.assertEqual(f.calls,1);self.assertEqual(r['retry_count'],0)
                self.assertEqual(r['reason'],reason)

    def test_schema_validation_never_retries(self):
        f=FakeProvider(value={'invalid':'response'});an=Analyzer(self.c,f)
        r=an.analyze_article(self.a)
        self.assertEqual(f.calls,1);self.assertEqual(r['reason'],'invalid_schema')

    def test_fallback_actual_model_cache_and_reuse(self):
        c=replace(self.c,fallback_model='fallback')
        primary=FakeProvider(error=ProviderError('http_503'));fallback=self.provider([self.success()])
        an=Analyzer(c,primary)
        with patch.object(an,'_provider',return_value=fallback) as factory:
            r=an.analyze_article(self.a)
        self.assertEqual(primary.calls,2);self.assertEqual(fallback.generate.call_count,1)
        self.assertEqual(factory.call_args.args[0].model,'fallback')
        self.assertEqual(r['model'],'fallback');self.assertEqual(r['requested_model'],'primary')
        self.assertTrue(r['fallback_used']);self.assertEqual(r['retry_count'],2)
        self.assertEqual([x['model'] for x in r['attempts']],['primary','primary','fallback'])
        self.assertFalse((c.cache_dir/(an._digest(self.a,'primary')+'.json')).exists())
        self.assertTrue((c.cache_dir/(an._digest(self.a,'fallback')+'.json')).exists())
        again=Analyzer(c,FakeProvider(error=AssertionError('No request permitted')))
        cached=again.analyze_article(self.a)
        self.assertEqual(again.calls,0);self.assertTrue(cached['cache_hit'])
        self.assertEqual(cached['model'],'fallback')
        self.assertIn('prompt_version',cached)

    def test_model_provider_prompt_schema_isolation(self):
        f=FakeProvider();a=Analyzer(self.c,f)
        original=a.analyze_article(self.a)
        for c in (replace(self.c,model='second'),replace(self.c,provider='openai')):
            x=Analyzer(c,f).analyze_article(self.a)
            self.assertNotEqual(original['content_hash'],x['content_hash'])
        with patch('src.news.llm.analyzer.PROMPT_VERSION','changed'):
            x=Analyzer(self.c,f).analyze_article(self.a)
            self.assertNotEqual(original['content_hash'],x['content_hash'])
        with patch('src.news.llm.analyzer.VERSION','changed'):
            x=Analyzer(self.c,f).analyze_article(self.a)
            self.assertNotEqual(original['content_hash'],x['content_hash'])
        self.assertEqual(f.calls,5)

    def test_retry_count_does_not_consume_article_budget(self):
        f=self.provider([ProviderError('http_503'),self.success(),self.success()])
        an=Analyzer(replace(self.c,max_articles=2),f)
        an.analyze_article(self.a)
        an.analyze_article({**self.a,'body':'Another article.'})
        self.assertEqual(an.calls,3);self.assertEqual(an.processed,2)
        self.assertEqual(an.analyze_article({**self.a,'body':'Third article.'})['reason'],'run_limit')


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.a=article('Nvidia CEO discusses AI safety and existing company strategy.',headline='Nvidia CEO discusses AI safety',source=' BBC ')
        self.c=Config(provider='gemini',model='test',api_key='test',cache_dir=self.root)
    def tearDown(self):self.tmp.cleanup()
    def output(self,a=None,s=None,edges=None,c=None):
        a=a or self.a;c=c or self.c
        return build_research_output_v3([a],edges or [],config=c,analyzer=Analyzer(c,FakeProvider(s)),now='2026-09-18T08:00:00Z')

    def test_known_source_normalized_confidence(self):
        for name in ('BBC','bbc',' Bbc  '):
            r=self.output(a={**self.a,'source':name})['articles'][0]
            q=r['ticker_analysis'][0]['quantitative']
            self.assertIsNone(q['confidence']['value'])
            self.assertEqual(q['confidence']['source_quality'],'High')
            self.assertEqual(q['confidence']['source_quality_policy_notice'],SOURCE_POLICY_NOTICE)
            self.assertEqual(q['relevance']['value'],.45)
            self.assertTrue(all(v is None for k,v in q['impact'].items() if k!='reason'))

    def test_unknown_source_null_and_explicit_policy_override(self):
        r=self.output(a={**self.a,'source':'Unknown outlet'})['articles'][0]
        q=r['ticker_analysis'][0]['quantitative']['confidence']
        self.assertIsNone(q['value']);self.assertEqual(q['source_quality'],'Unknown')
        self.assertEqual(Config(source_quality={' BBC ': 'Medium'}).source_tier('bbc'),'Medium')
        self.assertEqual(Config(source_quality={}).source_tier('BBC'),'Unknown')

    def test_unsupported_classification_candidate_is_preserved_but_does_not_change_final(self):

        s = semantic(self.a)

        s.update(
            article_class="geopolitical_event",
            event_type="war",
            operational_event=True,
        )

        s["citations"].append(
            {
                "field": "event_type",
                "quote": self.a["headline"],
                "source_field": "headline",
            }
        )

        r = self.output(
            s=s
        )["articles"][0]

        # Gemini / semantic candidate should now be preserved
        # for audit and arbitration instead of being deleted.
        self.assertEqual(
            r["classification_assessment"]["candidates"]["article_class"],
            "geopolitical_event",
        )

        self.assertIn(
            "article_class",
            r["semantic_validation"]["accepted"],
        )

        self.assertIn(
            "event_type",
            r["semantic_validation"]["accepted"],
        )

        # Validator recognises the disagreement.
        self.assertEqual(
            r["semantic_validation"]["classification_arbitration"]["decision"],
            "classification_conflict",
        )

        # But "war" does not map through the bounded
        # V3.1.2 canonical taxonomy for this article,
        # so final deterministic classification remains unchanged.
        self.assertEqual(
            r["classification_assessment"]["arbitration"]["decision"],
            "deterministic_only",
        )

        self.assertFalse(
            r["classification_assessment"]["arbitration"]["applied"]
        )

        self.assertEqual(
            r["classification_assessment"]["final"],
            {
                "article_class": "commentary",
                "event_type": "commentary",
                "event_subtype": "commentary",
            },
        )

        # Severity remains independently rule-controlled.
        self.assertEqual(
            r["severity_assessment"]["severity_final"],
            "Low",
        )

        self.assertEqual(
            r["severity_assessment"]["severity_source"],
            "rule",
        )

    def test_ai_indirect_candidate_no_edge_no_qualification(self):
        s=semantic(self.a);s['candidate_indirect_tickers']=['AAPL']
        r=self.output(s=s)['articles'][0]
        self.assertFalse(any(t['ticker']=='AAPL' and t['qualification'].startswith('qualified_') for t in r['ticker_analysis']))
        self.assertEqual(r['semantic_validation']['candidate_relationships'][0]['state'],'unverified')

    def test_future_edge_ineligible(self):
        a=article('A 6.8 earthquake struck Taiwan and TSMC wafer fabrication was interrupted.',headline='Taiwan earthquake interrupts TSMC wafer fabrication')
        e=edge(channel_family='advanced_semiconductors',counterparty='TSMC',product_or_business='advanced chips',known_at_utc='2030-01-01')
        r=self.output(a=a,edges=[e])['articles'][0]
        self.assertFalse(any(t.get('evidence') for t in r['ticker_analysis']))

    def test_api_primary_quantitative_legacy_audit_compatible(self):
        data=self.output();p=self.root/'output.json';p.write_text(json.dumps(data))
        response,status=read_intelligence(self.root,p)
        self.assertEqual(status,200)
        self.assertEqual(response['presentation_policy']['primary_numeric_relevance'],'ticker_analysis[].quantitative.relevance')
        t=response['articles'][0]['ticker_analysis'][0]
        self.assertEqual(t['quantitative']['relevance']['value'],.45)
        self.assertEqual(t['relevance']['relationship_score'],.15)
        self.assertIn('classification_assessment',response['articles'][0])

    def test_run_counts_and_cached_success(self):
        first=self.output();second=self.output()
        self.assertEqual(first['summary']['llm_calls'],1)
        self.assertEqual(second['summary']['llm_calls'],0)
        self.assertEqual(second['summary']['cache_hits'],1)
        self.assertEqual(second['summary']['enrichment_success'],1)
        self.assertEqual(second['summary']['enrichment_failure'],0)
