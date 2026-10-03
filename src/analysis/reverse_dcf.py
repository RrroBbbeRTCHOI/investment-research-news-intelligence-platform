"""Isolated Moat 3 cash-flow mathematics. Never alters the legacy DCF model."""
import math
from src.data.earnings_quality_inputs import number


def calculate_terminal_value(cash_flow_n, discount_rate, terminal_growth):
    values = [number(v) for v in (cash_flow_n, discount_rate, terminal_growth)]
    if None in values:
        return None
    cf, rate, growth = values
    if rate <= growth or rate <= -1 or growth <= -1:
        return None
    return cf * (1 + growth) / (rate - growth)


def _value(start, growth, rate, terminal, years=5):
    if any(number(v) is None for v in (start, growth, rate, terminal)):
        return None
    start,growth,rate,terminal=[number(v) for v in (start,growth,rate,terminal)]
    if start <= 0 or growth <= -1 or rate <= terminal or rate <= 0 or terminal <= -1 or years != 5:
        return None
    try:
        explicit = sum(start * (1 + growth)**t / (1 + rate)**t for t in range(1, years + 1))
        tv = calculate_terminal_value(start * (1 + growth)**years, rate, terminal)
        result = explicit + tv / (1 + rate)**years
        return result if math.isfinite(result) else None
    except (OverflowError, ZeroDivisionError):
        return None


def calculate_fcff_dcf_value(starting_fcff, growth, wacc, terminal_growth, years=5):
    return _value(starting_fcff, growth, wacc, terminal_growth, years)


def calculate_fcfe_dcf_value(starting_fcfe, growth, cost_of_equity, terminal_growth, years=5):
    return _value(starting_fcfe, growth, cost_of_equity, terminal_growth, years)


def _solve(target, start, rate, terminal, bounds=(-.95, 3.0), model='FCFF'):
    out = {'model': model, 'growth': None, 'year5_cash_flow': None, 'target': target,
           'starting_cash_flow': start, 'discount_rate': rate, 'terminal_growth': terminal,
           'horizon': 5, 'status': 'insufficient_evidence', 'iterations': 0,
           'residual': None, 'bounds': list(bounds)}
    if any(number(v) is None for v in (target, start, rate, terminal)):
        return out
    target,start,rate,terminal=[number(v) for v in (target,start,rate,terminal)]
    if target <= 0 or start <= 0 or rate <= 0 or terminal <= -1 or terminal >= rate:
        out['status'] = 'invalid_inputs'
        return out
    low, high = bounds
    if not -1 < low < high:
        out['status'] = 'invalid_bounds'
        return out
    lv, hv = _value(start, low, rate, terminal), _value(start, high, rate, terminal)
    if lv is None or hv is None or not lv <= target <= hv:
        out['status'] = 'no_solution_in_bounds'
        return out
    for i in range(160):
        mid = (low + high) / 2
        pv = _value(start, mid, rate, terminal)
        if pv is None:
            out['status'] = 'numerical_failure'
            return out
        if abs(pv - target) <= max(1e-8, abs(target) * 1e-10):
            out.update(growth=mid, year5_cash_flow=start*(1+mid)**5,
                       status='converged', iterations=i+1, residual=pv-target)
            return out
        if pv < target:
            low = mid
        else:
            high = mid
    out['status'] = 'not_converged'
    return out


def solve_implied_fcff_growth(market_ev, starting_fcff, wacc, terminal_growth, bounds=(-.95, 3.0)):
    return _solve(market_ev, starting_fcff, wacc, terminal_growth, bounds, 'FCFF')


def solve_implied_fcfe_growth(market_cap, starting_fcfe, cost_of_equity, terminal_growth, bounds=(-.95, 3.0)):
    return _solve(market_cap, starting_fcfe, cost_of_equity, terminal_growth, bounds, 'FCFE')


def build_sensitivity_matrix(target, start, rate, terminal, config, model='FCFF'):
    out = {'rows': [], 'terminals': [], 'minimum': None, 'maximum': None,
           'discount_effect_pp': None, 'terminal_effect_pp': None, 'driver': 'Unknown'}
    if number(rate) is None or number(terminal) is None:
        return out
    terminals = [terminal + x for x in config['terminal_growth_offsets']]
    rates = [rate + x for x in config['discount_rate_offsets']]
    out['terminals'] = terminals
    values = []
    for r in rates:
        cells = []
        for t in terminals:
            cell = _solve(target, start, r, t, config['solver_growth_bounds'], model)
            cell['base'] = abs(r-rate)<1e-12 and abs(t-terminal)<1e-12
            cells.append(cell)
            if cell['growth'] is not None:
                values.append(cell['growth'])
        out['rows'].append({'discount_rate': r, 'cells': cells})
    if values:
        out.update(minimum=min(values), maximum=max(values))
    def envelope(cells):
        numbers = [c['growth'] for c in cells if c['growth'] is not None]
        return (max(numbers)-min(numbers))*100 if len(numbers)==len(cells) and len(numbers)>1 else None
    out['discount_effect_pp'] = envelope([_solve(target,start,r,terminal,config['solver_growth_bounds'],model) for r in rates])
    out['terminal_effect_pp'] = envelope([_solve(target,start,rate,t,config['solver_growth_bounds'],model) for t in terminals])
    a,b=out['discount_effect_pp'],out['terminal_effect_pp']
    if a is not None and b is not None:
        out['driver']='discount rate' if a>b else 'terminal growth' if b>a else 'equal displayed effects'
    return out
