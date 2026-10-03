"""Deterministic observations, separate from the frozen scoring methodology.

Interpretation v1: growth-gap trigger >= 10 percentage points; not a score rule.
Cash support uses existing cash/accrual boundaries (1.0/0, 0.8/0.03).
Two consecutive comparable annual observations are required for a repeated pattern.
Reconciliation tolerance is numerical only: max(1 currency unit, 1e-6 * scale).
"""
from src.data.earnings_quality_inputs import aligned, comparable
from src.analysis.historical_trends import _calculate_growth

RULE_VERSION = '1.5'
GAP = .10
GAP_EPSILON = 1e-12  # Floating-point boundary tolerance, not an economic threshold.
GROWTH_NAMES = ('revenue', 'operating_income', 'pretax_income', 'net_income', 'ocf', 'fcf')


def close(left, right):
    return abs(left - right) <= max(1., max(abs(left), abs(right)) * 1e-6)


def growth_decomposition(inputs):
    periods = inputs['periods']
    output = {}
    for name in GROWTH_NAMES:
        current = periods[0]['values'].get(name) if periods else None
        previous = periods[1]['values'].get(name) if len(periods) > 1 else None
        valid = comparable(current, previous)
        growth = _calculate_growth(current['value'], previous['value']) if valid else {'value': None, 'status': 'missing'}
        output[name + '_growth'] = {**growth, 'current': current, 'previous': previous,
            'availability': 'available' if valid else 'unknown',
            'period_alignment': 'matched' if valid else 'unknown',
            'reason': None if valid else 'Missing, non-adjacent, duplicate, or incompatible periods/units.',
            'evidence': [f['evidence_id'] for f in (current, previous) if f]}
    return output


def cash_history(inputs):
    history = []
    for period in inputs['periods']:
        values = period['values']
        ni, ocf, assets = (values.get(k) for k in ('net_income', 'ocf', 'assets'))
        conversion = accrual = None
        if aligned(ni, ocf) and ni['value'] != 0:
            conversion = ocf['value'] / ni['value']
        if aligned(ni, ocf, assets) and assets['value'] != 0:
            accrual = (ni['value'] - ocf['value']) / assets['value']
        status = 'Unknown'
        reason = 'Aligned NI, OCF and positive assets are required for interpretation.'
        if aligned(ni, ocf) and ni['value'] <= 0:
            reason = 'Non-positive earnings: cash-conversion ratio does not establish support.'
        elif conversion is not None and accrual is not None and assets['value'] > 0:
            reason = None
            if conversion >= 1 and accrual <= 0:
                status = 'Supported'
            elif conversion < .8 or accrual > .03:
                status = 'Concern'
            else:
                status = 'Mixed'
        history.append({'period': period['period'], 'cash_conversion': conversion, 'accrual_ratio': accrual,
                        'status': status, 'reason': reason,
                        'availability': 'available' if status != 'Unknown' else 'partial',
                        'cash_conversion_availability': 'available' if conversion is not None else 'unknown',
                        'accrual_availability': 'available' if accrual is not None else 'unknown',
                        'inputs': {k: values.get(k) for k in ('net_income', 'ocf', 'assets')},
                        'evidence': [f['evidence_id'] for f in (ni, ocf, assets) if f]})
    return history


def working_capital(inputs):
    periods = []
    required = ('cash_net_income', 'net_income', 'da', 'deferred_tax', 'sbc', 'other_non_cash',
                'working_capital', 'receivables', 'inventory', 'payables', 'other_working_capital',
                'ocf', 'fcf', 'capex')
    for period in inputs['periods'][:2]:
        v = period['values']
        ok = aligned(*(v.get(k) for k in required))
        residuals = {}
        if ok:
            x = {k: v[k]['value'] for k in required}
            wc_sum = sum(x[k] for k in ('receivables', 'inventory', 'payables', 'other_working_capital'))
            ocf_sum = sum(x[k] for k in ('cash_net_income', 'da', 'deferred_tax', 'sbc', 'other_non_cash', 'working_capital'))
            residuals = {'wc': x['working_capital'] - wc_sum, 'ocf': x['ocf'] - ocf_sum,
                         'fcf': x['fcf'] - x['ocf'] - x['capex']}
            ok = (x['capex'] <= 0 and close(x['cash_net_income'], x['net_income'])
                  and close(x['working_capital'], wc_sum) and close(x['ocf'], ocf_sum)
                  and close(x['fcf'], x['ocf'] + x['capex']))
        periods.append({'period': period['period'], 'details': {k: v.get(k) for k in required},
                        'reconciliation': 'matched' if ok else 'incomplete', 'residuals': residuals,
                        'evidence': [v[k]['evidence_id'] for k in required if v.get(k)]})
    complete = (len(periods) == 2 and all(p['reconciliation'] == 'matched' for p in periods)
                and comparable(periods[0]['details']['ocf'], periods[1]['details']['ocf']))
    delta = None
    if complete:
        delta = {k: periods[0]['details'][k]['value'] - periods[1]['details'][k]['value']
                 for k in ('ocf', 'fcf', 'capex', 'working_capital')}
    return {'availability': 'available' if complete else 'partial', 'periods': periods, 'changes': delta,
            'reconciliation': 'matched' if complete else 'incomplete',
            'reason': None if complete else 'The annual NI-to-OCF, WC-detail or OCF-to-FCF bridge is incomplete or incompatible.'}


def diagnosis(rule, kind, severity, statement, used, evidence, status='available', reason=None):
    return {'rule_id': rule, 'rule_version': RULE_VERSION, 'type': kind, 'severity': severity,
            'statement': statement, 'inputs': used, 'evidence': evidence, 'availability': status,
            'confidence': 'traceable_observation' if status == 'available' else 'insufficient_evidence',
            'reason': reason}


def build_diagnostics(inputs, non_core):
    growth = growth_decomposition(inputs)
    cash = cash_history(inputs)
    wc = working_capital(inputs)
    out = []
    c = cash[0] if cash else {'status': 'Unknown', 'reason': 'No annual inputs.', 'inputs': {}, 'evidence': []}
    cash_text = {
        'Supported': 'Operating cash flow covers reported net income and the aligned accrual ratio is non-positive.',
        'Concern': 'Cash conversion or accruals fall in the documented cash-support concern range; investigate the earnings-to-cash difference.',
        'Mixed': 'Cash conversion and accruals provide mixed support under the documented V1 rules.',
        'Unknown': 'Cash support cannot be concluded from the available aligned inputs.'}[c['status']]
    if c['status'] == 'Unknown' and c.get('cash_conversion') is not None:
        cash_text += (f" Observed OCF / NI is {c['cash_conversion']:.2f}x for {c['period']}; "
                      'this observation does not resolve the missing accrual or non-positive-earnings limitation.')
    out.append(diagnosis('EQ-CASH-01', 'cash_support', c['status'].lower(), cash_text,
                         c['inputs'], c['evidence'], 'unknown' if c['status'] == 'Unknown' else 'available', c['reason']))
    # Cross-metric comparisons require common period metadata, not just six individually valid growth rates.
    cross = (all(growth[k + '_growth']['status'] == 'normal' for k in GROWTH_NAMES)
             and aligned(*(growth[k + '_growth']['current'] for k in GROWTH_NAMES))
             and aligned(*(growth[k + '_growth']['previous'] for k in GROWTH_NAMES)))
    # A missing FCF series must not suppress a valid NI/operating comparison.
    pairs = {'ni_vs_oi': ('net_income', 'operating_income'),
             'pretax_vs_oi': ('pretax_income', 'operating_income'),
             'ni_vs_ocf': ('net_income', 'ocf'), 'fcf_vs_oi': ('fcf', 'operating_income')}
    gaps, comparisons = {}, {}
    for key, (left, right) in pairs.items():
        l, r = growth[left + '_growth'], growth[right + '_growth']
        valid = (l['status'] == r['status'] == 'normal'
                 and aligned(l['current'], r['current']) and aligned(l['previous'], r['previous']))
        gaps[key] = l['value'] - r['value'] if valid else None
        comparisons[key] = {'value': gaps[key], 'availability': 'available' if valid else 'unknown',
                            'reason': None if valid else 'Missing, turnaround, N/M or incompatible pair.',
                            'evidence': l['evidence'] + r['evidence']}
    earnings_keys = ('ni_vs_oi', 'pretax_vs_oi', 'ni_vs_ocf')
    gap_concern = any(gaps[k] is not None and gaps[k] >= GAP - GAP_EPSILON for k in earnings_keys)
    valid_count = sum(gaps[k] is not None for k in earnings_keys)
    labels = {'ni_vs_oi': 'NI minus operating-income growth',
              'pretax_vs_oi': 'Pretax minus operating-income growth', 'ni_vs_ocf': 'NI minus OCF growth'}
    text = ' '.join(f"{labels[k]}: {gaps[k] * 100:.1f} pp." if gaps[k] is not None
                    else f"{labels[k]}: insufficient evidence." for k in earnings_keys)
    if valid_count:
        text += (' At least one gap reaches the 10 pp investigation trigger.' if gap_concern
                 else ' No 10 pp upward gap was triggered in the available comparisons.')
    text += ' These comparisons do not establish non-core or tax causality.'
    out.append(diagnosis('EQ-GROWTH-01', 'earnings_growth', 'concern' if gap_concern else 'observation' if valid_count else 'unknown',
                         text, {'growth': growth, 'gaps': gaps, 'comparisons': comparisons, 'trigger_pp': 10},
                         [e for v in growth.values() for e in v['evidence']],
                         'available' if valid_count == 3 else 'partial' if valid_count else 'unknown',
                         None if valid_count == 3 else 'Some comparisons lack normal aligned annual inputs.'))
    material = [e for e in non_core.get('validated_events', [])
                if e.get('weight') is not None and e['materiality'] in ('Material', 'Highly Material')]
    # Historical SEC facts stay visible, but must match the current statement
    # denominator before influencing its summary. Do not mix fiscal snapshots.
    current_pretax = growth['pretax_income_growth']['current']
    sec_pretax = non_core.get('pretax_evidence', {})
    evidence_current = bool(current_pretax and current_pretax['availability'] == 'available'
                            and current_pretax['currency'] == 'USD'
                            and current_pretax['period'] == sec_pretax.get('end')
                            and sec_pretax.get('value') is not None
                            and close(current_pretax['value'], sec_pretax['value']))
    current_material = bool(material) and evidence_current
    scoped_coverage = non_core['coverage'] == 'reconciled_nonoperating_scope'
    if material:
        text = 'Validated matched-period items are material relative to pretax income: ' + ', '.join(
            f"{e['topic']} ({e['signed_contribution'] * 100:+.1f}%, {e['direction']})" for e in material)
        text += '. Coverage remains limited; filing-period materiality alone does not explain year-over-year growth.'
        if not evidence_current:
            text += ' This filing does not reconcile to the current diagnostic period/denominator; it is historical evidence only.'
        severity, status, reason = 'concern', 'available', None
    elif scoped_coverage:
        text = 'No identified item reaches the existing materiality threshold within the reconciled non-operating table scope; unusual operating items and recurrence remain outside this conclusion.'
        severity, status, reason = 'observation', 'available', None
    else:
        text = 'Insufficient evidence to conclude that non-core earnings are immaterial. No validated material item in the available subset establishes a clean result.'
        severity, status, reason = 'unknown', 'unknown', non_core['reason']
    out.append(diagnosis('EQ-NONCORE-01', 'non_core_evidence', severity, text,
                         {'validated_events': non_core.get('validated_events', []), 'coverage': non_core['coverage'], 'current_period_match': evidence_current},
                         non_core['evidence'], status, reason))
    fcf_available = gaps['fcf_vs_oi'] is not None
    fcf_gap = fcf_available and abs(gaps['fcf_vs_oi']) >= GAP - GAP_EPSILON
    text = (f"FCF growth minus operating-income growth: {gaps['fcf_vs_oi'] * 100:.1f} pp. " if fcf_available else 'FCF growth comparison is unavailable. ')
    if fcf_gap:
        text += 'Cash flow trend requires further review: the absolute growth difference reaches 10 pp. '
    if wc['changes'] is not None:
        d = wc['changes']
        text += (f"The reconciled bridge shows changes of {d['ocf']:,.0f} in OCF, {d['capex']:,.0f} in signed CapEx "
                 f"and {d['working_capital']:,.0f} in the cash-flow working-capital adjustment. "
                 'These are cash-flow arithmetic contributions, not proof of structural improvement or temporary timing.')
    else:
        text += 'The working-capital bridge is incomplete; no causal attribution is made.'
    out.append(diagnosis('EQ-FCF-01', 'fcf_support', 'caution' if fcf_gap else 'observation' if fcf_available or wc['changes'] else 'unknown',
                         text, {'growth_gap': gaps.get('fcf_vs_oi'), 'working_capital': wc},
                         comparisons['fcf_vs_oi']['evidence'] + [e for p in wc['periods'] for e in p['evidence']],
                         'available' if wc['changes'] else 'partial', wc['reason']))
    repeated_cash = (len(cash) >= 2 and all(p['status'] == 'Supported' for p in cash[:2])
                     and comparable(cash[0]['inputs']['net_income'], cash[1]['inputs']['net_income']))
    concern = gap_concern or c['status'] == 'Concern' or current_material
    # Production coverage is deliberately incomplete; no automatic all-clear from a finite keyword search.
    scoped_support = (repeated_cash and cross and not gap_concern and not material and scoped_coverage
                      and non_core.get('pretax_evidence', {}).get('end') == c.get('period')
                      and growth['pretax_income_growth']['current']['currency'] == 'USD'
                      and close(growth['pretax_income_growth']['current']['value'], non_core['pretax_evidence']['value'])
                      and close(growth['operating_income_growth']['current']['value'], non_core['operating_evidence']['value']))
    sustainability = 'Concern' if concern else 'Supported' if scoped_support else 'Mixed' if c['status'] == 'Mixed' else 'Unknown / Insufficient Evidence'
    strengths = [cash_text] if c['status'] == 'Supported' else []
    if repeated_cash:
        strengths.append('Cash-support conditions are satisfied in two adjacent annual observations; this is historical support, not a forecast.')
    concerns = [d['statement'] for d in out if d['severity'] in ('concern', 'caution')]
    summary = ' '.join([cash_text, text if fcf_gap else '',
                        'Headline earnings/cash growth warrants investigation.' if gap_concern else '',
                        'Validated material non-core items match the current denominator and require review.' if current_material else '',
                        'Historical cash and growth support are consistent within the reconciled non-operating scope; this is not a forecast or proof that operating earnings contain no unusual items.' if scoped_support else 'A complete underlying-earnings conclusion remains unavailable; the evidence does not justify an all-clear.']).strip()
    return {'growth_decomposition': growth, 'cash_support': {'current': c, 'history': cash},
            'working_capital': wc, 'diagnostics': out,
            'interpretation': {'summary': summary, 'strengths': strengths, 'concerns': concerns,
                'sustainability': sustainability, 'availability': 'partial',
                'reason': 'Limited historical assessment; no forecast, recurrence assumption or complete non-core coverage.',
                'rule_version': RULE_VERSION}}
