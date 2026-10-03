"""Moat 1 input provenance and conservative period alignment; no scoring rules."""
from datetime import date
import math
from src.data import historical_financial_data as fmp
from src.data.financial_data import get_total_assets
from src.data.market_data import get_company_info

INCOME_FIELDS = {'revenue': 'revenue', 'operating_income': 'operatingIncome',
                 'pretax_income': 'incomeBeforeTax', 'net_income': 'netIncome'}
CASH_FIELDS = {'ocf': 'operatingCashFlow', 'fcf': 'freeCashFlow',
               'capex': 'capitalExpenditure', 'working_capital': 'changeInWorkingCapital',
               'receivables': 'accountsReceivables', 'inventory': 'inventory',
               'payables': 'accountsPayables', 'other_working_capital': 'otherWorkingCapital',
               'cash_net_income': 'netIncome', 'da': 'depreciationAndAmortization',
               'deferred_tax': 'deferredIncomeTax', 'sbc': 'stockBasedCompensation',
               'other_non_cash': 'otherNonCashItems',
               'deferred_revenue_change': 'deferredRevenue', 'tax_paid': 'incomeTaxesPaid'}


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError, OverflowError):
        return None


def iso_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def fact(ticker, row, field, source='FMP', endpoint='income-statement'):
    value = number(row.get(field))
    end = iso_date(row.get('date'))
    year = str(row.get('fiscalYear') or '')
    currency = row.get('reportedCurrency')
    reason = None
    if value is None:
        reason = 'missing_value'
    elif row.get('unit') not in (None, 'currency_units'):
        reason = 'unsupported_unit'
    elif row.get('symbol') != ticker:
        reason = 'ticker_mismatch'
    elif not end or not year.isdigit() or row.get('period') != 'FY':
        reason = 'unknown_annual_period'
    elif not isinstance(currency, str) or len(currency) != 3:
        reason = 'unknown_currency'
    return {'ticker': ticker, 'value': value, 'period': str(end) if end else None,
            'fiscal_year': year or None, 'period_type': row.get('period'),
            'source': source, 'source_field': field, 'currency': currency,
            'source_url': f'{fmp.FMP_BASE_URL}/{endpoint}' if source == 'FMP' else None,
            'unit': 'currency_units', 'availability': 'available' if reason is None else 'unknown',
            'reason': reason, 'period_alignment': 'not_checked',
            'evidence_id': f'{source}:{ticker}:{endpoint}:{row.get("date")}:{field}',
            'filing_date': row.get('filingDate'), 'reconciliation': 'not_checked'}


def aligned(*facts):
    return bool(facts) and all(f and f['availability'] == 'available' for f in facts) and len({
        (f['ticker'], f['period'], f['fiscal_year'], f['currency'], f['unit'], f['period_type'])
        for f in facts}) == 1


def comparable(current, previous):
    if not current or not previous or any(f['availability'] != 'available' for f in (current, previous)):
        return False
    if any(current[k] != previous[k] for k in ('ticker', 'currency', 'unit', 'period_type', 'source')):
        return False
    return (int(current['fiscal_year']) - int(previous['fiscal_year']) == 1
            and 350 <= (iso_date(current['period']) - iso_date(previous['period'])).days <= 380)


def normalize_inputs(ticker, income, cash, assets=None, errors=None):
    """Never skip the latest row just because an older row is more convenient."""
    ticker = ticker.upper().strip()
    facts = []
    grouped = {}
    for rows, fields, endpoint in ((income, INCOME_FIELDS, 'income-statement'),
                                    (cash, CASH_FIELDS, 'cash-flow-statement')):
        for row in rows:
            key = str(row.get('date') or '')
            bucket = grouped.setdefault(key, {})
            for name, field in fields.items():
                item = fact(ticker, row, field, endpoint=endpoint)
                if name in bucket:
                    item['availability'] = 'unknown'
                    item['reason'] = 'duplicate_period'
                bucket[name] = item
                facts.append(item)
            if endpoint == 'income-statement':
                for name, field in (('other_income', 'totalOtherIncomeExpensesNet'),
                                    ('interest_income', 'interestIncome'),
                                    ('income_tax', 'incomeTaxExpense')):
                    item = fact(ticker, row, field, endpoint=endpoint)
                    if name in bucket:
                        item.update(availability='unknown', reason='duplicate_period')
                    bucket[name] = item
                    facts.append(item)
    for item in assets or []:
        bucket = grouped.setdefault(item['period'] or '', {})
        if 'assets' in bucket:
            item = {**item, 'availability': 'unknown', 'reason': 'duplicate_period'}
        bucket['assets'] = item
        facts.append(item)
    periods = []
    # Asset-only periods must not choose the current income/cash comparison period.
    for end in sorted(grouped, reverse=True):
        values = grouped[end]
        if not any(k in values for k in ('revenue', 'ocf')):
            continue
        core = [values.get(k) for k in (*INCOME_FIELDS, 'ocf', 'fcf')]
        match = aligned(*core)
        for value in values.values():
            value['period_alignment'] = 'matched' if match and aligned(core[0], value) else 'unknown'
        periods.append({'period': end or None, 'values': values,
                        'alignment': 'matched' if match else 'unknown'})
    return {'ticker': ticker, 'periods': periods, 'evidence': facts, 'errors': errors or [],
            'availability': 'available' if periods and periods[0]['alignment'] == 'matched' else 'partial'}



def _load_history(ticker, endpoint, loader):
    """Reuse valid FMP history before the provider's API-key gate.

    The shared loader checks credentials before its cache. EQ can consume
    already-recorded statements without live credentials. Reuse the existing
    cache reader and its TTL; expired/corrupt entries still go through the
    original loader. Never treat an empty cached list as a cache miss.
    """
    cached = fmp._load_cache(endpoint, ticker, fmp.HISTORICAL_TREND_YEARS)
    if cached is not None:
        return cached
    return loader(ticker)


def load_eq_inputs(ticker):
    ticker = ticker.upper().strip()
    errors = []
    datasets = []
    for name, endpoint, loader in (
            ('income', 'income-statement', fmp.get_historical_income_statement),
            ('cash', 'cash-flow-statement', fmp.get_historical_cash_flow_statement)):
        try:
            datasets.append(_load_history(ticker, endpoint, loader))
        except Exception as error:
            datasets.append([])
            errors.append({'source': name, 'reason': type(error).__name__})
    # Prefer the existing annual FMP balance endpoint: its explicit currency and
    # fiscal metadata match the income/cash sources without inferred Yahoo dates.
    assets = []
    try:
        balance = _load_history(ticker, 'balance-sheet-statement',
                                fmp.get_historical_balance_sheet)
        assets = [fact(ticker, row, 'totalAssets', endpoint='balance-sheet-statement')
                  for row in balance]
    except Exception as error:
        errors.append({'source': 'balance', 'reason': type(error).__name__})
    target_dates = {r.get('date') for r in datasets[0]}
    supplied_dates = {a['period'] for a in assets}
    # Keep malformed or conflicting FMP rows unknown; do not overwrite them with
    # a convenient alternative. Yahoo only fills entirely absent asset periods.
    if target_dates <= supplied_dates:
        return normalize_inputs(ticker, *datasets, assets=assets, errors=errors)
    try:
        series = get_total_assets(ticker)
        info = get_company_info(ticker) or {}
        if series is not None:
            for end, value in series.items():
                stamp = str(end)[:10]
                if stamp in supplied_dates:
                    continue
                # Match the provider's fiscal-year label by exact report end, never calendar-year inference.
                rows = [r for r in datasets[0] if r.get('date') == stamp]
                row = {'symbol': ticker, 'date': stamp, 'fiscalYear': rows[0].get('fiscalYear') if len(rows) == 1 else None,
                       'period': 'FY', 'reportedCurrency': info.get('financialCurrency'), 'Total Assets': value}
                assets.append(fact(ticker, row, 'Total Assets', 'Yahoo', 'balance_sheet'))
    except Exception as error:
        errors.append({'source': 'assets', 'reason': type(error).__name__})
    return normalize_inputs(ticker, *datasets, assets=assets, errors=errors)
