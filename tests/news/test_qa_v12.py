"""Negation, action vocabulary and channel isolation stress regressions."""
import copy
import json
from pathlib import Path
import unittest
from src.news.event_gate import evaluate_gate
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.exposure_matcher import load_exposure_edges, match_exposures
from .helpers import article

ROOT=Path(__file__).resolve().parents[2]

def families(event):
    return {c['channel_family'] for c in generate_channels(event)['candidate_channels']}

class QAV12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles=json.loads((ROOT/'data/news/normalized/stress_test_articles.json').read_text())['articles']
        cls.events=[extract_event(a) for a in cls.articles]
        cls.edges,status=load_exposure_edges(ROOT)
        assert status['status']=='loaded'

    def matches(self,event):
        pairs,_=match_exposures(event,generate_channels(event),self.edges,prediction_time='2026-09-18T09:00:00Z')
        return {p['ticker']:p for p in pairs}

    def test_01_explicit_no_power_is_false(self):
        e=extract_event(article('An earthquake struck Taiwan. There was no power disruption.'))
        self.assertIs(e['power_disruption'],False)
        self.assertEqual(e['evidence_fields']['power_disruption']['assertion'],'negated')

    def test_02_false_power_not_candidate(self):
        e=extract_event(article('An earthquake struck Taiwan. No power disruption occurred.'))
        self.assertNotIn('electricity_grid',families(e))

    def test_03_no_shutdown_not_event(self):
        text='No factory shutdown, financing action, earnings announcement, regulatory decision or discrete operational event was announced.'
        self.assertFalse(evaluate_gate(article(text,headline=text))['is_event'])
        self.assertIsNone(extract_event(article(text,headline=text)))

    def test_04_tesla_commentary_rejected(self):
        self.assertFalse(evaluate_gate(self.articles[7])['is_event'])
        self.assertIsNone(self.events[7])

    def test_05_tsmc_interruption_accepted(self):
        e=self.events[4]
        self.assertIsNotNone(e)
        self.assertEqual(e['event_type'],'supply_chain')
        self.assertEqual(e['event_subtype'],'production_interruption')

    def test_06_tsmc_interruption_true(self):
        self.assertIs(self.events[4]['production_disruption'],True)

    def test_07_tsmc_geography_and_entities(self):
        e=self.events[4]
        self.assertEqual(e['primary_country'],'Taiwan')
        self.assertIn('TSMC',e['companies_mentioned'])
        self.assertEqual(e['tickers_mentioned'],[])

    def test_08_azure_expansion(self):
        e=self.events[0]
        self.assertEqual(e['event_type'],'product_technology')
        p=self.matches(e)
        self.assertEqual({t for t,r in p.items() if r['matched']},{'MSFT'})
        self.assertIn('datacenter_infrastructure',families(e))

    def test_09_google_product_accepted(self):
        e=self.events[3]
        self.assertEqual(e['event_type'],'product_technology')
        self.assertIn('GOOGL',e['tickers_mentioned'])

    def test_10_google_not_nvidia(self):
        e=self.events[3]; p=self.matches(e)
        self.assertFalse(p['NVDA']['matched'])
        self.assertEqual(p['NVDA']['relevance_score'],0)
        self.assertNotIn('advanced_semiconductors',families(e))

    def test_11_port_is_operational_event(self):
        e=self.events[2]
        self.assertEqual((e['event_type'],e['event_subtype']),('supply_chain','port_disruption'))
        self.assertIs(e['port_disruption'],True)
        self.assertIs(e['logistics_disruption'],True)
        self.assertEqual(e['primary_country'],'Taiwan')

    def test_12_consumer_port_not_semiconductors(self):
        e=self.events[2]; p=self.matches(e)
        self.assertEqual(families(e),{'logistics'})
        self.assertFalse(p['NVDA']['matched']); self.assertFalse(p['AAPL']['matched'])
        self.assertEqual(e['technologies_mentioned'],[])

    def test_13_retail_distribution_center_accepted(self):
        e=self.events[5]
        self.assertEqual(e['event_subtype'],'distribution_center_opening')
        self.assertEqual(e['tickers_mentioned'],['AMZN'])
        self.assertEqual(e['primary_country'],'United States')
        self.assertEqual(e['primary_region'],'Texas')
        self.assertIsNone(e['city'])

    def test_14_retail_not_aws_exposure(self):
        e=self.events[5]; p=self.matches(e)
        self.assertEqual(families(e),{'logistics','ecommerce_demand'})
        self.assertFalse(p['AMZN']['matched'])
        self.assertGreater(p['AMZN']['relevance_score'],0)
        self.assertNotIn('AWS',e['products_mentioned'])

    def test_15_china_regulation(self):
        e=self.events[6]
        self.assertEqual(e['event_type'],'government_policy')
        self.assertEqual(e['primary_country'],'China')
        self.assertIs(e['regulatory_channel'],True)
        self.assertEqual(families(e),{'regulatory_general','digital_advertising'})
        self.assertFalse(any(p['matched'] for p in self.matches(e).values()))

    def test_16_japan_no_fabricated_disruption(self):
        e=self.events[1]
        self.assertEqual(e['event_type'],'natural_disaster')
        self.assertIsNot(e['production_disruption'],True)
        self.assertIsNot(e['port_disruption'],True)
        self.assertIsNot(e['power_disruption'],True)
        self.assertEqual(families(e),set())
        self.assertFalse(any(p['matched'] for p in self.matches(e).values()))

    def test_17_company_mention_not_event(self):
        for text in ['Tesla CEO comments on electric vehicle demand.',
                     'Microsoft discusses long-term cloud opportunities.',
                     'Google and NVIDIA are technology companies.']:
            with self.subTest(text=text):
                self.assertFalse(evaluate_gate(article(text,headline=text))['is_event'])

    def test_required_negation_variations(self):
        for phrase in ['There was no power disruption.', 'Power was not disrupted.',
                       'The quake passed without power disruption.', 'There were no power disruptions.',
                       'The power supply remained operational.', 'Power was unaffected.']:
            with self.subTest(phrase=phrase):
                e=extract_event(article('An earthquake struck Taiwan. '+phrase))
                self.assertIs(e['power_disruption'],False)
                self.assertNotIn('electricity_grid',families(e))

    def test_absence_of_reports_is_unknown_not_false(self):
        for text in ['There were no reports of major factory shutdowns, port closures or power disruptions.',
                     'Officials found no evidence of power disruption.']:
            e=extract_event(article('An earthquake struck Taiwan. '+text))
            self.assertIsNone(e['power_disruption'])
            self.assertEqual(e['evidence_fields']['power_disruption']['assertion'],'unknown')
            self.assertNotIn('electricity_grid',families(e))

    def test_negated_condition_does_not_erase_preceding_root_event(self):
        e=extract_event(article('An earthquake struck Taiwan without power disruption.',headline='Taiwan quake'))
        self.assertEqual(e['event_type'],'natural_disaster')
        self.assertIs(e['power_disruption'],False)

    def test_negation_scope_resets_at_contrast(self):
        e=extract_event(article('No power disruption occurred, but rail services were suspended in Taiwan.'))
        self.assertIs(e['power_disruption'],False)
        self.assertIs(e['logistics_disruption'],True)
        self.assertIn('logistics',families(e))
        self.assertNotIn('electricity_grid',families(e))

    def test_no_port_closure_is_false(self):
        e=extract_event(article('An earthquake struck Taiwan. There was no port closure.'))
        self.assertIs(e['port_disruption'],False)

    def test_no_factory_shutdown_not_positive_flags(self):
        e=extract_event(article('An earthquake struck Taiwan. No factory shutdown occurred.'))
        self.assertIs(e['production_disruption'],False)
        self.assertIsNot(e['capacity_disruption'],True)
        self.assertNotIn('manufacturing',families(e))

    def test_multi_item_negative_list_no_event_or_channels(self):
        for prefix in ('No','There were no reports of','There was no evidence of'):
            text=prefix+' factory shutdown, financing action, earnings announcement or power outage was announced.'
            self.assertIsNone(extract_event(article(text,headline=text)))

    def test_negated_expansions_and_product_actions_fail(self):
        for text in ['Microsoft did not expand Azure capacity in the United States.',
                     'Google does not announce a new AI model.',
                     'Amazon did not open a new retail distribution center.',
                     'China has not introduced new rules for online advertising platforms.',
                     'TSMC did not interrupt production in Taiwan.']:
            with self.subTest(text=text):
                self.assertIsNone(extract_event(article(text,headline=text)))

    def test_wording_variations_not_exact_headlines(self):
        cases=[('TSMC interrupted production at a facility in Taiwan.','supply_chain'),
               ('Azure cloud capacity was expanded by Microsoft in the United States.','product_technology'),
               ('Google unveiled an artificial intelligence model.','product_technology'),
               ('Amazon inaugurated a fulfilment centre in Texas.','supply_chain'),
               ('New online advertising rules were introduced in China.','government_policy')]
        for text,kind in cases:
            with self.subTest(text=text):
                e=extract_event(article(text,headline=text))
                self.assertIsNotNone(e)
                self.assertEqual(e['event_type'],kind)

    def test_tsmc_indirect_edges_preserved(self):
        p=self.matches(self.events[4])
        self.assertEqual({t for t,r in p.items() if r['matched']},{'NVDA','AAPL'})
        self.assertFalse(p['NVDA']['direct_mention'])
        self.assertTrue({'manufacturing','supply_chain','advanced_semiconductors'}<=families(self.events[4]))

    def test_explicitly_excluded_peer_mentions_not_used(self):
        e=self.events[0]
        self.assertEqual(e['tickers_mentioned'],['MSFT'])
        self.assertNotIn('AWS',e['products_mentioned'])

    def test_candidate_generator_does_not_mutate_facts(self):
        e=copy.deepcopy(self.events[1]); original=copy.deepcopy(e)
        generate_channels(e)
        self.assertEqual(e,original)

    def test_false_and_null_flags_cannot_trigger_power(self):
        for value in (False,None):
            e=copy.deepcopy(self.events[1]); e['power_disruption']=value
            self.assertNotIn('electricity_grid',families(e))

    def test_old_negated_entity_evidence_not_channel_input(self):
        e=copy.deepcopy(self.events[1]); e['products_mentioned']=['AWS']
        e['evidence_fields']['products_mentioned']={'value':['AWS'],'evidence':'The event does not involve AWS.'}
        self.assertNotIn('cloud_services',families(e))

    def test_stress_batch_counts(self):
        self.assertEqual(sum(e is not None for e in self.events),7)
        self.assertEqual([a['article_id'] for a,e in zip(self.articles,self.events) if e is None],['stress_008'])

    def test_expansion_discussion_and_educational_content_not_events(self):
        for text in ['Microsoft discusses Azure capacity expansion.',
                     'A guide to cloud capacity expansion.',
                     'What is a factory shutdown?']:
            with self.subTest(text=text):
                self.assertIsNone(extract_event(article(text,headline=text)))

    def test_industry_mention_cannot_override_non_disruption(self):
        e=extract_event(article('An earthquake struck Taiwan. Semiconductors production was unaffected.'))
        self.assertIs(e['production_disruption'],False)
        self.assertNotIn('supply_chain',families(e))
