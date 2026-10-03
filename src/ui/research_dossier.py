"""Presentation aggregation only: all analytical work stays in existing services."""
import logging
from src.data.reuse import scoped
from src.services.cache import cached
from src.services import company_service, rating_service, historical_trends_service, sec_filing_service
from src.services.historical_roe_service import get_historical_roe
from src.services.analyst_summary_service import get_analyst_summary
from src.services.financial_interpretation_service import build_financial_interpretation
from src.services.valuation_interpretation_service import build_valuation_interpretation
from src.services.earnings_quality_service import build_earnings_quality, expose_scores
from src.ui.adapters import adapt_company, adapt_recommendation, get_empty_recommendation_context
from src.ui.research_context import DEFAULT_PEERS, adapt_earnings_quality_diagnostics
from src.ui.formatters import format_percent, format_multiple, format_price, format_score
from src.analysis.company_metrics import safe_float

SECTIONS = [('overview','Overview'), ('financials','Financials'), ('valuation','Valuation'),
            ('historical-trends','Historical Trends'), ('earnings-quality','Earnings Quality'),
            ('financial-health','Financial Health'), ('sec-filings','SEC Filings'), ('relevant-events','Events')]

def compact(value, kind='money', currency='USD'):
    value = safe_float(value)
    if value is None: return 'Unavailable'
    if kind == 'percent': return format_percent(value)
    if kind == 'pp':
        points = round(value * 100, 1)
        return ('0.0' if points == 0 else f'{points:+.1f}') + ' pp'
    if kind == 'multiple': return format_multiple(value, 2)
    if kind == 'price': return format_price(value) if currency == 'USD' else f'{currency} {value:,.2f}'
    prefix = '$' if currency == 'USD' else (currency + ' ' if currency else '')
    for scale, suffix in ((1e12,'T'),(1e9,'B'),(1e6,'M')):
        if abs(value) >= scale: return f'{prefix}{value/scale:,.2f}{suffix}'
    return f'{prefix}{value:,.2f}'

def _statements(fi, history):
    if not fi: return []
    currency = fi['period'].get('currency') or ''
    modes = []
    specs = [('income','Income Statement','income_statement',['revenue','gross_profit','operating_income','net_income'],('revenue','net_income')),
             ('cash','Cash Flow','cash_flow',['ocf','capex','fcf'],('ocf','fcf')),
             ('balance','Balance Sheet','balance_sheet',['cash','assets','equity','debt'],('assets','equity'))]
    for key,label,source,names,pair in specs:
        rows=[]
        for name in names:
            metric=fi[source]['metrics'][name]
            rows.append({'key':name,'label':{'ocf':'Operating Cash Flow','fcf':'Free Cash Flow','assets':'Total Assets','debt':'Total Debt'}.get(name,name.replace('_',' ').title()),
                         'current':compact(metric['current'],currency=currency),'prior':compact(metric['prior'],currency=currency),
                         'change':compact(metric['change'],currency=currency), 'raw':metric})
        ratios = ([(name.replace('_',' ').title()+' Margin', item, 'percent') for name,item in fi['income_statement']['margin_analysis'].items() if name in ('gross_profit','operating_income','net_income')]
                  if key=='income' else [('FCF Margin',fi['cash_flow']['fcf_margin'],'percent')] if key=='cash'
                  else [('Debt / Equity',fi['balance_sheet']['liquidity']['debt_equity'],'multiple'),('Net Cash (Cash − Debt)',fi['balance_sheet']['liquidity']['net_cash'],'money')])
        for title,item,kind in ratios:
            rows.append({'key':title,'label':title,'current':compact(item.get('current'),kind,currency),'prior':compact(item.get('prior'),kind,currency),'change':compact(item.get('change'),'pp' if kind == 'percent' else kind,currency),'raw':item})
        if key == 'income':
            for field, title, kind in [('revenue_growth', 'Revenue Growth', 'percent'), ('eps', 'EPS', 'price')]:
                observations = history.get('revenue_growth' if field == 'revenue_growth' else 'eps_growth', [])
                raw_values = {side: next((r.get(field) for r in observations if str(r.get('year')) == str(fi['period'].get(side, ''))[:4]), None) for side in ('current', 'prior')}
                raw_values['change'] = (raw_values['current'] - raw_values['prior']) if all(safe_float(raw_values[side]) is not None for side in ('current','prior')) else None
                rows.append({'key':field, 'label':title, 'raw':raw_values,
                             'current':compact(raw_values['current'], kind, currency),
                             'prior':compact(raw_values['prior'], kind, currency),
                             'change':compact(raw_values['change'], 'pp' if field == 'revenue_growth' else 'price', currency)})
        higher_is_better={'revenue','gross_profit','operating_income','net_income','ocf','fcf','cash','equity','revenue_growth','eps',
                     'Gross Profit Margin','Operating Income Margin','Net Income Margin',
                     'FCF Margin','Net Cash (Cash − Debt)'}
        lower_is_better={'debt','Debt / Equity'}
        for row in rows:
            change=safe_float(row['raw'].get('change')) if isinstance(row.get('raw'),dict) else None
            if change is None or change == 0: row['direction']='neutral'
            elif row['key'] in higher_is_better: row['direction']='positive' if change > 0 else 'negative'
            elif row['key'] in lower_is_better: row['direction']='positive' if change < 0 else 'negative'
            else: row['direction']='neutral'
        series=[]
        for name in pair:
            metric=fi[source]['metrics'][name]
            history=fi['trend_context'].get(name,{}).get('history') or [{'period':fi['period']['prior'],'value':metric['prior']},{'period':fi['period']['current'],'value':metric['current']}]
            series.append({'label':name.replace('_',' ').title(),'points':sorted(history,key=lambda x:x['period'] or '')})
        modes.append({'key':key,'label':label,'rows':rows,'series':series})
    return modes

def _build(ticker):
    errors={}
    def guarded(name, loader, fallback):
        try: return loader()
        except Exception:
            logging.getLogger(__name__).warning('Dossier section unavailable: %s/%s', ticker, name)
            errors[name]='Data temporarily unavailable.'
            return fallback
    peers=DEFAULT_PEERS.get(ticker,[])
    empty={key:None for key in ('price_raw','market_cap_raw','revenue_growth_raw','roe_raw','roic_raw','operating_margin_raw','fcf_margin_raw','debt_to_equity_raw','pe_raw','forward_pe_raw')}
    raw=guarded('overview',lambda:company_service.get_company_data(ticker),dict(empty,ticker=ticker,company_name=ticker,exchange='Unavailable'))
    company=adapt_company(raw)
    report=guarded('rating',lambda:rating_service.get_rating_report(ticker,peers),{})
    company.update(adapt_recommendation(report) if report else get_empty_recommendation_context())
    fi=guarded('financials',lambda:build_financial_interpretation(ticker),None)
    valuation=guarded('valuation',lambda:build_valuation_interpretation(ticker,raw),None)
    from src.analysis.valuation import calculate_peer_median
    peer_pe=guarded('peer-valuation',lambda:calculate_peer_median(peers, "P/E"),None)
    history=guarded('historical-trends',lambda:historical_trends_service.build_historical_trends(ticker,peers),{})
    eq=guarded('earnings-quality',lambda:build_earnings_quality(ticker),None)
    sec=guarded('sec-filings',lambda:sec_filing_service.build_sec_filing(ticker,peers),{})
    quality=adapt_earnings_quality_diagnostics(eq if eq else expose_scores({}))
    financial_history = dict(history.get('financial_history', {}))
    financial_history['roe'] = guarded('historical-roe', lambda:get_historical_roe(ticker), [])
    financial_history['roic'] = [{'year':row['period'], 'roic':row['value']} for row in
        quality.get('research_analysis', {}).get('roic_trend', {}).get('history', [])][::-1]
    analyst_summary = get_analyst_summary(ticker, fi, eq or {}) if fi else None
    filings = [dict(filing, evidence=[item for item in quality.get('research_analysis', {}).get('evidence', [])
               if item.get('accession') and item.get('accession') == filing.get('accession_number')])
               for filing in sec.get('sec_filings', [])]
    # Present the production hierarchy with existing score functions only.
    from src.analysis.rating import (calculate_growth_score, calculate_financial_health_score,
        calculate_six_month_momentum, score_momentum, calculate_annualised_volatility,
        score_risk_from_volatility, score_valuation_expected_return)
    growth=guarded('growth-score',lambda:calculate_growth_score(ticker),None)
    health=guarded('health-score',lambda:calculate_financial_health_score(ticker),None)
    momentum=guarded('momentum-score',lambda:score_momentum(calculate_six_month_momentum(ticker)),None)
    risk=guarded('risk-score',lambda:score_risk_from_volatility(calculate_annualised_volatility(ticker)),None)
    profiles=[('Fundamental',company.get('fundamental_score_raw')),
              ('Valuation',score_valuation_expected_return(company.get('expected_return_raw'))),
              ('Momentum',momentum)]
    methodology=[('Growth',growth,None),('Earnings Quality',quality['score_raw'],None),
                 ('Financial Health',health,None),('Risk adjustment',risk,'Small volatility penalty'),
                 ('Profitability',None,'Not separately scored')]
    company.update(financial_interpretation=fi,valuation_interpretation=valuation,earnings_quality_diagnostics=quality,
                   historical_trends={'financials':financial_history,'market_relative_performance':history.get('market_history',{})},
                   sec_filings=sec.get('sec_filings',[]),sec_error=sec.get('sec_error'))
    valuation_detail=report.get('Valuation Detail',{}) if isinstance(report,dict) else {}
    dcf_base=safe_float(valuation_detail.get('dcf_base'))
    spectrum=[]
    values=[company.get(k) for k in ('fair_value_low_raw','fair_value_raw','fair_value_high_raw','price_raw')]
    position_values=values+([dcf_base] if dcf_base is not None else [])
    if all(safe_float(v) is not None for v in values) and max(position_values)>min(position_values):
        minimum,maximum=min(position_values),max(position_values)
        markers=list(zip(('Low','Composite fair value','High','Current price'),values))
        if dcf_base is not None: markers.insert(2,('Base DCF',dcf_base))
        for label,value in markers:
            spectrum.append({'label':label,'value':format_price(value),'raw':value,'position':8+84*(value-minimum)/(maximum-minimum)})
    debt_fact=((fi or {}).get('balance_sheet',{}).get('metrics',{}).get('debt',{}).get('current_fact') or {})
    return {'ticker':ticker,'company':company,'rating':{
                'profiles':[{'label':label,'raw':value,'display':format_score(value)} for label,value in profiles],
                'methodology':[{'label':label,'raw':value,'display':format_score(value) if value is not None else note,
                                'note':note} for label,value,note in methodology]},
            'financials':{'interpretation':fi,'modes':guarded('financial-presentation', lambda: _statements(fi, financial_history), []),
                          'analyst_summary':analyst_summary},'valuation':{'interpretation':valuation,'spectrum':spectrum,'peer_median_pe':peer_pe},
            'historical_trends':company['historical_trends'],'earnings_quality':quality,'financial_health':fi,
            'financial_health_meta':{'debt':{'source':debt_fact.get('source') or 'FMP',
                'field':debt_fact.get('source_field') or 'totalDebt',
                'definition':'Provider-normalized total debt may include debt-like liabilities beyond SEC term debt.',
                'reconciliation':'No like-for-like SEC debt reconciliation is available in the current dossier.'}},
            'sec_filings':filings,'relevant_events':{'ticker':ticker,'endpoint':'/api/news/intelligence'},
            'errors':errors,'sections':SECTIONS}

@scoped
def build_research_dossier_context(ticker):
    ticker=ticker.upper().strip()
    # Shared 300s cache and provider scope coalesce repeat loads across section URLs.
    return cached(('research-dossier-revenue-resilience-v1.4',ticker),lambda:_build(ticker),acceptable=lambda d:not d['errors'])
