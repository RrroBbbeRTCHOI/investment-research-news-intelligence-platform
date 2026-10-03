#!/usr/bin/env python3
"""CRQ Stage 7 — revised experimental policy + evidence-first AAPL/MAG7 review.

No APIs; no edits to existing stage files, .env, rating or production scoring.
The 40/60 candidate weights are NOT empirically calibrated. Organic growth is
shown as attribution context, not a quality penalty. An SEC category bridge is
not automatically an audited Core Revenue Purity score. No scores for MAG7 are
manufactured from missing evidence.

Run from production root:
  python3 scripts/core_revenue_v1_stage7.py --self-test
  python3 scripts/core_revenue_v1_stage7.py
  python3 scripts/core_revenue_v1_stage7.py --make-evidence-template
  python3 scripts/core_revenue_v1_stage7.py --evidence /path/to/independently_reviewed.json
"""
import argparse
import csv
import io
import json
import math
from pathlib import Path

import core_revenue_v1_stage6 as stage6

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
TICKERS = ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'META', 'TSLA')
CANDIDATE_WEIGHTS = {'purity': 0.40, 'recognition': 0.60}


def require(cond, why):
    if not cond:
        raise ValueError(why)


def load(path):
    require(path.is_file(), f'Missing required prior report: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def write_new(path, content):
    """Idempotent; never silently overwrite an existing, changed report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = content.replace('\r\n', '\n')
    if path.exists():
        require(path.read_text(encoding='utf-8') == content,
                f'File already exists with different content; refusing overwrite: {path}')
        print('Unchanged:', path)
        return
    path.write_text(content, encoding='utf-8')
    print('Saved:', path)


def candidate_score(purity=None, recognition=None, *, recognition_reviewed=False,
                    unresolved_ar=False, material_issue=False):
    """Strict gates; an undisclosed recognition issue cannot be masked by purity."""
    components = {'purity': purity, 'recognition': recognition}
    for name, v in components.items():
        if v is not None:
            stage6.value(v, name)
            require(v <= 100, f'{name} must not exceed 100')
    result = {'candidate_score': None, 'status': 'NOT_SCORED',
              'components': components, 'coverage_pct':
              100 * sum(CANDIDATE_WEIGHTS[k] for k, v in components.items() if v is not None),
              'weights': CANDIDATE_WEIGHTS}
    if material_issue:
        result.update(status='MANUAL_REVIEW_REQUIRED',
                      reason='Confirmed material recognition issue; no automatic CRQ score.')
    elif unresolved_ar:
        result['reason'] = 'Trade-AR investigation remains unresolved; not an automatic deduction.'
    elif not recognition_reviewed or recognition is None:
        result['reason'] = 'Source-located, independently reviewed recognition assessment is mandatory.'
    elif recognition < 50:
        result.update(status='MANUAL_REVIEW_REQUIRED',
                      reason='Recognition below experimental 50-point review gate; composite withheld.')
    elif purity is None:
        result['reason'] = 'Independently reviewed operating/non-core revenue split is missing.'
    else:
        result.update(candidate_score=round(.4 * purity + .6 * recognition, 2),
                      status='EXPERIMENTAL_CANDIDATE_NOT_PRODUCTION',
                      reason='Uncalibrated proposal; no official EQ integration or investment rating.')
    result['coverage_pct'] = round(result['coverage_pct'], 1)
    return result


def assess_aapl(stage2, stage5, evidence):
    require(stage2.get('ticker') == stage5.get('ticker') == 'AAPL', 'Ticker mismatch')
    require(stage2.get('fiscal_year') == stage5.get('fiscal_year') == 2025, 'Fiscal year mismatch')
    require(stage2.get('fmp_reconciliation', {}).get('status') == 'MATCH', 'Stage 2 not reconciled')
    require(str(stage5.get('reconciliation', '')).startswith('PASS'), 'Stage 5 not reconciled')
    reported = stage6.value(stage2['revenue_classification']['reported_total_usd'],
                            'SEC reported revenue', allow_zero=False)
    categories = stage2.get('revenue_categories', [])
    require(len(categories) == 5 and abs(sum(c['FY2025_usd_millions'] * 1e6
            for c in categories) - reported) <= reported * .00001,
            'AAPL SEC categories do not reconcile to revenue')
    flagged = stage5.get('revenue_recognition_diagnostics', {}).get('trade_ar_growth_investigation_flag')
    require(isinstance(flagged, bool), 'Stage 5 Trade AR flag missing')

    purity = recognition = None
    organic = {'verified_organic_growth_share_pct': None,
               'status': 'UNKNOWN', 'quality_penalty': None}
    messages = []
    if evidence is None:
        messages.append('No separately reviewed AAPL evidence supplied; all quality dimensions unscored.')
    else:
        require(isinstance(evidence, dict) and evidence.get('ticker') == 'AAPL',
                'Evidence ticker must be AAPL')
        require(str(evidence.get('fiscal_year')) == '2025', 'Evidence fiscal-year mismatch')
        require(evidence.get('analyst_verified') is True,
                'Document has not been independently analyst-reviewed')
        p = evidence.get('purity')
        if stage6.reviewed(p, 'source_url', 'source_locator', 'classification_policy', 'reviewer_rationale'):
            core = stage6.value(p.get('confirmed_core_revenue_usd'), 'confirmed core revenue')
            noncore = stage6.value(p.get('confirmed_noncore_revenue_usd'), 'confirmed non-core revenue')
            unknown = stage6.value(p.get('unclassified_revenue_usd'), 'unclassified revenue')
            total = stage6.value(p.get('reported_total_revenue_usd'), 'classified total')
            require(abs(total - reported) / reported <= .001, 'Purity vs SEC revenue mismatch')
            require(abs(core + noncore + unknown - reported) / reported <= .001,
                    'Core/non-core/unclassified do not reconcile')
            if unknown / reported <= .001:
                purity = round(core / reported * 100, 4)
            else:
                messages.append('Purity withheld: material unclassified revenue.')
        else:
            messages.append('Purity withheld: category coverage alone is NOT verified core purity.')

        r = evidence.get('recognition')
        recognition_reviewed = stage6.reviewed(
            r, 'source_url', 'source_locator', 'published_rubric_id', 'reviewer_rationale')
        material = (isinstance(r, dict) and
                    r.get('confirmed_material_recognition_issue') is True)
        resolved = (isinstance(r, dict) and r.get('ar_investigation_resolved') is True)
        if recognition_reviewed:
            recognition = stage6.value(r.get('documented_reviewer_score'), 'reviewed recognition score')
            require(recognition <= 100, 'Recognition score > 100')
        else:
            messages.append('Recognition unscored: rubric, source and independent review missing.')

        og = evidence.get('organic')
        if (stage6.reviewed(og, 'source_url', 'source_locator',
                            'attribution_method', 'reviewer_rationale') and purity is not None):
            prior = stage6.value(og.get('prior_core_revenue_usd'), 'prior core revenue')
            current = stage6.value(og.get('current_core_revenue_usd'), 'current core revenue')
            org = stage6.value(og.get('verified_organic_increment_usd'), 'organic increment')
            acq = stage6.value(og.get('verified_acquisition_increment_usd'), 'acquisition increment')
            other = stage6.value(og.get('verified_other_increment_usd'), 'other increment')
            require(abs(current - p['confirmed_core_revenue_usd']) / reported <= .001,
                    'Organic vs purity revenue mismatch')
            delta = current - prior
            if delta > 0 and abs(org + acq + other - delta) / delta <= .001 and org <= delta:
                organic.update(status='EVIDENCE_RECONCILED_CONTEXT_ONLY',
                               verified_organic_growth_share_pct=round(100 * org / delta, 2))
            else:
                messages.append('Organic bridge cannot be expressed as a clean positive growth share.')
        else:
            messages.append('Organic attribution is descriptive; missing disclosure does not imply poor quality.')
    if evidence is None:
        recognition_reviewed = material = resolved = False
    scored = candidate_score(
        purity, recognition, recognition_reviewed=recognition_reviewed,
        unresolved_ar=flagged and not resolved, material_issue=material)
    return {'ticker': 'AAPL', 'fiscal_year': 2025, 'reported_revenue_usd': reported,
            'classification_coverage_pct': stage5.get('operating_category_coverage_pct'),
            'classification_is_not_purity': True,
            'trade_ar_growth_investigation_flag': flagged,
            'organic_growth_attribution': organic, 'revised_quality_model': scored,
            'notes': messages, 'model_calibrated': False,
            'production_scoring_modified': False}


def synthetic_cases():
    cases = [
        ('high_purity_high_recognition', 100, 95, True, False, False),
        ('recognition_zero_not_masked', 100, 0, True, False, False),
        ('recognition_below_review_gate', 100, 49, True, False, False),
        ('recognition_at_review_gate', 100, 50, True, False, False),
        ('purity_low_recognition_high', 60, 95, True, False, False),
        ('recognition_missing', 100, None, False, False, False),
        ('purity_missing', None, 95, True, False, False),
        ('AR_investigation_open', 100, 95, True, True, False),
        ('material_recognition_issue', 100, 95, True, False, True),
    ]
    result = []
    for name, p, r, reviewed, flagged, material in cases:
        score = candidate_score(p, r, recognition_reviewed=reviewed,
                                unresolved_ar=flagged, material_issue=material)
        result.append({'scenario': name, 'synthetic_only': True,
                       'purity': p, 'recognition': r,
                       'score': score['candidate_score'], 'status': score['status'],
                       'reason': score['reason']})
    return result


def reviewer_template(stage2):
    """Convenient candidate amounts; explicit review booleans ALWAYS false."""
    template = stage6.make_evidence_template()['AAPL']
    template['ticker'] = 'AAPL'
    template['fiscal_year'] = 2025
    template['purity']['reported_total_revenue_usd'] = stage2['revenue_classification']['reported_total_usd']
    template['candidate_operating_categories_UNVERIFIED'] = [
        {'name': c['name'], 'reported_revenue_usd': c['FY2025_usd_millions'] * 1_000_000,
         'proposed_classification': 'OPERATING_CATEGORY_FOR_REVIEW'}
        for c in stage2.get('revenue_categories', [])]
    template['instructions'] = (
        'Reviewer must verify policy, source location and specific numbers independently. '
        'Do not set analyst_verified merely to force a numeric score. '
        '100% classification coverage alone does not prove transaction integrity. '
        'Recognition score requires a separately approved documented rubric; '
        'AR gap alone is NOT a penalty.')
    return template


def self_test():
    cases = {x['scenario']: x for x in synthetic_cases()}
    assert cases['recognition_zero_not_masked']['score'] is None
    assert cases['recognition_zero_not_masked']['status'] == 'MANUAL_REVIEW_REQUIRED'
    assert cases['recognition_below_review_gate']['score'] is None
    assert cases['recognition_at_review_gate']['score'] == 70
    assert cases['high_purity_high_recognition']['score'] == 97
    assert cases['AR_investigation_open']['score'] is None
    assert cases['material_recognition_issue']['score'] is None
    assert cases['recognition_missing']['score'] is None
    for name in ('recognition', 'purity'):
        data = {'purity': 75, 'recognition': 75}
        result = candidate_score(**data, recognition_reviewed=True)['candidate_score']
        data[name] += 1
        assert candidate_score(**data, recognition_reviewed=True)['candidate_score'] > result
    for bad in (-1, 101, float('nan'), float('inf')):
        try:
            candidate_score(bad, 80, recognition_reviewed=True)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid score was accepted')
    stage2 = {'ticker': 'AAPL', 'fiscal_year': 2025,
              'fmp_reconciliation': {'status': 'MATCH'},
              'revenue_classification': {'reported_total_usd': 100},
              'revenue_categories': [{'name': x, 'FY2025_usd_millions': .00002}
                                     for x in ('iPhone', 'Mac', 'iPad', 'Wearables', 'Services')]}
    stage5 = {'ticker': 'AAPL', 'fiscal_year': 2025, 'reconciliation': 'PASS:',
              'operating_category_coverage_pct': 100,
              'revenue_recognition_diagnostics': {'trade_ar_growth_investigation_flag': True}}
    assert assess_aapl(stage2, stage5, None)['revised_quality_model']['candidate_score'] is None
    unverified = reviewer_template(stage2)
    assert not unverified['analyst_verified']
    try:
        assess_aapl(stage2, stage5, unverified)
    except ValueError:
        pass
    else:
        raise AssertionError('Unverified source accepted')
    print('STAGE 7 SELF-TEST PASS: candidate weights, mandatory recognition, issue gates, '
          'non-scoring organic attribution, FY/reconciliation and no fabricated scores.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--make-evidence-template', action='store_true')
    ap.add_argument('--evidence', type=Path, default=None)
    ap.add_argument('--stage2', type=Path, default=OUT / 'aapl_sec_stage2_review.json')
    ap.add_argument('--stage5', type=Path, default=OUT / 'aapl_stage5_scoring_readiness.json')
    ap.add_argument('--stage6', type=Path, default=OUT / 'stage6_rubric_and_sensitivity.json')
    ap.add_argument('--mag7', type=Path, default=OUT / 'mag7_crq_v1_pilot.json')
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    stage2 = load(args.stage2)
    if args.make_evidence_template:
        path = OUT / 'aapl_stage7_analyst_review_UNVERIFIED.json'
        write_new(path, json.dumps(reviewer_template(stage2), ensure_ascii=False, indent=2) + '\n')
        return
    stage5 = load(args.stage5)
    stage6_report = load(args.stage6)
    mag7 = load(args.mag7)
    require(stage6_report.get('status') == 'DESIGN_UNDER_REVIEW_NOT_PRODUCTION_APPROVED',
            'Stage 6 status not suitable for this revision')
    readiness = stage6.inspect_input(stage5, mag7)
    ev = load(args.evidence) if args.evidence is not None else None
    aapl = assess_aapl(stage2, stage5, ev)
    worklist = []
    for row in readiness:
        ticker = row['ticker']
        worklist.append({
            'ticker': ticker, 'fiscal_year': row['fiscal_year'],
            'SEC_categories_reconciled': ticker == 'AAPL',
            'operating_noncore_classification_approved': False,
            'recognition_rubric_independently_reviewed': False,
            'receivables_definition_reviewed': ticker == 'AAPL',
            'organic_growth_attribution': 'CONTEXT_ONLY_NOT_SCORE',
            'candidate_CRQ': None,
            'next_evidence': ('AAPL: independently approve operating/non-core revenue split; '
                              'investigate Trade AR; document RRI rubric'
                              if ticker == 'AAPL' else
                              'Collect SEC revenue categories, non-core classification, '
                              'trade-AR definition and a documented recognition review')})
    report = {
        'model_version': 'CRQ V1 Stage 7 - experimental redesign NOT production-approved',
        'candidate_weights': CANDIDATE_WEIGHTS,
        'original_weights': stage6.WEIGHTS,
        'reason_for_revision': [
            '55/25/20: an RRI of zero still allowed an 80 composite.',
            'Pure disclosed operating category coverage can cluster near 100.',
            'Low organic share can reflect legitimate acquisitions; attribution is context, not a penalty.'
        ],
        'organic_growth_policy': 'Report independently verified bridge separately; not included in quality score.',
        'recognition_review_gate': 50,
        'recognition_review_gate_empirically_calibrated': False,
        'confirmed_material_recognition_issue': 'Manual review required; no automatic score.',
        'unresolved_trade_AR_flag': 'Block automated score pending review, not an automatic penalty.',
        'AAPL': aapl, 'synthetic_scenarios': synthetic_cases(),
        'MAG7_evidence_worklist': worklist,
        'production_use_approved': False,
        'api_calls': 0, 'production_scoring_modified': False
    }
    suffix = 'stage7_revised_model_review' if ev is None else 'stage7_revised_model_with_reviewed_evidence'
    write_new(OUT / f'{suffix}.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    sio = io.StringIO()
    col = ['scenario', 'synthetic_only', 'purity', 'recognition', 'score', 'status', 'reason']
    writer = csv.DictWriter(sio, col)
    writer.writeheader(); writer.writerows(report['synthetic_scenarios'])
    write_new(OUT / 'stage7_synthetic_scenarios.csv', sio.getvalue())
    sio = io.StringIO()
    col = list(worklist[0])
    writer = csv.DictWriter(sio, col)
    writer.writeheader(); writer.writerows(worklist)
    write_new(OUT / 'stage7_mag7_evidence_worklist.csv', sio.getvalue())
    print('AAPL candidate CRQ:', aapl['revised_quality_model']['candidate_score'],
          '|', aapl['revised_quality_model']['status'])
    print('Model: EXPERIMENTAL 40% purity / 60% recognition; organic attribution CONTEXT ONLY.')
    print('MAG7 official CRQ: NOT SCORED. No APIs or changes to production models.')


if __name__ == '__main__':
    main()
