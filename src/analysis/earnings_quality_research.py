"""Evidence-only V2 synthesis; legacy scores and diagnostic keys remain intact."""
from src.analysis.earnings_quality_research_evidence import normalize_evidence, group_families, load_rules
from src.analysis.earnings_quality_attribution import build_attribution
from src.analysis.earnings_quality_diagnostics import cash_history, close
from src.data.earnings_quality_inputs import aligned, number, iso_date


def roic_history(ticker):
    """Historical context using the unchanged Yahoo OI/(debt+equity) definition."""
    from src.data.financial_data import get_operating_income, get_total_debt, get_equity
    try:
        oi, debt, equity = (loader(ticker) for loader in (get_operating_income, get_total_debt, get_equity))
        if oi is None or debt is None or equity is None or not all(s.index.is_unique for s in (oi, debt, equity)):
            return []
        out = []
        for period, value in oi.items():
            d = number(debt.get(period)); e = number(equity.get(period)); v = number(value)
            denominator = d + e if d is not None and e is not None else None
            ratio = v / denominator if v is not None and denominator is not None and denominator > 0 else None
            out.append({'period': str(period)[:10], 'value': ratio, 'operating_income': v,
                        'debt': d, 'equity': e, 'source': 'Yahoo annual statements',
                        'formula': 'Operating Income / (Total Debt + Shareholders Equity)',
                        'availability': 'available' if ratio is not None else 'unknown'})
        return sorted(out, key=lambda row: row['period'], reverse=True)
    except Exception:
        return []


def roic_trend(history, rules):
    result = {'status': 'unavailable', 'history': history, 'note': 'Historical diagnostic using the legacy formula; not NOPAT/average capital and not a score.'}
    rows = history[:3]
    if len(rows) < 3 or any(r['value'] is None or not iso_date(r['period']) for r in rows):
        return result
    if any(not 350 <= (iso_date(a['period']) - iso_date(b['period'])).days <= 380 for a, b in zip(rows, rows[1:])):
        return result
    changes = [(a['value'] - b['value']) * 100 for a, b in zip(rows, rows[1:])]
    tolerance = rules['roic_stable_pp']
    result['status'] = ('stable' if all(abs(x) <= tolerance for x in changes) else
                        'improving' if all(x >= 0 for x in changes) else
                        'deteriorating' if all(x <= 0 for x in changes) else 'volatile')
    result['changes_pp'] = changes
    return result


def core_revenue(inputs, items, families):
    current = inputs['periods'][0]['period'] if inputs['periods'] else None
    relevant = [e for e in items if 'operating_revenue' in e['categories'] and e['validation_level'] >= 3 and e['period'] == current]
    unusual = [e for e in relevant if set(e['topics']) & {'regulatory_credits', 'unusual_revenue_recognition', 'customer_concentration', 'related_party_transactions'}]
    observations = [f"Period-matched filing evidence discusses {', '.join(e['topics'])}; earnings share and recurrence require separate evidence." for e in relevant]
    return {'status': 'caution' if unusual else 'unknown', 'confidence': 'partial_evidence' if relevant else 'insufficient_evidence',
            'observations': observations, 'unusual_revenue_items': [e['evidence_id'] for e in unusual],
            'evidence': [e['evidence_id'] for e in relevant],
            'limitations': ['No complete segment/product reconciliation or acquired-versus-organic revenue split is available.',
                            'A disclosed recurring revenue category does not prove that total revenue is recurring or core.',
                            'Core Revenue remains excluded from the legacy score.'], 'score': None}


def margin_quality(attribution):
    bridge = attribution['bridges'][0]
    growth = attribution['growth']
    revenue, oi = growth['revenue_growth'], growth['operating_income_growth']
    changes = []
    for side in ('previous', 'current'):
        r, o = revenue[side], oi[side]
        changes.append(o['value'] / r['value'] if aligned(r, o) and r['value'] > 0 else None)
    gap = bridge['gap_pp']
    if None in changes:
        state = 'unknown'
    elif revenue['value'] is not None and revenue['value'] > 0 and oi['current']['value'] < oi['previous']['value']:
        state = 'operating_deterioration_investigation'
    elif gap is not None and bridge['investigation_priority'] == 'review':
        state = 'margin_expansion_investigation' if gap > 0 else 'margin_compression_investigation'
    elif gap is not None:
        state = 'roughly_proportional'
    else:
        state = 'unknown'
    return {'status': state, 'growth_gap_pp': gap, 'prior_margin': changes[0], 'current_margin': changes[1],
            'evidence': bridge['evidence'], 'note': 'Growth/margin comparison only; cost causality and sustainability are not inferred.'}


def working_capital_details(inputs):
    fields = ('receivables', 'inventory', 'payables', 'deferred_revenue_change', 'other_working_capital', 'working_capital', 'deferred_tax', 'tax_paid')
    out = []
    for p in inputs['periods'][:2]:
        v = p['values']
        names = ('receivables', 'inventory', 'payables', 'other_working_capital')
        valid = aligned(v.get('working_capital'), *(v.get(k) for k in names))
        residual = v['working_capital']['value'] - sum(v[k]['value'] for k in names) if valid else None
        out.append({'period': p['period'], 'fields': {k: v.get(k) for k in fields},
                    'tax_related_working_capital': {'value': None, 'availability': 'unknown', 'reason': 'Tax payments/deferred tax do not identify tax-payable working-capital movements.'},
                    'residual': residual, 'reconciliation': 'matched' if residual is not None and close(residual, 0) else 'partial',
                    'note': 'Cash-flow adjustments, not balance-sheet growth. Deferred revenue is not added to an already reported WC subtotal. Tax paid is not a tax-related WC change; that attribution remains unknown.'})
    return out


def build_research(inputs, evidence, roic=None):
    rules = load_rules()
    items = normalize_evidence(inputs, evidence, rules)
    families = group_families(items, rules)
    attribution = build_attribution(inputs, items, rules)
    revenue = core_revenue(inputs, items, families)
    margin = margin_quality(attribution)
    cash = cash_history(inputs)
    current = cash[0] if cash else {'status': 'Unknown'}
    investigations = [b for b in attribution['bridges'] if b['investigation_priority'] == 'review']
    current_end = inputs['periods'][0]['period'] if inputs['periods'] else None
    actual = [e for e in items if e['validation_level'] >= 2 and e['evidence_type'] != 'statement']
    matched = [e for e in actual if e['period'] == current_end and current_end is not None]
    state = 'Concern' if investigations or current['status'] == 'Concern' else 'Caution' if revenue['status'] == 'caution' else 'Unknown / Partial Evidence'
    strengths = ['Aligned operating cash flow supports reported net income under the existing cash/accrual diagnostic.'] if current['status'] == 'Supported' else []
    concerns = [f"{b['from']} → {b['to']} growth differs by {b['gap_pp']:+.1f} pp; {b['summary']}" for b in investigations]
    if revenue['status'] == 'caution':
        concerns.append('Current revenue-related disclosures require review; no complete core-revenue conclusion is available.')
    summary = (' '.join(strengths) if strengths else 'Cash support is ' + current['status'].lower() + ' under the existing aligned diagnostic.')
    if investigations:
        largest = max(investigations, key=lambda b: abs(b['gap_pp']))
        summary += f" The largest observed growth gap is {largest['from']} → {largest['to']} ({largest['gap_pp']:+.1f} pp). {largest['summary']}"
    summary += ' ' + attribution['fcf']['summary']
    summary += f' {len(actual)} actual-event/result evidence records are available, including {len(matched)} matched to the current period; overlapping sources are not independent events.'
    if matched:
        summary += ' Current evidence discusses ' + ', '.join(sorted({c for e in matched for c in e['categories']})) + '; category relevance alone does not establish causation.'
    summary += ' Sustainable underlying earnings remain unproven; no forecast or complete core/non-core allocation is made.'
    return {'rule_version': rules['version'], 'rule_id': 'EQ2-RESEARCH', 'evidence': items,
            'event_families': families, 'attribution': attribution, 'core_revenue': revenue,
            'margin_quality': margin, 'roic_trend': roic_trend(roic or [], rules),
            'working_capital': working_capital_details(inputs),
            'interpretation': {'state': state, 'summary': summary, 'strengths': strengths, 'concerns': concerns,
                'coverage': {'actual_records': len(actual), 'current_period_records': len(matched), 'families': len(families)},
                'limitations': rules['warnings']}}
