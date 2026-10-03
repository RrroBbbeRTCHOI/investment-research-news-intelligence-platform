"""Deterministic statement interpretation. All thresholds are diagnostic only."""
from src.analysis.financial_statement_bridges import (FIELDS,metric,ratio,bridge,same,value,
                                                      significance,fcf_bridge,close)


def operating_leverage(revenue,operating,gap):
    if revenue is None or operating is None or gap is None:return 'unknown'
    if revenue<0 and operating<0:return 'both_declining'
    if revenue*operating<0:return 'mixed'
    if abs(gap)<5:return 'roughly_proportional'
    return 'positive_operating_leverage' if gap>0 else 'negative_operating_leverage'


def margin(periods,name):
    r=ratio(periods,name,'revenue'); pp=r['change']*100 if r['change'] is not None else None
    return {**r,'change_pp':pp,'significance':significance(pp,True),
            'state':'unavailable' if pp is None else 'stable' if abs(pp)<1 else 'expanding' if pp>0 else 'compressing'}


def trend(periods,name,as_margin=False):
    observations=[]
    for i,p in enumerate(periods):
        v=ratio(periods[i:],name,'revenue')['current'] if as_margin else metric(periods[i:],name)['current']
        observations.append({'period':p['period'],'value':v})
    changes=[]
    for i in range(len(periods)-1):
        if as_margin:
            d=ratio(periods[i:],name,'revenue')['change']
            changes.append(d*100 if d is not None else None)
        else:changes.append(metric(periods[i:],name)['growth_pct'])
    status='unknown'; tolerance=1 if as_margin else 5
    if len(changes)>=2 and all(v is not None for v in changes):
        a,b=changes[:2]
        if a*b<0:status='reversal'
        elif len(changes)>=3 and sum(x*y<0 for x,y in zip(changes,changes[1:]))>=2:status='unusually_volatile'
        elif abs(a-b)<tolerance:status='consistent_with_trend'
        else:status='acceleration' if a>b else 'deceleration'
    return {'state':status,'history':observations,'changes':changes,
            'note':'Signed growth/margin-change trajectory, not a forecast or quality judgment.'}


def interpret(ticker,periods,moat1=None,errors=None):
    names=[n for fields in FIELDS.values() for n in fields]
    m={name:metric(periods,name) for name in names}
    # CapEx growth is explicitly the change in positive outlay magnitude.
    cap=m['capex']
    if cap['availability']=='available' and cap['current']<=0 and cap['prior']<0:
        cap['growth_pct']=(cap['current']/cap['prior']-1)*100
        cap['growth_status']='normal'
        cap['significance']=significance(cap['growth_pct'])
    income_names=['revenue','gross_profit','operating_income','pretax_income','net_income']
    bridges=[bridge(m,a,b) for a,b in zip(income_names,income_names[1:])]
    operating=bridge(m,'revenue','operating_income')
    operating['state']=operating_leverage(m['revenue']['growth_pct'],m['operating_income']['growth_pct'],operating['growth_gap_pp'])
    margins={k:margin(periods,k) for k in income_names[1:]}
    costs={k:{**m[k],'revenue_share':margin(periods,k)} for k in
           ('cost_of_revenue','rd','sales_marketing','sga','ga','sbc','da')}
    below=bridges[-2]; tax=bridges[-1]
    # Arithmetic coverage is limited to an exact reported subtotal; no overlapping driver sums.
    other=m['other_income']; tax_expense=m['income_tax']
    for item,component,sign in ((below,other,1),(tax,tax_expense,-1)):
        ok=component['availability']=='available'
        for side in ('current','prior'):
            a,b=m[item['from']],m[item['to']]
            ok=ok and same(a[side+'_fact'],b[side+'_fact'],component[side+'_fact'])
            if ok:ok=close(b[side]-a[side],sign*component[side])
        if ok:
            item.update(evidence_coverage='arithmetic_supported',unresolved_portion=0,
                        supported_drivers=[{'name':component['name'],'current':component['current'],
                                            'prior':component['prior'],'evidence':component['evidence']}])
        else:item['unresolved_portion']=item['current_difference']
    etr=ratio(periods,'income_tax','pretax_income'); tax['effective_tax_rate']=etr
    tax['effective_tax_rate_change_pp']=etr['change']*100 if etr['change'] is not None else None
    gap=tax['growth_gap_pp']
    tax['state']='unknown' if gap is None else 'aligned' if abs(gap)<10 else 'large_below_tax_gap'
    if gap is not None and abs(gap)>=10 and tax['evidence_coverage']=='arithmetic_supported' and etr['change'] is not None:
        if etr['change']>=.01 and gap<0:tax['state']='tax_headwind'
        elif etr['change']<=-.01 and gap>0:tax['state']='tax_tailwind'
    # Consume upstream evidence verbatim; never reclassify SEC text or calculate EQ.
    upstream=moat1 or {}; research=upstream.get('research_analysis',{})
    refs={}; current=periods[0]['period'] if periods else None
    for e in research.get('evidence',[]):
        if e.get('period')!=current or e.get('validation_level',0)<3:continue
        refs[e['evidence_id']]=e
        categories=set(e.get('categories',[]))
        for item,relevant in ((below,{'below_operating','volatile_market','actual_event'}),(tax,{'tax'})):
            if categories & relevant:
                item.setdefault('narrative_references',[]).append(e['evidence_id'])
                if item['evidence_coverage']=='insufficient_evidence':item['evidence_coverage']='partial_narrative'
    liquidity={k:ratio(periods,a,b) for k,a,b in
               [('current_ratio','current_assets','current_liabilities'),('cash_debt','cash','debt'),('debt_equity','debt','equity')]}
    net=[];quick=[]
    for p in periods[:2]:
        v=p['values']; c,d=v.get('cash'),v.get('debt')
        net.append(value(c)-value(d) if same(c,d) else None)
        fs=[v.get(k) for k in ('cash','short_investments','receivables','current_liabilities')]
        quick.append(sum(value(f) for f in fs[:3])/value(fs[3]) if same(*fs) and value(fs[3])>0 else None)
    net=(net+[None,None])[:2];quick=(quick+[None,None])[:2]
    comparable_balance=all(m[k]['availability']=='available' for k in ('cash','debt'))
    liquidity['net_cash']={'current':net[0],'prior':net[1], 'change':net[0]-net[1] if comparable_balance and all(v is not None for v in net) else None}
    liquidity['quick_ratio']={'current':quick[0],'prior':quick[1], 'note':'(Cash + short-term investments + receivables) / current liabilities; no missing component is assumed zero.'}
    change=liquidity['current_ratio']['change']
    liquidity['state']='unknown' if change is None else 'liquidity_stable' if abs(change)<.1 else 'liquidity_strengthening' if change>0 else 'liquidity_weakening'
    debtchange=liquidity['debt_equity']['change']
    liquidity['leverage_state']='unknown' if debtchange is None else 'leverage_stable' if abs(debtchange)<.1 else 'leverage_increasing' if debtchange>0 else 'leverage_decreasing'
    wc={};wc_states=[]
    for name in ('receivables','inventory','payables','deferred_revenue'):
        b=bridge(m,'revenue',name);g=b['growth_gap_pp']
        state='unknown' if g is None else 'aligned'
        if g is not None and g>=10 and m[name]['growth_pct']>0:
            state={'receivables':'receivables_build','inventory':'inventory_build','payables':'payable_support','deferred_revenue':'contract_liability_build'}[name]
        if g is not None and name in ('receivables','inventory') and m[name]['growth_pct']<0 and g<=-10:state='working_capital_release'
        wc[name]={**b,'state':state,'growth_pct':m[name]['growth_pct']}
        if state not in ('unknown','aligned'):wc_states.append(state)
    wc['state']='mixed' if len(set(wc_states))>1 else wc_states[0] if wc_states else 'aligned' if all(wc[k]['state']=='aligned' for k in ('receivables','inventory','payables','deferred_revenue')) else 'unknown'
    cashbridge=[bridge(m,'net_income','ocf'),bridge(m,'ocf','fcf')]
    cashratio=ratio(periods,'ocf','net_income'); cv=cashratio['current']
    ni=m['net_income']['current']; ocf=m['ocf']['current']
    cashstate='unknown'
    if ni is not None and same(m['net_income']['current_fact'],m['ocf']['current_fact']):
        cashstate='negative_earnings' if ni<0 else 'unknown' if ni==0 else 'strong_cash_conversion' if cv>=1 else 'moderate_cash_conversion' if cv>=.8 else 'weak_cash_conversion'
    capex=fcf_bridge(periods,m)
    # Signed provider CapEx remains visible. Outlay ratios invert its sign only when non-positive.
    cr=ratio(periods,'capex','revenue');co=ratio(periods,'capex','ocf')
    for r in (cr,co):
        for key in ('current','prior','change'):r[key]=-r[key] if r[key] is not None else None
        if any(m['capex'][s] is not None and m['capex'][s]>0 for s in ('current','prior')):r.update(current=None,prior=None,change=None)
    priorities=[]
    def add(rule,level,text,evidence):
        priorities.append({'rule':rule,'level':level,'interpretation':text,'evidence':evidence})
    rg,og=m['revenue']['growth_pct'],m['operating_income']['growth_pct']
    opposite = (m['revenue']['change'] is not None and m['operating_income']['change'] is not None
                and m['revenue']['change'] * m['operating_income']['change'] < 0
                and all(same(m['revenue'][side+'_fact'],m['operating_income'][side+'_fact']) for side in ('current','prior')))
    if opposite:add('operating_divergence','High','Revenue and operating income moved in opposite directions; inspect operating costs and margins.',m['revenue']['evidence']+m['operating_income']['evidence'])
    for item,rule in ((below,'below_operating'),(tax,'below_tax'),(cashbridge[0],'cash_lag'),(cashbridge[1],'fcf_divergence')):
        g=item['growth_gap_pp']
        if g is not None and abs(g)>=10 and (rule!='cash_lag' or g<0):
            add(rule,'High' if abs(g)>=30 else 'Medium',f"{item['to'].replace('_',' ').title()} growth differed from {item['from'].replace('_',' ')} by {g:+.1f} pp; review this bridge ({item['evidence_coverage']}).",m[item['from']]['evidence']+m[item['to']]['evidence'])
    for k in ('receivables','inventory'):
        g=wc[k]['growth_gap_pp']
        if wc[k]['state'].endswith('_build'):
            add(k+'_build','High' if g>=30 else 'Medium',f"{k.title()} grew {g:.1f} pp faster than revenue; investigate the balance build, not a presumed cash-flow cause.",m[k]['evidence']+m['revenue']['evidence'])
    for k,v in margins.items():
        if v['change_pp'] is not None and v['change_pp']<=-3:
            add(k+'_compression','High' if v['change_pp']<=-5 else 'Medium',f"{k.replace('_',' ').title()} margin compressed {abs(v['change_pp']):.1f} pp; pricing, mix, costs or other factors warrant investigation.",m[k]['evidence']+m['revenue']['evidence'])
    if m['debt']['growth_pct'] is not None and m['debt']['growth_pct']>=30 and m['cash']['change'] is not None and m['cash']['change']<0 and all(same(m['debt'][s+'_fact'],m['cash'][s+'_fact']) for s in ('current','prior')):
        add('debt_cash','High','Debt rose at least 30% while cash declined; review financing and liquidity movements without assuming debt is adverse.',m['debt']['evidence']+m['cash']['evidence'])
    for eid,e in refs.items():
        if e.get('validation_level',0)>=4 and set(e.get('categories',[])) & {'actual_event','tax','volatile_market'}:
            add('upstream_unusual_'+eid,'Medium','Moat 1 provides an amount-linked current-period disclosure; inspect its accounting location and materiality.',[eid])
    if cashstate=='weak_cash_conversion':add('conversion','Medium','OCF is below 0.8 times positive net income; inspect cash reconciliation. This is not a new quality score.',m['ocf']['evidence']+m['net_income']['evidence'])
    if not priorities:add('coverage','Informational','No configured investigation trigger was established; incomplete data is not evidence of absence.',[])
    order={'High':0,'Medium':1,'Low':2,'Informational':3}
    priorities.sort(key=lambda p:(order[p['level']],p['rule']))
    summary=[]
    if rg is not None and og is not None and operating['growth_gap_pp'] is not None:
        summary.append(f"Revenue changed {rg:+.1f}% and operating income {og:+.1f}%; {operating['state'].replace('_',' ')} (gap {operating['growth_gap_pp']:+.1f} pp).")
    if not summary:
        for name in ('revenue','operating_income'):
            if m[name]['change'] is not None:
                summary.append(f"{name.replace('_',' ').title()} changed {m[name]['change']:+,.0f} currency units; percentage growth is N/M or the cross-line comparison is unavailable.")
    for item in (below,tax):
        if item['growth_gap_pp'] is not None:
            summary.append(f"{item['from'].replace('_',' ').title()} to {item['to'].replace('_',' ')} growth gap is {item['growth_gap_pp']:+.1f} pp; {item['state'].replace('_',' ')} with {item['evidence_coverage'].replace('_',' ')}.")
    if cv is not None:summary.append(f"OCF / positive net income is {cv:.2f}x ({cashstate.replace('_',' ')}).")
    if capex['state']!='unknown':summary.append(f"FCF changed {capex['fcf_change']:+,.0f} currency units: OCF change {capex['ocf_change']:+,.0f}, signed CapEx effect {capex['capex_cash_effect']:+,.0f}; {capex['state'].replace('_',' ')}.")
    positives=[]
    if margins['operating_income']['state']=='expanding':positives.append(f"Operating margin expanded {margins['operating_income']['change_pp']:.1f} pp.")
    if cashstate=='strong_cash_conversion':positives.append(f"Positive earnings were covered by OCF at {cv:.2f}x.")
    limitations=['Financial movements do not establish economic causes. Missing inputs remain unknown.',
                  'Stock balance changes do not equal cash-flow working-capital changes; acquisitions, FX and other movements can intervene.',
                  'Cost lines may overlap (SG&A with G&A/marketing, SBC and D&A with functional expenses); never summed.',
                  'Annual statement diagnostics can differ from the unchanged top cards, which retain their existing provider/period definitions.',
                  'No forced SEC/EQ recomputation: Moat 1 references are available only when supplied or already cached.']
    if errors:limitations.extend(errors)
    complete=all(m[k]['availability']=='available' for k in ('revenue','operating_income','net_income','ocf','fcf','cash','debt','assets'))
    return {'ticker':ticker,'period':{'current':current,'prior':periods[1]['period'] if len(periods)>1 else None,
                                     'type':'annual','availability':'available' if complete else 'partial',
                                     'currency':(m['revenue']['current_fact'] or {}).get('currency')},
      'income_statement':{'metrics':{k:m[k] for k in income_names},'bridge':bridges,'operating_leverage':operating,
                          'below_operating':below,'tax_bridge':tax,'margin_analysis':margins,'cost_structure':costs},
      'balance_sheet':{'metrics':{k:m[k] for k in FIELDS['balance']},'liquidity':liquidity,'working_capital':wc},
      'cash_flow':{'metrics':{k:m[k] for k in ('net_income','ocf','capex','fcf')},'bridge':cashbridge,
                   'cash_conversion':{**cashratio,'state':cashstate},'fcf_margin':margin(periods,'fcf'),
                   'capex_revenue':cr,'capex_ocf':co,'capex_analysis':capex,
                   'moat1_cash_support':upstream.get('cash_support',upstream.get('cash_history'))},
      'trend_context':{**{k:trend(periods,k) for k in ('revenue','operating_income','net_income','ocf','fcf','debt','cash')},
                       'operating_margin':trend(periods,'operating_income',True),'fcf_margin':trend(periods,'fcf',True)},
      'investigation_priorities':priorities,
      'analyst_interpretation':{'state':'Review required' if priorities[0]['level'] in ('High','Medium') else 'No configured trigger' if complete else 'Partial / Unknown',
                               'positive_observation':positives[0] if positives else 'Unknown: no supported positive structural observation.',
                               'main_concern':priorities[0]['interpretation'],
                               'summary':' '.join(summary) if summary else 'Insufficient comparable annual evidence for interpretation.'},
      'evidence_references':{'moat1':refs,'moat1_state':research.get('interpretation'),
                             'financial_facts':{f['evidence_id']:f for p in periods for f in p['values'].values()}},
      'limitations':limitations}
