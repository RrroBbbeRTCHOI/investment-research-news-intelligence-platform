#!/usr/bin/env python3
"""Core Revenue Quality (CRQ) V1 Stage 6 — scoring RUBRIC and stress-test only.

No API calls. No change to production models, scores, historical reports or .env.
The V1 weights below are UNCALIBRATED candidates; synthetic scores are NOT
ratings for AAPL or any MAG7 company. Stage 5 SEC category coverage is NEVER
converted into a purity/recognition score. Outputs are independent audit files.

Run from project root:
    python3 scripts/core_revenue_v1_stage6.py --self-test
    python3 scripts/core_revenue_v1_stage6.py
    python3 scripts/core_revenue_v1_stage6.py --make-evidence-template
"""
import argparse
import copy
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
STAGE5 = OUT / 'aapl_stage5_scoring_readiness.json'
MAG7 = OUT / 'mag7_crq_v1_pilot.json'
WEIGHTS = {'purity': 0.55, 'organic': 0.25, 'recognition': 0.20}
ALTERNATIVE_WEIGHTS = {
    'V1_55_25_20': WEIGHTS,
    'purity_minus10_organic_plus10': {'purity': .45, 'organic': .35, 'recognition': .20},
    'purity_plus10_organic_minus10': {'purity': .65, 'organic': .15, 'recognition': .20},
    'recognition_plus10_purity_minus10': {'purity': .45, 'organic': .25, 'recognition': .30},
    'recognition_plus25_purity_minus25': {'purity': .30, 'organic': .25, 'recognition': .45},
}
TICKERS = ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'META', 'TSLA')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def value(x, label, allow_zero=True):
    require(isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x) and (x >= 0 if allow_zero else x > 0),
            '{} must be a finite {} number'.format(label, 'nonnegative' if allow_zero else 'positive'))
    return float(x)


def evidence_ref(x):
    """Citations are mandatory, not verified automatically from a string."""
    return (isinstance(x, str) and len(x.strip()) >= 10
            and not x.strip().lower().startswith(('test-', 'placeholder', 'todo')))


def reviewed(record, *keys):
    return (isinstance(record, dict) and record.get('analyst_verified') is True
            and all(evidence_ref(record.get(k)) for k in keys))


def weighted_score(parts, weights=WEIGHTS, unresolved_flag=False, material_issue=False):
    """Provisional number only; never silently turn a missing component into 0/100.

    A supported purity score and at least 70% weight coverage are required.
    If recognition is unscored while an AR investigation is unresolved, block
    even provisional publication. A confirmed material recognition issue blocks
    automatic scoring regardless of the arithmetic composite.
    """
    require(abs(sum(weights.values()) - 1) < 1e-9, 'Weights must sum to 1')
    require(set(parts).issubset(weights), 'Unexpected component')
    for k, s in parts.items():
        require(value(s, k) <= 100, 'Component score exceeds 100')
    cov = sum(weights[k] for k in parts)
    base = {'score': None, 'coverage_pct': round(cov * 100, 1), 'status': 'NOT_SCORED'}
    if material_issue:
        base['reason'] = 'Confirmed material recognition issue: manual investigation and model review required.'
    elif unresolved_flag and 'recognition' not in parts:
        base['reason'] = 'Unresolved receivables investigation and unreviewed recognition; composite withheld.'
    elif 'purity' not in parts:
        base['reason'] = 'Core revenue purity is mandatory; classification coverage alone is not purity.'
    elif cov < 0.70 - 1e-9:
        base['reason'] = 'Less than 70% independently assessed component weight.'
    else:
        base['score'] = round(sum(weights[k] * s for k, s in parts.items()) / cov, 2)
        base['status'] = 'EXPERIMENTAL_COMPLETE' if cov >= 1-1e-9 else 'EXPERIMENTAL_PROVISIONAL'
        base['reason'] = ('Candidate rubric only; requires calibration and human sign-off; '
                          'never a production Earnings Quality score.')
    return base


def assess_evidence(evidence, fiscal_year, revenue_usd, unresolved_ar_flag=False,
                    weights=WEIGHTS):
    """Score ONLY explicit, independently reviewer-approved numerical evidence.

    Expected optional evidence shape is in make_evidence_template(). There is no
    automatic classification from products/services, no AR-based numeric penalty,
    no inference of no misstatement from silence and no Gemini-generated score.
    """
    require(isinstance(evidence, dict), 'Evidence must be an object')
    require(evidence.get('fiscal_year') is not None and str(evidence.get('fiscal_year')) == str(fiscal_year), 'Evidence fiscal year mismatch')
    require(evidence.get('analyst_verified') is True, 'Evidence not approved by reviewer')
    reported = value(revenue_usd, 'reported revenue', allow_zero=False)
    parts = {}
    notes = []
    cl = evidence.get('purity')
    if reviewed(cl, 'source_url', 'source_locator', 'classification_policy', 'reviewer_rationale'):
        core = value(cl.get('confirmed_core_revenue_usd'), 'confirmed core revenue')
        noncore = value(cl.get('confirmed_noncore_revenue_usd'), 'confirmed non-core revenue')
        unclassified = value(cl.get('unclassified_revenue_usd'), 'unclassified revenue')
        cited_total = value(cl.get('reported_total_revenue_usd'), 'cited total', allow_zero=False)
        require(abs(cited_total-reported)/reported <= 0.001, 'Purity total and annual revenue mismatch')
        require(abs(core+noncore+unclassified-reported)/reported <= 0.001,
                'Core/noncore/unclassified amounts do not reconcile')
        if unclassified/reported <= 0.001:
            parts['purity'] = 100 * core/reported
        else:
            notes.append('Purity unscored: material unclassified revenue.')
    else:
        notes.append('Purity unscored: explicit approved core/non-core classification missing.')

    og = evidence.get('organic')
    if (reviewed(og, 'source_url', 'source_locator', 'attribution_method', 'reviewer_rationale')
            and 'purity' in parts):
        prev = value(og.get('prior_core_revenue_usd'), 'prior core revenue')
        cur = value(og.get('current_core_revenue_usd'), 'current core revenue')
        org = value(og.get('verified_organic_increment_usd'), 'organic increment')
        acquisition = value(og.get('verified_acquisition_increment_usd'), 'acquisition increment')
        other = value(og.get('verified_other_increment_usd'), 'other increment')
        require(abs(cur - evidence['purity']['confirmed_core_revenue_usd']) / reported <= .001,
                'Organic/current core revenue mismatch')
        change = cur - prev
        if (change > 0 and abs(org+acquisition+other-change)/change <= 0.001):
            parts['organic'] = 100*org/change
        else:
            notes.append('Organic unscored: non-positive growth or offsetting/unreconciled bridge.')
    else:
        notes.append('Organic unscored: complete approved organic/acquisition/other bridge missing.')

    rr = evidence.get('recognition')
    issue = bool(isinstance(rr, dict) and rr.get('confirmed_material_recognition_issue') is True)
    if reviewed(rr, 'source_url', 'source_locator', 'published_rubric_id', 'reviewer_rationale'):
        rri = value(rr.get('documented_reviewer_score'), 'recognition score')
        require(rri <= 100, 'Recognition score exceeds 100')
        # AR gap alone is a flag, never a deduction. An analyst must close
        # the investigation to permit a composite when such a flag exists.
        if not (unresolved_ar_flag and rr.get('ar_investigation_resolved') is not True):
            parts['recognition'] = rri
        else:
            notes.append('Recognition unscored: AR investigation unresolved.')
    else:
        notes.append('Recognition unscored: no approved assessment and documented rubric.')
    result = weighted_score(parts, weights,
                            unresolved_flag=unresolved_ar_flag and not
                            (isinstance(rr, dict) and rr.get('ar_investigation_resolved') is True),
                            material_issue=issue)
    result['components'] = {k: round(v, 3) for k, v in parts.items()}
    result['notes'] = notes
    return result


def make_evidence_template():
    """Blank: no inferred approvals, evidence or scores."""
    item = {
        'analyst_verified': False, 'fiscal_year': None,
        'purity': {'analyst_verified': False, 'source_url': None, 'source_locator': None,
                   'classification_policy': None, 'reviewer_rationale': None,
                   'reported_total_revenue_usd': None,
                   'confirmed_core_revenue_usd': None,
                   'confirmed_noncore_revenue_usd': None,
                   'unclassified_revenue_usd': None},
        'organic': {'analyst_verified': False, 'source_url': None, 'source_locator': None,
                    'attribution_method': None, 'reviewer_rationale': None,
                    'prior_core_revenue_usd': None, 'current_core_revenue_usd': None,
                    'verified_organic_increment_usd': None,
                    'verified_acquisition_increment_usd': None,
                    'verified_other_increment_usd': None},
        'recognition': {'analyst_verified': False, 'source_url': None, 'source_locator': None,
                        'published_rubric_id': None, 'reviewer_rationale': None,
                        'documented_reviewer_score': None,
                        'ar_investigation_resolved': False,
                        'confirmed_material_recognition_issue': False}}
    return {ticker: copy.deepcopy(item) for ticker in TICKERS}


def scenario_parts():
    """These are synthetic archetypes. NEVER assign them to actual tickers."""
    return [
        ('all_dimensions_strong', {'purity': 100, 'organic': 100, 'recognition': 92}, False, False),
        ('moderate_acquisition_contribution', {'purity': 95, 'organic': 66.667, 'recognition': 85}, False, False),
        ('acquisition_led_growth', {'purity': 95, 'organic': 13.333, 'recognition': 70}, False, False),
        ('recognition_zero_but_other_dimensions_max', {'purity': 100, 'organic': 100, 'recognition': 0}, False, False),
        ('unreviewed_recognition_no_flag', {'purity': 98, 'organic': 100}, False, False),
        ('unreviewed_recognition_AR_flag', {'purity': 98, 'organic': 100}, True, False),
        ('no_positive_growth_organic_unknown', {'purity': 94, 'recognition': 80}, False, False),
        ('purity_not_verified', {'organic': 100, 'recognition': 90}, False, False),
        ('confirmed_material_recognition_issue', {'purity': 100, 'organic': 100, 'recognition': 30}, False, True),
    ]


def stress_test():
    rows = []
    for name, parts, flagged, issue in scenario_parts():
        variants = {label: weighted_score(parts, weights, flagged, issue)
                    for label, weights in ALTERNATIVE_WEIGHTS.items()}
        scores = [v['score'] for v in variants.values() if v['score'] is not None]
        base = variants['V1_55_25_20']
        rows.append({
            'scenario': name, 'hypothetical_only': True, 'components': parts,
            'base_score': base['score'], 'coverage_pct': base['coverage_pct'],
            'status': base['status'], 'reason': base['reason'],
            'alternative_scores': {k: r['score'] for k, r in variants.items()},
            'sensitivity_min': min(scores) if scores else None,
            'sensitivity_max': max(scores) if scores else None,
            'sensitivity_span': round(max(scores)-min(scores), 2) if scores else None,
        })
    strong_other_weak_recognition = next(r for r in rows if r['scenario'] == 'recognition_zero_but_other_dimensions_max')
    limitations = [
        'V1 assigns 55% to core-revenue purity: companies with entirely ordinary operating sales can cluster near 100 and the component may not discriminate.',
        'Recognition score 0 still yields V1 overall 80 when purity and organic are 100. The 20% weight can mask a major weakness; do not approve V1 for production without validation/revision.',
        'A large acquired-business contribution is not inherently low-quality revenue. Organic attribution is a descriptive origin measure, not automatically a quality verdict.',
        'Missing recognition data can inflate a renormalized provisional score. Show coverage and never label an incomplete score Very Strong/Strong.',
        'AR growth divergence and year-end AR/revenue proxy trigger inquiry only; they never generate an automatic numerical integrity penalty.',
        'Thresholds and weighting are analyst-designed hypotheses; cross-company evidence and empirical calibration remain outstanding.'
    ]
    require(strong_other_weak_recognition['base_score'] == 80, 'Expected recognition masking diagnostic changed')
    return rows, limitations


def inspect_input(stage5, mag7):
    require(isinstance(stage5, dict) and stage5.get('ticker') == 'AAPL'
            and stage5.get('fiscal_year') == 2025,
            'Stage 5 ticker/FY mismatch; refusing to proceed')
    require(stage5.get('reconciliation', '').startswith('PASS:'), 'Stage 5 not reconciled')
    readiness = stage5.get('scoring_readiness', {})
    require(readiness.get('overall_CRQ_score') is None
            and readiness.get('status') == 'NOT_SCORED',
            'Stage 5 unexpectedly contains a numeric score')
    require(stage5.get('operating_category_coverage_not_score') is True,
            'Stage 5 category coverage must explicitly be non-scoring')
    r = stage5.get('revenue_recognition_diagnostics', {})
    flag = r.get('trade_ar_growth_investigation_flag')
    require(isinstance(flag, bool), 'Missing Stage 5 investigation status')
    require(isinstance(mag7, dict) and isinstance(mag7.get('results'), list),
            'Stage 1 MAG7 file needs results list')
    items = {row['ticker']: row for row in mag7['results']
             if isinstance(row, dict) and row.get('ticker') in TICKERS}
    require(len(items) == len(TICKERS) == len(mag7['results']),
            'MAG7 requires exactly seven distinct tickers; no duplicates/unknown')
    a = items['AAPL']
    require(a.get('fiscal_year') == 2025, 'AAPL Stage 1 vs Stage 5 year mismatch')
    require(a.get('financial_data_available') is True,
            'AAPL Stage 1 annual data missing')
    growth = a.get('revenue_growth_pct')
    require(isinstance(growth, (int, float)) and abs(growth-r.get('revenue_growth_pct')) <= .2,
            'AAPL Stage 1 vs Stage 5 revenue growth mismatch')
    require(all(row.get('crq_score') is None for row in items.values()),
            'Stage 1 contains a numerical CRQ score not approved by this stage')
    readiness_rows = []
    for ticker in TICKERS:
        item = items[ticker]
        readiness_rows.append({
            'ticker': ticker, 'fiscal_year': item.get('fiscal_year'),
            'financial_data_available': item.get('financial_data_available'),
            'periods_aligned': item.get('statement_periods_aligned'),
            'revenue_growth_pct': item.get('revenue_growth_pct'),
            'provider_receivables_growth_pct': item.get('receivables_growth_pct'),
            'provider_AR_definition_warning': 'Do not infer trade AR from FMP normalized receivables.',
            'SEC_category_reconciliation': 'PASS' if ticker == 'AAPL' else 'NOT_YET_REVIEWED',
            'classification_coverage_pct': stage5.get('operating_category_coverage_pct') if ticker == 'AAPL' else None,
            'purity_score': None, 'organic_score': None, 'recognition_score': None,
            'overall_CRQ': None, 'scoring_status': 'NOT_SCORED',
            'unresolved_trade_AR_investigation': flag if ticker == 'AAPL' else None,
        })
    return readiness_rows


def self_test():
    assert abs(sum(WEIGHTS.values())-1) < 1e-10
    rows, issues = stress_test()
    assert len(rows) == 9 and len(issues) >= 5
    assert rows[0]['base_score'] == 98.4
    assert rows[3]['base_score'] == 80
    assert rows[4]['status'] == 'EXPERIMENTAL_PROVISIONAL' and rows[4]['coverage_pct'] == 80
    assert rows[5]['status'] == 'NOT_SCORED'
    assert rows[6]['status'] == 'EXPERIMENTAL_PROVISIONAL' and rows[6]['coverage_pct'] == 75
    assert rows[7]['status'] == 'NOT_SCORED' and rows[8]['status'] == 'NOT_SCORED'
    assert weighted_score({'purity': 100})['score'] is None
    assert weighted_score({'purity': 100, 'recognition': 90})['coverage_pct'] == 75
    for key in WEIGHTS:
        lo = weighted_score({'purity': 65, 'organic': 65, 'recognition': 65})['score']
        inc = {'purity': 65, 'organic': 65, 'recognition': 65}
        inc[key] += 1
        assert weighted_score(inc)['score'] >= lo
    blank = make_evidence_template()['AAPL']
    assert blank['analyst_verified'] is False
    for test in [lambda: assess_evidence(blank, 2025, 416161e6),
                 lambda: assess_evidence(dict(blank, analyst_verified=True, fiscal_year=2024), 2025, 416161e6),
                 lambda: weighted_score({'purity': -1, 'organic': 90}),
                 lambda: weighted_score({'purity': float('nan'), 'organic': 90})]:
        try:
            test()
        except ValueError:
            continue
        raise AssertionError('Invalid/unverified test input accepted')
    # Approved synthetic evidence is used to test arithmetic and gate only.
    ref = 'https://www.sec.gov/Archives/edgar/data/TEST-FIXTURE-123'
    ev = {
        'analyst_verified': True, 'fiscal_year': 2025,
        'purity': {'analyst_verified': True, 'source_url': ref,
                   'source_locator': 'Test synthetic fixture line 10',
                   'classification_policy': 'Synthetic operating/non-operating split',
                   'reviewer_rationale': 'Synthetic independently defined core classification',
                   'reported_total_revenue_usd': 100, 'confirmed_core_revenue_usd': 95,
                   'confirmed_noncore_revenue_usd': 5, 'unclassified_revenue_usd': 0},
        'organic': {'analyst_verified': True, 'source_url': ref,
                    'source_locator': 'Test synthetic fixture line 11',
                    'attribution_method': 'Synthetic reconciled increments',
                    'reviewer_rationale': 'Synthetic attribution',
                    'prior_core_revenue_usd': 80, 'current_core_revenue_usd': 95,
                    'verified_organic_increment_usd': 10,
                    'verified_acquisition_increment_usd': 5,
                    'verified_other_increment_usd': 0},
        'recognition': {'analyst_verified': True, 'source_url': ref,
                        'source_locator': 'Test synthetic fixture line 12',
                        'published_rubric_id': 'SYNTHETIC_TEST_RUBRIC_ONLY',
                        'reviewer_rationale': 'Synthetic documented judgment',
                        'documented_reviewer_score': 85,
                        'ar_investigation_resolved': True,
                        'confirmed_material_recognition_issue': False}}
    result = assess_evidence(ev, 2025, 100)
    assert result['status'] == 'EXPERIMENTAL_COMPLETE'
    assert abs(result['score']-85.92) < .01
    ev['purity']['unclassified_revenue_usd'] = 5
    ev['purity']['confirmed_noncore_revenue_usd'] = 0
    assert assess_evidence(ev, 2025, 100)['score'] is None
    print('STAGE 6 SELF-TEST PASS: synthetic rubric, arithmetic, missing-evidence gates, FY guards, sensitivity and material-issue veto.')


def write_new(path, contents):
    """Never overwrite previous research reports or silently replace a review."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # csv.DictWriter emits CRLF; normalize before comparison for idempotent runs.
    contents = contents.replace('\r\n', '\n')
    if path.exists():
        if path.read_text(encoding='utf-8') == contents:
            print('Unchanged:', path)
            return
        raise ValueError('Existing report differs; refusing to overwrite: {}'.format(path))
    path.write_text(contents, encoding='utf-8')
    print('Saved:', path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--make-evidence-template', action='store_true')
    p.add_argument('--stage5', type=Path, default=STAGE5)
    p.add_argument('--mag7', type=Path, default=MAG7)
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    if a.make_evidence_template:
        path = OUT / 'stage6_evidence_template_UNVERIFIED.json'
        write_new(path, json.dumps(make_evidence_template(), indent=2, ensure_ascii=False)+'\n')
        return
    require(a.stage5.is_file(), 'Missing Stage 5 file: {}'.format(a.stage5))
    require(a.mag7.is_file(), 'Missing MAG7 Stage 1 file: {}'.format(a.mag7))
    stage5 = json.loads(a.stage5.read_text(encoding='utf-8'))
    mag7 = json.loads(a.mag7.read_text(encoding='utf-8'))
    readiness = inspect_input(stage5, mag7)
    scenarios, limitations = stress_test()
    report = {
        'stage': 'CRQ Stage 6: uncalibrated rubric, sensitivity & MAG7 readiness',
        'status': 'DESIGN_UNDER_REVIEW_NOT_PRODUCTION_APPROVED',
        'original_weights': WEIGHTS, 'tested_weights': ALTERNATIVE_WEIGHTS,
        'rubric': {
            'purity': '100 x approved documented core revenue / reconciled reported revenue; requires explicit reviewed core/noncore split; 100% product/segment classification is NOT purity.',
            'organic': '100 x documented organic core-revenue increment / positive total core-revenue increment; positive, fully reconciled bridge only; acquisition growth is not inherently low quality.',
            'recognition': '0-100 reviewer-assigned score under a documented, approved recognition rubric and source-located evidence; NEVER derived mechanically from AR divergence or absence of reported issues.',
            'gates': ['purity independently verified and scored',
                      'at least 70% scored weighted coverage',
                      'unresolved AR investigation plus missing recognition: block score',
                      'confirmed material recognition issue: block automatic score',
                      'same ticker, FY, currency and reconciled revenue periods'],
        },
        'synthetic_scenarios': scenarios,
        'model_risks_and_required_revisions': limitations,
        'MAG7_readiness': readiness,
        'AAPL': {'sec_FMP_reconciled': True,
                 'category_coverage_pct': stage5['operating_category_coverage_pct'],
                 'unresolved_trade_AR_flag': stage5['revenue_recognition_diagnostics']['trade_ar_growth_investigation_flag'],
                 'CRQ_score': None, 'status': 'NOT_SCORED',
                 'reason': 'Category coverage and AR diagnostics do not establish independently verified purity, organic attribution and recognition integrity.'},
        'conclusion': ('The baseline 55/25/20 design is not approved for production: '
                       'purity can be nondiscriminating and a recognition score of zero is masked when other scores are high. '
                       'Resolve/reweight with actual reviewed filings and calibration before adding the sixth Earnings Quality component.'),
        'api_calls': 0, 'production_scoring_modified': False
    }
    jpath = OUT / 'stage6_rubric_and_sensitivity.json'
    cpath = OUT / 'stage6_synthetic_sensitivity.csv'
    rpath = OUT / 'stage6_mag7_readiness.csv'
    write_new(jpath, json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    import io
    sio = io.StringIO()
    cols = ['scenario', 'hypothetical_only', 'base_score', 'coverage_pct', 'status', 'sensitivity_min', 'sensitivity_max', 'sensitivity_span']+list(ALTERNATIVE_WEIGHTS)
    w = csv.DictWriter(sio, fieldnames=cols)
    w.writeheader()
    for s in scenarios:
        w.writerow(dict(dict((k, s.get(k)) for k in cols if k not in ALTERNATIVE_WEIGHTS),
                        **s['alternative_scores']))
    write_new(cpath, sio.getvalue())
    sio = io.StringIO()
    cols = list(readiness[0])
    w = csv.DictWriter(sio, fieldnames=cols)
    w.writeheader()
    w.writerows(readiness)
    write_new(rpath, sio.getvalue())
    print('\nStage 6: synthetic rubric/stress-test COMPLETED; real MAG7 CRQ NOT SCORED.')
    print('AAPL SEC classification: 100% COVERAGE, not a verified purity/quality score.')
    print('V1 MODEL RISK: purity=100, organic=100, recognition=0 => V1 composite 80.')
    print('DECISION: V1 weights/rubric require revision and validation before production use.')
    print('No API calls. No production scoring, source reports or existing model outputs modified.')


if __name__ == '__main__':
    main()
