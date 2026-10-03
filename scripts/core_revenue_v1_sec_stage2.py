#!/usr/bin/env python3
"""CRQ V1, stage 2: SEC-anchored AAPL FY2025 evidence/reconciliation.

READ-ONLY for existing application/models. Reads the prior MAG7 pilot JSON;
creates a separate SEC review report and an UNVERIFIED pilot evidence candidate.

From repository root (after copying this script to scripts/):
  PYTHONPATH="$PWD" python3 scripts/core_revenue_v1_sec_stage2.py --self-test
  PYTHONPATH="$PWD" python3 scripts/core_revenue_v1_sec_stage2.py

This script is a deliberate, scope-limited AAPL pilot, NOT an automatic SEC
parser or completed MAG7 CRQ scorer. Filing facts below were transcribed from
Apple 2025 Form 10-K; see SOURCE and page locators, independently review.
"""
import argparse
import json
import math
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
SOURCE = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'

# SEC reported USD millions. Apple FY2025 Form 10-K, p.23 (PDF page 27),
# Products & Services Performance; cross-check Note 2 p.36 (PDF page 40).
CATEGORY_REVENUE_M = {
    'iPhone': (209586, 201183),
    'Mac': (33708, 29984),
    'iPad': (28023, 26694),
    'Wearables, Home and Accessories': (35686, 37005),
    'Services': (109158, 96169),
}
SEC_REVENUE_M = {2025: 416161, 2024: 391035}
SOURCE_LOCATORS = {
    'category_revenue': 'Apple FY2025 10-K, Item 7, Products and Services Performance, p.23 (PDF p.27)',
    'consolidated_revenue': 'Apple FY2025 10-K, Consolidated Statements of Operations, p.30 (PDF p.34)',
    'recognition_policy': 'Apple FY2025 10-K, Note 2 - Revenue, pp.35-36 (PDF pp.39-40)',
}


def fail(message):
    raise ValueError(message)


def verify_internal_sec():
    for yr, i in ((2025, 0), (2024, 1)):
        total = sum(row[i] for row in CATEGORY_REVENUE_M.values())
        if total != SEC_REVENUE_M[yr]:
            fail(f'SEC FY{yr} category sums differ: {total} vs {SEC_REVENUE_M[yr]}')


def snapshot_record(path):
    try:
        content = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        fail(f'MAG7 pilot report not found: {path}\nFirst run: PYTHONPATH="$PWD" python3 scripts/core_revenue_v1_pilot.py')
    results = content.get('results') if isinstance(content, dict) else None
    if not isinstance(results, list):
        fail('MAG7 pilot JSON has no results list.')
    candidates = [r for r in results if isinstance(r, dict) and r.get('ticker') == 'AAPL']
    if len(candidates) != 1:
        fail('Expected exactly one AAPL record in MAG7 report.')
    return candidates[0]


def verify_snapshot(row):
    if row.get('fiscal_year') != 2025:
        fail(f'FY mismatch: FMP FY{row.get("fiscal_year")} is not the FY2025 10-K. Refusing to score.')
    if row.get('currency') != 'USD' or row.get('period_end') != '2025-09-27':
        fail(f'Wrong FMP period/currency: {row.get("period_end")}, {row.get("currency")}')
    actual = row.get('revenue')
    prior = row.get('prior_revenue')
    if not isinstance(actual, (int, float)) or not math.isfinite(actual) or actual <= 0:
        fail('Missing/invalid AAPL FMP FY2025 consolidated revenue.')
    if not isinstance(prior, (int, float)) or not math.isfinite(prior) or prior <= 0:
        fail('Missing/invalid AAPL FMP FY2024 consolidated revenue.')
    # Strict reconciliation for these annual consolidated amounts; FMP reports USD.
    for yr, got in ((2025, actual), (2024, prior)):
        target = SEC_REVENUE_M[yr] * 1_000_000
        if abs(got - target) / target > 0.0001:
            fail(f'FMP/SEC FY{yr} revenue mismatch: ${got/1e9:.6f}B vs ${target/1e9:.6f}B')
    return actual, prior


def generate(row):
    verify_internal_sec()
    actual, prior = verify_snapshot(row)
    categories = []
    for name, (current, previous) in CATEGORY_REVENUE_M.items():
        categories.append({
            'name': name, 'FY2025_usd_millions': current,
            'FY2024_usd_millions': previous,
            'FY2025_share_of_consolidated_pct': round(100*current/SEC_REVENUE_M[2025], 3),
            'FY2025_yoy_growth_pct': round(100*(current/previous-1), 3),
            'business_classification': 'reported_operating_products_or_services',
            'source_url': SOURCE, 'source_locator': SOURCE_LOCATORS['category_revenue'],
        })
    # IMPORTANT: 'classified operating' is NOT proof of transaction-level purity
    # or absence of one-off revenue within the disclosed categories.
    documented_operating_total = sum(row['FY2025_usd_millions'] for row in categories)
    coverage = 100.0 * documented_operating_total / SEC_REVENUE_M[2025]
    observations = [
        {'topic': 'policy', 'finding': 'Products: control generally transfers on shipment; Services: recognition over time as delivered.',
         'source_locator': SOURCE_LOCATORS['recognition_policy']},
        {'topic': 'bundled_services', 'finding': 'Revenue is allocated using relative stand-alone selling prices; bundled-service portion is deferred.',
         'source_locator': SOURCE_LOCATORS['recognition_policy']},
        {'topic': 'third_party_apps', 'finding': 'App Store third-party applications are reported net, with Services sales representing retained commission.',
         'source_locator': SOURCE_LOCATORS['recognition_policy']},
        {'topic': 'receivables', 'finding': 'Prior MAG7 pilot receivables-growth divergence is an investigation signal, not proof of incorrect recognition.',
         'source_locator': 'MAG7 pilot FMP period-aligned balance/income statements'},
    ]
    report = {
        'model': 'CRQ V1 - stage 2 SEC evidence pilot',
        'ticker': 'AAPL', 'fiscal_year': 2025, 'currency': 'USD',
        'source_url': SOURCE, 'source_locators': SOURCE_LOCATORS,
        'fmp_reconciliation': {
            'FY2025_FMP_usd': actual, 'FY2025_SEC_usd': SEC_REVENUE_M[2025]*1_000_000,
            'FY2024_FMP_usd': prior, 'FY2024_SEC_usd': SEC_REVENUE_M[2024]*1_000_000,
            'status': 'MATCH',
        },
        'revenue_categories': categories,
        'revenue_classification': {
            'reported_total_usd': SEC_REVENUE_M[2025]*1_000_000,
            'documented_operating_categories_usd': documented_operating_total*1_000_000,
            'disclosure_classification_coverage_pct': round(coverage, 2),
            'provisional_core_revenue_purity_pct': round(coverage, 2),
            'qualifier': 'All five disclosed categories are ordinary operating products/services. This is classification-level coverage, not transaction-level validation or evidence that every dollar is non-recurring-free.',
        },
        'organic_growth_attribution': {
            'status': 'NOT_SCORED',
            'reason': 'This filing alone does not disclose a verified, quantified organic-vs-acquired revenue-growth bridge.',
        },
        'revenue_recognition_integrity': {
            'status': 'NOT_SCORED', 'score': None,
            'observations': observations,
            'reason': 'Disclosure of accounting policy is not proof of compliance or a numeric integrity score; further evidence/rubric required.',
        },
        'CRQ_overall_score': None,
        'CRQ_status': 'NOT_SCORED',
        'scoring_note': 'Do not promote this candidate to an official Earnings Quality subscore: the mandatory audit/rubric sign-off and >=70% component scoring coverage have not been met.',
        'receivables_growth_pct': row.get('receivables_growth_pct'),
        'revenue_growth_pct': row.get('revenue_growth_pct'),
    }
    # Compatible with core_revenue_v1_pilot.py --evidence JSON schema.
    # analyst_verified stays False by design. Even after human sign-off, only
    # purity (55% coverage) is available; the pilot cannot emit overall CRQ.
    candidate = {'AAPL': {
        'analyst_verified': False, 'fiscal_year': 2025,
        'disclosed_total_revenue': SEC_REVENUE_M[2025]*1_000_000,
        'core_revenue': documented_operating_total*1_000_000,
        'core_revenue_source': SOURCE + ' ; ' + SOURCE_LOCATORS['category_revenue'],
        'prior_core_revenue': SEC_REVENUE_M[2024]*1_000_000,
        'organic_core_revenue_increment': None, 'organic_growth_source': None,
        'revenue_recognition_score': None, 'recognition_review_source': None,
        'recognition_scoring_method': None,
        'caveat': 'SEC-reconciled operating-category classification only. Analyst must review before marking verified. Organic and recognition components not scored.'
    }}
    return report, candidate


def self_test():
    synthetic = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD','period_end':'2025-09-27',
                 'revenue':416161000000, 'prior_revenue':391035000000,
                 'revenue_growth_pct':6.4,'receivables_growth_pct':10.1}
    report, candidate = generate(synthetic)
    assert len(report['revenue_categories']) == 5
    assert report['fmp_reconciliation']['status'] == 'MATCH'
    assert report['revenue_classification']['disclosure_classification_coverage_pct'] == 100
    assert report['CRQ_overall_score'] is None
    assert candidate['AAPL']['analyst_verified'] is False
    try:
        generate(dict(synthetic, revenue=400000000000))
    except ValueError:
        pass
    else:
        raise AssertionError('FMP/SEC mismatch was not rejected')
    try:
        generate(dict(synthetic, fiscal_year=2026))
    except ValueError:
        pass
    else:
        raise AssertionError('period mismatch was not rejected')
    print('STAGE 2 SELF-TEST PASS: 5 categories; FMP reconciliation; period/mismatch refusal; no fabricated overall CRQ.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--snapshot', type=Path, default=OUT/'mag7_crq_v1_pilot.json', help='Prior stage-1 MAG7 JSON')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    report, candidate = generate(snapshot_record(args.snapshot))
    OUT.mkdir(parents=True, exist_ok=True)
    report_file = OUT/'aapl_sec_stage2_review.json'
    candidate_file = OUT/'aapl_sec_evidence_UNVERIFIED.json'
    for file, payload in ((report_file, report), (candidate_file, candidate)):
        if file.exists():
            fail(f'Output exists; refusing to overwrite review file: {file}')
        file.write_text(json.dumps(payload, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print('AAPL FY2025 SEC / FMP reconciliation: MATCH')
    print('SEC operating-category classification coverage: 100.0% (five categories)')
    print('Organic Growth Attribution: NOT SCORED')
    print('Revenue Recognition Integrity: NOT SCORED')
    print('Overall CRQ: NOT SCORED (do not treat coverage as a quality verdict)')
    print('Saved:', report_file)
    print('Saved:', candidate_file)
    print('Production models / scoring files / original MAG7 report: UNCHANGED')


if __name__ == '__main__':
    main()
