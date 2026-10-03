#!/usr/bin/env python3
"""Meridian Research — integrated MAG7 Core Revenue research tool.

One command, read-only for production. Consolidates local CRQ stages 1–7.
Outputs one JSON, one CSV, one human-readable MD, and an optional reviewer
worksheet. Validated financial indicators are distinct from quality scoring.

From the Production root, after copying this file into scripts/:
    python3 scripts/core_revenue_mag7_final.py --self-test
    python3 scripts/core_revenue_mag7_final.py
Optional re-fetch using the project's existing provider (only if desired):
    python3 scripts/core_revenue_mag7_final.py --refresh
Optional, experimental reviewer-attested scores (never production approved):
    python3 scripts/core_revenue_mag7_final.py --evidence /path/to/reviewed_evidence.json

No numeric 'recognition integrity' score is created by AR divergence alone.
No 'verified' designation is inferred solely from a JSON boolean or citation.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from io import StringIO
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'reports' / 'core_revenue_v1_pilot'
OUT = ROOT / 'reports' / 'core_revenue_final'
TICKERS = ('AAPL', 'MSFT', 'GOOGL', 'NVDA', 'AMZN', 'META', 'TSLA')
MODEL_VERSION = 'CRQ-V1-INTEGRATED-RESEARCH-CANDIDATE'
WEIGHTS = {'purity': 0.40, 'recognition': 0.60}  # experimental, NOT empirically calibrated


# Published revenue-disaggregation ledgers. Amounts are USD MILLIONS.
# 2025 / 2026 FY annual SEC 10-K sources (not provisional forecasts).
# They are tested against BOTH published totals AND the user's period-matched FMP.
# Classification here means disclosure coverage, NOT independent transaction quality.
SEC_FACTS = {
    'MSFT': {
        'fiscal_year': 2026, 'period_end': '2026-06-30', 'reported': (331839,281724),
        'source_url':'https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm',
        'source_locator':'FY2026 10-K, Note 18, Segment Information and Geographic Data, printed p.84 (PDF p.93)',
        'categories': [('Productivity and Business Processes',139996,120810),
                       ('Intelligent Cloud',137791,106265), ('More Personal Computing',54052,54649)],
    },
    'NVDA': {
        'fiscal_year': 2026, 'period_end': '2026-01-25', 'reported': (215938,130497),
        'source_url':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm',
        'source_locator':'FY2026 10-K, MD&A, Revenue by Reportable Segments, printed p.40 (PDF p.42)',
        'categories': [('Compute & Networking',193479,116193),('Graphics',22459,14304)],
    },
    'GOOGL': {
        'fiscal_year': 2025, 'period_end': '2025-12-31', 'reported': (402836,350018),
        'source_url':'https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm',
        'source_locator':'FY2025 10-K, Note 2, Revenues, Disaggregated Revenues, printed p.60 (PDF p.87)',
        'categories': [('Google Search & other',224532,198084),('YouTube ads',40367,36147),
                       ('Google Network',29792,30359),('Google subscriptions, platforms, and devices',48030,40340),
                       ('Google Cloud',58705,43229),('Other Bets',1537,1648),
                       ('Hedging gains (losses)',-127,211)],
        'special_notes': ['Hedging gain/loss is a separately disclosed REVENUE adjustment, not a product/service line. '
                          'The 100% reconciliation includes this negative adjustment; do not call it operating core sales '
                          'or automatically subtract it a second time.']
    },
    'AMZN': {
        'fiscal_year': 2025, 'period_end': '2025-12-31', 'reported': (716924,637959),
        'source_url':'https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm',
        'source_locator':'FY2025 10-K, Note 10, Segment Information, product/service net-sales table, printed p.69 (PDF p.83)',
        'categories': [('Online stores',269287,247029),('Physical stores',22561,21215),
                       ('Third-party seller services',172162,156146),('Advertising services',68635,56214),
                       ('Subscription services',49619,44374),('AWS',128725,107556),('Other',5935,5425)],
        'special_notes': ['Other includes multiple disclosed operating offerings; it is not automatically non-core.']
    },
    'META': {
        'fiscal_year': 2025, 'period_end': '2025-12-31', 'reported': (200966,164501),
        'source_url':'https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm',
        'source_locator':'FY2025 10-K, Consolidated and Segment Results, Revenue by Source/Segment',
        'categories': [('Family of Apps - Advertising',196175,160633),
                       ('Family of Apps - Other',2584,1722),('Reality Labs',2207,2146)],
        'special_notes': ['Family of Apps Advertising and Other are subcategories; no Family of Apps total is counted twice.']
    },
    'TSLA': {
        'fiscal_year': 2025, 'period_end': '2025-12-31', 'reported': (94827,97690),
        'source_url':'https://www.sec.gov/Archives/edgar/data/1318605/000162828026003952/tsla-20251231.htm',
        'source_locator':'FY2025 10-K, MD&A, Results of Operations, Revenues',
        'categories': [('Automotive sales',65821,72480),('Automotive regulatory credits',1993,2763),
                       ('Automotive leasing',1712,1827),('Services and other',12530,10534),
                       ('Energy generation and storage',12771,10086)],
        'special_notes': ['Regulatory credits are separately disclosed operating revenue and policy-sensitive; '
                          'do not label them fabricated or automatically remove them from GAAP revenue.']
    },
}


def verify_generic_sec(ticker, fmp):
    fact = SEC_FACTS[ticker]
    problems = []
    if (fmp.get('fiscal_year') != fact['fiscal_year'] or
        fmp.get('period_end') != fact['period_end'] or fmp.get('currency') != 'USD'):
        return None, [f'{ticker} SEC period/currency differs from FMP annual record; refusing attachment.']
    current, prior = fact['reported']
    if (sum(c[1] for c in fact['categories']) != current or
        sum(c[2] for c in fact['categories']) != prior):
        return None, [f'{ticker} SEC source ledger fails internal revenue bridge.']
    rev, prior_rev = finite(fmp.get('revenue')), finite(fmp.get('prior_revenue'))
    if rev is None or prior_rev is None or (abs(rev/current/1e6-1)>0.0001 or
                                          abs(prior_rev/prior/1e6-1)>0.0001):
        return None, [f'{ticker} FMP annual revenue does not match the SEC category ledger; refusing attachment.']
    mix = [{'name':name, 'current_revenue_usd':now*1e6,
            'previous_revenue_usd':before*1e6, 'yoy_change_usd':(now-before)*1e6,
            'share_pct':round(100*now/current,3)} for name,now,before in fact['categories']]
    return {
        'status': f'SEC_RECONCILED_FY{fact["fiscal_year"]}',
        'filing_url': fact['source_url'], 'source_locator':fact['source_locator'],
        'operating_category_disclosure_coverage_pct':100.0,
        'coverage_is_not_purity_or_quality_score':True,
        'category_mix':mix,
        'trade_ar_growth_pct':None, 'trade_ar_revenue_gap_pp':None,
        'trade_ar_investigation_flag':False, # unknown != false in next row: do not claim reviewed
        'trade_ar_source_definition':'NOT_SEC_VERIFIED',
        'special_notes':fact.get('special_notes', []),
    }, problems


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        z = float(value)
        return z if math.isfinite(z) else None
    except (ValueError, TypeError, OverflowError):
        return None


def fail_if(cond, message):
    if cond:
        raise ValueError(message)


def load_json(path, required=False):
    if not path.is_file():
        if required:
            raise FileNotFoundError(f'Required report not found: {path}')
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f'Invalid JSON at {path}: {e}') from e


def save_generated(path, content):
    """Atomic replace ONLY in the dedicated generated-report folder."""
    fail_if(path.parent != OUT, f'Unsafe output location: {path}')
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=OUT, encoding='utf-8',
                                         suffix='.tmp', delete=False, newline='') as f:
            tmp = Path(f.name)
            f.write(content)
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def s(v, digits=2, suffix=''):
    return 'N/A' if v is None else f'{v:+.{digits}f}{suffix}'


def pct_delta(a, b):
    return None if a is None or b is None else a - b


def source_snapshot(refresh=False, cache_only=False):
    snapshot = BASE / 'mag7_crq_v1_pilot.json'
    if not refresh:
        data = load_json(snapshot, required=True)
        rows = data.get('results') if isinstance(data, dict) else None
        fail_if(not isinstance(rows, list), 'Stage 1 report must contain results array')
        return rows, f'local Stage 1 snapshot: {snapshot}'
    # Import the existing stage-1 tool for its already-tested FMP integration;
    # this script is standalone for non-refresh runs.
    sys.path.insert(0, str(ROOT / 'scripts'))
    import core_revenue_v1_pilot as pilot
    rows = []
    for ticker in TICKERS:
        income, balance, errors = pilot.fetch(ticker, cache_only=cache_only)
        rows.append(pilot.describe(ticker, income, balance, error=errors))
    return rows, ('existing production FMP cache' if cache_only else
                  'existing production FMP API/cache')


def verify_aapl(stage2, stage3, stage4, stage5, fmp):
    """Check stage evidence before attaching SEC-anchored AAPL observations."""
    issues = []
    if any(x is None for x in (stage2, stage3, stage4, stage5)):
        return None, ['Missing AAPL Stage 2/3/4/5 report; not attaching SEC conclusions.']
    try:
        for label, rep in (('Stage 2', stage2), ('Stage 3', stage3),
                           ('Stage 4', stage4), ('Stage 5', stage5)):
            fail_if(rep.get('ticker') != 'AAPL' or rep.get('fiscal_year') != 2025,
                    f'{label} ticker or fiscal year mismatch')
            fail_if(rep.get('currency') != 'USD', f'{label} currency mismatch')
        fail_if(fmp.get('fiscal_year') != 2025 or fmp.get('currency') != 'USD',
                'FMP AAPL fiscal year/currency has changed; FY2025 SEC evidence does not apply.')
        total = finite(stage2['revenue_classification']['reported_total_usd'])
        fail_if(total is None or total <= 0, 'Missing FY2025 SEC total')
        fmp_rev = finite(fmp.get('revenue'))
        fail_if(fmp_rev is None or abs(fmp_rev - total)/total > .0001,
                'FMP current revenue differs from SEC FY2025')
        fail_if(stage2['fmp_reconciliation'].get('status') != 'MATCH',
                'SEC/FMP reconciliation not matched')
        fail_if(not str(stage5.get('reconciliation', '')).startswith('PASS'),
                'Stage 5 cross-report audit not passed')
        cats2 = stage2.get('revenue_categories', [])
        cats3 = stage3.get('categories', [])
        fail_if(len(cats2) != 5 or len(cats3) != 5, 'Expected five Apple business categories')
        by_name2 = {c['name']: finite(c['FY2025_usd_millions']) * 1e6 for c in cats2}
        by_name3 = {c['name']: finite(c['FY2025_usd']) for c in cats3}
        fail_if(by_name2.keys() != by_name3.keys(), 'Stage 2/3 categories differ')
        fail_if(any(abs(by_name2[k]-by_name3[k]) > 1 for k in by_name2),
                'Stage 2/3 amounts differ')
        fail_if(abs(sum(by_name2.values())-total)/total > .00001,
                'Five revenue categories do not reconcile')
        mix = []
        for row in cats3:
            inc = finite(row.get('FY2025_usd'))
            prior = finite(row.get('FY2024_usd'))
            mix.append({'name': row['name'], 'current_revenue_usd': inc,
                        'previous_revenue_usd': prior,
                        'yoy_change_usd': inc-prior if prior is not None else None,
                        'share_pct': round(100*inc/total, 3)})
        diag = stage5['revenue_recognition_diagnostics']
        trade = stage4['annual_metrics']['trade_accounts_receivable']
        fail_if(abs(finite(diag['trade_ar_growth_pct'])-
                    finite(trade['yoy_growth_pct'])) > .03,
                'Stage 4/5 trade AR growth differs')
        sec_url = stage2.get('source_url')
        fail_if(not isinstance(sec_url, str) or not sec_url.startswith('https://www.sec.gov/'),
                'SEC URL absent or malformed')
        return {
            'status': 'SEC_RECONCILED_FY2025',
            'filing_url': sec_url,
            'operating_category_disclosure_coverage_pct': round(100*sum(by_name2.values())/total, 2),
            'coverage_is_not_purity_or_quality_score': True,
            'category_mix': mix,
            'trade_ar_growth_pct': finite(diag['trade_ar_growth_pct']),
            'trade_ar_revenue_gap_pp': finite(diag['trade_ar_minus_revenue_growth_pp']),
            'trade_ar_investigation_flag': bool(diag['trade_ar_growth_investigation_flag']),
            'year_end_trade_ar_revenue_proxy_days': {
                'previous': diag['year_end_trade_ar_to_annual_revenue_proxy_days_FY2024'],
                'current': diag['year_end_trade_ar_to_annual_revenue_proxy_days_FY2025']},
            'trade_ar_source_definition': 'SEC trade receivables ONLY; not FMP combined receivables',
            'concentration': stage5.get('receivables_concentration_SEC_note4'),
            'revenue_recognition_not_inferred_from_AR': True,
        }, issues
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return None, [f'SEC/FMP cross-check refused: {exc}']


def complete_source(entry):
    return (isinstance(entry, dict) and all(
        isinstance(entry.get(k), str) and len(entry[k].strip()) >= 4
        for k in ('source_url', 'source_locator', 'reviewer', 'reviewed_at', 'reviewer_rationale'))
        and entry['source_url'].startswith('https://'))


def evidence_candidate(row, evidence):
    """Never imply that a self-attestation proves independent auditing."""
    output = {'score': None, 'purity_score': None, 'recognition_score': None,
              'coverage_pct': 0, 'status': 'NOT_SCORED', 'reasons': [],
              'model_calibrated': False, 'production_approved': False}
    if not isinstance(evidence, dict):
        output['reasons'].append('No independently documented purity/recognition rubric supplied.')
        return output
    if evidence.get('ticker') != row['ticker'] or evidence.get('fiscal_year') != row['fiscal_year']:
        output['reasons'].append('Evidence ticker/fiscal year mismatch.')
        return output
    if evidence.get('review_attestation') != 'REVIEWED_BY_NAMED_ANALYST':
        output['reasons'].append('Explicit analyst attestation absent; JSON true is not verification.')
        return output
    p, r = evidence.get('purity'), evidence.get('recognition')
    rev = finite(row.get('revenue'))
    if complete_source(p) and rev and rev > 0:
        core = finite(p.get('confirmed_core_revenue_usd'))
        noncore = finite(p.get('confirmed_noncore_revenue_usd'))
        unclassified = finite(p.get('unclassified_revenue_usd'))
        if all(v is not None and v >= 0 for v in (core, noncore, unclassified)):
            if abs((core+noncore+unclassified)-rev)/rev < .001 and unclassified/rev <= .001:
                output['purity_score'] = round(core/rev*100, 4)
            else:
                output['reasons'].append('Revenue split incomplete or does not match FMP period.')
        else:
            output['reasons'].append('Missing reconciled purity amounts.')
    else:
        output['reasons'].append('Missing source-located purity classification/reviewer.')
    if complete_source(r) and isinstance(r.get('rubric_id'), str) and r['rubric_id'].strip():
        v = finite(r.get('documented_reviewer_score'))
        if v is not None and 0 <= v <= 100:
            output['recognition_score'] = v
        else:
            output['reasons'].append('Invalid/missing recognition score.')
    else:
        output['reasons'].append('Missing reviewed recognition score/rubric/source.')
    output['coverage_pct'] = 100*sum(w for k,w in WEIGHTS.items()
                                     if output[f'{k}_score'] is not None)
    if r and r.get('confirmed_material_recognition_issue') is True:
        output['status'] = 'MANUAL_REVIEW_REQUIRED'
        output['reasons'].append('Confirmed material recognition issue; composite blocked.')
    elif row.get('open_trade_ar_investigation') and not (
            isinstance(r, dict) and r.get('ar_investigation_resolved') is True
            and isinstance(r.get('ar_resolution_source_locator'), str)
            and len(r['ar_resolution_source_locator'].strip()) >= 4):
        output['reasons'].append('Trade-AR review remains open; no automatic penalty, score withheld.')
    elif output['recognition_score'] is not None and output['recognition_score'] < 50:
        output['status'] = 'MANUAL_REVIEW_REQUIRED'
        output['reasons'].append('Below experimental recognition review threshold (50).')
    elif output['purity_score'] is not None and output['recognition_score'] is not None:
        output['score'] = round(.4*output['purity_score'] + .6*output['recognition_score'], 2)
        output['status'] = 'REVIEWER_ATTESTED_EXPERIMENTAL_NOT_AUDITED'
        output['reasons'].append('Reviewer-attested candidate only; evidence not independently audited by this tool and weights uncalibrated.')
    return output


def analyze_one(base, aapl_reports, evidence):
    ticker = base['ticker']
    row = {
        'ticker': ticker, 'fiscal_year': base.get('fiscal_year'),
        'period_end': base.get('period_end'), 'currency': base.get('currency'),
        'revenue_usd': finite(base.get('revenue')),
        'previous_revenue_usd': finite(base.get('prior_revenue')),
        'revenue_growth_pct': finite(base.get('revenue_growth_pct')),
        'provider_receivables_field': base.get('receivables_field'),
        'provider_receivables_growth_pct': finite(base.get('receivables_growth_pct')),
        'provider_receivables_definition_sec_verified': False,
        'sec': None, 'revenue_mix': None, 'organic_growth_attribution_pct': None,
        'open_trade_ar_investigation': False, 'notices': [],
        'data_status': 'FMP_ANNUAL_AVAILABLE' if base.get('financial_data_available') else 'MISSING_FMP_DATA',
        'quality': None,
    }
    if base.get('errors'):
        row['notices'].extend(str(x) for x in base['errors'])
    if not base.get('statement_periods_aligned'):
        row['notices'].append('Income and balance sheet periods/currency did not align; AR diagnostic withheld.')
        row['provider_receivables_growth_pct'] = None
    if ticker == 'AAPL':
        sec, issues = verify_aapl(*aapl_reports, fmp=base)
        row['notices'].extend(issues)
        if sec:
            row['sec'] = sec
            row['revenue_mix'] = sec['category_mix']
            row['open_trade_ar_investigation'] = sec['trade_ar_investigation_flag']
            row['provider_receivables_definition_sec_verified'] = True
            row['data_status'] = 'FMP_AND_SEC_RECONCILED'
    elif ticker in SEC_FACTS:
        sec, issues = verify_generic_sec(ticker, base)
        row['notices'].extend(issues)
        if sec:
            row['sec'] = sec
            row['revenue_mix'] = sec['category_mix']
            row['data_status'] = 'FMP_AND_SEC_RECONCILED'
            row['notices'].extend(sec.get('special_notes', []))
        row['notices'].append('Provider receivables not independently mapped to SEC trade AR; not comparable with Apple trade AR.')
    if row['revenue_growth_pct'] is None:
        row['notices'].append('Revenue growth unavailable; quality analysis incomplete.')
    ev = evidence.get(ticker) if isinstance(evidence, dict) else None
    row['quality'] = evidence_candidate(row, ev)
    if row['quality']['score'] is None and ticker == 'AAPL' and row['sec']:
        row['quality']['reasons'].append('SEC category coverage ≠ independently validated purity; open Trade AR investigation; recognition rubric missing.')
    if row['quality']['score'] is None and ticker != 'AAPL':
        row['quality']['reasons'].append('SEC disclosure categories may reconcile, but independently reviewed purity and recognition rubric are not supplied.')
    return row


def worksheet(rows):
    return {'_instructions': ('OPTIONAL reviewer worksheet; do not change attestation to force a score. '
                              'Supply source-located independent judgment, actual SEC category evidence, '
                              'fiscal-year-aligned amounts, and a documented RRI rubric. '
                              'Tool cannot independently verify uploaded URLs or reviewer identity. '
                              'Experimental candidate scores NEVER change production rating.'),
            **{r['ticker']: {
                'ticker': r['ticker'], 'fiscal_year': r['fiscal_year'],
                'review_attestation': 'NOT_REVIEWED',
                'purity': {'source_url': None, 'source_locator': None,
                           'reviewer': None, 'reviewed_at': None, 'reviewer_rationale': None,
                           'confirmed_core_revenue_usd': None,
                           'confirmed_noncore_revenue_usd': None,
                           'unclassified_revenue_usd': None},
                'recognition': {'source_url': None, 'source_locator': None,
                                'reviewer': None, 'reviewed_at': None,
                                'reviewer_rationale': None, 'rubric_id': None,
                                'documented_reviewer_score': None,
                                'confirmed_material_recognition_issue': None,
                                'ar_investigation_resolved': False,
                                'ar_resolution_source_locator': None},
                'organic_growth': {'source_url': None, 'attribution': None,
                                   'context_only_not_scored': True},
            } for r in rows}}


def report_md(rows, source):
    out = [
        '# MAG7 — Core Revenue research review', '',
        f'- Model: {MODEL_VERSION}',
        f'- Input: {source}',
        '- Experimental model: 40% reviewed purity + 60% reviewed recognition; organic growth is context.',
        '- This is **not** an audited CRQ, a production Earnings Quality score or an investment recommendation.',
        '- `Not Scored` = insufficient evidence, not zero quality.', '',
        '| Ticker | FY | Revenue growth | Receivables growth¹ | SEC coverage² | Candidate CRQ | Status |',
        '|---|---:|---:|---:|---:|---:|---|'
    ]
    for r in rows:
        sec = r['sec']
        q = r['quality']
        cov = f"{sec['operating_category_disclosure_coverage_pct']:.1f}%" if sec else 'N/A'
        ar = s(r['provider_receivables_growth_pct'], 2, '%')
        if sec and sec['trade_ar_growth_pct'] is not None:
            ar = s(sec['trade_ar_growth_pct'], 2, '%') + ' (SEC trade)'
        score = 'N/A' if q['score'] is None else f"{q['score']:.2f}*"
        out.append(f"| {r['ticker']} | {r['fiscal_year'] or 'N/A'} | "
                   f"{s(r['revenue_growth_pct'], 2, '%')} | {ar} | {cov} | "
                   f"{score} | {q['status']} |")
    out.extend(['', '¹ The non-Apple FMP receivables fields have not been independently mapped to SEC trade receivables; do not rank firms by this figure.',
                '² Coverage means reported operating revenue categories reconcile to reported total; it is NOT a purity or transaction-integrity score.',
                '* Asterisk denotes a reviewer-attested, uncalibrated experimental candidate, not an audited score.', ''])
    for r in rows:
        out.append(f"## {r['ticker']} — FY{r['fiscal_year'] or 'unknown'}")
        out.append(f"Revenue growth: {s(r['revenue_growth_pct'], 2, '%')}. "
                   f"CRQ: {'Not Scored' if r['quality']['score'] is None else str(r['quality']['score']) + ' (experimental)'}.")
        if r['sec']:
            sec = r['sec']
            out.append(f"SEC filing: {sec['filing_url']}")
            if sec.get('trade_ar_growth_pct') is not None:
                out.append(f"SEC trade AR {s(sec['trade_ar_growth_pct'], 2, '%')}; "
                           f"gap to revenue {s(sec['trade_ar_revenue_gap_pp'], 2, ' pp')}. "
                           'Investigation flag is not an allegation of misstatement.')
            out.append(f"Business breakdown (FY{r['fiscal_year']} USD billions; YoY increment USD billions):")
            for c in sec['category_mix']:
                out.append(f"- {c['name']}: {c['current_revenue_usd']/1e9:.3f}; "
                           f"change {s(c['yoy_change_usd']/1e9 if c['yoy_change_usd'] is not None else None,3)}")
        for n in dict.fromkeys(r['quality']['reasons'] + r['notices']):
            out.append(f'- {n}')
        out.append('')
    out.extend(['## Interpretation rules',
                '- **Do not** identify provider net receivables as trade receivables without SEC reconciliation.',
                '- **Do not** subtract normal deferred-revenue recognition from core revenue.',
                '- **Do not** interpret product/service growth contribution as acquisition-adjusted organic growth.',
                '- **Do not** award revenue-recognition integrity points for merely lacking known restatements.',
                '- **Do not** feed a candidate score into the production Earnings Quality or Buy/Sell/Hold rating.', ''])
    return '\n'.join(out) + '\n'


def export(rows, origin):
    report = {
        'model_version': MODEL_VERSION, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': origin, 'candidate_weights': WEIGHTS,
        'weights_empirically_validated': False, 'production_use_approved': False,
        'production_modified': False,
        'caveat': 'Only reviewer-attested experimental candidate scores possible with full evidence; default N/A is correct.',
        'companies': rows,
    }
    save_generated(OUT/'mag7_core_revenue_review.json', json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    fields = ['ticker', 'fiscal_year', 'period_end', 'revenue_usd', 'revenue_growth_pct',
              'provider_receivables_field', 'provider_receivables_growth_pct',
              'sec_category_coverage_pct', 'sec_trade_ar_growth_pct', 'sec_trade_ar_gap_pp',
              'open_trade_ar_investigation', 'organic_growth_attribution_pct',
              'candidate_purity', 'candidate_recognition', 'candidate_crq', 'status', 'reason']
    sio = StringIO()
    w = csv.DictWriter(sio, fieldnames=fields)
    w.writeheader()
    for r in rows:
        sec = r['sec'] or {}
        q = r['quality']
        w.writerow({
            'ticker':r['ticker'], 'fiscal_year':r['fiscal_year'], 'period_end':r['period_end'],
            'revenue_usd':r['revenue_usd'], 'revenue_growth_pct':r['revenue_growth_pct'],
            'provider_receivables_field':r['provider_receivables_field'],
            'provider_receivables_growth_pct':r['provider_receivables_growth_pct'],
            'sec_category_coverage_pct':sec.get('operating_category_disclosure_coverage_pct'),
            'sec_trade_ar_growth_pct':sec.get('trade_ar_growth_pct'),
            'sec_trade_ar_gap_pp':sec.get('trade_ar_revenue_gap_pp'),
            'open_trade_ar_investigation':r['open_trade_ar_investigation'],
            'organic_growth_attribution_pct':r['organic_growth_attribution_pct'],
            'candidate_purity':q['purity_score'], 'candidate_recognition':q['recognition_score'],
            'candidate_crq':q['score'], 'status':q['status'], 'reason': ' | '.join(q['reasons']),
        })
    save_generated(OUT/'mag7_core_revenue_review.csv', sio.getvalue())
    save_generated(OUT/'mag7_core_revenue_review.md', report_md(rows, origin))
    sheet = OUT/'reviewer_evidence_template.json'
    if not sheet.exists():
        sheet.write_text(json.dumps(worksheet(rows), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


def self_test():
    base = [{'ticker':t, 'fiscal_year':2025, 'period_end':'2025-09-27', 'currency':'USD',
             'revenue':416161e6 if t == 'AAPL' else 100e9,
             'prior_revenue':391035e6 if t == 'AAPL' else 90e9,
             'revenue_growth_pct':6.43 if t == 'AAPL' else 11.11,
             'receivables_growth_pct':10.13, 'receivables_field':'netReceivables',
             'statement_periods_aligned':True, 'financial_data_available':True,'errors':[]}
            for t in TICKERS]
    rows = [analyze_one(b, (None, None, None, None), {}) for b in base]
    assert len(rows) == 7 and all(r['quality']['score'] is None for r in rows)
    assert not rows[0]['provider_receivables_definition_sec_verified']
    assert 'Missing AAPL' in rows[0]['notices'][0]
    candidate_row = {'ticker': 'TEST', 'fiscal_year': 2025,
                     'revenue':100, 'open_trade_ar_investigation':False}
    item = {'ticker':'TEST','fiscal_year':2025,
            'review_attestation':'REVIEWED_BY_NAMED_ANALYST',
            'purity':{'source_url':'https://example.org/test',
                      'source_locator':'Note 1', 'reviewer':'Analyst X',
                      'reviewed_at':'2026-01-01', 'reviewer_rationale':'Test fixture',
                      'confirmed_core_revenue_usd':95,
                      'confirmed_noncore_revenue_usd':5,
                      'unclassified_revenue_usd':0},
            'recognition':{'source_url':'https://example.org/test',
                           'source_locator':'Note 2', 'reviewer':'Analyst X',
                           'reviewed_at':'2026-01-01', 'reviewer_rationale':'Test fixture',
                           'rubric_id':'TEST_RUBRIC', 'documented_reviewer_score':90,
                           'confirmed_material_recognition_issue':False}}
    result = evidence_candidate(candidate_row, item)
    assert result['score'] == 92 and result['status'].startswith('REVIEWER_ATTESTED')
    candidate_row['open_trade_ar_investigation'] = True
    assert evidence_candidate(candidate_row,item)['score'] is None
    item['recognition']['ar_investigation_resolved'] = True
    item['recognition']['ar_resolution_source_locator'] = 'Note 4'
    assert evidence_candidate(candidate_row,item)['score'] == 92
    item['recognition']['confirmed_material_recognition_issue'] = True
    assert evidence_candidate(candidate_row,item)['score'] is None
    item['recognition']['confirmed_material_recognition_issue'] = False
    item['recognition']['documented_reviewer_score'] = 0
    assert evidence_candidate(candidate_row,item)['score'] is None
    item['recognition']['documented_reviewer_score'] = 90
    item['fiscal_year'] = 2026
    assert evidence_candidate(candidate_row,item)['score'] is None
    # Test AAPL SEC evidence against actual Stage 2-5 outputs, when available.
    prior = tuple(load_json(BASE/f'aapl_{label}.json') for label in (
        'sec_stage2_review','stage3_quantitative_review',
        'stage4_recognition_review','stage5_scoring_readiness'))
    if all(x is not None for x in prior):
        sec, errors = verify_aapl(*prior, fmp=base[0])
        assert sec is not None, errors
        assert sec['operating_category_disclosure_coverage_pct'] == 100.0
        assert round(sec['trade_ar_revenue_gap_pp'],1) == 12.6
    for ticker, f in SEC_FACTS.items():
        assert sum(x[1] for x in f['categories']) == f['reported'][0], ticker
        assert sum(x[2] for x in f['categories']) == f['reported'][1], ticker
        d = {'fiscal_year':f['fiscal_year'],'period_end':f['period_end'], 'currency':'USD',
             'revenue':f['reported'][0]*1e6,'prior_revenue':f['reported'][1]*1e6}
        checked, problems = verify_generic_sec(ticker,d)
        assert checked is not None, problems
        assert checked['operating_category_disclosure_coverage_pct'] == 100
        assert verify_generic_sec(ticker, dict(d,fiscal_year=1990))[0] is None
    print('SELF-TEST PASS: MAG7 aggregation, six SEC ledgers, source definition, missing-data gates, FY guard,')
    print('candidate arithmetic, open-AR block, material-issue veto and no fabricated scores.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--self-test', action='store_true', help='No API requests or production changes')
    ap.add_argument('--refresh', action='store_true', help='Re-fetch using existing FMP code/cache (not necessary with Stage 1 snapshot)')
    ap.add_argument('--cache-only', action='store_true', help='With --refresh, never access FMP network')
    ap.add_argument('--evidence', type=Path, help='Optional source-located, analyst-attested review JSON')
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    if args.cache_only and not args.refresh:
        ap.error('--cache-only requires --refresh')
    raw, origin = source_snapshot(refresh=args.refresh, cache_only=args.cache_only)
    fail_if(len(raw) != len(TICKERS), 'Exactly seven MAG7 rows required')
    indexed = {r.get('ticker'):r for r in raw if isinstance(r, dict)}
    fail_if(set(indexed) != set(TICKERS) or len(indexed) != len(raw),
            'Missing, duplicate or unexpected MAG7 ticker in input')
    aapl = tuple(load_json(BASE/name) for name in (
        'aapl_sec_stage2_review.json', 'aapl_stage3_quantitative_review.json',
        'aapl_stage4_recognition_review.json','aapl_stage5_scoring_readiness.json'))
    reviewed = load_json(args.evidence, required=True) if args.evidence else {}
    fail_if(not isinstance(reviewed, dict), '--evidence must contain a ticker-keyed object')
    rows = [analyze_one(indexed[t], aapl, reviewed) for t in TICKERS]
    export(rows, origin)
    print('\nMAG7 CORE REVENUE — INTEGRATED REVIEW')
    print('Ticker  FY    Revenue YoY   SEC coverage  Experimental CRQ  Status')
    for r in rows:
        sec = r['sec'] or {}
        q = r['quality']
        coverage = sec.get('operating_category_disclosure_coverage_pct')
        cv = 'N/A' if coverage is None else f'{coverage:.0f}%'
        cs = 'N/A' if q['score'] is None else f"{q['score']:.1f}*"
        print(f"{r['ticker']:<6}  {str(r['fiscal_year']):<4}  {s(r['revenue_growth_pct'],1,'%'):>11}   "
              f"{cv:>8}          {cs:>6}        {q['status']}")
    print('\nOutput folder:', OUT)
    for name in ('mag7_core_revenue_review.json','mag7_core_revenue_review.csv',
                 'mag7_core_revenue_review.md','reviewer_evidence_template.json'):
        print(' ', name)
    print('Production models and previous Stage 1-7 files: UNCHANGED.')
    print('Numeric scores require source-located reviewer evidence; no scores fabricated.')


if __name__ == '__main__':
    main()
