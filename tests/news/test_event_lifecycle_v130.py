"""Concrete lifecycle actions, not final-outcome or liability assertions."""
import json
from pathlib import Path
import unittest
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.schemas import validate_event
from .helpers import article

ROOT = Path(__file__).resolve().parents[2]

class LifecycleTests(unittest.TestCase):
    def event(self, text):
        return extract_event(article(text, headline=text))

    def check(self, text, kind, subtype):
        e = self.event(text)
        self.assertIsNotNone(e, text)
        self.assertEqual((e['event_type'], e['event_subtype']), (kind, subtype))
        validate_event(e)
        return e

    def test_01_doj_lawsuit(self):
        self.check('U.S. Justice Department files antitrust lawsuit against Apple', 'legal_antitrust', 'lawsuit')

    def test_02_eu_charge(self):
        self.check('European Commission charges Microsoft over Teams bundling', 'legal_antitrust', 'charge')

    def test_03_ftc_complaint(self):
        self.check('FTC files antitrust complaint against Amazon', 'legal_antitrust', 'complaint')

    def test_04_remedy_proposal(self):
        self.check('Prosecutors propose Google divest Chrome', 'legal_antitrust', 'remedy_proposal')

    def test_05_formal_scrutiny(self):
        self.check('Microsoft AI partnership faces formal EU regulatory scrutiny', 'legal_antitrust', 'investigation')

    def test_06_recall(self):
        self.check('Tesla recalls 2 million vehicles over Autopilot safeguards', 'corporate_action', 'recall')

    def test_07_transaction_termination(self):
        self.check('Amazon and iRobot terminate acquisition', 'corporate_transaction', 'acquisition_terminated')

    def test_08_workforce(self):
        self.check('Tesla cuts more than 10% of workforce', 'corporate_action', 'workforce_reduction')

    def test_09_market_access(self):
        e=self.check('Chinese government departments restrict employee use of iPhones', 'government_policy', 'regulation')
        self.assertIs(e['regulatory_change'], True)
        self.assertIsNone(e['import_restriction'])

    def test_10_lawsuit_speculation(self):
        self.assertIsNone(self.event('Analysts say Apple could face future lawsuit'))

    def test_11_layoff_speculation(self):
        self.assertIsNone(self.event('Tesla may cut jobs next year'))

    def test_12_hypothetical_divestiture(self):
        self.assertIsNone(self.event('Google could be forced to sell Chrome'))
        e=extract_event(article('U.S. prosecutors proposed that Google divest Chrome.',
                                headline='Google could be forced to sell Chrome'))
        self.assertEqual(e['event_subtype'], 'remedy_proposal')

    def test_13_hypothetical_scrutiny(self):
        self.assertIsNone(self.event('Regulators may scrutinize Microsoft AI deals'))

    def test_negation(self):
        for text in ('No recall was announced.', 'No lawsuit has been filed.',
                     'The regulator denied opening an investigation.',
                     'The company denied plans for layoffs.',
                     'FTC did not file an antitrust complaint against Amazon.',
                     'Tesla announced no job cuts.',
                     'Amazon did not terminate the acquisition.',
                     'European Commission has not charged Microsoft with antitrust violations.'):
            with self.subTest(text=text): self.assertIsNone(self.event(text))

    def test_non_events(self):
        for text in ('Tesla discussed a hiring slowdown.',
                     'Tesla dismissed an employee.',
                     'Analysts forecast workforce reduction at Tesla.',
                     'A rumor claims Tesla recalled two million vehicles.',
                     'A politician criticized Apple business practices.',
                     'Microsoft partnership attracts regulatory interest.',
                     'Tesla software update improves vehicle safety.',
                     'A report lists customer complaint statistics.',
                     'Google is considering a settlement of a lawsuit.'):
            with self.subTest(text=text): self.assertIsNone(self.event(text))

    def test_legal_lifecycle_variants(self):
        samples=(('FTC launched an investigation into Amazon.', 'investigation'),
                 ('The European Commission is formally examining the transaction.', 'investigation'),
                 ('A lawsuit was filed against Apple.', 'lawsuit'),
                 ('FTC filed a formal complaint against Amazon.', 'complaint'),
                 ('DOJ brought formal charges against Apple.', 'charge'),
                 ('Prosecutors proposed remedies for Google.', 'remedy_proposal'),
                 ('Prosecutors asked court to require divestiture.', 'remedy_proposal'),
                 ('The court ordered to divest the business.', 'ruling'),
                 ('The European Commission fined Apple.', 'fine'),
                 ('The regulator penalized Microsoft.', 'fine'),
                 ('Google settled a lawsuit.', 'settlement'),
                 ('Microsoft agreed to legally binding commitments with the European Commission.', 'settlement'),
                 ('The European Commission provisionally accepted commitments from Microsoft.', 'regulatory_scrutiny'))
        for text,subtype in samples:
            with self.subTest(text=text):self.check(text,'legal_antitrust',subtype)

    def test_corporate_action_variants(self):
        samples=(('Tesla announced a safety recall.', 'corporate_action','recall'),
                 ('A safety recall was initiated by Tesla.', 'corporate_action','recall'),
                 ('Tesla lays off employees.', 'corporate_action','workforce_reduction'),
                 ('Tesla began layoffs.', 'corporate_action','workforce_reduction'),
                 ('Tesla announced job cuts.', 'corporate_action','workforce_reduction'),
                 ('Tesla implemented workforce reductions.', 'corporate_action','workforce_reduction'),
                 ('The merger was abandoned by Amazon.', 'corporate_transaction','acquisition_terminated'),
                 ('The transaction was withdrawn.', 'corporate_transaction','acquisition_terminated'))
        for text,kind,subtype in samples:
            with self.subTest(text=text): self.check(text,kind,subtype)

    def test_announced_review_is_not_opened_investigation(self):
        self.check('The European Commission said it would analyze Microsoft deal with Mistral.',
                   'legal_antitrust','regulatory_scrutiny')
        self.assertIsNone(self.event('Analysts said the European Commission would analyze Microsoft deal.'))

    def test_channels_are_not_liability(self):
        e=self.event('FTC files antitrust complaint against Amazon')
        self.assertIs(e['legal_channel'],True)
        self.assertIsNone(e['severity_score'])
        self.assertIsNone(e['production_disruption'])
        self.assertIn('legal_antitrust',{c['channel_family'] for c in generate_channels(e)['candidate_channels']})

    def test_it_outage_not_cause_attribution(self):
        e=self.event('A global IT outage disrupted airlines and banks.')
        self.assertEqual(e['event_type'],'infrastructure_outage')
        self.assertEqual(e['tickers_mentioned'],[])
        self.assertIsNone(e['cloud_service_disruption'])
        e=self.event('CrowdStrike reported a Windows update defect. A global IT outage disrupted services.')
        self.assertNotIn('MSFT',e['tickers_mentioned'])
        self.assertIsNone(e['cloud_service_disruption'])

    def test_service_wording(self):
        for text in ('Microsoft Office 365 disruption affected users.',
                     'Azure-backed workloads unavailable.',
                     'Microsoft services disrupted.'):
            with self.subTest(text=text):
                self.assertEqual(self.event(text)['event_type'],'infrastructure_outage')

    def test_historical_13_30(self):
        expected={13:('legal_antitrust','fine'),14:('legal_antitrust','lawsuit'),
                  15:('government_policy','regulation'),16:('legal_antitrust','charge'),
                  17:('infrastructure_outage','outage'),18:('legal_antitrust','ruling'),
                  19:('legal_antitrust','remedy_proposal'),20:('legal_antitrust','complaint'),
                  21:('corporate_transaction','acquisition_terminated'),22:('legal_antitrust','fine'),
                  23:None,24:('legal_antitrust','fine'),25:None,26:None,
                  27:('corporate_action','recall'),28:('supply_chain','production_interruption'),
                  29:('corporate_action','workforce_reduction'),30:('legal_antitrust','regulatory_scrutiny')}
        data=json.loads((ROOT/'data/news/normalized/historical_validation_H13_H30.json').read_text())['articles']
        for a in data:
            with self.subTest(article=a['article_id']):
                e=extract_event(a)
                self.assertEqual((e['event_type'],e['event_subtype']) if e else None,
                                 expected[int(a['article_id'].split('H')[-1])])
                if e:validate_event(e)
