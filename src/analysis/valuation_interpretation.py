"""Deterministic expectations narrative, with exact numerical gaps, not ratings."""
from src.analysis.valuation_cash_flows import build_cash_flows, borrowed_debt, result
from src.analysis.cost_of_capital import calculate_cost_of_equity,calculate_cost_of_debt,calculate_wacc
from src.analysis.reverse_dcf import solve_implied_fcff_growth,solve_implied_fcfe_growth,build_sensitivity_matrix
from src.analysis.financial_statement_bridges import value
from src.data.earnings_quality_inputs import comparable,iso_date,number


def historical_growth(periods,key,cash_history=None):
    observations=[]
    for i,p in enumerate(periods):
        v=(cash_history[i].get(key) if cash_history is not None else value(p['values'].get(key)))
        observations.append({'period':p['period'],'value':v})
    all_observations=observations
    usable=[]
    for observation in all_observations:
        if observation['value'] is None or observation['value']<=0:break
        usable.append(observation)
    observations=usable
    periods=periods[:len(observations)]
    out={'value':None,'observations':all_observations,'used_observations':observations,
         'method':'Longest recent contiguous positive annual-window CAGR (at least three observations)',
         'status':'Insufficient History'}
    if len(observations)<3:return out
    anchor='operating_income' if cash_history is not None else key
    if not all(comparable(a['values'].get(anchor),b['values'].get(anchor)) for a,b in zip(periods,periods[1:])):return out
    years=len(observations)-1
    out.update(value=(observations[0]['value']/observations[-1]['value'])**(1/years)-1,
               status='Calculated' if cash_history is None else 'Proxy',years=years,
               current_period=observations[0]['period'],prior_period=observations[-1]['period'])
    return out


def consistency(ff,fe,gap_pp):
    if ff['growth'] is None or fe['growth'] is None:
        return {'status':'Cross-check unavailable','gap_pp':None,'note':'Missing FCFE does not disable FCFF.'}
    gap=(ff['growth']-fe['growth'])*100
    return {'status':'FCFF / FCFE Reconciliation Required' if abs(gap)>=gap_pp else 'Within configured comparison band',
            'gap_pp':gap,'note':f'{gap_pp:g} pp is a platform review convention, not a valuation verdict. Models are never averaged; financing, EV, NWC and discount-rate assumptions may differ.'}


def build_interpretation(inputs,basic=None):
    periods=inputs['periods'];config=inputs['config'];market=inputs['market'];basic=basic or {}
    c=periods[0]['values'] if periods else {};p=periods[1]['values'] if len(periods)>1 else {}
    moat1=inputs.get('moat1') or {};moat2=inputs.get('moat2') or {}
    evidence=(moat1.get('research_analysis') or {}).get('evidence',[])
    cash=build_cash_flows(periods,config,evidence);current=cash['current'] or {}
    debt=borrowed_debt(c);tax=cash['tax'];rf=inputs['risk_free'];beta=inputs['beta'];erp=config.get('erp') or {};tg=config.get('terminal_growth') or {}
    currency_ok=all(market[k].get('currency')=='USD' for k in ('market_cap','enterprise_value')) and bool(c) and all(f.get('currency')=='USD' for f in c.values() if f.get('availability')=='available')
    re=calculate_cost_of_equity(rf.get('value'),beta.get('value'),erp.get('value'))
    rd=calculate_cost_of_debt(c,p,inputs.get('debt_yield'))
    cap=market['market_cap']['value'] if currency_ok else None
    preferred=value(c.get('preferred_book'))
    wacc=calculate_wacc(cap,debt['value'],re,rd['value'],tax['value'],preferred=preferred)
    ev_value=market['enterprise_value']['value'] if currency_ok else None
    if ev_value is not None and ev_value<=0:ev_value=None
    ev={'value':ev_value,'method':'Provider market-EV proxy','confidence':'Proxy',
        'source':market['enterprise_value'],'market_cap':market['market_cap'],'debt':debt,
        'cash':c.get('cash'),'short_investments':c.get('short_investments'),
        'preferred':c.get('preferred_book'),'nci':c.get('nci'),
        'cash_treatment':'No independent cash deduction: provider EV cash/excess-cash treatment is not fully disclosed.',
        'investments_treatment':'No independent investment deduction: operating/non-operating classification is unavailable.',
        'other_non_operating_assets':'Unknown; not separately deducted',
        'residual_adjustment':ev_value-cap-debt['value'] if all(v is not None for v in (ev_value,cap,debt['value'])) else None,
        'note':'Residual = provider EV - market cap - book borrowing debt; it is NOT measured excess cash. Provider EV may use different debt/lease, cash, preferred or NCI definitions. This limits FCFF inference.'}
    ff=solve_implied_fcff_growth(ev_value,current.get('fcff'),wacc['value'],tg.get('value'),config['solver_growth_bounds'])
    fe=solve_implied_fcfe_growth(cap,current.get('fcfe'),re,tg.get('value'),config['solver_growth_bounds'])
    if preferred is not None and preferred>0:
        fe=solve_implied_fcfe_growth(cap,None,re,tg.get('value'),config['solver_growth_bounds'])
        fe['reason']='Preferred capital is present; common-equity income allocation is not supported.'
    for model in (ff,fe):
        model['confidence']='Proxy / assumption-dependent' if model['status']=='converged' else 'Insufficient Evidence'
        if beta.get('kind')=='Fallback Assumption' or rf.get('kind')=='Fallback' or tax['confidence']=='Fallback':model['confidence']='Low Confidence' if model['status']=='converged' else 'Insufficient Evidence'
    matrix=build_sensitivity_matrix(ev_value,current.get('fcff'),wacc['value'],tg.get('value'),config)
    equity_matrix=build_sensitivity_matrix(cap,current.get('fcfe'),re,tg.get('value'),config,'FCFE')
    historical=inputs['historical_pe'];pe=market['pe']['value'];median=historical.get('median')
    premium=pe/median-1 if pe is not None and pe>0 and median is not None and median>0 else None
    reported=value(c.get('fcf'))
    snapshot={**market,'historical_median_pe':median,'historical_premium':premium,
              'reported_fcf_yield':reported/cap if reported is not None and cap is not None and cap>0 else None,
              'fcf_yield_method':'Latest annual provider Reported FCF / current market cap; not FCFF yield',
              'reported_fcf_period':periods[0]['period'] if periods else None}
    history={k:historical_growth(periods,k,cash['history'] if k in ('fcff','fcfe') else None)
             for k in ('fcff','fcfe','fcf','revenue','operating_income')}
    gaps=[]
    for k,v in history.items():
        gaps.append({'comparison':k+' CAGR','observed':v['value'],'gap_pp':(ff['growth']-v['value'])*100 if ff['growth'] is not None and v['value'] is not None else None,
                     'note':v['method']+'; '+v['status'],'history':v})
    for k in ('revenue','operating_income'):
        metric=((moat2.get('income_statement') or {}).get('metrics') or {}).get(k,{})
        growth=metric.get('growth_pct');observed=growth/100 if growth is not None else None
        gaps.append({'comparison':'Latest '+k+' growth','observed':observed,'gap_pp':(ff['growth']-observed)*100 if ff['growth'] is not None and observed is not None else None,
                     'note':'Read from unchanged Moat 2 output; flow/period differs from forward 5Y FCFF.'})
    priced=(f"Under the stated assumptions, the current market enterprise value implies approximately {ff['growth']:.1%} annual FCFF growth over the next five years."
            if ff['growth'] is not None else 'Market-implied FCFF growth is unavailable because the required inputs or bounded solution are not supported.')
    available_gaps=[r for r in gaps if r['gap_pp'] is not None]
    demanding=max(available_gaps,key=lambda r:r['gap_pp']) if available_gaps else None
    demanding_text=(f"The largest displayed gap is {demanding['gap_pp']:+.1f} pp versus {demanding['comparison']}. This is a historical comparison, not a forecast."
                    if demanding else 'Unknown: comparable implied and historical growth are required.')
    check=consistency(ff,fe,config['reconciliation_gap_pp'])
    limits=list(inputs.get('errors',[]))+[
        'Legacy valuation and Moat 3 use different cash-flow/discount/EV definitions. Neither silently replaces the other.',
        'Constant five-year growth and Gordon terminal growth are conditional model assumptions; implied growth is not a market forecast.',
        'Reported FCF, FCFF and FCFE are distinct. FCFF uses WACC; FCFE uses cost of equity.',
        'Balance-sheet operating NWC is an arithmetic proxy and may include acquisitions/FX; no cash-flow causation is inferred.',
        'Debt is book short/long borrowing, excluding separately identified leases; the provider EV may use a different lease scope.',
        'Historical accounting debt cost is not current marginal borrowing yield. Preferred/NCI and non-operating assets may be incompletely captured.',
        'Provider EV is a disclosed proxy: no unsupported assertion that all cash is excess or all investments are non-operating.',
        'Historical P/E is a fiscal-date price/annual-EPS proxy, not a daily point-in-time trailing-P/E series.',
        'Cash flows may be nonpositive; the single-growth V1 model declines to solve such bases. No turnaround forecast is invented.',
        'Finite five-year financial history may be insufficient for historical normalized FCFF/FCFE CAGR.',
        'Taxes use validated accounting observations; absence of cached Moat 1 evidence does not prove absence of unusual tax items.'
    ]
    if not currency_ok:limits.append('Market/statement currency is not explicitly compatible with the USD assumption set; EV/equity targets are unavailable.')
    for name,obj in [('Risk-free rate',rf),('ERP',erp),('Terminal growth',tg)]:
        if obj.get('value') is None:limits.append(name+': missing or expired dated assumption.')
    return {'ticker':inputs['ticker'],'snapshot':snapshot,'historical_valuation':{**historical,'premium':premium},
            'cash_flows':cash,'cost_of_capital':{'risk_free':rf,'beta':beta,'erp':erp,'cost_of_equity':re,'cost_of_debt':rd,'debt':debt,'tax':tax,'wacc':wacc},
            'enterprise_value':ev,'primary':ff,'cross_check':fe,'consistency':check,
            'expectation_gaps':gaps,'sensitivity':matrix,'equity_sensitivity':equity_matrix,
            'fundamentals':{'legacy_cards':{k:basic.get(k) for k in ('revenue_growth_raw','operating_margin_raw','fcf_margin_raw','roic_raw')},
                            'moat1_quality':moat1.get('classification'),'moat1_score':moat1.get('score_raw'),
                            'moat2_interpretation':moat2.get('analyst_interpretation'),
                            'moat2_margins':(moat2.get('income_statement') or {}).get('margin_analysis'),
                            'note':'Read existing module outputs. Premium or strong fundamentals alone do not establish valuation support.'},
            'risk_summary':{'priced_in':priced,'most_demanding':demanding_text,
                            'sensitivity_driver':matrix['driver']+' within the displayed envelope',
                            'main_review':check['status'] if check['gap_pp'] is not None and abs(check['gap_pp'])>=config['reconciliation_gap_pp'] else 'Review starting cash flow, working-capital/tax normalization, EV scope and discount-rate assumptions.',
                            'support_risk':'Lower sustainable starting cash flow or a higher required return increases the conditional growth requirement; no price or return prediction is made.'},
            'assumptions':config,'limitations':limits,'input_provenance':inputs['market'],
            'retrieved_at':inputs['retrieved_at']}
