"""Arithmetic attribution and bounded evidence associations, independent of scores."""
from src.data.earnings_quality_inputs import aligned, comparable
from src.analysis.earnings_quality_diagnostics import close, growth_decomposition
from src.analysis.earnings_quality_research_evidence import load_rules

BRIDGES = (
    ('revenue', 'operating_income', ['operating_revenue', 'operating_cost']),
    ('operating_income', 'pretax_income', ['below_operating', 'volatile_market', 'actual_event']),
    ('pretax_income', 'net_income', ['tax']),
    ('net_income', 'ocf', ['working_capital', 'operating_cost']),
    ('ocf', 'fcf', ['capex']),
)


def fcf_attribution(inputs):
    history = []
    for p in inputs['periods'][:2]:
        v = p['values']
        facts = [v.get(k) for k in ('ocf', 'capex', 'fcf')]
        ok = aligned(*facts)
        residual = None
        if ok:
            residual = v['fcf']['value'] - v['ocf']['value'] - v['capex']['value']
            ok = v['capex']['value'] <= 0 and close(v['fcf']['value'], v['ocf']['value'] + v['capex']['value'])
        history.append({'period': p['period'], 'inputs': dict(zip(('ocf', 'capex', 'fcf'), facts)),
                        'residual': residual, 'reconciled': ok})
    valid = len(history) == 2 and all(p['reconciled'] for p in history) and comparable(history[0]['inputs']['ocf'], history[1]['inputs']['ocf'])
    out = {'status': 'incomplete', 'attribution': 'unknown', 'history': history, 'changes': None,
           'summary': 'No validated OCF-to-FCF attribution is available.',
           'limitation': 'Arithmetic contributions do not establish CapEx purpose or productivity.'}
    if not valid:
        return out
    delta = {k: history[0]['inputs'][k]['value'] - history[1]['inputs'][k]['value'] for k in ('ocf', 'capex', 'fcf')}
    if not close(delta['fcf'], delta['ocf'] + delta['capex']):
        return out
    if delta['fcf'] >= 0:
        status, text = 'not_declining', 'Reported FCF did not decline between the aligned annual periods.'
    elif delta['ocf'] >= 0 and delta['capex'] < 0:
        status, text = 'capex_increase', 'Reported FCF weakness is arithmetically explained by higher capital expenditure while OCF did not decline.'
    elif delta['ocf'] < 0 and delta['capex'] >= 0:
        status, text = 'ocf_weakness', 'Reported FCF weakness is arithmetically explained by weaker OCF; capital expenditure did not increase.'
    else:
        status, text = 'mixed', 'Both weaker OCF and increased capital expenditure contributed arithmetically to the reported FCF decline.'
    out.update(status=status, attribution='supported', changes=delta, summary=text)
    return out


def arithmetic_bridge(inputs, left, right):
    periods = inputs['periods'][:2]
    out = {'status': 'unknown', 'history': [], 'change_in_adjustment': None,
           'scope': 'No validated arithmetic bridge.'}
    if len(periods) != 2:
        return out
    for p in periods:
        v = p['values']
        if not aligned(v.get(left), v.get(right)):
            return out
        values = {k: f['value'] for k, f in v.items() if f and f['availability'] == 'available'}
        if (left, right) == ('operating_income', 'pretax_income'):
            names = ('other_income',)
            ok = aligned(v.get(left), v.get('other_income')) and close(values[right] - values[left], values['other_income'])
            adjustment = values.get('other_income')
            scope = 'Net other-income subtotal; its components may overlap and are not separately summed.'
        elif (left, right) == ('pretax_income', 'net_income'):
            names = ('income_tax',)
            ok = aligned(v.get(left), v.get('income_tax')) and close(values[left] - values.get('income_tax', 0), values[right])
            adjustment = -values['income_tax'] if 'income_tax' in values else None
            scope = 'Reported tax provision only, contingent on pretax minus tax matching net income.'
        elif (left, right) == ('net_income', 'ocf'):
            names = ('cash_net_income', 'da', 'deferred_tax', 'sbc', 'other_non_cash', 'working_capital')
            ok = aligned(v.get(left), *(v.get(k) for k in names))
            if ok:
                ok = close(values['cash_net_income'], values['net_income']) and close(sum(values[k] for k in names), values['ocf'])
            adjustment = sum(values[k] for k in names[1:]) if ok else None
            scope = 'NI-to-OCF adjustments; working-capital subtotal is counted once, without its overlapping detail rows.'
        else:
            return out
        out['history'].append({'period': p['period'], 'reconciled': bool(ok), 'adjustment': adjustment,
                               'inputs': {k: v.get(k) for k in (left, right, *names)},
                               'residual': values[right] - values[left] - adjustment if adjustment is not None else None})
        out['scope'] = scope
    if all(h['reconciled'] for h in out['history']) and comparable(periods[0]['values'].get(left), periods[1]['values'].get(left)):
        out['status'] = 'supported'
        out['change_in_adjustment'] = out['history'][0]['adjustment'] - out['history'][1]['adjustment']
    return out


def build_attribution(inputs, items, rules=None):
    rules = rules or load_rules()
    growth = growth_decomposition(inputs)
    fcf = fcf_attribution(inputs)
    bridges = []
    for left, right, categories in BRIDGES:
        a, b = growth[left + '_growth'], growth[right + '_growth']
        valid = (a['status'] == b['status'] == 'normal' and aligned(a['current'], b['current'])
                 and aligned(a['previous'], b['previous']))
        gap = (b['value'] - a['value']) * 100 if valid else None
        ends = {f['period'] for f in (a['current'], a['previous']) if f}
        relevant = [e for e in items if e['validation_level'] >= 3 and e['period'] in ends
                    and set(e['categories']) & set(categories)]
        arithmetic = fcf if left == 'ocf' else arithmetic_bridge(inputs, left, right)
        supported = arithmetic.get('attribution', arithmetic.get('status')) == 'supported'
        status = 'supported' if supported else 'partially supported' if relevant else 'unknown'
        summary = ('The reported statement adjustment reconciles both annual periods; this supports arithmetic attribution, not a complete economic explanation.'
                   if supported and left != 'ocf' else fcf['summary'] if left == 'ocf' else
                   'Period-matched evidence is relevant, but no complete validated causal attribution is available.' if relevant else
                   'No validated causal attribution available.')
        bridges.append({'rule_id': 'EQ2-BRIDGE-' + left.upper(), 'rule_version': rules['version'],
                        'from': left, 'to': right, 'gap_pp': gap,
                        'investigation_priority': 'review' if gap is not None and abs(gap) >= rules['gap_pp'] - 1e-10 else 'unknown' if gap is None else 'observation',
                        'attribution': status, 'evidence_strength': 'reconciled_arithmetic' if supported else 'period_matched_evidence' if relevant else 'insufficient',
                        'evidence': [e['evidence_id'] for e in relevant], 'drivers': sorted({c for e in relevant for c in e['categories']}),
                        'arithmetic': arithmetic, 'summary': summary})
    return {'growth': growth, 'bridges': bridges, 'fcf': fcf}
