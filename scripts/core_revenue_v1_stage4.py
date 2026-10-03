#!/usr/bin/env python3
"""CRQ V1 Stage 4: AAPL FY2025 SEC trade-receivables / recognition evidence audit.

Read-only with respect to all production code and earlier pilot reports. This
script reads the outputs of Stages 1-3, checks period and revenue alignment,
and generates separate Stage 4 diagnostic reports. Values in SEC_FACTS were
manually transcribed from Apple FY2025 10-K and should be independently
verified against the cited filing. It does NOT produce an integrity/CRQ score.

From the production repo root:
  python3 scripts/core_revenue_v1_stage4.py --self-test
  python3 scripts/core_revenue_v1_stage4.py
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
SEC_URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'
SEC_FACTS_M = {
    2025: {'revenue': 416161, 'trade_ar': 39777, 'vendor_nontrade_ar': 33180},
    2024: {'revenue': 391035, 'trade_ar': 33410, 'vendor_nontrade_ar': 32833},
}
SEC_DEFERRED_FROM_OPENING_M = {2025: 8229, 2024: 7728}
FLAG_THRESHOLD_PP = 10.0  # Investigation rule only, not a quality score.
SOURCES = {
    'ar': 'AAPL FY2025 Form 10-K, Consolidated Balance Sheets, p.31 (PDF p.35)',
    'revenue': 'AAPL FY2025 Form 10-K, Note 2 - Revenue, pp.35-36 (PDF pp.39-40)',
    'recognition': 'AAPL FY2025 Form 10-K, Note 2 - Revenue, pp.35-36 (PDF pp.39-40)',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def num(value, label):
    require(not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value), f'{label}: missing/invalid number')
    return float(value)


def stage1_aapl(payload):
    require(isinstance(payload, dict) and isinstance(payload.get('results'), list),
            'Stage 1 requires a results list')
    rows = [v for v in payload['results'] if isinstance(v, dict) and v.get('ticker') == 'AAPL']
    require(len(rows) == 1, 'Stage 1 must contain exactly one AAPL record')
    return rows[0]


def close_usd(a, b, name, tolerance=0.0001):
    require(abs(a-b)/b <= tolerance, f'{name}: SEC/FMP mismatch; refuses comparison')


def audit(stage1, stage2, stage3):
    r = stage1_aapl(stage1)
    for name, record in [('Stage 1', r), ('Stage 2', stage2), ('Stage 3', stage3)]:
        require(record.get('ticker') == 'AAPL' and record.get('fiscal_year') == 2025,
                f'{name}: ticker/fiscal-year mismatch')
    require(r.get('period_end') == '2025-09-27' and r.get('currency') == 'USD'
            and r.get('statement_periods_aligned') is True,
            'Stage 1: statements are not FY2025 period-aligned USD')
    require(stage2.get('currency') == 'USD' and stage3.get('currency') == 'USD',
            'Stage 2 or 3 currency mismatch')
    require(stage2.get('fmp_reconciliation', {}).get('status') == 'MATCH'
            and stage3.get('reconciliation', {}).get('SEC_vs_FMP') == 'MATCH'
            and stage3.get('reconciliation', {}).get('category_bridge') == 'MATCH',
            'Previous evidence reconciliation was not confirmed')
    for year, raw in [(2025, r.get('revenue')), (2024, r.get('prior_revenue'))]:
        close_usd(num(raw, f'Stage 1 revenue {year}'), SEC_FACTS_M[year]['revenue']*1e6,
                  f'FY{year} revenue')
    for year, key in [(2025, 'FY2025_revenue_usd'), (2024, 'FY2024_revenue_usd')]:
        close_usd(num(stage3['reconciliation'].get(key), f'Stage 3 {key}'),
                  SEC_FACTS_M[year]['revenue']*1e6, f'Stage 3 FY{year}')

    cur, prior = SEC_FACTS_M[2025], SEC_FACTS_M[2024]
    def growth(key):
        return 100 * (cur[key]/prior[key]-1)
    revenue_growth = growth('revenue')
    trade_growth = growth('trade_ar')
    vendor_growth = growth('vendor_nontrade_ar')
    combined25 = cur['trade_ar'] + cur['vendor_nontrade_ar']
    combined24 = prior['trade_ar'] + prior['vendor_nontrade_ar']
    combined_growth = 100 * (combined25/combined24-1)
    trade_gap = trade_growth - revenue_growth
    combined_gap = combined_growth - revenue_growth

    # FMP `netReceivables` may equal trade AR + vendor non-trade receivables;
    # classify its observable aggregation without assuming provider conventions.
    observed = r.get('receivables')
    prior_observed = r.get('prior_receivables')
    match = 'UNAVAILABLE'
    observed_m = observed / 1e6 if isinstance(observed, (int, float)) else None
    if observed_m is not None and math.isfinite(observed_m):
        if abs(observed_m - combined25) / combined25 <= 0.001:
            match = 'MATCHES_TRADE_PLUS_VENDOR_NONTRADE_FY2025'
        elif abs(observed_m - cur['trade_ar']) / cur['trade_ar'] <= 0.001:
            match = 'MATCHES_TRADE_AR_FY2025'
        else:
            match = 'OTHER_OR_UNRESOLVED_PROVIDER_DEFINITION'
    # Stage 1 does not preserve prior receivables level; infer from its
    # reported annual growth only when current raw value is known.
    reported_ar_growth = r.get('receivables_growth_pct')
    if isinstance(reported_ar_growth, (int, float)) and math.isfinite(reported_ar_growth):
        if abs(reported_ar_growth-combined_growth) < 0.15 and match.startswith('MATCHES_TRADE_PLUS'):
            match += '_AND_GROWTH'
        elif abs(reported_ar_growth-trade_growth) < 0.15 and match == 'MATCHES_TRADE_AR_FY2025':
            match += '_AND_GROWTH'
        else:
            match += '_GROWTH_NOT_RECONCILED'

    out = {
        'model': 'CRQ V1 Stage 4 - recognition evidence / field-definition audit (not a score)',
        'ticker': 'AAPL', 'fiscal_year': 2025, 'currency': 'USD',
        'source_url': SEC_URL,
        'source_locators': SOURCES,
        'reconciliation': {'prior_stages': 'MATCH', 'FY2025_fmp_sec': 'MATCH',
                           'FY2024_fmp_sec': 'MATCH'},
        'annual_metrics': {
            'revenue': {'FY2024_usd_m': prior['revenue'], 'FY2025_usd_m': cur['revenue'],
                        'yoy_growth_pct': round(revenue_growth, 3)},
            'trade_accounts_receivable': {
                'FY2024_usd_m': prior['trade_ar'], 'FY2025_usd_m': cur['trade_ar'],
                'yoy_growth_pct': round(trade_growth, 3)},
            'vendor_nontrade_receivables': {
                'FY2024_usd_m': prior['vendor_nontrade_ar'],
                'FY2025_usd_m': cur['vendor_nontrade_ar'],
                'yoy_growth_pct': round(vendor_growth, 3)},
            'trade_plus_vendor_receivables': {
                'FY2024_usd_m': combined24, 'FY2025_usd_m': combined25,
                'yoy_growth_pct': round(combined_growth, 3)},
        },
        'fmp_receivables': {
            'field': r.get('receivables_field'),
            'FY2025_usd': observed if isinstance(observed, (int, float)) else None,
            'yoy_growth_pct': reported_ar_growth,
            'definition_reconciliation': match,
            'warning': 'Do not label provider netReceivables as trade AR without resolving its definition.'
        },
        'recognition_diagnostics': {
            'trade_ar_minus_revenue_growth_pp': round(trade_gap, 3),
            'combined_ar_minus_revenue_growth_pp': round(combined_gap, 3),
            'trade_ar_gap_investigation_threshold_pp': FLAG_THRESHOLD_PP,
            'trade_ar_gap_flag': trade_gap > FLAG_THRESHOLD_PP,
            'year_end_trade_ar_to_revenue_proxy_days': {
                'FY2024': round(365*prior['trade_ar']/prior['revenue'], 2),
                'FY2025': round(365*cur['trade_ar']/cur['revenue'], 2),
                'note': 'Year-end AR/revenue x365 is a simple exposure proxy, not average-AR DSO.'
            },
            'recognized_from_opening_deferred_revenue': {
                'FY2025_usd_m': SEC_DEFERRED_FROM_OPENING_M[2025],
                'FY2024_usd_m': SEC_DEFERRED_FROM_OPENING_M[2024],
                'FY2025_pct_of_total_revenue': round(100*SEC_DEFERRED_FROM_OPENING_M[2025]/cur['revenue'], 3),
                'note': 'Normally recognized delivery of previously deferred obligations; not intrinsically non-core revenue.'
            },
            'SEC_recognition_policy_observations': [
                'Products are generally recognized when control transfers (usually shipment); services as delivered over time.',
                'Bundled hardware and services use relative stand-alone selling prices; bundled-service revenue is deferred.',
                'Third-party App Store applications are reported net; recognized Services sales are retained commissions.'
            ],
            'interpretation': 'Trade AR grew faster than net sales: investigate billing mix, collection timing, terms, and other disclosed drivers. This alone neither establishes recognition irregularity nor warrants a numeric quality penalty.'
        },
        'score': {'core_revenue_purity': None, 'organic_growth_attribution': None,
                  'revenue_recognition_integrity': None, 'overall_CRQ': None,
                  'status': 'NOT_SCORED',
                  'reason': 'SEC field-definition audit and investigation flags are evidence, not a validated scoring rubric.'},
        'supersedes': 'Stage 3 receivables-growth comparison when interpreting *trade* receivables; Stage 3 remains a historical pilot record.',
        'production_files_modified': False,
    }
    return out


def self_test():
    sec = SEC_FACTS_M
    tr = sec[2025]['trade_ar'] + sec[2025]['vendor_nontrade_ar']
    pr = sec[2024]['trade_ar'] + sec[2024]['vendor_nontrade_ar']
    base = {'ticker':'AAPL', 'fiscal_year':2025,'currency':'USD', 'period_end':'2025-09-27',
            'statement_periods_aligned': True,
            'revenue': sec[2025]['revenue']*1e6,
            'prior_revenue': sec[2024]['revenue']*1e6,
            'receivables': tr*1e6, 'receivables_field':'netReceivables',
            'receivables_growth_pct':100*(tr/pr-1)}
    s1 = {'results':[base]}
    s2 = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD',
          'fmp_reconciliation': {'status':'MATCH'}}
    s3 = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD',
          'reconciliation': {'SEC_vs_FMP':'MATCH','category_bridge':'MATCH',
                             'FY2025_revenue_usd':sec[2025]['revenue']*1e6,
                             'FY2024_revenue_usd':sec[2024]['revenue']*1e6}}
    result = audit(s1,s2,s3)
    assert abs(result['recognition_diagnostics']['trade_ar_minus_revenue_growth_pp']-12.632) < .01
    assert abs(result['recognition_diagnostics']['combined_ar_minus_revenue_growth_pp']-3.710) < .01
    assert result['recognition_diagnostics']['trade_ar_gap_flag'] is True
    assert result['fmp_receivables']['definition_reconciliation'] == 'MATCHES_TRADE_PLUS_VENDOR_NONTRADE_FY2025_AND_GROWTH'
    assert result['score']['overall_CRQ'] is None
    assert abs(result['recognition_diagnostics']['recognized_from_opening_deferred_revenue']['FY2025_pct_of_total_revenue']-1.977) < .01
    for bad in [dict(base, fiscal_year=2024), dict(base, revenue=400e9),
                dict(base, statement_periods_aligned=False)]:
        try:
            audit({'results':[bad]},s2,s3)
            raise AssertionError('Mismatched financials incorrectly accepted')
        except ValueError:
            pass
    print('STAGE 4 SELF-TEST PASS: trade vs combined AR, recognition flag, deferred revenue, strict alignment, no fabricated scores.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--stage1', type=Path, default=OUT/'mag7_crq_v1_pilot.json')
    p.add_argument('--stage2', type=Path, default=OUT/'aapl_sec_stage2_review.json')
    p.add_argument('--stage3', type=Path, default=OUT/'aapl_stage3_quantitative_review.json')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    for name, path in [('Stage 1',args.stage1),('Stage 2',args.stage2),('Stage 3',args.stage3)]:
        require(path.is_file(), f'Missing {name}: {path}')
    result = audit(*[json.loads(f.read_text(encoding='utf-8'))
                     for f in (args.stage1,args.stage2,args.stage3)])
    OUT.mkdir(parents=True,exist_ok=True)
    output_json = OUT / 'aapl_stage4_recognition_review.json'
    output_csv = OUT / 'aapl_stage4_receivables_comparison.csv'
    for output in (output_json,output_csv):
        require(not output.exists(), f'Output exists; refusing to overwrite: {output}')
    output_json.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    rows = []
    for name, entry in result['annual_metrics'].items():
        rows.append({'metric':name,'FY2024_usd_m':entry['FY2024_usd_m'],
                     'FY2025_usd_m':entry['FY2025_usd_m'],
                     'yoy_growth_pct':entry['yoy_growth_pct']})
    with output_csv.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['metric','FY2024_usd_m','FY2025_usd_m','yoy_growth_pct'])
        writer.writeheader(); writer.writerows(rows)
    diag=result['recognition_diagnostics']
    print('AAPL FY2025 Stage 4: SEC revenue and periods MATCH')
    print('FMP receivables definition:',result['fmp_receivables']['definition_reconciliation'])
    for name, value in [('Revenue',result['annual_metrics']['revenue']['yoy_growth_pct']),
                        ('SEC trade AR',result['annual_metrics']['trade_accounts_receivable']['yoy_growth_pct']),
                        ('Trade + vendor AR',result['annual_metrics']['trade_plus_vendor_receivables']['yoy_growth_pct'])]:
        print(f'  {name:<19} YoY {value:+.2f}%')
    print('Trade AR - revenue growth: {:+.2f} pp | Investigation flag: {}'.format(
        diag['trade_ar_minus_revenue_growth_pp'],diag['trade_ar_gap_flag']))
    print('Recognized from opening deferred revenue: $8.229B (normal disclosed revenue; not a non-core deduction)')
    print('Revenue Recognition Integrity: NOT SCORED; Overall CRQ: NOT SCORED')
    print('Saved:',output_json)
    print('Saved:',output_csv)
    print('Existing production/models/Stage 1-3 reports: UNCHANGED; no API calls.')


if __name__ == '__main__':
    main()
