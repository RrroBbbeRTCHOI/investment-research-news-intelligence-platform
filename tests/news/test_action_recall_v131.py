"""Confirmed regulatory/corporate actions; no fixture-ID production rules."""
import json
from pathlib import Path
import unittest
from src.news.event_extractor import extract_event
from src.news.channel_generator import generate_channels
from src.news.schemas import validate_event
from .helpers import article

ROOT=Path(__file__).resolve().parents[2]

class ActionRecallTests(unittest.TestCase):
    def event(self,text):
        return extract_event(article(text,headline=text))

    def check(self,text,kind,subtype):
        e=self.event(text)
        self.assertIsNotNone(e,text)
        self.assertEqual((e['event_type'],e['event_subtype']),(kind,subtype))
        validate_event(e)
        return e

    def test_01_dma_probe(self):
        self.check('European Commission opens formal DMA investigation into Apple','legal_antitrust','investigation')

    def test_02_ftc_inquiry(self):
        self.check('FTC launches Section 6(b) inquiry into Microsoft AI partnership','legal_antitrust','investigation')

    def test_03_statement_objections(self):
        self.check('European Commission issues statement of objections to Google','legal_antitrust','charge')

    def test_04_designation(self):
        self.check('Apple iPadOS designated gatekeeper under DMA','government_policy','regulation')

    def test_05_fine(self):
        self.check('Meta fined by competition authority','legal_antitrust','fine')

    def test_06_settlement(self):
        self.check('Meta agrees to settle privacy lawsuit for $1.4 billion','legal_antitrust','settlement')

    def test_07_layoffs(self):
        self.check('AWS lays off several hundred employees','corporate_action','workforce_reduction')

    def test_08_prices(self):
        e=self.check('Tesla cuts vehicle prices by 10%','corporate_action','pricing_change')
        self.assertIs(e['price_change_explicit'],True)
        self.assertIsNone(e['production_disruption'])

    def test_09_export_license(self):
        e=self.check('US requires export license for Nvidia H20 sales to China','trade_export_control','export_controls')
        self.assertIs(e['export_restriction'],True)
        self.assertIn('regulatory_export',{c['channel_family'] for c in generate_channels(e)['candidate_channels']})

    def test_10_yield_problem(self):
        self.check('Nvidia design flaw caused low yields and shipment delays','supply_chain','production_constraint')

    def test_11_recovery_preserves_event(self):
        e=extract_event(article('Nvidia said a design flaw caused low production yields and delayed shipments. The issue was fixed.',
                                headline='Nvidia says yield issue has been fixed'))
        self.assertEqual(e['event_subtype'],'production_constraint')
        self.assertIn('caused low production yields',e['event_summary'])
        self.assertIs(e['logistics_disruption'],True)

    def test_12_possible_investigation(self):
        self.assertIsNone(self.event('Regulators may investigate Apple'))

    def test_13_possible_pricing(self):
        self.assertIsNone(self.event('Tesla may cut prices next month'))

    def test_14_possible_layoffs(self):
        self.assertIsNone(self.event('Amazon may cut jobs'))

    def test_15_no_subpoena(self):
        self.assertIsNone(self.event('Nvidia has not received a subpoena'))

    def test_negated_actions(self):
        for text in ('FTC did not launch a Section 6(b) inquiry.',
                     'Apple was not designated gatekeeper under DMA.',
                     'The European Commission has not issued a statement of objections.',
                     'Meta did not agree to settle the lawsuit.',
                     'AWS has not eliminated several hundred roles.',
                     'US does not require export licenses for Nvidia sales.',
                     'Tesla did not cut vehicle prices.',
                     'Nvidia design flaw did not cause low yields.',
                     'Nvidia says yield issue has not been fixed.'):
            with self.subTest(text=text):self.assertIsNone(self.event(text))

    def test_commentary_and_rumor(self):
        for text in ('Regulators are considering whether to investigate Apple.',
                     'Analysts expect FTC to launch an inquiry.',
                     'Rumors say AWS laid off several hundred staff.',
                     'Analysts expect Tesla cuts vehicle prices.',
                     'Tesla is considering layoffs.',
                     'Tesla hiring slowdown continues.',
                     'Analysts cut Tesla price targets.',
                     'Tesla share prices fell.',
                     'Tesla raises stock prices.',
                     'Nvidia production is challenging.',
                     'FTC formal inquiry may occur next month.'):
            with self.subTest(text=text):self.assertIsNone(self.event(text))

    def test_generic_variants(self):
        for text,kind,subtype in (
            ('Competition authority opened a formal inquiry into Apple.','legal_antitrust','investigation'),
            ('FTC issued compulsory information requests to Amazon.','legal_antitrust','investigation'),
            ('The competition investigation was opened by the FTC.','legal_antitrust','investigation'),
            ('Competition Board imposed fines on Meta.','legal_antitrust','fine'),
            ('A penalty was imposed on Meta by the Competition Board.','legal_antitrust','fine'),
            ('Meta agreed to pay $1.4 billion to settle a Texas lawsuit.','legal_antitrust','settlement'),
            ('A regulatory settlement was announced by the FTC.','legal_antitrust','settlement'),
            ('Amazon eliminated several hundred roles.','corporate_action','workforce_reduction'),
            ('Microsoft reduced headcount.','corporate_action','workforce_reduction'),
            ('Meta cut staff.','corporate_action','workforce_reduction'),
            ('Microsoft raised subscription prices.','corporate_action','pricing_change'),
            ('Apple implemented a price increase.','corporate_action','pricing_change'),
            ('Amazon discounted products.','corporate_action','pricing_change'),
            ('US government imposed an indefinite licensing requirement on chip exports.','trade_export_control','export_controls'),
            ('Nvidia chip sales require an export license.','trade_export_control','export_controls'),
            ('Nvidia exports were restricted.','trade_export_control','export_controls'),
            ('Nvidia production yields fell.','supply_chain','production_constraint'),
            ('Nvidia manufacturing issue delayed shipments.','supply_chain','production_constraint')):
            with self.subTest(text=text):self.check(text,kind,subtype)

    def test_investigation_finding_not_court_ruling(self):
        e=self.check("The Competition Commission of India's investigations unit found in a confidential report that Apple exploited its position.",'legal_antitrust','investigation_finding')
        self.assertIsNone(e['severity_score'])

    def test_actual_action_with_uncertain_consequence(self):
        e=self.event('European Commission opened a formal non-compliance investigation into Apple which could lead to penalties.')
        self.assertEqual(e['event_subtype'],'investigation')
        e=self.event('The U.S. government required licenses for exports of Nvidia H20 chips, with the requirement expected to remain indefinitely.')
        self.assertIs(e['export_restriction'],True)

    def test_existing_boundaries(self):
        expected={'historical_H07','historical_H12','historical_H23','historical_H25','historical_H26'}
        for f in (ROOT/'data/news/normalized').glob('historical_validation*.json'):
            for a in json.loads(f.read_text()).get('articles',[]):
                if a['article_id'] in expected:
                    with self.subTest(article=a['article_id']):self.assertIsNone(extract_event(a))

    def test_historical_31_60(self):
        data=json.loads((ROOT/'data/news/normalized/historical_validation_H31_H60.json').read_text())['articles']
        for a in data:
            with self.subTest(article=a['article_id']):
                e=extract_event(a)
                if a['article_id'] in ('historical_H38','historical_H56'):
                    self.assertIsNone(e)
                else:
                    self.assertIsNotNone(e)
                    validate_event(e)
                if a['article_id']=='historical_H57':
                    self.assertEqual(e['event_subtype'],'production_constraint')
                    self.assertIn('fixed',e['event_summary'])
                if a['article_id']=='historical_H58':self.assertIs(e['export_restriction'],True)
