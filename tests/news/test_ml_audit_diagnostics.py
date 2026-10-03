"""Diagnostic fixes only; model specification remains frozen."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.news.ml import model_stability_analysis as stability
from src.news.ml.late_cohort_error_analysis import select_cohort
from src.news.ml.model import build_b2b_subtype_keep_set, add_b2b_grouped_subtype

class AuditDiagnosticsTests(TestCase):
    def test_cohort_uses_dates_not_collection_ids(self):
        rows = pd.DataFrame({'case_id':['H95','H12','H91'],
                             'effective_event_date':['2023-05-15','2024-07-19','2025-01-02'],
                             'threshold':[.03,.03,.03]})
        self.assertEqual(select_cohort(rows,'2024-07-19').case_id.tolist(),['H12','H91'])

    def test_boundaries_keep_same_date_together_and_threshold_fixed(self):
        rows=pd.DataFrame({'effective_event_date':['2024-07-19']*3+['2025-01-01'],
                           'threshold':[.03,.03,.02,.03]})
        self.assertEqual(select_cohort(rows,'2024-07-19','2025-01-01').index.tolist(),[0,1])
        with self.assertRaises(ValueError):select_cohort(rows,'2025-01-01','2024-01-01')

    def test_missing_dates_fail(self):
        with self.assertRaises(ValueError):
            select_cohort(pd.DataFrame({'effective_event_date':[None],'threshold':[.03]}),'2024-01-01')

    def test_structured_metrics_preserve_precision_and_undefined_auc(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            pd.DataFrame({'label_material_3d_3pct':[0,0]}).to_csv(out/'material_reaction_dataset_v1.csv',index=False)
            pd.DataFrame([dict(threshold=.03,model=m,n_predictions=2,
                               log_loss=.123456789,brier_score=.012345678,roc_auc=np.nan)
                          for m in ['B1','B2b']]).to_csv(out/'material_reaction_metrics_v1.csv',index=False)
            result=stability.read_result('sample',out)
            self.assertAlmostEqual(result['b1_log_loss'],.123456789,places=9)
            self.assertTrue(np.isnan(result['b1_auc']))

    def test_runner_uses_cli_isolation_and_never_rewrites_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'input.csv';source.write_text('fixture')
            model=root/'src/news/material_reaction_model.py';model.parent.mkdir(parents=True);model.write_text('frozen sentinel')
            with patch.object(stability,'PROJECT_ROOT',root), patch.object(stability,'seed_price_cache') as seed, patch.object(stability.subprocess,'run') as run, patch.object(stability,'read_result',return_value={}):
                stability.run_model_for_dataset('version','input.csv',root/'runs')
                args=run.call_args.args[0]
                self.assertEqual(args[args.index('--input')+1],str(source))
                self.assertEqual(args[args.index('--output-dir')+1],str(root/'runs/version'))
                seed.assert_called_once_with(source,root/'runs/version')
                self.assertEqual(model.read_text(),'frozen sentinel')
                with self.assertRaises(FileExistsError):stability.run_model_for_dataset('version','input.csv',root/'runs')

    def test_train_only_rare_mapping_ignores_future_frequency(self):
        train=pd.DataFrame({'event_subtype':['common']*3+['rare']*2})
        test=pd.DataFrame({'event_subtype':['rare']*10+['new']*10+['common']})
        keep=build_b2b_subtype_keep_set(train)
        self.assertEqual(keep,{'common'})
        mapped=add_b2b_grouped_subtype(test,keep)
        self.assertTrue(mapped.iloc[:20].event_subtype_grouped.eq('OTHER_RARE').all())
        self.assertEqual(mapped.iloc[-1].event_subtype_grouped,'common')
        self.assertEqual(build_b2b_subtype_keep_set(train),keep)
