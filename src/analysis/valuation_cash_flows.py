"""Moat 3 pure cash-flow bridges; Reported FCF and legacy FCFF stay separate."""
from statistics import median
from src.analysis.financial_statement_bridges import same, value, close
from src.data.earnings_quality_inputs import comparable, number


def result(value=None, method='Unknown', confidence='Insufficient Evidence', inputs=None, reason=None):
    return {'value': value, 'method': method, 'confidence': confidence,
            'status': 'available' if value is not None else 'insufficient_evidence',
            'inputs': inputs or {}, 'reason': reason}


def calculate_operating_nwc(facts):
    names=('current_assets','cash','short_investments','current_liabilities','short_debt','current_lease')
    fs=[facts.get(n) for n in names]
    if same(*fs) and all(value(f)>=0 for f in fs):
        ca,cash,inv,cl,debt,lease=[value(f) for f in fs]
        # Where the provider exposes total debt, confirm leases are not already
        # counted in its short/long borrowing fields before adding them back.
        total,long,alllease=[facts.get(n) for n in ('debt','long_debt','lease_total')]
        if lease>0 and (not same(fs[0],total,long,alllease) or
                        not close(value(total),debt+value(long)+value(alllease))):
            return result(inputs=dict(zip(names,fs)),reason='Current lease/short debt overlap cannot be resolved from the reported debt bridge.')
        if ca-cash-inv<0 or cl-debt-lease<0:
            return result(inputs=dict(zip(names,fs)),reason='Operating-current-asset/liability exclusions exceed their subtotals.')
        return result((ca-cash-inv)-(cl-debt-lease), 'Preferred operating-current bridge', 'Proxy',
                      dict(zip(names,fs)), 'Balance-sheet arithmetic; not a cash-flow causality claim. Residual current balances may include non-operating items.')
    names=('receivables','inventory','other_operating_assets','payables','accrued_operating','deferred_revenue','other_operating_liabilities')
    fs=[facts.get(n) for n in names]
    if same(*fs) and all(value(f)>=0 for f in fs):
        v=[value(f) for f in fs]
        return result(sum(v[:3])-sum(v[3:]),'Explicit operating components','Proxy',dict(zip(names,fs)),
                      'Requires explicitly operating-labelled residual components; no generic other-current balance is assumed operating.')
    return result(inputs={n:facts.get(n) for n in names}, reason='A complete operating-current bridge or all identified operating components are required.')


def calculate_delta_operating_nwc(current, prior):
    a,b=calculate_operating_nwc(current),calculate_operating_nwc(prior)
    common=set(a['inputs']) & set(b['inputs'])
    valid=a['value'] is not None and b['value'] is not None and a['method']==b['method'] and common
    valid=valid and all(comparable(current.get(n),prior.get(n)) for n in common)
    return result(a['value']-b['value'] if valid else None, a['method'] if valid else 'Unknown',
                  'Proxy' if valid else 'Insufficient Evidence', {'current':a,'prior':b},
                  'Positive delta is cash use; negative delta is arithmetic release. Different methods or unmatched periods are not mixed.')


def calculate_normalized_tax_rate(periods, config, tax_evidence=None):
    observations=[]; excluded=[]; tax_evidence=tax_evidence or []
    for p in periods[:3]:
        fs=p['values'];pretax,tax=fs.get('pretax_income'),fs.get('income_tax')
        rate=value(tax)/value(pretax) if same(pretax,tax) and value(pretax)>0 else None
        reason=None
        if rate is None: reason='Missing aligned tax/positive pretax income'
        elif not config['tax_rate_bounds'][0]<=rate<=config['tax_rate_bounds'][1]:reason='Outside configured economic validation interval'
        elif any(e.get('period')==p['period'] and e.get('validation_level',0)>=3 and 'tax' in e.get('categories',[]) for e in tax_evidence):
            reason='Validated period-matched unusual tax evidence; exclude conservatively, do not invent an adjusted rate'
        item={'period':p['period'],'rate':rate,'pretax':pretax,'tax':tax,'reason':reason}
        (excluded if reason else observations).append(item)
    # Valid observations must still belong to one same-currency/source annual run.
    rows=periods[:3]
    if len(rows)>1 and any(not comparable(a['values'].get('pretax_income'),b['values'].get('pretax_income')) for a,b in zip(rows,rows[1:])):
        excluded+= [{**o,'reason':'Recent annual tax window is not consecutive/comparable'} for o in observations];observations=[]
    if len(observations)>=2:
        out=result(median(o['rate'] for o in observations),'3Y median ETR' if len(observations)==3 else '2-observation median fallback',
                   'Calculated' if len(observations)==3 else 'Fallback')
    else:
        fallback=config.get('statutory_tax_fallback')
        valid=isinstance(fallback,dict) and number(fallback.get('value')) is not None and 0<=fallback['value']<=.6 and all(fallback.get(k) for k in ('source','observation_date','version','method')) and not fallback.get('stale',True)
        out=result(fallback['value'],'Explicit statutory/blended reference','Fallback',{'reference':fallback}) if valid else result(reason='Fewer than two valid recent ETR observations and no fresh documented statutory reference.')
    out.update(years_used=[o['period'] for o in observations],observations=observations,excluded=excluded)
    return out


def borrowed_debt(facts):
    names=('short_debt','long_debt');fs=[facts.get(n) for n in names]
    if same(*fs) and all(value(f)>=0 for f in fs):
        total,lease=facts.get('debt'),facts.get('lease_total')
        if same(fs[0],total,lease) and not close(sum(value(f) for f in fs)+value(lease),value(total)):
            return result(reason='Provider total debt does not reconcile to borrowing plus identified leases.')
        return result(sum(value(f) for f in fs),'Book borrowing debt: short + long, excludes identified leases','Proxy',dict(zip(names,fs)),
                      'Book value is a market-debt proxy; lease capital is excluded consistently with operating lease expense convention.')
    return result(reason='Explicit comparable short and long borrowing debt required; total liabilities and ambiguous total debt are not substitutes.')


def calculate_net_borrowing(current, prior):
    issued,repaid=current.get('debt_issued'),current.get('debt_repaid')
    if same(issued,repaid) and value(issued)>=0 and value(repaid)>=0:
        return result(value(issued)-value(repaid),'Debt issued minus positive repayments','Calculated',{'issued':issued,'repaid':repaid})
    net=current.get('net_borrowing')
    if value(net) is not None:
        return result(value(net),'Reported signed net debt issuance','Calculated',{'net_debt_issuance':net},
                      'Provider financing-cash-flow net amount; no lease-balance movement is added.')
    a,b=borrowed_debt(current),borrowed_debt(prior)
    if a['value'] is not None and b['value'] is not None and all(comparable(current.get(n),prior.get(n)) for n in ('short_debt','long_debt')):
        return result(a['value']-b['value'],'BALANCE-SHEET PROXY','Proxy',{'current':a,'prior':b},
                      'Debt balance change may include FX, acquisitions and reclassifications; not exact financing cash flow.')
    return result(reason='No usable financing debt cash flow or matched borrowing-debt proxy.')


def calculate_nopat(ebit,tax):
    return number(ebit)*(1-number(tax)) if number(ebit) is not None and number(tax) is not None and 0<=tax<=1 else None


def calculate_fcff(ebit,tax,da,capex_outlay,delta_nwc):
    nopat=calculate_nopat(ebit,tax)
    if any(number(v) is None for v in (nopat,da,capex_outlay,delta_nwc)) or da<0 or capex_outlay<0:return None
    return nopat+da-capex_outlay-delta_nwc


def calculate_fcfe(ni,da,capex_outlay,delta_nwc,net_borrowing):
    if any(number(v) is None for v in (ni,da,capex_outlay,delta_nwc,net_borrowing)) or da<0 or capex_outlay<0:return None
    return ni+da-capex_outlay-delta_nwc+net_borrowing


def build_cash_flows(periods, config, tax_evidence=None):
    tax=calculate_normalized_tax_rate(periods,config,tax_evidence)
    history=[]
    for i,p in enumerate(periods):
        current=p['values'];prior=periods[i+1]['values'] if i+1<len(periods) else {}
        delta=calculate_delta_operating_nwc(current,prior); borrowing=calculate_net_borrowing(current,prior)
        ebit,ni,da,capex=[current.get(k) for k in ('operating_income','net_income','da','capex')]
        outlay=-value(capex) if value(capex) is not None and value(capex)<=0 else None
        # Working capital must align with the income/cash period too, not merely itself.
        anchors=[current.get(k) for k in delta['inputs']['current']['inputs']]
        current_tax=calculate_normalized_tax_rate(periods[i:],config,tax_evidence)
        ff=calculate_fcff(value(ebit),current_tax['value'],value(da),outlay,delta['value']) if same(ebit,da,capex,*anchors) else None
        borrowing_facts=[current.get('net_borrowing')] if borrowing['method']=='Reported signed net debt issuance' else [current.get(k) for k in ('debt_issued','debt_repaid')] if borrowing['method']=='Debt issued minus positive repayments' else [current.get('short_debt'),current.get('long_debt')]
        fe=calculate_fcfe(value(ni),value(da),outlay,delta['value'],borrowing['value']) if same(ni,da,capex,*anchors,*borrowing_facts) else None
        history.append({'period':p['period'],'fcff':ff,'fcfe':fe,'tax':current_tax,'delta_nwc':delta,
                        'net_borrowing':borrowing,'capex_outlay':outlay,'ebit':ebit,'ni':ni,'da':da,'capex':capex,
                        'reported_fcf':current.get('fcf'),
                        'confidence':'Proxy' if ff is not None else 'Insufficient Evidence'})
    return {'tax':tax,'history':history,'current':history[0] if history else None}
