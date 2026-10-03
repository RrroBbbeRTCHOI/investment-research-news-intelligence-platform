#!/usr/bin/env python3
"""CRQ V1 Stage 3: AAPL FY2025 quantitative revenue bridge (READ-ONLY).

Consumes the existing local outputs of Stage 1 and Stage 2; makes NO API calls;
does not change production scoring, Rating, Earnings Quality or existing reports.

Run from project root after placing this file in scripts/:
    python3 scripts/core_revenue_v1_stage3.py --self-test
    python3 scripts/core_revenue_v1_stage3.py

A SEC-classified operating-category share of 100% is NOT proof that each
transaction is organic, recurring or correctly recognized. No overall CRQ
score is created without the necessary evidence/rubric.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
STAGE1 = OUT / 'mag7_crq_v1_pilot.json'
STAGE2 = OUT / 'aapl_sec_stage2_review.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(value, name):
    require(not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value), f'Invalid or missing {name}')
    return float(value)


def get_aapl(snapshot):
    results = snapshot.get('results') if isinstance(snapshot, dict) else None
    require(isinstance(results, list), 'Stage 1 JSON is missing results list')
    matches = [x for x in results if isinstance(x, dict) and x.get('ticker') == 'AAPL']
    require(len(matches) == 1, 'Stage 1 must have exactly one AAPL row')
    return matches[0]


def calculate(stage1: dict, stage2: dict):
    row = get_aapl(stage1)
    require(stage2.get('ticker') == 'AAPL' and stage2.get('fiscal_year') == 2025,
            'Stage 2 is not AAPL FY2025')
    require(row.get('fiscal_year') == 2025 and row.get('period_end') == '2025-09-27'
            and row.get('currency') == 'USD' and row.get('statement_periods_aligned') is True,
            'Stage 1 AAPL annual period/currency alignment failed')
    recon = stage2.get('fmp_reconciliation', {})
    require(recon.get('status') == 'MATCH', 'Stage 2 FMP/SEC reconciliation failed')
    current = numeric(recon.get('FY2025_SEC_usd'), 'FY2025 SEC revenue')
    prior = numeric(recon.get('FY2024_SEC_usd'), 'FY2024 SEC revenue')
    require(current > prior > 0, 'Stage 3 growth-contribution bridge requires positive total increment')
    for year, sec, key in ((2025, current, 'revenue'), (2024, prior, 'prior_revenue')):
        fmp = numeric(row.get(key), f'Stage 1 FY{year} FMP revenue')
        require(abs(fmp - sec) / sec < 0.0001, f'Stage 1 and Stage 2 FY{year} revenue mismatch')
    source = stage2.get('source_url')
    require(isinstance(source, str) and source.startswith('https://www.sec.gov/'),
            'Stage 2 missing SEC source URL')
    category_rows = stage2.get('revenue_categories')
    require(isinstance(category_rows, list) and len(category_rows) == 5,
            'Exactly five source-backed revenue categories required')
    total_change = current - prior
    categories = []
    names = set()
    for entry in category_rows:
        name = entry.get('name')
        require(isinstance(name, str) and name.strip() and name not in names,
                'Blank or duplicate category name')
        names.add(name)
        require(entry.get('source_url') == source and entry.get('source_locator'),
                f'Uncited revenue category: {name}')
        current_m = numeric(entry.get('FY2025_usd_millions'), f'{name} FY2025')
        prior_m = numeric(entry.get('FY2024_usd_millions'), f'{name} FY2024')
        require(current_m >= 0 and prior_m > 0, f'Invalid category amounts: {name}')
        curr_usd, prev_usd = current_m * 1_000_000, prior_m * 1_000_000
        change = curr_usd - prev_usd
        categories.append({
            'name': name,
            'FY2024_usd': int(prev_usd),
            'FY2025_usd': int(curr_usd),
            'revenue_delta_usd': int(change),
            'FY2025_revenue_share_pct': round(curr_usd / current * 100, 3),
            'category_yoy_growth_pct': round(change / prev_usd * 100, 3),
            'contribution_to_consolidated_growth_pp': round(change / prior * 100, 3),
            'share_of_net_revenue_increment_pct': round(change / total_change * 100, 3),
            'source_url': source,
            'source_locator': entry['source_locator'],
        })
    require(abs(sum(c['FY2025_usd'] for c in categories) - current) < 1,
            'FY2025 category totals do not match SEC consolidated revenue')
    require(abs(sum(c['FY2024_usd'] for c in categories) - prior) < 1,
            'FY2024 category totals do not match SEC consolidated revenue')
    require(abs(sum(c['revenue_delta_usd'] for c in categories) - total_change) < 1,
            'Category growth bridge does not match SEC total growth')
    classification = stage2.get('revenue_classification', {})
    operating = numeric(classification.get('documented_operating_categories_usd'),
                        'Stage 2 disclosed operating-category amount')
    require(abs(operating - current) < 1, 'Stage 2 operating-category coverage mismatch')
    arg = row.get('receivables_growth_pct')
    rg = row.get('revenue_growth_pct')
    if arg is not None and rg is not None:
        arg = numeric(arg, 'AR growth')
        rg = numeric(rg, 'FMP revenue growth')
        delta_pp = round(arg - rg, 2)
        ar_diagnostic = ('Investigate receivables growth vs revenue; this is not proof of revenue misstatement.'
                         if delta_pp > 10 else
                         'No >10 pp receivables-growth divergence under the existing pilot flag; not an integrity verdict.')
    else:
        delta_pp, ar_diagnostic = None, 'Receivables growth not available.'
    categories_by_increment = sorted(categories,
        key=lambda x: x['revenue_delta_usd'], reverse=True)
    lead = categories_by_increment[0]
    lead_contribution = lead['share_of_net_revenue_increment_pct']
    report = {
        'model': 'CRQ V1 - Stage 3 Quantitative Revenue Bridge (not a CRQ score)',
        'ticker': 'AAPL', 'fiscal_year': 2025, 'currency': 'USD',
        'source_url': source,
        'reconciliation': {'SEC_vs_FMP': 'MATCH', 'FY2024_revenue_usd': int(prior),
                           'FY2025_revenue_usd': int(current),
                           'revenue_delta_usd': int(total_change),
                           'revenue_growth_pct': round(total_change / prior * 100, 3),
                           'category_bridge': 'MATCH'},
        'categories': categories,
        'disclosed_operating_revenue_share_pct': 100.0,
        'disclosure_classification_coverage_pct': 100.0,
        'revenue_growth_lead': {'category': lead['name'],
                                'revenue_delta_usd': lead['revenue_delta_usd'],
                                'share_of_net_revenue_increment_pct': lead_contribution},
        'recognition_diagnostic': {'receivables_growth_pct': arg,
                                   'revenue_growth_pct': rg,
                                   'receivables_minus_revenue_growth_pp': delta_pp,
                                   'observation': ar_diagnostic,
                                   'revenue_recognition_policy_source': stage2.get('source_locators', {}).get('recognition_policy')},
        'subcomponents': {
            'core_revenue_purity': {'score': None, 'status': 'NOT_SCORED',
                'classification_level_operating_revenue_share_pct': 100.0,
                'reason': 'Disclosure classification alone does not establish transaction-level purity or a validated CRP scoring rubric.'},
            'organic_growth_attribution': {'score': None, 'status': 'NOT_SCORED',
                'reason': 'Product/service category growth is not an organic-vs-acquired revenue bridge.'},
            'revenue_recognition_integrity': {'score': None, 'status': 'NOT_SCORED',
                'reason': 'An accounting policy and one receivables-growth observation cannot establish numerical recognition integrity.'},
        },
        'overall_crq_score': None, 'overall_crq_status': 'NOT_SCORED',
        'scoring_coverage_pct': 0.0,
        'source_provenance': {'SEC': source, 'FMP': row.get('statement_source')},
        'production_files_modified': False,
    }
    positive_lead = f"{lead['name']} contributed {lead_contribution:.1f}% of the net revenue increase"
    bridge = f"FY2025 revenue rose {report['reconciliation']['revenue_growth_pct']:.1f}% year over year; {positive_lead}."
    if delta_pp is None:
        followup = 'Revenue-recognition diagnostics remain incomplete.'
    elif delta_pp > 0:
        followup = f'Accounts receivable grew {delta_pp:.1f} percentage points faster than revenue; review its drivers without inferring misstatement.'
    else:
        followup = f'Accounts receivable growth trailed revenue growth by {abs(delta_pp):.1f} percentage points; this alone cannot establish recognition quality.'
    report['deterministic_analyst_note'] = (bridge + ' ' + followup
        + ' Organic growth and revenue-recognition integrity remain unscored pending additional evidence.')
    return report


def self_test():
    source = 'https://www.sec.gov/Archives/edgar/data/320193/test'
    cats = [('iPhone',209586,201183), ('Mac',33708,29984), ('iPad',28023,26694),
            ('Wearables, Home and Accessories',35686,37005), ('Services',109158,96169)]
    row = {'ticker': 'AAPL', 'fiscal_year': 2025, 'period_end': '2025-09-27',
           'currency': 'USD', 'statement_periods_aligned': True,
           'revenue': 416161000000, 'prior_revenue': 391035000000,
           'revenue_growth_pct': 100 * (416161/391035 - 1), 'receivables_growth_pct': 10.1,
           'statement_source': 'TEST FMP'}
    stage1 = {'results': [row]}
    stage2 = {'ticker': 'AAPL', 'fiscal_year': 2025, 'source_url': source,
              'source_locators': {'recognition_policy':'TEST Note 2'},
              'fmp_reconciliation': {'status':'MATCH', 'FY2025_SEC_usd':416161000000,
                                     'FY2024_SEC_usd':391035000000},
              'revenue_classification': {'documented_operating_categories_usd':416161000000},
              'revenue_categories': [{'name':name,'FY2025_usd_millions':curr,
                 'FY2024_usd_millions':prev,'source_url':source,'source_locator':'TEST filing'}
                 for name,curr,prev in cats]}
    result = calculate(stage1,stage2)
    assert result['reconciliation']['revenue_delta_usd'] == 25_126_000_000
    assert abs(sum(x['contribution_to_consolidated_growth_pp'] for x in result['categories'])
               -result['reconciliation']['revenue_growth_pct']) < 0.01
    assert result['revenue_growth_lead']['category'] == 'Services'
    assert result['overall_crq_score'] is None
    assert all(c['score'] is None for c in result['subcomponents'].values())
    for bad in (dict(row, period_end='2024-09-28'), dict(row, revenue=400_000_000_000),
                dict(row, statement_periods_aligned=False)):
        try:
            calculate({'results':[bad]},stage2)
            raise AssertionError('Invalid annual input was accepted')
        except ValueError:
            pass
    broken = dict(stage2, revenue_categories=stage2['revenue_categories'][:-1])
    try:
        calculate(stage1,broken)
        raise AssertionError('Incomplete SEC categories were accepted')
    except ValueError:
        pass
    print('STAGE 3 SELF-TEST PASS: 5 SEC categories, revenue bridge, alignment/reconciliation refusal, no fabricated CRQ score.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--stage1', type=Path, default=STAGE1)
    parser.add_argument('--stage2', type=Path, default=STAGE2)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    require(args.stage1.is_file(), f'Stage 1 file not found: {args.stage1}')
    require(args.stage2.is_file(), f'Stage 2 file not found: {args.stage2}')
    result = calculate(json.loads(args.stage1.read_text(encoding='utf-8')),
                       json.loads(args.stage2.read_text(encoding='utf-8')))
    OUT.mkdir(parents=True, exist_ok=True)
    json_out = OUT / 'aapl_stage3_quantitative_review.json'
    csv_out = OUT / 'aapl_stage3_category_bridge.csv'
    for p in (json_out,csv_out):
        require(not p.exists(), f'Output already exists, refusing to overwrite: {p}')
    json_out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    cols = ['name','FY2024_usd','FY2025_usd','revenue_delta_usd',
            'FY2025_revenue_share_pct','category_yoy_growth_pct',
            'contribution_to_consolidated_growth_pp','share_of_net_revenue_increment_pct',
            'source_url','source_locator']
    with csv_out.open('w',newline='',encoding='utf-8') as file:
        writer = csv.DictWriter(file,fieldnames=cols)
        writer.writeheader()
        writer.writerows(result['categories'])
    print('AAPL FY2025 SEC / FMP + category bridge: MATCH')
    print('FY2025 revenue change: ${:.3f}B ({:.2f}%)'.format(
        result['reconciliation']['revenue_delta_usd']/1e9,
        result['reconciliation']['revenue_growth_pct']))
    for cat in result['categories']:
        print('  {:<34} {:+8.3f}B | growth contribution {:+.2f} pp'.format(
            cat['name'],cat['revenue_delta_usd']/1e9,
            cat['contribution_to_consolidated_growth_pp']))
    print('Operating-category disclosure coverage: 100% (NOT a revenue quality score)')
    print('Overall CRQ: NOT SCORED (organic/recognition evidence and rubric pending)')
    print('Analyst note:',result['deterministic_analyst_note'])
    print('Saved:',json_out)
    print('Saved:',csv_out)
    print('Production files/models unchanged; no API requests made.')


if __name__ == '__main__':
    main()
