import tempfile
import unittest
from pathlib import Path
from src.news.channel_generator import generate_channels
from src.news.event_extractor import extract_event
from src.news.exposure_matcher import load_exposure_edges, match_exposures, edge_ineligibility
from .helpers import article, edge, workbook

AT='2026-09-17T09:00:00Z'

class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.event=extract_event(article())
        self.channels=generate_channels(self.event)

    def pairs(self,edges):
        return match_exposures(self.event,self.channels,edges,prediction_time=AT)[0]

    def test_verified_match_without_direct_mention(self):
        p=next(p for p in self.pairs([edge()]) if p['ticker']=='NVDA')
        self.assertTrue(p['matched']); self.assertFalse(p['direct_mention'])
        self.assertGreater(p['relevance_score'],0)
        self.assertIn('source_url',p['matched_edges'][0])

    def test_partial_lower_than_verified(self):
        a=next(p for p in self.pairs([edge()]) if p['matched'])
        b=next(p for p in self.pairs([edge(evidence_status='partial')]) if p['matched'])
        self.assertLess(b['relevance_score'],a['relevance_score'])

    def test_blocked_and_hypothesis_do_not_match(self):
        for status in ('blocked','hypothesis',None,'unverified'):
            with self.subTest(status=status):
                self.assertFalse(any(p['matched'] for p in self.pairs([edge(evidence_status=status)])))

    def test_country_only_incompatible_channel_fails(self):
        self.assertFalse(any(p['matched'] for p in self.pairs([edge(channel_family='digital_advertising')])))

    def test_channel_only_incompatible_country_fails(self):
        self.assertFalse(any(p['matched'] for p in self.pairs([edge(country='Japan')])))

    def test_temporal_and_provenance_rejections(self):
        cases=[({'known_at_utc':'2027-01-01'},'future_known_at'),
               ({'valid_from':'2027-01-01'},'future_valid_from'),
               ({'valid_to':'2026-08-01'},'expired_edge'),
               ({'known_at_utc':None},'missing_known_at_unsuitable_for_history'),
               ({'valid_from':None},'missing_valid_from'),
               ({'known_at_utc':'bad date'},'invalid_timestamp'),
               ({'stage':'planned'},'non_operating_capacity'),
               ({'source_locator':None},'missing_source_provenance'),
               ({'facility_or_route':'Fab X','stage':None},'unverified_operating_stage')]
        for changes,reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(edge_ineligibility(edge(**changes),AT),reason)
                self.assertFalse(any(p['matched'] for p in self.pairs([edge(**changes)])))

    def test_date_only_known_at_conservative(self):
        self.assertEqual(edge_ineligibility(edge(known_at_utc='2026-09-17'),AT),'future_known_at')

    def test_inclusive_validity_bounds(self):
        self.assertIsNone(edge_ineligibility(edge(valid_from=AT,valid_to=AT),AT))

    def test_missing_time_no_fallback_to_today(self):
        self.assertEqual(edge_ineligibility(edge(),None),'missing_prediction_time')

    def test_direct_mention_not_exposure(self):
        self.event['tickers_mentioned']=['AAPL']
        p=next(p for p in self.pairs([]) if p['ticker']=='AAPL')
        self.assertTrue(p['direct_mention']); self.assertFalse(p['matched'])
        self.assertEqual(p['relevance_score'],0.15)

    def test_severity_not_relevance_without_edge(self):
        self.event['severity_score']=1.0
        self.assertTrue(all(p['relevance_score']==0 for p in self.pairs([])))

    def test_score_range_and_duplicate_edges_no_inflation(self):
        self.event['severity_score']=1.0
        self.event['tickers_mentioned']=['NVDA']
        p=self.pairs([edge(),edge(edge_id='second')])
        self.assertTrue(all(0<=r['relevance_score']<=1 for r in p))
        self.assertEqual([r['relevance_score'] for r in p],[r['relevance_score'] for r in self.pairs([edge()])])

    def test_narrow_subchannel_not_assumed(self):
        self.assertFalse(any(p['matched'] for p in self.pairs([edge(channel_subtype='hbm_die_fabrication')])))

    def test_missing_workbook_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            rows,status=load_exposure_edges(Path(td))
            self.assertEqual(rows,[]); self.assertEqual(status['status'],'missing_workbook')

    def test_workbook_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            workbook(Path(td),[edge()])
            rows,status=load_exposure_edges(Path(td))
            self.assertEqual(status['status'],'loaded')
            self.assertEqual(rows[0]['ticker'],'NVDA')
            self.assertTrue(any(p['matched'] for p in self.pairs(rows)))

    def test_corrupt_workbook_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'broken.xlsx'; p.write_bytes(b'not a zip')
            rows,status=load_exposure_edges(Path(td),p)
            self.assertEqual(rows,[]); self.assertEqual(status['status'],'invalid_workbook')

    def test_duplicate_edge_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            workbook(Path(td),[edge(),edge()])
            rows,status=load_exposure_edges(Path(td))
            self.assertEqual(rows,[]); self.assertEqual(status['status'],'invalid_workbook')
