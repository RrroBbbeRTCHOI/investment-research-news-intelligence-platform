#!/usr/bin/env python3
"""Read-only MAG7 Core Revenue Quality V1 pilot.

Uses existing production FMP annual data/cache. Never changes production
Earnings Quality, Rating, valuation, or the Core Revenue placeholder.
An overall CRQ score is available only with independently verified revenue
classification evidence supplied through --evidence.

Run from the repository root:
    python3 scripts/core_revenue_v1_pilot.py
    python3 scripts/core_revenue_v1_pilot.py --self-test
    python3 scripts/core_revenue_v1_pilot.py --make-evidence-template
"""
import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
import sys

TICKERS = ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'META', 'TSLA')
WEIGHTS = {'purity': 0.55, 'organic': 0.25, 'recognition': 0.20}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'reports' / 'core_revenue_v1_pilot'
EVIDENCE = OUT / 'verified_evidence.json'


def number(x):
    if isinstance(x, bool):
        return None
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except (ValueError, TypeError, OverflowError):
        return None


def year(x):
    try:
        y = int(x)
        return y if 1990 <= y <= 2100 else None
    except (ValueError, TypeError):
        return None


def valid_annual(row, ticker):
    return (isinstance(row, dict) and row.get('symbol') == ticker
            and row.get('period') == 'FY' and year(row.get('fiscalYear'))
            and row.get('reportedCurrency') and row.get('date'))


def annual_rows(rows, ticker):
    result = {}
    for row in rows or []:
        if not valid_annual(row, ticker):
            continue
        y = year(row.get('fiscalYear'))
        if y in result:
            # Duplicate fiscal-year records are ambiguous; do not select one.
            result[y] = None
        else:
            result[y] = row
    return result


def yoy(current, previous):
    if current is None or previous is None or previous <= 0:
        return None
    return 100.0 * (current / previous - 1.0)


def fmt(v, digits=1, suffix=''):
    return 'N/A' if v is None else f'{v:,.{digits}f}{suffix}'


def find_receivables(row):
    if not isinstance(row, dict):
        return None, None
    # FMP's receivables fields vary across versions/company filings.
    for key in ('netReceivables', 'accountsReceivables', 'accountsReceivable'):
        value = number(row.get(key))
        if value is not None and value >= 0:
            return value, key
    return None, None


def describe(ticker, income, balance, error=None):
    inc = annual_rows(income, ticker)
    bal = annual_rows(balance, ticker)
    latest = max(inc) if inc else None
    current = inc.get(latest) if latest is not None else None
    prior = inc.get(latest - 1) if latest is not None else None
    revenue = number(current.get('revenue')) if current else None
    prev_rev = number(prior.get('revenue')) if prior else None
    rg = yoy(revenue, prev_rev)
    br = bal.get(latest) if latest is not None else None
    bp = bal.get(latest - 1) if latest is not None else None
    ar, ar_field = find_receivables(br)
    prior_ar, _ = find_receivables(bp)
    # Different balance/income period dates or currency must not be paired.
    aligned = bool(current and prior and br and bp
                   and current.get('date') == br.get('date')
                   and prior.get('date') == bp.get('date')
                   and current.get('reportedCurrency') == br.get('reportedCurrency')
                   and prior.get('reportedCurrency') == bp.get('reportedCurrency')
                   and current.get('reportedCurrency') == prior.get('reportedCurrency'))
    if not aligned:
        ar, prior_ar, ar_field = None, None, None
    arg = yoy(ar, prior_ar)
    result = {
        'ticker': ticker, 'fiscal_year': latest,
        'currency': current.get('reportedCurrency') if current else None,
        'period_end': current.get('date') if current else None,
        'revenue': revenue, 'prior_revenue': prev_rev,
        'revenue_growth_pct': rg, 'receivables': ar,
        'receivables_field': ar_field, 'receivables_growth_pct': arg,
        'receivables_minus_revenue_growth_pp': (arg - rg) if arg is not None and rg is not None else None,
        'financial_data_available': revenue is not None and prev_rev is not None,
        'statement_periods_aligned': aligned,
        'statement_source': 'FMP annual income-statement / balance-sheet-statement',
        'recognition_diagnostic': ('Receivables growth outpaces revenue by >10 pp: investigate; not proof of misstatement.'
                                   if arg is not None and rg is not None and arg - rg > 10
                                   else 'No automated red flag from this single receivables-growth diagnostic.'
                                   if arg is not None and rg is not None
                                   else 'Receivables comparison unavailable or period not aligned.'),
        'crq_score': None, 'score_coverage_pct': 0.0,
        'score_status': 'Not Scored',
        'unavailable_reason': 'Verified core/non-core segment split and organic-growth attribution are not in normalized statements.',
        'errors': error or [],
    }
    return result


def verified_evidence_score(result, evidence):
    """Optional pilot score; evidence must be analyst-reviewed and cited.

    recognition_score is a reviewer-assigned, documented V1 pilot assessment,
    NOT a numerical score calculated from receivables growth.
    """
    if not isinstance(evidence, dict) or not evidence.get('analyst_verified'):
        return result
    fy = year(evidence.get('fiscal_year'))
    revenue = result['revenue']
    core = number(evidence.get('core_revenue'))
    disclosed_total = number(evidence.get('disclosed_total_revenue'))
    core_source = evidence.get('core_revenue_source')
    score_parts = {}
    if (fy == result['fiscal_year'] and revenue and core is not None
            and disclosed_total and core_source and 0 <= core <= disclosed_total
            and abs(disclosed_total - revenue) / revenue <= 0.01):
        score_parts['purity'] = 100.0 * core / disclosed_total
        prev_core = number(evidence.get('prior_core_revenue'))
        organic_increment = number(evidence.get('organic_core_revenue_increment'))
        organic_source = evidence.get('organic_growth_source')
        if (prev_core is not None and organic_increment is not None and organic_source
                and core > prev_core >= 0 and 0 <= organic_increment <= core - prev_core):
            score_parts['organic'] = 100.0 * organic_increment / (core - prev_core)
        rri = number(evidence.get('revenue_recognition_score'))
        rri_source = evidence.get('recognition_review_source')
        rri_method = evidence.get('recognition_scoring_method')
        if rri is not None and 0 <= rri <= 100 and rri_source and rri_method:
            score_parts['recognition'] = rri
    coverage = sum(WEIGHTS[k] for k in score_parts)
    result['score_coverage_pct'] = round(coverage * 100, 1)
    result['component_scores'] = score_parts
    # Purity is mandatory, and at least 70% of the total model must be reviewed.
    if 'purity' in score_parts and coverage >= 0.70:
        result['crq_score'] = round(sum(WEIGHTS[k] * s for k, s in score_parts.items()) / coverage, 2)
        result['score_status'] = 'Provisional (verified evidence; incomplete)' if coverage < 0.999 else 'Pilot score (all components reviewed)'
        result['unavailable_reason'] = None
    else:
        result['unavailable_reason'] = 'Insufficient verified evidence or <70% scoring coverage; purity is mandatory.'
    return result


def evidence_template():
    return {t: {
        'analyst_verified': False, 'fiscal_year': None,
        'disclosed_total_revenue': None, 'core_revenue': None,
        'core_revenue_source': None, 'prior_core_revenue': None,
        'organic_core_revenue_increment': None, 'organic_growth_source': None,
        'revenue_recognition_score': None, 'recognition_review_source': None,
        'recognition_scoring_method': None,
    } for t in TICKERS}


def fetch(ticker, cache_only=False):
    from src.data import historical_financial_data as fmp
    income, balance, errors = None, None, []
    for label, endpoint, loader in (
        ('income', 'income-statement', fmp.get_historical_income_statement),
        ('balance', 'balance-sheet-statement', fmp.get_historical_balance_sheet),
    ):
        try:
            # Existing 5Y cache first; normal mode falls back to the existing FMP provider.
            data = fmp._load_cache(endpoint, ticker, 5) if cache_only else loader(ticker, years=5)
            if data is None:
                errors.append(f'{label}: no valid 5Y cache')
            if label == 'income': income = data
            else: balance = data
        except Exception as exc:
            errors.append(f'{label}: {type(exc).__name__}: {str(exc)[:120]}')
    return income, balance, errors


def self_test():
    rows = [
        {'symbol':'AAPL','period':'FY','fiscalYear':'2025','date':'2025-09-27','reportedCurrency':'USD','revenue':120},
        {'symbol':'AAPL','period':'FY','fiscalYear':'2024','date':'2024-09-28','reportedCurrency':'USD','revenue':100},
    ]
    bs = [
        {'symbol':'AAPL','period':'FY','fiscalYear':'2025','date':'2025-09-27','reportedCurrency':'USD','netReceivables':25},
        {'symbol':'AAPL','period':'FY','fiscalYear':'2024','date':'2024-09-28','reportedCurrency':'USD','netReceivables':20},
    ]
    result = describe('AAPL',rows,bs)
    assert abs(result['revenue_growth_pct'] - 20.0) < 1e-8
    assert abs(result['receivables_growth_pct'] - 25.0) < 1e-8
    assert result['crq_score'] is None  # Raw FMP revenue alone MUST NOT imply core purity.
    verified_evidence_score(result, {'analyst_verified': True,'fiscal_year':'2025',
        'disclosed_total_revenue':120,'core_revenue':114,'core_revenue_source':'TEST-FIXTURE: filing',
        'prior_core_revenue':94,'organic_core_revenue_increment':16,
        'organic_growth_source':'TEST-FIXTURE: acquisition bridge',
        'revenue_recognition_score':90,'recognition_review_source':'TEST-FIXTURE: footnote',
        'recognition_scoring_method':'TEST-FIXTURE: reviewed pilot rubric'})
    assert abs(result['crq_score'] - 90.25) < 1e-8, result['crq_score']
    assert result['score_coverage_pct'] == 100.0
    assert describe('AAPL',rows,bs)['crq_score'] is None
    print('SELF TEST PASS: period matching, raw diagnostic, no fabricated scores, weighted CRQ.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--cache-only', action='store_true', help='Never make live FMP calls.')
    parser.add_argument('--make-evidence-template', action='store_true')
    parser.add_argument('--evidence', type=Path, help='Optional analyst-verified SEC evidence JSON.')
    parser.add_argument('--tickers', nargs='+', default=list(TICKERS), choices=TICKERS)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    OUT.mkdir(parents=True,exist_ok=True)
    if args.make_evidence_template:
        if EVIDENCE.exists():
            print('Template already exists; no existing evidence overwritten:', EVIDENCE)
        else:
            EVIDENCE.write_text(json.dumps(evidence_template(),indent=2)+'\n',encoding='utf-8')
            print('Empty evidence template:',EVIDENCE)
        return
    evidence = {}
    if args.evidence:
        evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    rows = []
    for ticker in args.tickers:
        print(f'Checking {ticker} ...', flush=True)
        inc, bal, err = fetch(ticker,args.cache_only)
        item = describe(ticker,inc,bal,err)
        verified_evidence_score(item,evidence.get(ticker))
        rows.append(item)
        print(f"  FY={item['fiscal_year']} | revenue growth={fmt(item['revenue_growth_pct'],1,'%')} | "
              f"AR growth={fmt(item['receivables_growth_pct'],1,'%')} | "
              f"CRQ={fmt(item['crq_score'])} | {item['score_status']}")
        for problem in err:
            print('  NOTE:',problem)
    json_path = OUT / 'mag7_crq_v1_pilot.json'
    csv_path = OUT / 'mag7_crq_v1_pilot.csv'
    json_path.write_text(json.dumps({'model':'CRQ V1 pilot','weights':WEIGHTS,'results':rows},
                                    indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    cols = ['ticker','fiscal_year','currency','revenue','prior_revenue','revenue_growth_pct',
            'receivables_growth_pct','receivables_minus_revenue_growth_pp',
            'crq_score','score_coverage_pct','score_status','unavailable_reason']
    with csv_path.open('w',newline='',encoding='utf-8') as fh:
        writer=csv.DictWriter(fh,fieldnames=cols,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print('\nSaved:',json_path,'\nSaved:',csv_path)
    print('Reminder: receivables divergence is an investigation flag, NEVER proof of bad revenue.')
    print('No production scoring files or existing model outputs were modified.')


if __name__=='__main__':
    main()
