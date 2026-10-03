"""Moat 3 acquisition/normalization, reusing existing providers and bounded caches."""
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
import json
import os
import time
from src.data import historical_financial_data as fmp
from src.data.earnings_quality_inputs import _load_history, fact, number, iso_date
from src.data.market_data import get_company_info, get_price_history
from src.data.reuse import scoped, reuse
from src.services.cache import cached
from src.analysis.financial_statement_bridges import normalize
from src.services.financial_interpretation_service import _history_failure

CONFIG_PATH=Path(__file__).resolve().parents[2]/'data/valuation_assumptions.json'
EXTRA={
 'income':{'interest_expense':'interestExpense'},
 'balance':{'short_debt':'shortTermDebt','long_debt':'longTermDebt',
            'current_lease':'capitalLeaseObligationsCurrent','lease_total':'capitalLeaseObligations',
            'preferred_book':'preferredStock','nci':'minorityInterest',
            'other_operating_assets':'otherOperatingCurrentAssets',
            'accrued_operating':'accruedOperatingLiabilities',
            'other_operating_liabilities':'otherOperatingCurrentLiabilities'},
 'cash':{'net_borrowing':'netDebtIssuance','debt_issued':'debtIssuance','debt_repaid':'debtRepayment'}
}
ENDPOINTS={'income':'income-statement','balance':'balance-sheet-statement','cash':'cash-flow-statement'}


def today():
    return datetime.fromtimestamp(time.time(),timezone.utc).date()


def dated_assumption(record, default_age=62):
    out=deepcopy(record) if isinstance(record,dict) else {}
    stamp=iso_date(out.get('observation_date'));v=number(out.get('value'))
    age=(today()-stamp).days if stamp else None
    valid=stamp is not None and age>=0 and v is not None and all(out.get(k) for k in ('source','version','method'))
    limit=out.get('max_age_days',default_age)
    out.update(age_days=age,stale=not valid or age>limit,value=v if valid and age<=limit else None)
    if out['stale']:out['reason']='Missing, future-dated or expired versioned observation; update the external assumption.'
    return out


def load_assumptions():
    path=Path(os.environ.get('MOAT3_ASSUMPTIONS_FILE',str(CONFIG_PATH)))
    with path.open() as f:config=json.load(f)
    if config.get('horizon')!=5 or config.get('currency')!='USD':raise ValueError('Moat 3 V1 supports the explicit 5Y USD contract only')
    for name in ('erp','terminal_growth','risk_free_fallback','statutory_tax_fallback'):
        if config.get(name) is not None:config[name]=dated_assumption(config[name],365 if name in ('terminal_growth','statutory_tax_fallback') else 62)
    return config


def normalize_valuation_inputs(ticker,datasets):
    periods=normalize(ticker,datasets)
    buckets={p['period']:p['values'] for p in periods}
    for kind,fields in EXTRA.items():
        for row in datasets.get(kind,[]):
            if not isinstance(row,dict) or str(row.get('date') or '') not in buckets:continue
            bucket=buckets[str(row['date'])]
            for key,source_field in fields.items():
                item=fact(ticker,row,source_field,endpoint=ENDPOINTS[kind])
                if row.get('startDate'):
                    start,end=iso_date(row['startDate']),iso_date(row.get('date'))
                    if not start or not end or not 350<=(end-start).days<=380:item.update(availability='unknown',reason='incompatible_duration')
                if key in bucket:item.update(availability='unknown',reason='duplicate_period')
                bucket[key]=item
    for period in periods:
        end=iso_date(period['period'])
        if end and end>today():
            for item in period['values'].values():
                item.update(availability='unknown',reason='future_statement_period')
    return periods


def _risk_free(config):
    try:
        history=get_price_history('^TNX',period='5d')
        if history is not None and 'Close' in history:
            values=history['Close'].dropna()
            if not values.empty:
                rate=number(values.iloc[-1]);stamp=iso_date(values.index[-1])
                if rate is not None and 0<rate<25 and stamp and 0<=(today()-stamp).days<=7:
                    return {'value':rate/100,'source':'Yahoo ^TNX US 10-year nominal Treasury yield index',
                            'observation_date':str(stamp),'retrieved_at':str(today()),'method':'Observed Treasury-yield quote proxy; Close quoted in percent',
                            'version':'TNX-observed-v1','kind':'Proxy','stale':False,'age_days':(today()-stamp).days}
    except Exception:
        pass
    out=deepcopy(config.get('risk_free_fallback') or {})
    out.update(kind='Fallback',confidence='Low Confidence')
    out['stale_market_quote']=True
    out['note']='Live Treasury quote unavailable; use dated configured Treasury reference only within its permitted age.'
    return out


def observed_beta(ticker,info):
    try:
        import pandas as pd
        a,b=get_price_history(ticker,'5y'),get_price_history('SPY','5y')
        if a is not None and b is not None:
            frame=pd.concat([a['Close'].rename('company'),b['Close'].rename('market')],axis=1).dropna()
            if frame.index.tz is not None:frame.index=frame.index.tz_localize(None)
            # Exclude the unfinished current month/week; all returns use common endpoints.
            for freq,minimum,months,method in [('ME',36,60,'5Y monthly total-return proxy vs SPY'),('W-FRI',52,24,'2Y weekly total-return proxy vs SPY')]:
                sampled=frame.resample(freq).last().dropna()
                cutoff=pd.Timestamp(today())
                sampled=sampled[(sampled.index<cutoff)&(sampled.index>=cutoff-pd.DateOffset(months=months))]
                returns=sampled.pct_change(fill_method=None).dropna()
                if len(returns)>=minimum and returns['market'].var()>1e-12:
                    beta=number(returns['company'].cov(returns['market'])/returns['market'].var())
                    if beta is not None:return {'value':beta,'source':'Existing Yahoo adjusted-price history / SPY',
                        'method':method,'window':f'{sampled.index[0].date()} to {sampled.index[-1].date()}',
                        'observation_date':str(sampled.index[-1].date()),'observations':len(returns),'kind':'Calculated',
                        'note':'Common sampled adjusted-price endpoints; SPY is the market proxy, not a universal market portfolio.'}
    except Exception:
        pass
    beta=number(info.get('beta'))
    if beta is not None:return {'value':beta,'source':'Yahoo info.beta','window':'Provider window not supplied',
                               'observation_date':None,'retrieved_at':str(today()),'method':'Provider observed beta proxy',
                               'kind':'Proxy','confidence':'Low Confidence'}
    return {'value':None,'source':None,'window':None,'method':'Unknown','kind':'Insufficient Evidence'}


def historical_valuation(ticker):
    from src.analysis.valuation import get_historical_pe
    try:
        history=get_historical_pe(ticker)
        records=[]
        if history is not None:
            for row in history.head(5).to_dict('records'):
                v=number(row.get('P/E'));d=iso_date(row.get('Date'))
                if v is not None and v>0 and d and d<=today():records.append({'period':str(d),'pe':v,'price':number(row.get('Price')),'eps':number(row.get('EPS'))})
        from statistics import median
        return {'median':median(x['pe'] for x in records) if len(records)>=3 else None,
                'observations':records,'method':'Existing fiscal-date nearest-price / annual diluted-EPS proxy',
                'status':'Proxy' if len(records)>=3 else 'Insufficient History',
                'note':'Up to five annual observations, not daily trailing P/E. Fiscal EPS may not have been public on the matched quote date; not point-in-time investable history. Price adjustment/EPS split basis may differ.'}
    except Exception:
        return {'median':None,'observations':[],'status':'Insufficient History','method':'Existing annual P/E proxy','note':'Historical valuation source unavailable.'}


@scoped
def load_valuation_inputs(ticker):
    def load():
        config=load_assumptions();datasets={};errors=[]
        for kind,loader in [('income',fmp.get_historical_income_statement),('balance',fmp.get_historical_balance_sheet),('cash',fmp.get_historical_cash_flow_statement)]:
            try:datasets[kind]=_load_history(ticker,ENDPOINTS[kind],loader)
            except Exception as e:datasets[kind]=[];errors.append(_history_failure(kind,e))
        try:info=get_company_info(ticker) or {}
        except Exception:info={};errors.append('Market data unavailable')
        timestamp=number(info.get('regularMarketTime'))
        quote_date=str(datetime.fromtimestamp(timestamp,timezone.utc).date()) if timestamp is not None and timestamp>0 else None
        market={k:{'value':number(info.get(field)),'source':f'Yahoo info.{field}',
                   'observation_date':quote_date,'retrieved_at':str(today()),'currency':info.get('currency'),
                   'method':'Provider market observation; field-specific timestamp unavailable' if quote_date is None else 'Provider quote-date proxy; fields may update asynchronously'}
                for k,field in [('price','currentPrice'),('market_cap','marketCap'),('enterprise_value','enterpriseValue'),('pe','trailingPE'),('forward_pe','forwardPE')]}
        beta=observed_beta(ticker,info)
        if beta['value'] is None and config.get('allow_beta_one_fallback'):
            beta.update(value=1.0,kind='Fallback Assumption',confidence='Low Confidence',method='Explicit market-beta fallback')
        risk_free=cached(('moat3-risk-free',config['version']),lambda:_risk_free(config))
        moat1=cached(('eq-diagnostics-v2-final',ticker),lambda:None,acceptable=lambda _:False)
        if moat1 is None:
            bundle=cached(('eq-scoring-v1',ticker),lambda:None,acceptable=lambda _:False)
            if bundle is not None:
                summary=bundle.get('summary',{})
                moat1={'classification':summary.get('Earnings Quality'),'score_raw':summary.get('Earnings Quality Score'),
                       'research_analysis':{},'coverage':'Cached score only; narrative diagnostics not loaded'}
        from src.data.reuse import state
        st=state();moat2=deepcopy(st['values'].get(('financial-interpretation-v1',ticker))) if st else None
        if moat2 is None:
            from src.analysis.financial_statement_diagnostics import interpret
            # Reuse the unchanged Moat 2 producer with already loaded raw data.
            moat2=interpret(ticker,normalize(ticker,datasets),moat1,errors)
        return {'ticker':ticker,'periods':normalize_valuation_inputs(ticker,datasets),'market':market,
                'beta':beta,'risk_free':risk_free,'config':config,'historical_pe':historical_valuation(ticker),
                'moat1':moat1,'moat2':moat2,'errors':errors,'retrieved_at':str(today())}
    return reuse(('moat3-inputs',ticker),load)
