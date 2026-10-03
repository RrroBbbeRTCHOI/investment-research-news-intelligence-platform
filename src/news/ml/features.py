"""Read-only event labels and strictly pre-t0 yfinance Close features."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

NUMERIC_FEATURES = ['pre20_vol', 'pre60_vol', 'pre5_stock_return',
                    'pre5_qqq_relative', 'pre20_stock_return', 'pre20_qqq_relative']
CATEGORICAL_FEATURES = ['event_type', 'event_subtype', 'relationship_type']
THRESHOLDS = (0.02, 0.03, 0.04)
DATE_COLUMNS = ['effective_event_date', 't0_session', 't3_session']


def target_column(threshold):
    return f'label_material_3d_{round(threshold * 100)}pct'


def material_labels(relative_returns, threshold):
    """Strict >, decimal returns (0.02 is two percentage points)."""
    return (np.abs(np.asarray(relative_returns, dtype=float)) > threshold).astype(int)


def load_eligible(path):
    df = pd.read_csv(path)
    required = {'case_id', 'ticker', 'ml_eligible', 'event_engine_status',
                'stock_return_3d', 'qqq_return_3d', 'qqq_relative_3d',
                *DATE_COLUMNS, *CATEGORICAL_FEATURES}
    if missing := required - set(df.columns):
        raise ValueError(f'Missing input columns: {sorted(missing)}')
    eligible = df['ml_eligible'].astype(str).str.strip().str.lower()
    if not eligible.isin(['true', 'false', '1', '0']).all():
        raise ValueError('ml_eligible must explicitly be True/False or 1/0')
    df = df.loc[eligible.isin(['true', '1'])].copy()
    if df['event_engine_status'].fillna('').str.startswith('rejected').any() or df['event_type'].eq('boundary').any():
        raise ValueError('Rejected/boundary row marked ML eligible; correct source eligibility before training')
    if df[['case_id', 'ticker']].isna().any().any() or df.duplicated(['case_id', 'ticker']).any():
        raise ValueError('Missing or duplicate event-company identity')
    for c in DATE_COLUMNS:
        df[c] = pd.to_datetime(df[c], errors='raise').dt.normalize()
        if df[c].isna().any():
            raise ValueError(f'Missing {c}')
    if (df.t3_session < df.t0_session).any() or (df.t0_session < df.effective_event_date).any():
        raise ValueError('Invalid event/label session order')
    relative = pd.to_numeric(df['qqq_relative_3d'], errors='raise')
    if not np.isfinite(relative).all():
        raise ValueError('Non-finite three-day outcome')
    recomputed = pd.to_numeric(df.stock_return_3d) - pd.to_numeric(df.qqq_return_3d)
    if not np.allclose(relative, recomputed, rtol=0, atol=2e-6):
        raise ValueError('QQQ-relative outcome disagrees with stock minus QQQ return')
    # Source CSV is rounded to six decimals: retain its supplied relative-return
    # value for labels, rather than moving a threshold by another rounding step.
    for threshold in THRESHOLDS:
        name = target_column(threshold)
        labels = material_labels(relative, threshold)
        source = name.replace('label_', '')
        if source in df and not np.array_equal(pd.to_numeric(df[source]).to_numpy(), labels):
            raise ValueError(f'Inconsistent supplied label: {source}')
        df[name] = labels
    df['label_qqq_relative_3d'] = relative
    keep = ['case_id', 'ticker', 'event_name', 'event_engine_status', 'ml_eligible',
            'event_date_reported', 'event_time_utc', 'prior_trading_session',
            *DATE_COLUMNS, *CATEGORICAL_FEATURES, 'label_qqq_relative_3d',
            *[target_column(t) for t in THRESHOLDS]]
    df = df[[c for c in keep if c in df]].copy()
    return df.sort_values(['effective_event_date', 'case_id', 'ticker']).reset_index(drop=True)


def clean_close(close):
    if isinstance(close, pd.DataFrame):
        if close.shape[1] != 1:
            raise ValueError('Expected one ticker Close series')
        close = close.iloc[:, 0]
    close = pd.to_numeric(close, errors='coerce').copy()
    dates = pd.DatetimeIndex(pd.to_datetime(close.index))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    close.index = dates.normalize()
    close = close.sort_index()
    if close.index.duplicated().any():
        raise ValueError('Duplicate price dates')
    return close.where(np.isfinite(close) & (close > 0))


def load_prices(rows, cache_dir, refresh=False):
    """One persisted download per ticker/range; no silent provider-failure imputation."""
    if rows.empty:
        return {}, []
    import yfinance as yf
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache / 'yf_metadata'))
    start = (rows.t0_session.min() - pd.Timedelta(days=160)).date().isoformat()
    end = rows.t0_session.max().date().isoformat()  # yfinance end is exclusive
    result, provenance = {}, []
    for ticker in sorted(set(rows.ticker) | {'QQQ'}):
        if not isinstance(ticker, str) or not ticker.isalnum():
            raise ValueError(f'Invalid ticker: {ticker!r}')
        path = cache / f'{ticker}_{start}_{end}_close.csv'
        meta_path = path.with_suffix('.json')
        if refresh or not path.exists() or not meta_path.exists():
            data = yf.download(ticker, start=start, end=end, auto_adjust=False,
                               back_adjust=False, repair=False, progress=False,
                               threads=False, interval='1d', timeout=30)
            if data is None or data.empty or 'Close' not in data:
                raise RuntimeError(f'yfinance Close unavailable for {ticker}; retry when provider is available')
            close = clean_close(data['Close'])
            if close.dropna().empty:
                raise RuntimeError(f'No usable Close values for {ticker}')
            close.rename('Close').to_csv(path, index_label='Date')
            meta = dict(provider='yfinance/Yahoo Finance', ticker=ticker, start=start,
                        end_exclusive=end, auto_adjust=False, back_adjust=False,
                        repair=False, column='Close', downloaded_at=datetime.now(timezone.utc).isoformat(),
                        yfinance_version=yf.__version__, sha256=sha256(path.read_bytes()).hexdigest())
            meta_path.write_text(json.dumps(meta, indent=2) + '\n')
        meta = json.loads(meta_path.read_text())
        if meta['sha256'] != sha256(path.read_bytes()).hexdigest() or meta.get('auto_adjust') is not False:
            raise ValueError(f'Price cache provenance mismatch: {path}')
        close = pd.read_csv(path, index_col='Date', parse_dates=True)['Close']
        result[ticker] = clean_close(close)
        provenance.append(meta)
    return result, provenance


def context_features(stock, qqq, t0):
    anchor = pd.Timestamp(t0).normalize()
    stock, qqq = clean_close(stock), clean_close(qqq)
    # QQQ defines observed US sessions; missing stock values stay missing. No
    # forward-fill and no compression of missing sessions into longer horizons.
    q = qqq.loc[qqq.index < anchor]
    s = stock.reindex(q.index)
    returns = s.pct_change(fill_method=None)
    values = {}
    for n in (20, 60):
        window = returns.tail(n)
        values[f'pre{n}_vol'] = float(window.std(ddof=1) * np.sqrt(252)) if len(window) == n and window.notna().all() else np.nan
    for n in (5, 20):
        sw, qw = s.tail(n + 1), q.tail(n + 1)
        valid_s = len(sw) == n + 1 and sw.notna().all()
        valid_q = len(qw) == n + 1 and qw.notna().all()
        sr = float(sw.iloc[-1] / sw.iloc[0] - 1) if valid_s else np.nan
        qr = float(qw.iloc[-1] / qw.iloc[0] - 1) if valid_q else np.nan
        values[f'pre{n}_stock_return'] = sr
        values[f'pre{n}_qqq_relative'] = sr - qr
    observed = s.dropna()
    values['feature_last_session'] = observed.index.max() if len(observed) else pd.NaT
    values['feature_session_count'] = int(s.notna().sum())
    return values


def build_dataset(rows, prices):
    result = rows.copy(deep=True)
    contexts = [context_features(prices[r.ticker], prices['QQQ'], r.t0_session)
                for r in result.itertuples()]
    for c in NUMERIC_FEATURES + ['feature_last_session', 'feature_session_count']:
        result[c] = [x[c] for x in contexts]
    result['target'] = result[target_column(0.02)]
    return result
