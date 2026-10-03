import json
import tempfile
import unittest
from pathlib import Path
from src.news.pipeline import run_pipeline
from .helpers import article, edge, normalized, workbook

class PipelineTests(unittest.TestCase):
    def test_zero_events(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article('A guide to fruit nutrition.')])
            result=run_pipeline(root)
            self.assertEqual((result['accepted'],result['rejected'],result['company_matches']),(0,1,0))
            self.assertEqual(json.loads((root/'data/news/events/events_v1.json').read_text())['events'],[])

    def test_empty_articles(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[])
            self.assertEqual(run_pipeline(root)['articles'],0)

    def test_missing_workbook_still_emits_events(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=normalized(root,[article()]); original=p.read_bytes()
            result=run_pipeline(root)
            self.assertEqual(result['accepted'],1); self.assertEqual(result['company_matches'],0)
            self.assertEqual(result['pairs'],7)
            self.assertEqual(result['exposure_knowledge']['status'],'missing_workbook')
            self.assertEqual(p.read_bytes(),original)

    def test_real_loader_to_match_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article()]); workbook(root,[edge()])
            result=run_pipeline(root)
            self.assertEqual(result['company_matches'],1)
            data=json.loads((root/'data/news/matches/event_company_matches_v1.json').read_text())
            self.assertEqual([m['ticker'] for m in data['matches'] if m['matched']],['NVDA'])

    def test_prediction_cannot_precede_ingestion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article()])
            with self.assertRaisesRegex(ValueError,'availability'):
                run_pipeline(root,prediction_time='2026-09-17T08:30:00Z')

    def test_missing_observation_times_no_knowledge_match(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article(published_at=None,fetched_at=None)]); workbook(root,[edge()])
            self.assertEqual(run_pipeline(root)['company_matches'],0)

    def test_publication_alone_not_full_text_availability(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article(fetched_at=None)]); workbook(root,[edge()])
            self.assertEqual(run_pipeline(root)['company_matches'],0)

    def test_duplicate_articles_rejected_not_double_counted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); normalized(root,[article(),article()])
            with self.assertRaisesRegex(ValueError,'unique'):
                run_pipeline(root)
