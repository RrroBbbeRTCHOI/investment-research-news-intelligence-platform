#!/usr/bin/env python3
"""Meridian CRQ V1: one-file, offline MAG7 evidence audit and *gated* candidate model.

Reads existing Production reports; never calls APIs or changes Production scoring.

Usage from project root:
  python3 scripts/core_revenue_model_v1.py --self-test
  python3 scripts/core_revenue_model_v1.py
  python3 scripts/core_revenue_model_v1.py --evidence reports/core_revenue_final/reviewer_evidence_template.json

Only approved, sourced reviewer evidence can generate EXPERIMENTAL candidate scores.
This tool checks internal consistency but cannot authenticate analysts or independently
verify URLs, material accounting judgments, or empirically calibrate the 40/60 weights.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

MODEL = 'MERIDIAN-CRQ-V1-EVIDENCE-GATED-2026-10'
WEIGHTS = {'purity': 0.4, 'recognition': 0.6}  # Experimental, uncalibrated
TICKERS = ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'META', 'TSLA')
DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def read_json(p: Path) -> dict:
    if not p.is_file():
        raise ValueError(f'Missing input file: {p}')
    x = json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(x, dict):
        raise ValueError(f'JSON must contain an object: {p}')
    return x


def check(condition, msg):
    if not condition:
        raise ValueError(msg)


def number(x, field):
    check(type(x) in (int, float) and math.isfinite(x), f'Invalid numeric {field}: {x!r}')
    return float(x)


def approx(a, b, tol=1_000_000):
    return abs(a - b) <= tol


def pct(a, b):
    return None if b == 0 else round(a / b * 100, 4)


def signed(x, decimals=2):
    return f'{x:+.{decimals}f}'


def verify_aapl(row, stage4, stage5):
    check(stage4.get('ticker') == stage5.get('ticker') == row['ticker'] == 'AAPL', 'AAPL ticker mismatch')
    check(stage4.get('fiscal_year') == stage5.get('fiscal_year') == row['fiscal_year'], 'AAPL year mismatch')
    ar = stage4['annual_metrics']
    check(approx(number(ar['revenue']['FY2025_usd_m'], 'AAPL SEC 2025 revenue')*1e6,
                 number(row['revenue_usd'], 'AAPL FMP revenue')), 'AAPL SEC/FMP mismatch')
    check(approx(number(ar['revenue']['FY2024_usd_m'], 'AAPL SEC 2024 revenue')*1e6,
                 number(row['previous_revenue_usd'], 'AAPL FMP prior revenue')), 'AAPL FY2024 mismatch')
    t25 = number(ar['trade_accounts_receivable']['FY2025_usd_m'], 'FY2025 trade AR')
    t24 = number(ar['trade_accounts_receivable']['FY2024_usd_m'], 'FY2024 trade AR')
    v25 = number(ar['vendor_nontrade_receivables']['FY2025_usd_m'], 'FY2025 vendor AR')
    v24 = number(ar['vendor_nontrade_receivables']['FY2024_usd_m'], 'FY2024 vendor AR')
    check(approx((t25 + v25)*1e6, number(stage4['fmp_receivables']['FY2025_usd'], 'FMP net AR')),
          'FMP netReceivables is not reconciled to trade+vendor AR')
    check(abs((t25/t24 - 1)*100 - number(ar['trade_accounts_receivable']['yoy_growth_pct'], 'AR growth')) < .025,
          'AAPL trade AR growth mismatch')
    rev_growth = (row['revenue_usd']/row['previous_revenue_usd'] - 1)*100
    gap = (t25/t24 - 1)*100 - rev_growth
    check(abs(gap - number(stage5['revenue_recognition_diagnostics']['trade_ar_minus_revenue_growth_pp'],
                                  'Stage 5 gap')) < .03, 'Stage 4/5 trade AR gap mismatch')
    check(stage5['reconciliation'].startswith('PASS'), 'AAPL Stage 5 reconciliation failed')
    return {
        'trade_ar_fy2024_usd_m': t24, 'trade_ar_fy2025_usd_m': t25,
        'vendor_ar_fy2024_usd_m': v24, 'vendor_ar_fy2025_usd_m': v25,
        'trade_ar_growth_pct': round((t25/t24-1)*100, 4),
        'trade_ar_minus_revenue_growth_pp': round(gap, 4),
        'trade_ar_investigation_open': bool(stage5['revenue_recognition_diagnostics']['trade_ar_growth_investigation_flag']),
        'year_end_trade_ar_revenue_proxy_days': {
            'FY2024': stage5['revenue_recognition_diagnostics']['year_end_trade_ar_to_annual_revenue_proxy_days_FY2024'],
            'FY2025': stage5['revenue_recognition_diagnostics']['year_end_trade_ar_to_annual_revenue_proxy_days_FY2025'],
        },
        'from_opening_deferred_revenue_usd_m': stage5['revenue_recognition_diagnostics']['recognized_from_opening_deferred_revenue_FY2025_usd_m'],
        'note': 'Trade AR only (SEC); proxy uses year-end balance, NOT standard average-balance DSO. Gap is a review flag, not proof of misstatement.',
        'source_url': stage4['source_url'],
        'source_locator': stage4['source_locators']['ar'],
    }


def verify_company(row, stage4=None, stage5=None):
    ticker = row['ticker']
    check(ticker in TICKERS, f'Unexpected ticker {ticker}')
    check(row['currency'] == 'USD', f'{ticker} currency changed')
    year = row['fiscal_year']
    check(type(year) is int and 2020 <= year <= 2035, f'{ticker} invalid fiscal year')
    rev = number(row['revenue_usd'], f'{ticker} revenue')
    prev = number(row['previous_revenue_usd'], f'{ticker} previous revenue')
    check(rev > 0 and prev > 0, f'{ticker} revenue must be positive')
    check(abs((rev/prev-1)*100 - number(row['revenue_growth_pct'], f'{ticker} growth')) < .025,
          f'{ticker} growth inconsistent')
    sec = row['sec']
    check(sec and sec['status'] == f'SEC_RECONCILED_FY{year}', f'{ticker} SEC evidence unavailable')
    check(str(sec.get('filing_url', '')).startswith('https://www.sec.gov/'), f'{ticker} missing SEC source')
    entries = sec['category_mix']
    check(isinstance(entries, list) and len(entries) >= 2, f'{ticker} bad SEC category ledger')
    names = [e['name'] for e in entries]
    check(len(names) == len(set(names)), f'{ticker} duplicate categories')
    sum_now = sum(number(e['current_revenue_usd'], e['name']+' current') for e in entries)
    sum_prev = sum(number(e['previous_revenue_usd'], e['name']+' prior') for e in entries)
    check(approx(sum_now, rev) and approx(sum_prev, prev), f'{ticker} both-year SEC category totals must reconcile')
    check(approx(sum_now, sum(number(e['current_revenue_usd'], e['name']) for e in row['revenue_mix'])),
          f'{ticker} SEC/revenue_mix mismatch')
    category_rows = []
    for e in entries:
        now = number(e['current_revenue_usd'], f'{ticker} {e["name"]}')
        prior = number(e['previous_revenue_usd'], f'{ticker} {e["name"]} prior')
        check(approx(now-prior, number(e['yoy_change_usd'], f'{ticker} {e["name"]} change')),
              f'{ticker} category bridge mismatch {e["name"]}')
        category_rows.append({
            'name': e['name'], 'current_revenue_usd': now, 'previous_revenue_usd': prior,
            'change_usd': now-prior, 'share_of_gaap_revenue_pct': pct(now, rev),
            'contribution_to_gaap_revenue_growth_pp': pct(now-prior, prev),
        })
    check(approx(sum(e['change_usd'] for e in category_rows), rev-prev), f'{ticker} growth bridge mismatch')
    adjustments = {}
    if ticker == 'GOOGL':
        adj = next(e for e in category_rows if e['name'] == 'Hedging gains (losses)')
        gross_operating = rev - adj['current_revenue_usd']
        check(gross_operating > 0, 'GOOGL adjusted denominator invalid')
        adjustments = {
            'hedging_adjustment_usd': adj['current_revenue_usd'],
            'gross_operating_sales_before_hedging_usd': gross_operating,
            'hedging_adjustment_as_pct_gaap_revenue': pct(adj['current_revenue_usd'], rev),
            'note': 'Signed GAAP revenue bridge; a negative adjustment can make gross operating sales exceed reported revenue. NOT automatically a purity penalty.',
        }
    elif ticker == 'TSLA':
        cr = next(e for e in category_rows if e['name'] == 'Automotive regulatory credits')
        adjustments = {
            'regulatory_credits_usd': cr['current_revenue_usd'],
            'revenue_excluding_credits_context_only_usd': rev-cr['current_revenue_usd'],
            'regulatory_credits_as_pct_gaap_revenue': pct(cr['current_revenue_usd'], rev),
            'credit_contribution_to_gaap_growth_pp': cr['contribution_to_gaap_revenue_growth_pp'],
            'note': 'Legitimate disclosed operating revenue; excluding credits is a sensitivity analysis, NOT automatic non-core classification or allegation.',
        }
    aapl = verify_aapl(row, stage4, stage5) if ticker == 'AAPL' else None
    fmp_ar_growth = row.get('provider_receivables_growth_pct')
    return {
        'ticker': ticker, 'fiscal_year': year, 'period_end': row['period_end'],
        'filing_url': sec['filing_url'], 'source_locator': sec.get('source_locator', 'See original AAPL SEC evidence notes'),
        'revenue_usd': rev, 'previous_revenue_usd': prev,
        'revenue_growth_pct': round((rev/prev-1)*100, 4),
        'sec_disclosure_coverage_pct': 100., 'sec_reconciliation': 'PASS_FY_AND_PRIOR_FY',
        'revenue_mix': category_rows,
        'adjustments_and_sensitive_revenue': adjustments,
        'provider_ar_growth_pct': fmp_ar_growth,
        'provider_ar_definition_sec_verified': ticker == 'AAPL',
        'provider_ar_comparison_warning': None if ticker == 'AAPL' else 'FMP netReceivables not mapped to SEC trade AR; no cross-company Trade AR comparison or numeric recognition score.',
        'aapl_sec_trade_ar_diagnostic': aapl,
        'organic_growth_pct': row.get('organic_growth_attribution_pct'),
        'organic_growth_status': 'NOT_VERIFIED_AND_NOT_IN_COMPOSITE',
    }


def complete_source(d):
    return isinstance(d, dict) and all(isinstance(d.get(k), str) and len(d[k].strip()) >= 4
        for k in ('source_url', 'source_locator', 'reviewer', 'reviewed_at', 'reviewer_rationale')) \
        and d['source_url'].startswith('https://')


def score_candidate(company, evidence):
    """Experimental conditional score, not a certified revenue-recognition opinion.

    Use an explicit signed revenue adjustment to reconcile GOOGL's negative hedge line;
    a positive disclosed credit (TSLA) is included unless independent evidence labels it
    non-core under a predeclared policy. Noncore classification is NOT automatic.
    """
    result = {'candidate_crq': None, 'candidate_purity': None, 'candidate_recognition': None,
              'evidence_coverage_pct': 0, 'status': 'NOT_SCORED', 'reasons': [],
              'weights_empirically_validated': False, 'production_approved': False}
    if not isinstance(evidence, dict):
        result['reasons'].append('No independently reviewed purity and recognition evidence supplied.')
        return result
    if evidence.get('ticker') != company['ticker'] or evidence.get('fiscal_year') != company['fiscal_year']:
        result['reasons'].append('Evidence ticker/fiscal-year mismatch.')
        return result
    if evidence.get('review_attestation') != 'REVIEWED_BY_NAMED_ANALYST':
        result['reasons'].append('A named reviewer and explicit attestation are required; self-attestation is not independently verified by the tool.')
        return result
    purity = evidence.get('purity')
    recognition = evidence.get('recognition')
    if complete_source(purity) and isinstance(purity.get('classification_policy_id'), str) \
       and len(purity['classification_policy_id'].strip()) >= 4:
        try:
            core = number(purity.get('confirmed_core_revenue_usd'), 'core revenue')
            noncore = number(purity.get('confirmed_noncore_revenue_usd'), 'non-core revenue')
            unclassified = number(purity.get('unclassified_revenue_usd'), 'unclassified revenue')
            signed_adj = number(purity.get('signed_revenue_adjustment_usd', 0), 'signed adjustment')
            check(core >= 0 and noncore >= 0 and unclassified >= 0, 'Operating amounts cannot be negative')
            expected_adjustments = company['adjustments_and_sensitive_revenue'].get('hedging_adjustment_usd', 0)
            check(approx(signed_adj, expected_adjustments, 1), 'Signed adjustment must agree with known GAAP hedge bridge')
            check(approx(core+noncore+unclassified+signed_adj, company['revenue_usd']),
                  'Purity ledger must reconcile including signed revenue adjustments')
            denominator = core+noncore+unclassified
            check(denominator > 0 and unclassified <= denominator*.001,
                  'Purity classification incomplete')
            result['candidate_purity'] = round(100*core/denominator, 4)
        except ValueError as ex:
            result['reasons'].append('Purity: '+str(ex))
    else:
        result['reasons'].append('Purity: missing reviewed, source-located classification policy and amount ledger.')
    if complete_source(recognition) and isinstance(recognition.get('rubric_id'), str) and len(recognition['rubric_id'].strip()) >= 4 \
       and isinstance(recognition.get('scoring_basis'), str) and len(recognition['scoring_basis'].strip()) >= 40:
        try:
            value = number(recognition.get('documented_reviewer_score'), 'recognition score')
            check(0 <= value <= 100, 'Recognition score outside [0, 100]')
            check(type(recognition.get('confirmed_material_recognition_issue')) is bool,
                  'Material-issue finding must be explicitly assessed, not null')
            result['candidate_recognition'] = round(value, 4)
        except ValueError as ex:
            result['reasons'].append('Recognition: '+str(ex))
    else:
        result['reasons'].append('Recognition: sourced rubric, scoring basis and independent review unavailable.')
    result['evidence_coverage_pct'] = round(100*(.4*(result['candidate_purity'] is not None) +
                                                    .6*(result['candidate_recognition'] is not None)), 2)
    if isinstance(recognition, dict) and recognition.get('confirmed_material_recognition_issue') is True:
        result['status'] = 'MANUAL_REVIEW_REQUIRED'
        result['reasons'].append('Confirmed material issue: automatic composite forbidden.')
        return result
    aapl = company['aapl_sec_trade_ar_diagnostic']
    if aapl and aapl['trade_ar_investigation_open'] and not (
            isinstance(recognition, dict) and recognition.get('ar_investigation_resolved') is True and
            isinstance(recognition.get('ar_resolution_source_locator'), str) and len(recognition['ar_resolution_source_locator'].strip()) >= 4):
        result['reasons'].append('AAPL: open SEC trade AR investigation, composite withheld (not penalized).')
        return result
    if result['candidate_recognition'] is not None and result['candidate_recognition'] < 50:
        result['status'] = 'MANUAL_REVIEW_REQUIRED'
        result['reasons'].append('Experimental recognition review gate <50; composite withheld.')
        return result
    if result['evidence_coverage_pct'] == 100:
        result['candidate_crq'] = round(.4*result['candidate_purity']+.6*result['candidate_recognition'], 2)
        result['status'] = 'REVIEWER_ATTESTED_EXPERIMENTAL_UNCALIBRATED'
        result['reasons'].append('Candidate only; source URLs/attestations are not independently audited by this program.')
    return result


def generate(rows, stage4, stage5, evidence=None):
    check(len(rows) == 7, f'Expected 7 MAG7 companies, got {len(rows)}')
    tickers = [r['ticker'] for r in rows]
    check(len(set(tickers)) == 7 and set(tickers) == set(TICKERS), 'MAG7 tickers missing or duplicated')
    output = []
    for row in rows:
        item = verify_company(row, stage4, stage5)
        item['quality'] = score_candidate(item, (evidence or {}).get(item['ticker']))
        output.append(item)
    return output


def report_md(items):
    lines = [
        '# Meridian MAG7 — Core Revenue evidence and scoring readiness', '',
        'Source: uploaded local MAG7 integrated JSON and AAPL Stage 4/5 JSON. The original SEC sources are linked in each record.',
        '', '## Status', '',
        '| Ticker | FY | Revenue growth | SEC category coverage | Candidate CRQ | Status |',
        '|:--|--:|--:|--:|--:|:--|',
    ]
    for r in items:
        q = r['quality']
        score = 'N/A' if q['candidate_crq'] is None else str(q['candidate_crq'])+'*'
        lines.append(f"| {r['ticker']} | {r['fiscal_year']} | {signed(r['revenue_growth_pct'])}% | 100% | {score} | {q['status']} |")
    lines += ['', '100% SEC category coverage means **classification completeness**, not 100% revenue purity or integrity.',
              'Candidate 40% purity / 60% recognition weights are uncalibrated. *An asterisk denotes a reviewer-attested EXPERIMENTAL score, never production approval.*',
              '', '## Company diagnostics', '']
    for r in items:
        lines += [f"### {r['ticker']} FY{r['fiscal_year']}", '',
                  f"- SEC source: {r['filing_url']} ({r['source_locator']}).",
                  f"- Reported revenue: ${r['revenue_usd']/1e9:,.3f}B; growth {signed(r['revenue_growth_pct'])}%."]
        for c in sorted(r['revenue_mix'], key=lambda x: x['current_revenue_usd'], reverse=True):
            lines.append(f"- {c['name']}: ${c['current_revenue_usd']/1e9:,.3f}B, "
                         f"{c['share_of_gaap_revenue_pct']:.2f}% of reported revenue; "
                         f"growth contribution {signed(c['contribution_to_gaap_revenue_growth_pp'])} pp.")
        d = r['aapl_sec_trade_ar_diagnostic']
        if d:
            lines.append(f"- SEC trade AR grew {d['trade_ar_growth_pct']:.2f}%, {signed(d['trade_ar_minus_revenue_growth_pp'])} pp above revenue growth. Investigation flag only; NOT evidence of improper recognition.")
            lines.append(f"- End-of-year AR/revenue proxy {d['year_end_trade_ar_revenue_proxy_days']['FY2024']} → {d['year_end_trade_ar_revenue_proxy_days']['FY2025']} days (not standard DSO).")
        if r['provider_ar_comparison_warning']:
            lines.append('- '+r['provider_ar_comparison_warning'])
        if r['adjustments_and_sensitive_revenue']:
            lines.append('- Special item: '+r['adjustments_and_sensitive_revenue']['note'])
        lines.append('- CRQ: '+str(r['quality']['candidate_crq'])+'; '+ '; '.join(r['quality']['reasons']))
        lines.append('')
    lines += ['## Model controls', '',
              '- Do not reclassify Tesla regulatory credits as fake/non-core just because they are policy-dependent.',
              '- Google hedging gains/losses are signed adjustments; do not subtract them twice or allow purity >100%.',
              '- Deferred revenue recognized as obligations are satisfied is normal, not a non-core deduction.',
              '- Accounts receivable divergence is an investigation signal, not a numeric recognition-integrity penalty.',
              '- Product-segment growth is not the same as acquisition/FX-adjusted organic growth.',
              '- Do not feed candidate scores into production Earnings Quality or Buy/Sell/Hold until independent validation and calibration.']
    return '\n'.join(lines)+'\n'


def export(output_dir, items, input_paths):
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {'model_version': MODEL, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'inputs': [str(x) for x in input_paths], 'scoring_weights_experimental': WEIGHTS,
              'production_approved': False, 'weights_calibrated': False, 'production_modified': False,
              'companies': items}
    (output_dir/'mag7_crq_model_review.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    columns = ('ticker fiscal_year revenue_growth_pct sec_disclosure_coverage_pct '
               'provider_ar_growth_pct sec_trade_ar_growth_pct sec_trade_ar_gap_pp '
               'google_hedging_adjustment_pct tesla_regulatory_credit_share_pct '
               'candidate_purity candidate_recognition candidate_crq evidence_coverage_pct status reasons').split()
    with (output_dir/'mag7_crq_model_review.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in items:
            ar = r['aapl_sec_trade_ar_diagnostic'] or {}
            sp = r['adjustments_and_sensitive_revenue']
            q = r['quality']
            writer.writerow({
                'ticker': r['ticker'], 'fiscal_year': r['fiscal_year'],
                'revenue_growth_pct': r['revenue_growth_pct'],
                'sec_disclosure_coverage_pct': r['sec_disclosure_coverage_pct'],
                'provider_ar_growth_pct': r['provider_ar_growth_pct'],
                'sec_trade_ar_growth_pct': ar.get('trade_ar_growth_pct'),
                'sec_trade_ar_gap_pp': ar.get('trade_ar_minus_revenue_growth_pp'),
                'google_hedging_adjustment_pct': sp.get('hedging_adjustment_as_pct_gaap_revenue'),
                'tesla_regulatory_credit_share_pct': sp.get('regulatory_credits_as_pct_gaap_revenue'),
                'candidate_purity': q['candidate_purity'],
                'candidate_recognition': q['candidate_recognition'],
                'candidate_crq': q['candidate_crq'],
                'evidence_coverage_pct': q['evidence_coverage_pct'],
                'status': q['status'], 'reasons': ' | '.join(q['reasons']),
            })
    (output_dir/'mag7_crq_model_review.md').write_text(report_md(items), encoding='utf-8')
    return report


def self_test():
    # Must exercise genuine uploaded files or their copies in production; no API.
    p = Path(__file__).resolve().parent
    candidates = [
        (p/'mag7_core_revenue_review.json', p/'aapl_stage4_recognition_review.json', p/'aapl_stage5_scoring_readiness.json'),
        (DEFAULT_ROOT/'reports/core_revenue_final/mag7_core_revenue_review.json',
         DEFAULT_ROOT/'reports/core_revenue_v1_pilot/aapl_stage4_recognition_review.json',
         DEFAULT_ROOT/'reports/core_revenue_v1_pilot/aapl_stage5_scoring_readiness.json'),
    ]
    known = next((v for v in candidates if all(x.exists() for x in v)), None)
    check(known is not None, 'Self-test requires the three input JSON reports alongside this file or in Production reports/.')
    raw, st4, st5 = (read_json(x) for x in known)
    out = generate(raw['companies'], st4, st5)
    check(len(out) == 7 and all(x['sec_reconciliation'] == 'PASS_FY_AND_PRIOR_FY' for x in out), 'MAG7 reconciliation failed')
    check(all(x['quality']['candidate_crq'] is None for x in out), 'Fabricated score found')
    a = next(x for x in out if x['ticker'] == 'AAPL')
    check(a['aapl_sec_trade_ar_diagnostic']['trade_ar_investigation_open'], 'AAPL investigation dropped')
    check(abs(a['aapl_sec_trade_ar_diagnostic']['trade_ar_minus_revenue_growth_pp']-12.63) < .03, 'AR gap invalid')
    g = next(x for x in out if x['ticker'] == 'GOOGL')
    check(g['adjustments_and_sensitive_revenue']['hedging_adjustment_usd'] < 0, 'Google hedge sign lost')
    t = next(x for x in out if x['ticker'] == 'TSLA')
    check(2 < t['adjustments_and_sensitive_revenue']['regulatory_credits_as_pct_gaap_revenue'] < 2.2, 'Tesla credit share wrong')
    test = deepcopy(a)
    test['aapl_sec_trade_ar_diagnostic']['trade_ar_investigation_open'] = False
    good = {'ticker': 'AAPL', 'fiscal_year': 2025, 'review_attestation': 'REVIEWED_BY_NAMED_ANALYST',
            'purity': {'source_url': a['filing_url'], 'source_locator': 'FY2025 Note 2',
                       'reviewer':'TEST ANALYST', 'reviewed_at':'2026-10-02',
                       'reviewer_rationale':'Synthetic example ONLY', 'classification_policy_id':'TEST_1',
                       'confirmed_core_revenue_usd':a['revenue_usd']*.95,
                       'confirmed_noncore_revenue_usd':a['revenue_usd']*.05,
                       'unclassified_revenue_usd':0, 'signed_revenue_adjustment_usd':0},
            'recognition': {'source_url':a['filing_url'], 'source_locator':'FY2025 Note 2',
                            'reviewer':'TEST ANALYST', 'reviewed_at':'2026-10-02',
                            'reviewer_rationale':'Synthetic example ONLY', 'rubric_id':'TEST_RRI_1',
                            'scoring_basis':'Synthetic rubric with numerical components for testing only.',
                            'documented_reviewer_score':90, 'confirmed_material_recognition_issue':False,
                            'ar_investigation_resolved':True,
                            'ar_resolution_source_locator':'FY2025 Note 4 synthetic test'}}
    check(score_candidate(test,good)['candidate_crq'] == 92, 'Candidate math incorrect')
    good['recognition']['ar_investigation_resolved'] = False
    check(score_candidate(a,good)['candidate_crq'] is None, 'Open AAPL AR incorrectly scored')
    good['recognition']['ar_investigation_resolved'] = True
    good['recognition']['confirmed_material_recognition_issue'] = True
    check(score_candidate(test,good)['candidate_crq'] is None, 'Material issue veto failed')
    good['recognition']['confirmed_material_recognition_issue'] = False
    good['recognition']['documented_reviewer_score'] = 0
    check(score_candidate(test,good)['candidate_crq'] is None, 'Low RRI gate failed')
    badrow = deepcopy(raw['companies'][0]);badrow['revenue_usd'] += 2_000_000
    try:
        verify_company(badrow, st4, st5)
        raise AssertionError('Invalid revenue accepted')
    except ValueError:
        pass
    print('SELF-TEST PASS: MAG7 both-year SEC bridge; AAPL trade/vendor AR; Google signed hedging;')
    print('Tesla credits; candidate arithmetic; unresolved-AR/material/low-RRI gates; mismatch rejection; no fabricated scores.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--input', type=Path, default=DEFAULT_ROOT/'reports/core_revenue_final/mag7_core_revenue_review.json')
    parser.add_argument('--aapl-stage4', type=Path, default=DEFAULT_ROOT/'reports/core_revenue_v1_pilot/aapl_stage4_recognition_review.json')
    parser.add_argument('--aapl-stage5', type=Path, default=DEFAULT_ROOT/'reports/core_revenue_v1_pilot/aapl_stage5_scoring_readiness.json')
    parser.add_argument('--evidence', type=Path, default=None, help='Optional *independently reviewed* evidence, ticker-keyed JSON')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_ROOT/'reports/core_revenue_final')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    src, st4, st5 = read_json(args.input), read_json(args.aapl_stage4), read_json(args.aapl_stage5)
    reviewed = read_json(args.evidence) if args.evidence else {}
    rows = generate(src['companies'], st4, st5, reviewed)
    report = export(args.output_dir, rows, [args.input, args.aapl_stage4, args.aapl_stage5])
    print('\nMERIDIAN CORE REVENUE: MAG7 EVIDENCE AUDIT')
    print('Ticker  FY    Revenue YoY   SEC reconciled   Candidate CRQ   Status')
    for r in report['companies']:
        q = r['quality']; v = 'N/A' if q['candidate_crq'] is None else f"{q['candidate_crq']:.2f}*"
        print(f"{r['ticker']:<6}  {r['fiscal_year']}  {r['revenue_growth_pct']:>+9.2f}%   "
              f"{'PASS':^14}   {v:^13}   {q['status']}")
    print('\nOutputs:', args.output_dir)
    print('Production scoring untouched; candidate weights uncalibrated; missing evidence is NOT a zero score.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AssertionError) as ex:
        print('REFUSED:', ex, file=sys.stderr)
        raise SystemExit(2)
