#!/usr/bin/env python3
"""CRQ V1 Stage 5: consolidate AAPL SEC evidence and assess scoring readiness.

Uses Stage 2-4 reports ONLY; does not fetch APIs, mutate production or issue a CRQ
score. A 100% operating-category disclosure reconciliation is NOT an earnings
quality score. Source-located SEC Note 4 concentration percentages below are
manually transcribed from Apple's FY2025 10-K and require analyst review.

From the production root:
  python3 scripts/core_revenue_v1_stage5.py --self-test
  python3 scripts/core_revenue_v1_stage5.py
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
NOTE4_EVIDENCE = {
    'source_url': 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
    'source_locator': 'Apple FY2025 Form 10-K, Note 4 - Financial Instruments, Accounts Receivable / Trade Receivables',
    'FY2025_carrier_share_of_trade_ar_pct': 34.0,
    'FY2024_carrier_share_of_trade_ar_pct': 38.0,
    'FY2025_one_customer_share_of_trade_ar_pct': 12.0,
    'status': 'SEC note transcribed; classification/concentration evidence, not proof of collectibility'
}

def require(test, message):
    if not test:
        raise ValueError(message)

def positive(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0, f'{name}: missing/nonpositive')
    return float(value)

def audit(s2, s3, s4):
    for label, source in [('Stage 2', s2), ('Stage 3', s3), ('Stage 4', s4)]:
        require(source.get('ticker') == 'AAPL' and source.get('fiscal_year') == 2025
                and source.get('currency') == 'USD', f'{label}: ticker/year/currency mismatch')
    sec_url = s2.get('source_url')
    require(isinstance(sec_url, str) and sec_url.startswith('https://www.sec.gov/')
            and s3.get('source_url') == sec_url and s4.get('source_url') == sec_url,
            'SEC source is inconsistent')
    require(s2.get('fmp_reconciliation', {}).get('status') == 'MATCH'
            and s3.get('reconciliation', {}).get('SEC_vs_FMP') == 'MATCH'
            and s3.get('reconciliation', {}).get('category_bridge') == 'MATCH'
            and s4.get('reconciliation', {}).get('prior_stages') == 'MATCH',
            'Previous reports did not reconcile')
    classification = s2['revenue_classification']
    revenue25 = positive(classification.get('reported_total_usd'), 'FY2025 SEC revenue')
    operating25 = positive(classification.get('documented_operating_categories_usd'), 'FY2025 operating categories')
    require(abs(revenue25 - operating25) < 1, 'Classification is not 100% reconciled')
    cats = s3.get('categories', [])
    require(len(cats) == 5 and len({c['name'] for c in cats}) == 5,
            'Expected five distinct AAPL revenue categories')
    require(abs(sum(positive(c['FY2025_usd'], c['name']+' FY2025') for c in cats) - revenue25) < 1,
            'FY2025 stage 3 category sum mismatch')
    sales = s4.get('annual_metrics', {}).get('revenue', {})
    revenue24 = positive(sales.get('FY2024_usd_m'), 'FY2024 revenue')
    require(abs(positive(sales.get('FY2025_usd_m'), 'FY2025 revenue') * 1e6 - revenue25) < 1,
            'Stage 4 revenue differs from Stage 2')
    ar = s4.get('annual_metrics', {}).get('trade_accounts_receivable', {})
    ar24 = positive(ar.get('FY2024_usd_m'), 'FY2024 trade AR')
    ar25 = positive(ar.get('FY2025_usd_m'), 'FY2025 trade AR')
    rev25m = revenue25 / 1e6
    revenue_growth_pct = 100 * (rev25m / revenue24 - 1)
    ar_growth_pct = 100 * (ar25 / ar24 - 1)
    trade_gap = ar_growth_pct - revenue_growth_pct
    diag = s4.get('recognition_diagnostics', {})
    require(abs(trade_gap - diag.get('trade_ar_minus_revenue_growth_pp', float('nan'))) < .03,
            'Stage 4 trade AR growth-gap mismatch')
    require(diag.get('trade_ar_gap_flag') is (trade_gap > 10), 'Stage 4 AR flag mismatch')
    source_recognized = diag.get('recognized_from_opening_deferred_revenue', {})
    deferred_recognized = positive(source_recognized.get('FY2025_usd_m'), 'Recognized from opening deferral')
    require(abs(deferred_recognized/rev25m*100 - source_recognized.get('FY2025_pct_of_total_revenue', float('nan'))) < .03,
            'Deferred revenue percentage mismatch')
    require(s4.get('score', {}).get('overall_CRQ') is None,
            'Prior Stage 4 contains an unexpected overall CRQ score')
    ar_days24 = 365 * ar24 / revenue24
    ar_days25 = 365 * ar25 / rev25m
    shares = sorted(({'name': c['name'], 'FY2025_revenue_share_pct': round(100*c['FY2025_usd']/revenue25, 2)}
                     for c in cats), key=lambda x: x['FY2025_revenue_share_pct'], reverse=True)
    report = {
        'stage': 'CRQ V1 Stage 5 - revenue diagnostics and scoring readiness, NOT a quality score',
        'ticker': 'AAPL', 'fiscal_year': 2025, 'currency': 'USD', 'source_url': sec_url,
        'reconciliation': 'PASS: Stage 2 category totals, Stage 3 category bridge, Stage 4 SEC/FMP periods and AR facts',
        'operating_category_coverage_pct': round(100*operating25/revenue25, 2),
        'operating_category_coverage_not_score': True,
        'FY2025_revenue_mix': shares,
        'revenue_recognition_diagnostics': {
            'revenue_growth_pct': round(revenue_growth_pct, 2),
            'trade_ar_growth_pct': round(ar_growth_pct, 2),
            'trade_ar_minus_revenue_growth_pp': round(trade_gap, 2),
            'trade_ar_growth_investigation_flag': trade_gap > 10,
            'year_end_trade_ar_to_annual_revenue_proxy_days_FY2024': round(ar_days24, 2),
            'year_end_trade_ar_to_annual_revenue_proxy_days_FY2025': round(ar_days25, 2),
            'proxy_days_change': round(ar_days25-ar_days24, 2),
            'proxy_limit': 'Year-end trade AR / annual revenue x 365; not average-balance DSO and not proof of misstatement.',
            'recognized_from_opening_deferred_revenue_FY2025_usd_m': deferred_recognized,
            'recognized_from_opening_deferred_revenue_share_pct': round(100*deferred_recognized/rev25m, 2),
            'deferred_note': 'Normal discharge of previously deferred obligations, not a non-core revenue deduction.'
        },
        'receivables_concentration_SEC_note4': NOTE4_EVIDENCE,
        'scoring_readiness': {
            'core_revenue_purity': 'CANDIDATE ONLY: all disclosed categories are operating products/services, but category coverage is not a validated transaction-level purity score',
            'organic_growth_attribution': 'UNKNOWN: acquisition/FX-adjusted organic revenue growth bridge not verified',
            'revenue_recognition_integrity': 'UNKNOWN: trade AR divergence triggers investigation but cannot imply an integrity score',
            'effective_scoring_coverage_pct': 0.0,
            'overall_CRQ_score': None,
            'status': 'NOT_SCORED',
            'before_scoring': ['analyst sign-off on core/non-core classification and scoring rubric',
                               'evidence-based organic-growth attribution or explicit unavailable status',
                               'validated revenue-recognition assessment and ≥70% weighted-score coverage']
        },
        'analyst_note': (
            f'FY2025 revenue rose {revenue_growth_pct:.1f}%, while trade receivables grew '
            f'{ar_growth_pct:.1f}% (+{trade_gap:.1f} pp faster). The simple year-end '
            f'trade-AR/revenue proxy increased by {ar_days25-ar_days24:.1f} days. '
            'This merits collection-timing and channel-mix review, not an automatic quality penalty. '
            'All disclosed products/services are classified as operating revenue, but '
            'organic-growth attribution and recognition-integrity scores remain unverified.'
        ),
        'production_files_modified': False, 'api_calls': 0
    }
    return report

def self_test():
    # Exact published amounts for synthetic consistency tests only; no production modifications.
    url = NOTE4_EVIDENCE['source_url']
    cats = [('iPhone',209586),('Mac',33708),('iPad',28023),
            ('Wearables, Home and Accessories',35686),('Services',109158)]
    s2 = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD','source_url':url,
          'fmp_reconciliation':{'status':'MATCH'},
          'revenue_classification':{'reported_total_usd':416161e6,
                                    'documented_operating_categories_usd':416161e6}}
    s3 = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD','source_url':url,
          'reconciliation':{'SEC_vs_FMP':'MATCH','category_bridge':'MATCH'},
          'categories':[{'name':n,'FY2025_usd':a*1e6} for n,a in cats]}
    growth = 100*(39777/33410-416161/391035)
    s4 = {'ticker':'AAPL','fiscal_year':2025,'currency':'USD','source_url':url,
          'reconciliation':{'prior_stages':'MATCH'},
          'annual_metrics': {'revenue':{'FY2024_usd_m':391035,'FY2025_usd_m':416161},
                             'trade_accounts_receivable':{'FY2024_usd_m':33410,'FY2025_usd_m':39777}},
          'recognition_diagnostics':{'trade_ar_minus_revenue_growth_pp':round(growth,3),
              'trade_ar_gap_flag':True,
              'recognized_from_opening_deferred_revenue':{'FY2025_usd_m':8229,
                 'FY2025_pct_of_total_revenue':round(100*8229/416161,3)}},
          'score': {'overall_CRQ':None}}
    result = audit(s2,s3,s4)
    assert abs(result['revenue_recognition_diagnostics']['trade_ar_minus_revenue_growth_pp']-12.63) < .02
    assert result['revenue_recognition_diagnostics']['proxy_days_change'] > 0
    assert result['operating_category_coverage_pct'] == 100
    assert result['scoring_readiness']['overall_CRQ_score'] is None
    for tamper in [dict(s2, fiscal_year=2024),
                   dict(s2, revenue_classification=dict(s2['revenue_classification'], documented_operating_categories_usd=400e9))]:
        try:
            audit(tamper,s3,s4)
        except ValueError:
            continue
        raise AssertionError('Accepted mismatched or un-reconciled evidence')
    print('STAGE 5 SELF-TEST PASS: cross-stage reconciliation, source alignment, trade AR proxy, invalid-input rejection, no fabricated quality score.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--stage2',type=Path,default=OUT/'aapl_sec_stage2_review.json')
    parser.add_argument('--stage3',type=Path,default=OUT/'aapl_stage3_quantitative_review.json')
    parser.add_argument('--stage4',type=Path,default=OUT/'aapl_stage4_recognition_review.json')
    args=parser.parse_args()
    if args.self_test:
        self_test(); return
    inputs=[]
    for path in (args.stage2,args.stage3,args.stage4):
        require(path.is_file(),f'Missing prior stage report: {path}')
        inputs.append(json.loads(path.read_text(encoding='utf-8')))
    result=audit(*inputs)
    OUT.mkdir(parents=True,exist_ok=True)
    j=OUT/'aapl_stage5_scoring_readiness.json'
    c=OUT/'aapl_stage5_revenue_mix.csv'
    require(not j.exists() and not c.exists(), 'Stage 5 output already exists; refusing to overwrite')
    j.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with c.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['name','FY2025_revenue_share_pct'])
        writer.writeheader(); writer.writerows(result['FY2025_revenue_mix'])
    r=result['revenue_recognition_diagnostics']
    print('AAPL Stage 5: SEC reconciliation PASS')
    print(f"Trade AR {r['trade_ar_growth_pct']:+.2f}% vs revenue {r['revenue_growth_pct']:+.2f}%; gap {r['trade_ar_minus_revenue_growth_pp']:+.2f} pp")
    print(f"Year-end trade-AR/revenue proxy: {r['year_end_trade_ar_to_annual_revenue_proxy_days_FY2024']} -> {r['year_end_trade_ar_to_annual_revenue_proxy_days_FY2025']} days; NOT average-AR DSO")
    print('SEC carrier share of trade AR: 38% -> 34%; single large customer FY2025 12%.')
    print('Core Revenue classification coverage 100%; CRQ overall NOT SCORED.')
    print('Saved:',j,'\nSaved:',c)
    print('No API calls. No production scoring/model changes.')

if __name__ == '__main__':
    main()
