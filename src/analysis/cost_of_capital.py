"""Moat 3 discount rates only: CAPM for equity; WACC for FCFF."""
from src.analysis.valuation_cash_flows import result, borrowed_debt
from src.analysis.financial_statement_bridges import same,value
from src.data.earnings_quality_inputs import number,comparable


def calculate_cost_of_equity(risk_free,beta,erp):
    values=[number(x) for x in (risk_free,beta,erp)]
    if None in values or risk_free<0 or erp<0:return None
    v=risk_free+beta*erp
    return v if v>0 else None


def calculate_cost_of_debt(current,prior,market_yield=None):
    if isinstance(market_yield,dict) and number(market_yield.get('value')) is not None and 0<=market_yield['value']<1 and market_yield.get('source') and market_yield.get('observation_date') and not market_yield.get('stale',True):
        return result(market_yield['value'],'Observed borrowing yield','Market',{'market_yield':market_yield})
    a,b=borrowed_debt(current),borrowed_debt(prior)
    interest=current.get('interest_expense');fs=[current.get('short_debt'),current.get('long_debt'),interest]
    if a['value'] is not None and b['value'] is not None and same(*fs) and all(comparable(current.get(k),prior.get(k)) for k in ('short_debt','long_debt')):
        avg=(a['value']+b['value'])/2
        if avg>0 and value(interest)>0:
            rate=value(interest)/avg
            if rate<1:return result(rate,'Interest expense / average book borrowing debt','Proxy',{'interest':interest,'current_debt':a,'prior_debt':b,'average_debt':avg},'Historical accounting proxy, not marginal borrowing yield; interest scope may include lease interest.')
    return result(reason='No dated market borrowing yield or usable positive interest/average borrowing debt; a provider zero on positive debt is not assumed a free borrowing rate.')


def calculate_wacc(market_cap,debt,cost_equity,cost_debt,tax,preferred=None,preferred_cost=None):
    if any(number(v) is None for v in (market_cap,debt,cost_equity)) or market_cap<=0 or debt<0 or cost_equity<=0:return result(reason='Positive market equity value, nonnegative debt and cost of equity required.')
    if preferred is not None and (number(preferred) is None or preferred<0):return result(reason='Invalid preferred capital.')
    p=preferred if preferred is not None else 0
    # None is a disclosed common-equity/debt-only model limitation, not a measured zero.
    if p>0 and (number(preferred_cost) is None or preferred_cost<=0):return result(reason='Positive preferred capital requires a separately supported preferred cost.')
    total=market_cap+debt+p; ew=market_cap/total;dw=debt/total;pw=p/total
    if debt==0:
        w=ew*cost_equity+(pw*preferred_cost if p else 0)
    else:
        if number(cost_debt) is None or cost_debt<0 or number(tax) is None or not 0<=tax<=1:return result(reason='Positive debt requires supported debt cost and normalized tax rate.')
        w=ew*cost_equity+dw*cost_debt*(1-tax)+(pw*preferred_cost if p else 0)
    out=result(w,'Market equity / book borrowing debt weights','Proxy')
    out.update(equity_weight=ew,debt_weight=dw,preferred_weight=pw,
               preferred_treatment='No preferred claim supplied: common-equity/debt-only proxy, not proof of zero preferred' if preferred is None else 'Explicit preferred input',
               market_cap=market_cap,debt=debt,cost_of_equity=cost_equity,cost_of_debt=cost_debt,tax=tax)
    return out
