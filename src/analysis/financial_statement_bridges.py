"""Annual statement facts and arithmetic; no rating or Earnings Quality scoring."""
from src.data.earnings_quality_inputs import fact, aligned, comparable, number
from src.analysis.historical_trends import _calculate_growth
from src.analysis.earnings_quality_diagnostics import close

FIELDS = {
 'income': {'revenue':'revenue','gross_profit':'grossProfit','operating_income':'operatingIncome',
 'pretax_income':'incomeBeforeTax','net_income':'netIncome','income_tax':'incomeTaxExpense',
 'cost_of_revenue':'costOfRevenue','rd':'researchAndDevelopmentExpenses',
 'sales_marketing':'sellingAndMarketingExpenses','sga':'sellingGeneralAndAdministrativeExpenses',
 'ga':'generalAndAdministrativeExpenses','other_income':'totalOtherIncomeExpensesNet'},
 'balance': {'cash':'cashAndCashEquivalents','short_investments':'shortTermInvestments',
 'receivables':'netReceivables','inventory':'inventory','current_assets':'totalCurrentAssets',
 'assets':'totalAssets','payables':'accountPayables','current_liabilities':'totalCurrentLiabilities',
 'debt':'totalDebt','liabilities':'totalLiabilities','equity':'totalStockholdersEquity',
 'deferred_revenue':'deferredRevenue'},
 'cash': {'cash_net_income':'netIncome','ocf':'operatingCashFlow','capex':'capitalExpenditure',
 'fcf':'freeCashFlow','sbc':'stockBasedCompensation','da':'depreciationAndAmortization'}
}
# Accepted equivalent spellings for the existing annual balance schema.
# Do not substitute broader totals or gross/components for the requested line.
BALANCE_ALIASES = {
    'cash': ('cash', 'cash_and_cash_equivalents', 'cashAndEquivalents'),
    'short_investments': ('short_investments', 'short_term_investments'),
    'receivables': ('receivables', 'net_receivables', 'accountsReceivableNet', 'accountsReceivablesNet'),
    'inventory': ('inventories',),
    'current_assets': ('current_assets', 'currentAssets', 'total_current_assets'),
    'assets': ('assets', 'total_assets'),
    'payables': ('payables', 'accountsPayable', 'accountsPayables', 'accounts_payable'),
    'current_liabilities': ('current_liabilities', 'currentLiabilities', 'total_current_liabilities'),
    'debt': ('debt', 'total_debt'),
    'liabilities': ('liabilities', 'total_liabilities'),
    'equity': ('equity', 'stockholdersEquity', 'totalShareholdersEquity', 'total_stockholders_equity'),
    'deferred_revenue': ('deferred_revenue', 'deferredRevenueCurrent', 'currentDeferredRevenue', 'contractLiabilitiesCurrent'),
}


def balance_fact(ticker, row, name, primary):
    """Resolve an equivalent field within ONE source row; preserve provenance.

    Valid primary values (including zero) retain established semantics. Alias
    fallback requires a finite numeric value and agreement among usable aliases.
    No totals are inferred, no dates/currencies are borrowed, and raw caches stay
    provider-shaped. Existing fact validation still decides whether it is usable.
    """
    if number(row.get(primary)) is not None:
        return fact(ticker, row, primary, endpoint='balance-sheet-statement')
    candidates = [(key, number(row.get(key))) for key in BALANCE_ALIASES[name]
                  if key != primary and number(row.get(key)) is not None]
    if not candidates:
        return fact(ticker, row, primary, endpoint='balance-sheet-statement')
    if len({v for _, v in candidates}) != 1:
        result = fact(ticker, row, primary, endpoint='balance-sheet-statement')
        result.update(value=None, availability='unknown', reason='conflicting_balance_aliases',
                      canonical_field=name, alias_fields=[key for key, _ in candidates])
        return result
    chosen = candidates[0][0]
    result = fact(ticker, row, chosen, endpoint='balance-sheet-statement')
    result.update(canonical_field=name, normalized_from=chosen)
    return result


ENDPOINTS={'income':'income-statement','balance':'balance-sheet-statement','cash':'cash-flow-statement'}


def normalize(ticker, datasets):
    grouped={}
    for kind, fields in FIELDS.items():
        for row in datasets.get(kind, []):
            if not isinstance(row, dict):
                continue
            bucket=grouped.setdefault(str(row.get('date') or ''),{})
            for name, field in fields.items():
                f=(balance_fact(ticker,row,name,field) if kind == 'balance'
                   else fact(ticker,row,field,endpoint=ENDPOINTS[kind]))
                start=row.get('startDate')
                if start:
                    from src.data.earnings_quality_inputs import iso_date
                    a,b=iso_date(start),iso_date(row.get('date'))
                    if not a or not b or not 350 <= (b-a).days <= 380:
                        f.update(availability='unknown',reason='incompatible_duration')
                if name in bucket:
                    f.update(availability='unknown',reason='duplicate_period')
                bucket[name]=f
    # The latest income/cash observation anchors the pair even if incomplete.
    dates=sorted((d for d,v in grouped.items() if 'revenue' in v or 'ocf' in v),reverse=True)[:5]
    return [{'period':d,'values':grouped[d]} for d in dates]


def same(*facts):
    return aligned(*facts) and len({f['source'] for f in facts})==1


def value(f):
    return f['value'] if f and f.get('availability')=='available' else None


def significance(amount, pp=False):
    if amount is None:return 'unknown'
    thresholds=(1,3,5) if pp else (5,15,30)
    return ('minor','moderate','material','major')[sum(abs(amount)>=t for t in thresholds)]


def metric(periods,name):
    c=periods[0]['values'].get(name) if periods else None
    p=periods[1]['values'].get(name) if len(periods)>1 else None
    ok=comparable(c,p)
    growth=_calculate_growth(value(c),value(p)) if ok else {'value':None,'status':'missing'}
    g=growth['value']*100 if growth['value'] is not None else None
    return {'name':name,'current':value(c),'prior':value(p),'change':value(c)-value(p) if ok else None,
            'growth_pct':g,'growth_status':growth['status'],'availability':'available' if ok else 'unknown',
            'significance':significance(g),'current_fact':c,'prior_fact':p,
            'evidence':[f['evidence_id'] for f in (c,p) if f]}


def ratio(periods,numerator,denominator):
    out=[]
    for period in periods[:2]:
        a,b=(period['values'].get(k) for k in (numerator,denominator))
        out.append(value(a)/value(b) if same(a,b) and value(b)>0 else None)
    out=(out+[None,None])[:2]
    pair=metric(periods,numerator)['availability']=='available' and metric(periods,denominator)['availability']=='available'
    return {'current':out[0],'prior':out[1],
            'change':out[0]-out[1] if pair and all(x is not None for x in out) else None}


def bridge(metrics,left,right):
    a,b=metrics[left],metrics[right]
    ok=all(same(a[side+'_fact'],b[side+'_fact']) for side in ('current','prior'))
    gap=b['growth_pct']-a['growth_pct'] if ok and a['growth_pct'] is not None and b['growth_pct'] is not None else None
    return {'from':left,'to':right,'growth_gap_pp':gap,'significance':significance(gap,True),
            'current_difference':b['current']-a['current'] if same(a['current_fact'],b['current_fact']) else None,
            'prior_difference':b['prior']-a['prior'] if same(a['prior_fact'],b['prior_fact']) else None,
            'state':'unknown' if gap is None else 'aligned' if abs(gap)<10 else 'investigate',
            'evidence_coverage':'insufficient_evidence','supported_drivers':[],
            'unresolved_portion':None,'note':'A statement difference is not a core/non-core decomposition.'}


def fcf_bridge(periods,metrics):
    result={'state':'unknown','ocf_change':None,'capex_cash_effect':None,'fcf_change':None,
            'note':'Requires two comparable annual periods and signed CapEx reconciliation.'}
    if any(metrics[k]['availability']!='available' for k in ('ocf','capex','fcf')):return result
    for p in periods[:2]:
        o,c,f=(p['values'].get(k) for k in ('ocf','capex','fcf'))
        if not same(o,c,f) or value(c)>0 or not close(value(o)+value(c),value(f)):return result
    od,cd,fd=(metrics[k]['change'] for k in ('ocf','capex','fcf'))
    state='unchanged' if abs(fd)<1e-9 else 'both' if od*cd>0 else 'ocf_driven' if abs(od)>abs(cd) else 'capex_driven' if abs(cd)>abs(od) else 'offsetting'
    result.update(state=state,ocf_change=od,capex_cash_effect=cd,fcf_change=fd,
                  note='FCF change reconciles to OCF change plus signed CapEx change; this is arithmetic, not an investment-quality judgment.')
    return result
