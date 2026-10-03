import unittest
from src.news.live_content import classify_live_content, display_type
from src.news.v3_validation import prefilter

class SemanticRoutingTests(unittest.TestCase):
    def test_outlook_threats(self):
        for h in ['Apple, Samsung & Google Face US Import Ban Threat Over Audio Patents','Apple could face US import ban over patent dispute','Google may face antitrust action','Nvidia risks new export restrictions','Microsoft faces possible regulatory probe','Tesla could face production restrictions']:
            with self.subTest(h=h):
                a={'headline':h};self.assertEqual(classify_live_content(a,prefilter(a))['content_type'],'outlook')
    def test_completed_actions_win(self):
        for h in ['US imposes import ban on Apple devices','Regulator orders import ban','ITC blocks imports','ITC orders import ban on Apple devices','US bans Nvidia chip exports','FTC opens investigation into Meta','EU fines Apple','Microsoft reports earnings','Federal Reserve holds rates unchanged','US imposes import ban after Apple had faced months of legal threat','FTC opens probe after Meta faced possible investigation']:
            with self.subTest(h=h):
                a={'headline':h};self.assertEqual(classify_live_content(a,prefilter(a))['content_type'],'event')
    def test_final_display_authority(self):
        self.assertEqual(display_type({'content_type':'event','gate':{'is_event':True}}),'event')
        self.assertEqual(display_type({'content_type':'event','gate':{'is_event':False},'display_type':'event'}),'research')
        self.assertEqual(display_type({'content_type':'outlook','gate':{'is_event':False}}),'outlook')
    def test_form144_not_forced_to_outlook(self):
        a={'headline':'Form 144 APPLE INC For: 27 September By Investing'}
        self.assertNotEqual(classify_live_content(a,{'state':'surface'})['content_type'],'outlook')
        self.assertEqual(display_type({**a,'content_type':'event','gate':{'is_event':False}}),'research')
    def test_threat_alone_insufficient(self):
        a={'headline':'Apple TV show faces possible cancellation'}
        self.assertNotEqual(classify_live_content(a,{'state':'background'})['content_type'],'outlook')
