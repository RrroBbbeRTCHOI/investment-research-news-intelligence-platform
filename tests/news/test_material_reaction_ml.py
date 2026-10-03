"""Offline ML correctness tests: synthetic prices are tests only, never reported results."""
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from src.news.ml.features import (load_eligible, context_features, build_dataset, load_prices,
    material_labels, target_column, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
from src.news.ml.model import feature_frame, fit_model, predict, coefficients
from src.news.ml.validation import evaluate, expanding_splits

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT/'data/news/market_reaction/historical_market_reaction_H01_H30_v1.csv'


def synthetic_data(n=16):
    dates = pd.date_range('2020-01-01', periods=n, freq='7D')
    df = pd.DataFrame(dict(case_id=[f'E{i}' for i in range(n)], ticker=['AAPL']*n,
                          effective_event_date=dates, t0_session=dates,
                          t3_session=dates+pd.Timedelta(days=3),
                          event_type=['government_policy']*n, event_subtype=['regulation']*n,
                          relationship_type=['direct_mention']*n))
    for j,c in enumerate(NUMERIC_FEATURES):df[c] = np.arange(n)*.01+j*.002
    for t in (.02,.03,.04):df[target_column(t)] = np.arange(n)%2
    df['target'] = df[target_column(.02)]
    return df


class MaterialReactionTests(unittest.TestCase):
    def test_only_explicit_eligible_rows(self):
        df=load_eligible(INPUT)
        self.assertEqual(len(df),23)
        self.assertEqual(df[target_column(.02)].sum(),14)
        self.assertTrue(df.ml_eligible.all())

    def test_rejected_boundaries_excluded(self):
        df=load_eligible(INPUT)
        self.assertFalse(set(df.case_id)&{'H23','H25','H26','H07','H12','H01','H06'})
        self.assertFalse(df.event_engine_status.str.startswith('rejected').any())

    def test_future_rows_dynamic_not_hardcoded(self):
        raw=pd.read_csv(INPUT)
        row=raw.loc[raw.case_id.eq('H03')].copy();row['case_id']='H31'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.csv';pd.concat([raw,row]).to_csv(p,index=False)
            self.assertEqual(len(load_eligible(p)),24)

    def test_invalid_boundary_eligibility_fails_closed(self):
        raw=pd.read_csv(INPUT);raw.loc[raw.case_id.eq('H23'),'ml_eligible']=True
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.csv';raw.to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'Rejected/boundary'):load_eligible(p)

    def test_no_outcomes_or_ticker_in_x(self):
        df=synthetic_data()
        for c in ('stock_return_1d','stock_return_3d','qqq_relative_3d','material_3d_2pct','future_sentiment'):
            df[c]=12345
        for level in ('B1','B2'):
            x=feature_frame(df,level)
            self.assertEqual(list(x),NUMERIC_FEATURES+(CATEGORICAL_FEATURES if level=='B2' else []))
            self.assertNotIn('ticker',x)
            self.assertFalse(any('label' in c or 'target' in c or 'material' in c for c in x))

    def test_pre_event_prices_strictly_before_t0(self):
        dates=pd.bdate_range('2022-01-03',periods=100)
        stock=pd.Series(100*np.exp(np.arange(100)*.001),index=dates)
        qqq=pd.Series(100*np.exp(np.arange(100)*.0005),index=dates)
        first=context_features(stock,qqq,dates[80])
        stock.loc[dates[80]:]=1e10;qqq.loc[dates[80]:]=1e-5
        self.assertEqual(first,context_features(stock,qqq,dates[80]))
        self.assertLess(first['feature_last_session'],dates[80])
        self.assertAlmostEqual(first['pre5_stock_return'],np.exp(.005)-1)
        self.assertAlmostEqual(first['pre20_stock_return'],np.exp(.02)-1)
        self.assertAlmostEqual(first['pre5_qqq_relative'],np.exp(.005)-np.exp(.0025))

    def test_volatility_definition(self):
        dates=pd.bdate_range('2022-01-03',periods=90)
        stock=pd.Series(100*np.cumprod(1+np.sin(np.arange(90))*.01),index=dates)
        out=context_features(stock,stock,dates[80])
        r=stock.iloc[:80].pct_change(fill_method=None)
        self.assertAlmostEqual(out['pre20_vol'],r.tail(20).std(ddof=1)*np.sqrt(252))
        self.assertAlmostEqual(out['pre60_vol'],r.tail(60).std(ddof=1)*np.sqrt(252))

    def test_missing_price_sessions_not_compressed_or_filled(self):
        dates=pd.bdate_range('2022-01-03',periods=90)
        q=pd.Series(np.arange(90)+100.,index=dates);s=q.drop(dates[78])
        out=context_features(s,q,dates[80])
        self.assertTrue(np.isnan(out['pre5_stock_return']))
        self.assertTrue(np.isnan(out['pre20_vol']))

    def test_folds_use_only_past_mature_labels(self):
        data=synthetic_data()
        for train,test in expanding_splits(data):
            self.assertLess(data.loc[train,'effective_event_date'].max(),data.loc[test,'effective_event_date'].min())
            self.assertLess(data.loc[train,'t3_session'].max(),data.loc[test,'t0_session'].min())
            self.assertFalse(set(data.loc[train,'case_id'])&set(data.loc[test,'case_id']))

    def test_same_day_and_same_event_kept_together(self):
        df=synthetic_data()
        df.loc[11,['effective_event_date','t0_session','t3_session']]=df.loc[10,['effective_event_date','t0_session','t3_session']].values
        df.loc[11,'case_id']=df.loc[10,'case_id']
        for train,test in expanding_splits(df):
            if 10 in test:self.assertIn(11,test)
            self.assertFalse(10 in train and 11 in test)

    def test_unmatured_previous_label_excluded(self):
        df=synthetic_data();df.loc[9,'t3_session']=df.loc[12,'t0_session']
        for train,test in expanding_splits(df,min_train=5):
            if 10 in test or 11 in test or 12 in test:self.assertNotIn(9,train)

    def test_b0_is_prior_training_frequency(self):
        df=synthetic_data();preds,_=evaluate(df)
        for row in preds.itertuples():
            train=df[df.case_id.isin(row.train_case_ids.split('|'))]
            self.assertAlmostEqual(row.p_b0,train[target_column(row.threshold)].mean())

    def test_future_labels_cannot_change_earlier_predictions(self):
        df=synthetic_data();p1,_=evaluate(df)
        for t in (.02,.03,.04):df.loc[15,target_column(t)]=1-df.loc[15,target_column(t)]
        p2,_=evaluate(df)
        np.testing.assert_allclose(p1[['p_b0','p_b1','p_b2']],p2[['p_b0','p_b1','p_b2']])

    def test_unknown_categories(self):
        df=synthetic_data();m=fit_model(df.iloc[:10],df.target.iloc[:10],'B2')
        future=df.iloc[[10]].copy();future['event_subtype']='unseen_case'
        self.assertTrue(np.isfinite(predict(m,future,'B2',.5)).all())

    def test_missing_numeric_features(self):
        df=synthetic_data();df.loc[:,NUMERIC_FEATURES]=np.nan
        m=fit_model(df.iloc[:10],df.target.iloc[:10],'B2')
        self.assertTrue(np.isfinite(predict(m,df.iloc[10:],'B2',.5)).all())

    def test_preprocessing_fits_training_only(self):
        df=synthetic_data();df.loc[0,'pre20_vol']=np.nan
        m=fit_model(df.iloc[:10],df.target.iloc[:10],'B1')
        median=m['features'].named_transformers_['numeric']['impute'].statistics_[0]
        self.assertAlmostEqual(median,df.iloc[:10].pre20_vol.median())
        future=df.iloc[10:].copy();future['pre20_vol']=1e10
        predict(m,future,'B1',.5)
        self.assertEqual(median,m['features'].named_transformers_['numeric']['impute'].statistics_[0])

    def test_thresholds_strict_and_signed(self):
        for threshold in (.02,.03,.04):
            np.testing.assert_array_equal(material_labels([threshold,-threshold,threshold+.000001,-threshold-.000001,0],threshold),[0,0,1,1,0])

    def test_inconsistent_source_labels_rejected(self):
        raw=pd.read_csv(INPUT);raw.loc[raw.case_id.eq('H03'),'material_3d_2pct']=0
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.csv';raw.to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'Inconsistent supplied label'):load_eligible(p)

    def test_probabilities_and_required_metrics(self):
        preds,metrics=evaluate(synthetic_data())
        self.assertTrue(((preds[['p_b0','p_b1','p_b2a','p_b2b','p_b2']]>=0)&(preds[['p_b0','p_b1','p_b2a','p_b2b','p_b2']]<=1)).all().all())
        self.assertEqual(len(metrics), 15)
        self.assertEqual(set(zip(metrics.threshold, metrics.model)),
                         {(t, m) for t in (.02, .03, .04)
                          for m in ('B0', 'B1', 'B2a', 'B2b', 'B2')})
        self.assertTrue(metrics[['log_loss','brier_score','roc_auc']].notna().all().all())

    def test_small_and_empty_samples(self):
        for n in (0,1,9):
            df=synthetic_data(n);preds,metrics=evaluate(df)
            self.assertTrue(preds.empty)
            self.assertTrue(metrics.n_predictions.eq(0).all())
            self.assertEqual(len(metrics), 15)
            self.assertEqual(set(zip(metrics.threshold, metrics.model)),
                             {(t, m) for t in (.02, .03, .04)
                              for m in ('B0', 'B1', 'B2a', 'B2b', 'B2')})
        self.assertTrue(coefficients(synthetic_data(0)).empty)

    def test_single_class_training_fallback(self):
        df=synthetic_data()
        for t in (.02,.03,.04):df[target_column(t)]=0
        preds,metrics=evaluate(df)
        self.assertTrue(preds.fit_status.eq('single_class_base_rate_fallback').all())
        self.assertTrue(preds.p_b0.eq(0).all());self.assertTrue(preds.p_b2.eq(0).all())
        self.assertTrue(metrics.roc_auc.isna().all())
        self.assertTrue(np.isfinite(metrics.log_loss).all())

    def test_original_csv_not_mutated(self):
        original=sha256(INPUT.read_bytes()).hexdigest();df=load_eligible(INPUT)
        dates=pd.bdate_range('2022-01-01','2025-12-31');prices={t:pd.Series(np.arange(len(dates))+100.,index=dates) for t in set(df.ticker)|{'QQQ'}}
        built=build_dataset(df,prices)
        self.assertNotIn('target',df)
        self.assertEqual(len(built),len(df))
        self.assertEqual(original,sha256(INPUT.read_bytes()).hexdigest())

    def test_cache_reuse_and_close_download_parameters(self):
        df=synthetic_data(1);dates=pd.bdate_range('2019-09-01','2019-12-31')
        data=pd.DataFrame({'Close':np.arange(len(dates))+100.},index=dates)
        with tempfile.TemporaryDirectory() as d, patch('yfinance.download',return_value=data) as download:
            first,_=load_prices(df,d);self.assertEqual(download.call_count,2)
            for call in download.call_args_list:
                self.assertIs(call.kwargs['auto_adjust'],False)
                self.assertEqual(call.kwargs['end'],'2020-01-01')
            second,_=load_prices(df,d);self.assertEqual(download.call_count,2)
            pd.testing.assert_series_equal(first['AAPL'],second['AAPL'])

    def test_provider_failure_not_silently_imputed(self):
        with tempfile.TemporaryDirectory() as d, patch('yfinance.download',return_value=pd.DataFrame()):
            with self.assertRaisesRegex(RuntimeError,'unavailable'):load_prices(synthetic_data(1),d)
