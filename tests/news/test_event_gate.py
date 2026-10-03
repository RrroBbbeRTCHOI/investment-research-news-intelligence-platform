import unittest
from src.news.event_gate import evaluate_gate
from .helpers import article

class GateTests(unittest.TestCase):
    def test_opinion_rejected(self):
        self.assertFalse(evaluate_gate(article('Donald Trump and Census Bureau statistics show economic prosperity matters.',headline='Moore: Marriage deficit an economic catastrophe'))['is_event'])

    def test_sports_rejected(self):
        self.assertFalse(evaluate_gate(article('The team launched an attack and won the game.',headline='High school football scores'))['is_event'])

    def test_lifestyle_rejected(self):
        self.assertFalse(evaluate_gate(article('Apple fruit provides vitamins and nutrition.',headline='Fruit nutrition'))['is_event'])

    def test_hypothetical_denied_and_old_events_rejected(self):
        for text in ['If an earthquake struck Taiwan, factories could suffer.',
                     'Officials denied an earthquake struck Taiwan.',
                     'An earthquake struck Taiwan in 1999.',
                     'An earthquake struck Taiwan years ago.',
                     'An earthquake did not hit Taiwan.',
                     'NASA may order additional Starliner missions.']:
            with self.subTest(text=text):
                self.assertFalse(evaluate_gate(article(text))['is_event'])

    def test_all_event_types_have_positive_examples(self):
        samples=[('natural_disaster','An earthquake struck Taiwan.'),
            ('geopolitical_conflict','The governments signed a ceasefire.'),
            ('government_policy','The government enacted a regulation.'),
            ('trade_export_control','China imposed export controls.'),
            ('macro_monetary','The Federal Reserve cut interest rates.'),
            ('energy_commodity','OPEC cut oil output.'),
            ('supply_chain','The factory shut down in Taiwan.'),
            ('infrastructure_outage','AWS suffered an outage in Ireland.'),
            ('cybersecurity','Microsoft disclosed a data breach.'),
            ('labor_disruption','Port workers went on strike in Canada.'),
            ('corporate_earnings','Apple reported quarterly results.'),
            ('corporate_financing','Tesla secured financing.'),
            ('product_technology','NVIDIA unveiled a processor.'),
            ('legal_antitrust','The court blocked the acquisition.'),
            ('management_governance','The CEO resigned.'),
            ('corporate_transaction','Microsoft completed an acquisition.')]
        from src.news.event_extractor import extract_event
        for kind,text in samples:
            with self.subTest(kind=kind):
                e=extract_event(article(text,headline=text))
                self.assertIsNotNone(e)
                self.assertEqual(e['event_type'],kind)

    def test_keywords_without_assertion_fail(self):
        self.assertFalse(evaluate_gate(article('A guide to earthquakes, tariffs, sanctions, cyberattacks and acquisitions.'))['is_event'])
