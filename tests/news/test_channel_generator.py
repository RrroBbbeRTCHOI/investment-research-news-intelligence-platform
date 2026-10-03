import copy
import unittest
from src.news.channel_generator import generate_channels
from src.news.event_extractor import extract_event
from .helpers import article

class ChannelTests(unittest.TestCase):
    def test_earthquake_does_not_invent_semiconductors(self):
        e=extract_event(article('An earthquake struck Taiwan.'))
        old=copy.deepcopy(e)
        result=generate_channels(e)
        self.assertEqual(e,old)
        self.assertEqual([x['channel_family'] for x in result['candidate_channels']],['supply_chain'])
        self.assertIsNone(e['production_disruption'])
        self.assertIsNone(e['supply_channel'])
        self.assertEqual(result['candidate_channels'][0]['status'],'candidate')

    def test_unknown_or_false_does_not_become_disruption(self):
        e=extract_event(article('The CEO resigned.'))
        e['production_disruption']=False
        self.assertEqual(generate_channels(e)['candidate_channels'],[])

    def test_logistics_evidence_supports_candidate(self):
        e=extract_event(article())
        channels=generate_channels(e)['candidate_channels']
        self.assertTrue(any(c['channel_family']=='logistics' for c in channels))

    def test_generic_semiconductors_not_advanced(self):
        e=extract_event(article('Production of semiconductors was halted at a factory in Taiwan.'))
        self.assertIsNotNone(e)
        self.assertNotIn('advanced_semiconductors',[c['channel_family'] for c in generate_channels(e)['candidate_channels']])
