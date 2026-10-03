import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from src.news.historical_context import load_archive,context_for,THRESHOLDS,MODELS
from src.news.event_extractor import extract_event
from .helpers import article

class HistoricalContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.article=article('Tesla cuts vehicle prices by 10%.',headline='Tesla cuts vehicle prices')
        self.event=extract_event(self.article)
        source=self.root/'data/news/market_reaction/source.csv';source.parent.mkdir(parents=True)
        common=dict(ticker='TSLA',ml_eligible='True',event_engine_status='accepted',event_type=self.event['event_type'],event_subtype=self.event['event_subtype'],relationship_type='direct_mention',event_time_utc='',qqq_relative_3d='.04')
        rows=[dict(common,case_id='EARLY',event_date_reported='2026-09-01',effective_event_date='2026-09-01',t0_session='2026-09-01',t3_session='2026-09-03'),
              dict(common,case_id='CASE',event_date_reported='2026-09-17',effective_event_date='2026-09-17',t0_session='2026-09-17',t3_session='2026-09-21')]
        self.write_csv(source,rows)
        folder=self.root/'data/news/ml';folder.mkdir(parents=True)
        self.manifest=folder/'material_reaction_run_manifest_v1.json';self.manifest.write_text(json.dumps(dict(input_name='source.csv',input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),run_at='2026-09-30T00:00:00Z',min_train=1)))
        self.prediction_path=folder/'material_reaction_sensitivity_predictions_v1.csv'
        preds=[dict(rows[1],threshold=t,target=int(.04>t),prediction_t0='2026-09-17',train_label_end_max='2026-09-03',train_case_ids='EARLY',n_train=1,fold=1,**{f'p_{m.lower()}':.2 for m in MODELS}) for t in THRESHOLDS]
        self.write_csv(self.prediction_path,preds)
        self.mapping=self.root/'map.json';self.mapping.write_text(json.dumps({'article_to_case':{self.article['article_id']:'CASE'}}))

    @staticmethod
    def write_csv(path,rows):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    def get(self):
        return context_for(load_archive(self.root,self.mapping),self.article,self.event,'TSLA')

    def test_valid_context_explicitly_retrospective_all_models_thresholds(self):
        result=self.get();self.assertEqual(result['status'],'retrospective_oos_diagnostic')
        self.assertEqual(len(result['predictions']),15)
        self.assertFalse(result['used_for_relevance']);self.assertFalse(result['used_for_priority'])
        self.assertFalse(result['provenance']['available_at_event_time'])
        self.assertIsNone(result['probability'])
        self.assertIn('Not directional or causal',result['disclosure'])

    def test_no_implicit_case_number_inference(self):
        self.assertEqual(context_for(load_archive(self.root),self.article,self.event,'TSLA')['status'],'unavailable')
        self.mapping.write_text(json.dumps({'article_to_case':{'other':'CASE'}}));self.assertEqual(self.get()['status'],'unavailable')

    def test_wrong_event_ticker_and_date_unavailable(self):
        archive=load_archive(self.root,self.mapping)
        self.assertEqual(context_for(archive,self.article,self.event,'NVDA')['status'],'unavailable')
        self.assertEqual(context_for(archive,self.article,{**self.event,'event_subtype':'recall'},'TSLA')['status'],'unavailable')
        self.assertEqual(context_for(archive,{**self.article,'published_at':'2025-01-01'},self.event,'TSLA')['status'],'unavailable')

    def test_source_hash_failure_is_optional_not_a_relevance_failure(self):
        self.manifest.write_text(self.manifest.read_text().replace('source.csv','missing.csv'))
        self.assertEqual(self.get()['status'],'unavailable')

    def test_corrupt_predictions_never_exposed(self):
        original=self.prediction_path.read_text()
        for key,value in [('p_b2b','nan'),('p_b2b','1.1'),('train_label_end_max','2026-09-17'),('train_case_ids','CASE'),('target','0'),('event_type','other'),('n_train','5')]:
            with self.subTest(key=key):
                self.prediction_path.write_text(original)
                with self.prediction_path.open() as f:rows=list(csv.DictReader(f))
                rows[0][key]=value;self.write_csv(self.prediction_path,rows)
                self.assertEqual(self.get()['status'],'unavailable')

    def test_duplicate_prediction_rows_fail_closed(self):
        with self.prediction_path.open() as f:rows=list(csv.DictReader(f))
        self.write_csv(self.prediction_path,rows+[rows[0]])
        self.assertEqual(self.get()['status'],'unavailable')

    def test_missing_threshold_not_filled_or_selected_for_performance(self):
        with self.prediction_path.open() as f:rows=list(csv.DictReader(f))
        self.write_csv(self.prediction_path,rows[:2])
        self.assertEqual(self.get()['status'],'unavailable')
