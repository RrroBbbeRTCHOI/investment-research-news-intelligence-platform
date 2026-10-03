"""Positive controls plus wording variations and adversarial peer-edge checks."""
import copy
import json
from pathlib import Path
import unittest
from src.news.event_gate import evaluate_gate
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.exposure_matcher import match_exposures, load_exposure_edges
from .helpers import article, edge

ROOT=Path(__file__).resolve().parents[2]
AT='2026-09-18T09:00:00Z'

def pairs(event,edges):
    result,_=match_exposures(event,generate_channels(event),edges,prediction_time=AT)
    return {p['ticker']:p for p in result}

def cloud_edges():
    return [edge(edge_id=t,ticker=t,country='United States',channel_family='datacenter_infrastructure',
                 role='operator',product_or_business=b,counterparty=None)
            for t,b in [('AMZN','Amazon Web Services'),('MSFT','Azure; Microsoft 365; AI services'),
                        ('GOOGL','Google Cloud'),('META','Facebook; Instagram; Meta AI')]]

class QAV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles=json.loads((ROOT/'data/news/normalized/positive_control_articles.json').read_text())['articles']
        cls.events=[extract_event(a) for a in cls.articles]

    def test_01_earthquake_root_type(self):
        self.assertEqual(self.events[0]['event_type'],'natural_disaster')

    def test_02_earthquake_subtype(self):
        self.assertEqual(self.events[0]['event_subtype'],'earthquake')

    def test_03_no_inferred_port(self):
        self.assertIsNone(self.events[0]['port_disruption'])
        self.assertIs(self.events[0]['logistics_disruption'],True)

    def test_04_taiwan_geography(self):
        self.assertEqual(self.events[0]['primary_country'],'Taiwan')
        self.assertEqual(self.events[0]['tickers_mentioned'],[])

    def test_05_export_type(self):
        self.assertEqual(self.events[1]['event_type'],'trade_export_control')

    def test_06_export_policy_actor(self):
        self.assertEqual(self.events[1]['primary_country'],'United States')

    def test_07_export_destination(self):
        self.assertIn('China',self.events[1]['affected_countries'])

    def test_08_nvidia_mention(self):
        self.assertIn('NVDA',self.events[1]['tickers_mentioned'])

    def test_09_aws_amazon_match(self):
        self.assertTrue(pairs(self.events[2],cloud_edges())['AMZN']['matched'])

    def test_10_aws_not_microsoft(self):
        self.assertFalse(pairs(self.events[2],cloud_edges())['MSFT']['matched'])

    def test_11_aws_not_google(self):
        self.assertFalse(pairs(self.events[2],cloud_edges())['GOOGL']['matched'])

    def test_12_aws_not_meta(self):
        self.assertFalse(pairs(self.events[2],cloud_edges())['META']['matched'])

    def test_13_shanghai_geography(self):
        self.assertEqual(self.events[3]['primary_country'],'China')
        self.assertEqual(self.events[3]['city'],'Shanghai')
        self.assertIn('Shanghai',self.events[3]['evidence_fields']['city']['evidence'])

    def test_14_tesla_operational_match(self):
        e=edge(ticker='TSLA',country='China',channel_family='automotive',role='operator',product_or_business='Model 3')
        self.assertTrue(pairs(self.events[3],[e])['TSLA']['matched'])

    def test_15_fed_gate(self):
        self.assertTrue(evaluate_gate(self.articles[4])['is_event'])

    def test_16_fed_event_type(self):
        self.assertEqual(self.events[4]['event_type'],'macro_monetary')

    def test_17_fed_event_subtype(self):
        self.assertEqual(self.events[4]['event_subtype'],'rate_cut')

    def test_18_fed_channel_and_jurisdiction(self):
        self.assertIs(self.events[4]['interest_rate_channel'],True)
        self.assertEqual(self.events[4]['primary_country'],'United States')
        self.assertIn('Federal Reserve',self.events[4]['regulators'])

    def test_19_fed_zero_matches_valid(self):
        self.assertFalse(any(p['matched'] for p in pairs(self.events[4],cloud_edges()).values()))

    def test_20_invalid_peer_components_zero(self):
        p=pairs(self.events[2],cloud_edges())['MSFT']
        for c in ('edge_match','country_match','channel_match'):
            self.assertEqual(p['relevance_components'][c],0)
        self.assertEqual(p['relevance_score'],0)

    def test_21_tsmc_shared_upstream_match(self):
        e=extract_event(article('TSMC halted production of advanced semiconductors at its factory in Taiwan.'))
        rows=[edge(channel_family='advanced_semiconductors',role='buyer',counterparty='TSMC'),
              edge(edge_id='apple',ticker='AAPL',channel_family='advanced_semiconductors',role='buyer',counterparty='TSMC',evidence_status='partial'),
              edge(edge_id='unrelated',ticker='META',channel_family='advanced_semiconductors',role='buyer',counterparty='Samsung')]
        p=pairs(e,rows)
        self.assertTrue(p['NVDA']['matched']); self.assertTrue(p['AAPL']['matched'])
        self.assertFalse(p['META']['matched'])
        self.assertFalse(p['NVDA']['direct_mention'])

    def test_22_blocked_stays_blocked(self):
        rows=cloud_edges(); rows[0]['evidence_status']='blocked'
        self.assertFalse(any(p['matched'] for p in pairs(self.events[2],rows).values()))

    def test_23_known_at_unchanged(self):
        rows=cloud_edges(); rows[0]['known_at_utc']='2027-01-01'
        self.assertFalse(pairs(self.events[2],rows)['AMZN']['matched'])

    def test_24_valid_interval_unchanged(self):
        for field,value in [('valid_from','2027-01-01'),('valid_to','2025-12-31')]:
            with self.subTest(field=field):
                rows=cloud_edges(); rows[0][field]=value
                self.assertFalse(pairs(self.events[2],rows)['AMZN']['matched'])

    def test_root_precedence_across_sentence_order(self):
        cases=[('Rail services were suspended in Taiwan.','An earthquake struck Taiwan.','natural_disaster','earthquake'),
               ('A factory was closed in Taiwan.','A typhoon hit Taiwan.','natural_disaster','typhoon'),
               ('Chip production was halted at a factory in China.','The US announced export controls to China.','trade_export_control','export_controls')]
        for consequence,cause,kind,subtype in cases:
            with self.subTest(kind=kind):
                e=extract_event(article(cause,headline=consequence))
                self.assertEqual((e['event_type'],e['event_subtype']),(kind,subtype))

    def test_generic_transport_not_port_subtype(self):
        for text in ['Freight was disrupted in Taiwan.','Rail services were suspended in Taiwan.']:
            e=extract_event(article(text,headline=text))
            self.assertEqual(e['event_subtype'],'transport_disruption')
            self.assertIsNone(e['port_disruption'])

    def test_explicit_port_can_be_true(self):
        e=extract_event(article('The harbor was closed in Taiwan.',headline='Harbor closure'))
        self.assertEqual(e['event_subtype'],'port_disruption')
        self.assertIs(e['port_disruption'],True)

    def test_policy_country_aliases_and_passive_actor(self):
        for country in ('US','U.S.','United States'):
            for text in (f'{country} imposed export controls to China.',
                         f'Export controls on China were announced by the {country}.'):
                with self.subTest(text=text):
                    e=extract_event(article(text,headline=text))
                    self.assertEqual(e['primary_country'],'United States')
                    self.assertIn('China',e['affected_countries'])

    def test_rate_cut_wording_variations(self):
        for text in ['Federal Reserve cuts benchmark interest rate by 25 basis points.',
                     'The Federal Reserve lowered its policy rate.',
                     'The Federal Reserve announced a reduction in interest rates.']:
            e=extract_event(article(text,headline=text))
            self.assertEqual((e['event_type'],e['event_subtype']),('macro_monetary','rate_cut'))

    def test_regional_grid_is_not_entity_specific(self):
        e=extract_event(article('A regional electricity grid outage disrupted data centers in the United States.'))
        p=pairs(e,cloud_edges())
        self.assertEqual({t for t,v in p.items() if v['matched']},{'AMZN','MSFT','GOOGL','META'})

    def test_explicit_aws_dependency_can_match_peer(self):
        rows=cloud_edges(); rows[1].update(role='customer',counterparty='Amazon Web Services')
        self.assertTrue(pairs(self.events[2],rows)['MSFT']['matched'])

    def test_aws_requires_service_not_just_amazon_name(self):
        rows=cloud_edges(); rows[1].update(role='buyer',counterparty='Amazon retail')
        self.assertFalse(pairs(self.events[2],rows)['MSFT']['matched'])

    def test_operator_relation_is_not_customer_dependency(self):
        rows=cloud_edges(); rows[1]['counterparty']='AWS'
        self.assertFalse(pairs(self.events[2],rows)['MSFT']['matched'])

    def test_explicitly_named_peer_not_affected_subject(self):
        e=extract_event(article('AWS suffered an outage in the United States, unlike Microsoft which was unaffected.'))
        p=pairs(e,cloud_edges())
        self.assertTrue(p['AMZN']['matched']); self.assertFalse(p['MSFT']['matched'])

    def test_same_owner_wrong_business_blocked(self):
        rows=cloud_edges(); rows[0]['product_or_business']='Amazon retail stores'
        self.assertFalse(pairs(self.events[2],rows)['AMZN']['matched'])

    def test_tesla_halt_not_china_demand_exposure(self):
        rows=[edge(ticker='TSLA',country='China',channel_family='automotive',role='seller',stage='demand'),
              edge(edge_id='peer',ticker='AAPL',country='China',channel_family='manufacturing',role='buyer',counterparty='Foxconn')]
        self.assertFalse(any(p['matched'] for p in pairs(self.events[3],rows).values()))

    def test_entity_rule_applies_beyond_outages(self):
        cases=['Microsoft reported quarterly results in the United States.',
               'Microsoft secured financing in the United States.',
               'Microsoft disclosed a data breach in the United States.',
               'Microsoft CEO resigned in the United States.']
        for text in cases:
            e=extract_event(article(text,headline=text))
            candidates={'event_id':e['event_id'],'candidate_channels':[{'channel_family':'datacenter_infrastructure','channel_subtype':'unspecified','status':'candidate'}]}
            p,_=match_exposures(e,candidates,cloud_edges(),prediction_time=AT)
            self.assertEqual({x['ticker'] for x in p if x['matched']},{'MSFT'})

    def test_frozen_event_object_not_mutated_by_matching(self):
        event=copy.deepcopy(self.events[2]); original=copy.deepcopy(event)
        pairs(event,cloud_edges())
        self.assertEqual(event,original)

    def test_supplied_workbook_positive_matches(self):
        edges,status=load_exposure_edges(ROOT)
        self.assertEqual(status['status'],'loaded')
        expected=[{}, {'NVDA':['5']}, {'AMZN':['17']}, {'TSLA':['23']}, {}]
        for e,wanted in zip(self.events,expected):
            got={t:[r['edge_id'] for r in p['matched_edges']] for t,p in pairs(e,edges).items() if p['matched']}
            self.assertEqual(got,wanted)

    def test_named_supplier_generic_production_uses_real_edges(self):
        e=extract_event(article('TSMC reported a production outage in Taiwan.',headline='Supplier production outage'))
        edges,_=load_exposure_edges(ROOT)
        p=pairs(e,edges)
        self.assertTrue(p['NVDA']['matched']); self.assertTrue(p['AAPL']['matched'])
        self.assertEqual(e['tickers_mentioned'],[])
        self.assertNotIn('advanced semiconductors',e['technologies_mentioned'])
        self.assertIn('named_supplier_production_channel_refinement',p['NVDA']['matched_edges'][0]['match_reasons'])

    def test_unnamed_factory_does_not_refine_country_into_supplier(self):
        e=extract_event(article('Production was halted at a factory in Taiwan.',headline='Production halted'))
        edges,_=load_exposure_edges(ROOT)
        self.assertFalse(any(p['matched'] for p in pairs(e,edges).values()))

    def test_coordinated_services_preserve_own_business_edges(self):
        e=extract_event(article('AWS and Azure suffered an outage in the United States.'))
        p=pairs(e,cloud_edges())
        self.assertEqual({t for t,v in p.items() if v['matched']},{'AMZN','MSFT'})

    def test_supported_shared_facility_link(self):
        e=copy.deepcopy(self.events[2]); e['location_name']='Facility Q'
        e['evidence_fields']['location_name']={'value':'Facility Q','evidence':'AWS outage at Facility Q'}
        rows=cloud_edges(); rows[1].update(role='customer',facility_or_route='Facility Q')
        self.assertTrue(pairs(e,rows)['MSFT']['matched'])
