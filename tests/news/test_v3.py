import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.news.v3_config import Config
from src.news.llm.schemas import validate,SchemaError,PROPERTIES
from src.news.llm.analyzer import Analyzer
from src.news.llm.base import ProviderError
from src.news.v3_validation import prefilter,validate_semantics
from src.news.v3_scoring import quantify
from src.news.research_v3 import build_research_output_v3
from src.news.research_v2 import analyze_v2
from src.news.benchmark import evaluate,FIELDS
from src.news.ui_api import read_intelligence
from .helpers import article,edge

ROOT=Path(__file__).resolve().parents[2]

def semantic(a):
    result={k:None for k in PROPERTIES}
    for k,s in PROPERTIES.items():
        if s['type']=='array':result[k]=[]
        elif s['type']=='string':result[k]=''
    result.update(article_class='commentary',is_relevant_candidate=True,summary_short=a['headline'],summary_full=a['body'],severity_candidate='Low',severity_reason='Management commentary',llm_confidence=.8,severity_confidence=.8,
        citations=[{'field':f,'quote':a['headline'],'source_field':'headline'} for f in ['summary_short','summary_full','article_class']])
    return result

class FakeProvider:
    def __init__(self,value=None,error=None):self.value=value;self.error=error;self.calls=0
    def generate(self,a):
        self.calls+=1
        if self.error:raise self.error
        return copy.deepcopy(self.value if self.value is not None else semantic(a)),{'input_tokens':10,'output_tokens':20,'total_tokens':30}

class V3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.a=article('Nvidia CEO discusses AI safety and existing company strategy.',headline='Nvidia CEO discusses AI safety',article_url='https://example.com/original',source='Test source')
        self.c=Config(provider='gemini',model='test-model',api_key='test-only',cache_dir=self.root/'cache')
    def tearDown(self):self.tmp.cleanup()
    def runone(self,a=None,provider=None,edges=None):
        return build_research_output_v3([a or self.a],edges or [],config=self.c,analyzer=Analyzer(self.c,provider or FakeProvider()),now='2026-09-18T08:00:00Z')['articles'][0]
    def test_schema_valid_and_null(self):self.assertIsNone(validate(semantic(self.a))['primary_country'])
    def test_schema_malformed(self):
        for change in [{'extra':1},{'llm_confidence':float('nan')},{'llm_confidence':2},{'operational_event':'yes'},{'severity_candidate':'Extreme'}]:
            with self.assertRaises(SchemaError):validate({**semantic(self.a),**change})
    def test_schema_missing_field(self):
        s=semantic(self.a);s.pop('citations')
        with self.assertRaises(SchemaError):validate(s)
    def test_no_key(self):
        self.c.api_key='';f=FakeProvider();x=Analyzer(self.c,f).analyze_article(self.a)
        self.assertEqual(x['reason'],'missing_api_key');self.assertEqual(f.calls,0)
    def test_none_provider(self):
        f=FakeProvider();x=Analyzer(Config(),f).analyze_article(self.a)
        self.assertEqual(x['reason'],'provider_disabled');self.assertEqual(f.calls,0)
    def test_cache_cross_instance(self):
        f=FakeProvider();x=Analyzer(self.c,f).analyze_article(self.a);y=Analyzer(self.c,f).analyze_article(self.a)
        self.assertEqual(f.calls,1);self.assertTrue(y['cache_hit']);self.assertEqual(x['semantic'],y['semantic'])
    def test_cache_content_change(self):
        f=FakeProvider();a=Analyzer(self.c,f);a.analyze_article(self.a);a.analyze_article({**self.a,'body':self.a['body']+' New detail.'});self.assertEqual(f.calls,2)
    def test_reprocess_once_per_run(self):
        f=FakeProvider();Analyzer(self.c,f).analyze_article(self.a);self.c.reprocess=True;a=Analyzer(self.c,f);a.analyze_article(self.a);a.analyze_article(self.a);self.assertEqual(f.calls,2)
    def test_limit(self):
        self.c.max_articles=0;f=FakeProvider();self.assertEqual(Analyzer(self.c,f).analyze_article(self.a)['reason'],'run_limit');self.assertEqual(f.calls,0)
    def test_rate_limit_fallback(self):
        f=FakeProvider(error=ProviderError('http_429'));a=Analyzer(self.c,f);self.assertEqual(a.analyze_article(self.a)['reason'],'http_429');self.assertEqual(a.analyze_article({**self.a,'body':'Different valid article body.'})['reason'],'run_limit')
    def test_empty_provider_fallback(self):self.assertEqual(self.runone(provider=FakeProvider(value={}))['enrichment']['reason'],'invalid_schema')
    def test_invalid_response_fallback(self):
        r=self.runone(provider=FakeProvider(value={'invalid':'response'}));self.assertEqual(r['enrichment']['reason'],'invalid_schema');self.assertEqual(r['ticker_analysis'][0]['ticker'],'NVDA')
    def test_transport_failure_fallback(self):
        self.assertEqual(self.runone(provider=FakeProvider(error=ProviderError('transport_or_json_error')))['enrichment']['status'],'unavailable')
    def test_noise_and_macro(self):
        for h in ['Missing cruise passenger found','Celebrity national anthem performance']:
            self.assertEqual(prefilter(article(h,headline=h))['state'],'reject')
        self.assertEqual(prefilter(article('A semiconductor factory halted production in Taiwan.',headline='Taiwan production disruption'))['state'],'surface')
        self.assertEqual(prefilter(article('A chemical vapor cloud formed.',headline='Pool chemical vapor cloud'))['state'],'background')
        self.assertEqual(prefilter(article('Yen traders consider interest rates.',headline='Yen commentary on future rate changes'))['state'],'background')
    def test_llm_does_not_promote_exposure(self):
        s=semantic(self.a);s['candidate_indirect_tickers']=['AAPL'];r=self.runone(provider=FakeProvider(s))
        self.assertNotIn('AAPL',[t['ticker'] for t in r['ticker_analysis']]);self.assertEqual(r['semantic_validation']['candidate_relationships'][0]['state'],'unverified')
    def test_summaries_and_url(self):
        r=self.runone();self.assertEqual(r['article_summary']['summary_short'],self.a['headline']);self.assertEqual(r['article_url'],self.a['article_url'])
    def test_fake_citation_rejected(self):
        s=semantic(self.a);s['citations'][0]['quote']='A fabricated quote not in source';r=self.runone(provider=FakeProvider(s));self.assertIsNone(r['article_summary']['summary_short'])
    def test_fabricated_number_rejected(self):
        s=semantic(self.a);s['summary_short']='Nvidia revenue rose 991%.';self.assertIsNone(self.runone(provider=FakeProvider(s))['article_summary']['summary_short'])
    def test_commentary_severity_not_promoted(self):
        s=semantic(self.a);s['severity_candidate']='Critical';r=self.runone(provider=FakeProvider(s));self.assertEqual(r['severity']['level'],'Low');self.assertEqual(r['severity_assessment']['severity_candidate'],'Critical')
    def test_major_halt_and_unknown(self):
        h='A major fab production halt stopped manufacturing in Taiwan'
        self.assertEqual(self.runone(article(h+' Operations stopped today.',headline=h))['severity']['level'],'High')
        h='Community exhibition opens in Japan'
        self.assertEqual(self.runone(article(h+' Residents attended the exhibition.',headline=h))['severity']['level'],'Unknown')
    def test_aws_tesla_direct(self):
        for h,ticker in [('AWS service outage disrupts cloud services','AMZN'),('Tesla Shanghai production halt interrupts manufacturing','TSLA')]:
            r=self.runone(article(h+' The interruption occurred today.',headline=h));t=next(t for t in r['ticker_analysis'] if t['ticker']==ticker)
            self.assertEqual(t['relationship_type'],'direct_event_subject')
    def test_taiwan_edge_pit(self):
        a=article('A 6.8 earthquake struck Taiwan and TSMC wafer fabrication was interrupted.',headline='Taiwan earthquake interrupts TSMC wafer fabrication')
        e=edge(channel_family='advanced_semiconductors',counterparty='TSMC',product_or_business='advanced chips')
        r=self.runone(a,edges=[e]);self.assertTrue(any(t.get('evidence') for t in r['ticker_analysis']))
        e['known_at_utc']='2030-01-01';r=self.runone(a,edges=[e]);self.assertFalse(any(t.get('evidence') for t in r['ticker_analysis']))
    def test_quantification(self):
        self.c.source_quality={'Test source':'High'};r=self.runone();q=r['ticker_analysis'][0]['quantitative']
        self.assertIsNone(q['confidence']['value']);self.assertEqual(q['confidence']['source_quality'],'High');self.assertIsNone(q['impact']['value']);self.assertAlmostEqual(q['time_decay']['value'],2**(-24/72))
        self.assertEqual(q['relevance']['kind'],'normalized_heuristic')
    def test_missing_confidence_and_future_date(self):
        r=self.runone();q=r['ticker_analysis'][0]['quantitative'];self.assertIsNone(q['confidence']['value'])
        q=quantify({**self.a,'published_at':'2030-01-01'},r['ticker_analysis'][0],r,self.c,'2026-01-01');self.assertIsNone(q['time_decay']['value'])
    def test_ui_api_v3(self):
        data=build_research_output_v3([self.a],[],config=Config());p=self.root/'x.json';p.write_text(json.dumps(data));out,status=read_intelligence(self.root,p)
        self.assertEqual(status,200);self.assertEqual(out['schema_version'],'news_ui_v3');self.assertEqual(out['articles'][0]['article_url'],self.a['article_url']);self.assertIn('article_summary',out['articles'][0])
    def test_normalizer_url_fallback(self):
        from src.news.normalizer import normalize_article
        with patch('src.news.normalizer.load_detail',return_value=None):r=normalize_article({'uuid':'abc','title':'Test title','url':'https://example.com/original'}, {})
        self.assertEqual(r['article_url'],'https://example.com/original')
    def test_benchmark_pending_is_not_truth(self):
        b={'articles':[{'article_id':'1','review_status':'ai_candidate_only'}]};r=evaluate(b,{'articles':[]});self.assertEqual(r['human_verified_articles'],0);self.assertIsNone(r['metrics']['country_accuracy']['value'])
    def test_benchmark_denominators_and_missing(self):
        e=dict.fromkeys(FIELDS);e.update(should_surface=True,direct_tickers=['NVDA'],severity='Low')
        b={'articles':[{'article_id':'1','review_status':'human_verified','reviewer':'test reviewer','reviewed_at':'2026-09-23','expected':e}]}
        p={'articles':[{'article_id':'1','feed':{'state':'surface'},'severity':{'level':'Low'},'ticker_analysis':[{'ticker':'NVDA','relationship_type':'direct_company_subject','qualification':'qualified_direct_company_subject'}]}]}
        r=evaluate(b,p);self.assertEqual(r['metrics']['direct_ticker_precision'],{'numerator':1,'denominator':1,'value':1})
        with self.assertRaises(ValueError):evaluate(b,{'articles':[]})

    def test_refresh_never_enriches(self):
        from app import app
        data=build_research_output_v3([self.a],[],config=Config());p=self.root/'snapshot.json';p.write_text(json.dumps(data))
        with patch.dict(app.config,{'NEWS_INTELLIGENCE_OUTPUT_PATH':str(p)}), patch.object(Analyzer,'analyze_article',side_effect=AssertionError('Unexpected online enrichment')):
            client=app.test_client()
            self.assertEqual(client.get('/api/news/intelligence').status_code,200)
            self.assertEqual(client.get('/api/news/intelligence').status_code,200)
            self.assertEqual(client.get('/news').status_code,200)

    def test_export_controls_retained(self):
        h='US imposed export controls on advanced AI chips to China'
        r=self.runone(article(h+' The restrictions took effect today.',headline=h))
        self.assertTrue(r['gate']['is_event']);self.assertEqual(r['event']['event_type'],'trade_export_control')
        self.assertFalse(any(t.get('evidence') for t in r['ticker_analysis']))

    def test_config_rejects_invalid_decay(self):
        with self.assertRaises(ValueError):Config(half_life_hours=0)
        with self.assertRaises(ValueError):Config(source_quality=[])

class ProviderContractTests(unittest.TestCase):
    def test_gemini_structured_request_and_bad_usage(self):
        from src.news.llm.gemini_provider import GeminiProvider
        a=article();s=semantic(a);config=Config(provider='gemini',model='test',api_key='test')
        with patch('src.news.llm.gemini_provider.post',return_value={'steps':[{'type':'model_output','content':[{'type':'text','text':json.dumps(s)}]}],'usage':'bad'}) as request:
            result,usage=GeminiProvider(config).generate(a)
        self.assertEqual(result,s);self.assertIsNone(usage['input_tokens']);self.assertEqual(request.call_args.args[2]['response_format']['mime_type'],'application/json')
    def test_openai_structured_request(self):
        from src.news.llm.openai_provider import OpenAIProvider
        a=article();s=semantic(a);config=Config(provider='openai',model='test',api_key='test')
        with patch('src.news.llm.openai_provider.post',return_value={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(s)}]}]}) as request:
            result,_=OpenAIProvider(config).generate(a)
        self.assertEqual(result,s);self.assertTrue(request.call_args.args[2]['text']['format']['strict'])
    def test_refusal_and_empty(self):
        from src.news.llm.openai_provider import OpenAIProvider
        for response in [{'status':'incomplete'},{'status':'completed','output':[]},None]:
            with patch('src.news.llm.openai_provider.post',return_value=response):
                with self.assertRaises(ProviderError):OpenAIProvider(Config()).generate(article())
    def test_http_error_redacted(self):
        import urllib.error
        from src.news.llm.base import post
        with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.invalid',429,'secret response',{},None)):
            with self.assertRaisesRegex(ProviderError,'^http_429$'):post('https://example.invalid',{}, {},1)
