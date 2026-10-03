"""Evidence sidecar. Validates narrow annual tables without changing legacy scores."""
from copy import deepcopy
import hashlib
import re
from bs4 import BeautifulSoup
from src.analysis.financial_line_extractor import FINANCIAL_LINE_PATTERNS
from src.analysis.non_core_earnings import NON_CORE_WEIGHTS
from src.analysis.materiality import calculate_event_materiality
from src.data.earnings_quality_inputs import number, iso_date, aligned
from src.data.sec_filings import get_filing_html, get_latest_10k
from src.data.sec_data import get_sec_pretax_income, get_sec_operating_income

VERSION = '1.0'


def parse_signed_cell(text):
    text = text.strip().replace('\u2212', '-').replace(',', '').replace('$', '').strip()
    if re.fullmatch(r'\(\s*\d+(?:\.\d+)?\s*\)', text):
        return -float(text.strip('() '))
    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?', text):
        return number(text)
    return None  # Dash/blank/footnote is missing, never inferred zero.


def validate_non_core(legacy, html, filing, pretax, operating=None):
    legacy = deepcopy(legacy or {})
    result = {**legacy, 'legacy_report': legacy, 'validated_events': [], 'rejected_events': [],
              'duplicates': [], 'validated_amount': None, 'validated_ratio': None,
              'availability': 'insufficient_evidence', 'coverage': 'incomplete',
              'reason': 'No validated annual table evidence.', 'evidence': [],
              'rule_version': VERSION, 'reconciliation': 'not_reconciled',
              'scoring_note': 'Legacy scoring is frozen; validated evidence does not recalculate its score.'}
    for key in ('positive_events', 'negative_events', 'ignored_events'):
        result.setdefault(key, [])
    end = iso_date((pretax or {}).get('end'))
    start = iso_date((pretax or {}).get('start'))
    denominator = number((pretax or {}).get('value'))
    filing = filing or {}
    if (not html or not end or not start or not 350 <= (end - start).days + 1 <= 380
            or filing.get('report_date') != str(end)
            or filing.get('form') != '10-K' or (pretax or {}).get('form') != '10-K'
            or filing.get('accession_number') != (pretax or {}).get('accession')
            or not filing.get('url') or denominator is None or denominator <= 0):
        result['reason'] = 'Missing filing, positive denominator, matching accession, or annual period.'
        return result
    result['pretax_evidence'] = {**pretax, 'currency': 'USD', 'unit': 'USD',
                                 'evidence_id': f"SEC:{filing['accession_number']}:{pretax.get('fact_name')}:{end}"}
    soup = BeautifulSoup(html, 'html.parser')
    seen = {}
    candidates = []
    table_coverage = {}
    for table_index, table in enumerate(soup.find_all('table')):
        if table.find('table'):
            continue
        text = ' '.join(table.stripped_strings)
        lower = text.lower()
        # Narrow scope: explicit annual language + currency/scale in this table only.
        annual = bool(re.search(r'years? ended', lower)) and not re.search(r'(three|six|nine) months', lower)
        scales = re.findall(r'in\s+(millions|thousands|billions)', lower)
        unit = scales[0] if len(set(scales)) == 1 else None
        currency = bool(re.search(r'\bUSD\b|U\.S\. dollars|US dollars', text, re.I))
        multiplier = {'millions': 1e6, 'thousands': 1e3, 'billions': 1e9}.get(unit)
        years = []
        table_coverage[table_index] = {'unknown_rows': 0, 'events': []}
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'], recursive=False)
            values = [' '.join(c.stripped_strings) for c in cells]
            header_years = [int(v) for v in values if re.fullmatch(r'20\d{2}', v)]
            if header_years:
                years = header_years
                continue
            if len(values) < 2:
                continue
            label = values[0].lower()
            topics = [topic for topic, patterns in FINANCIAL_LINE_PATTERNS.items()
                      if any(label == pattern for pattern in patterns)]
            if not topics:
                # Unrecognized monetary rows prevent a complete scoped reconciliation.
                if any(parse_signed_cell(v) is not None for v in values[1:]):
                    table_coverage[table_index]['unknown_rows'] += 1
                continue
            reason = None
            if not annual or not currency or not multiplier:
                reason = 'unknown_duration_currency_or_unit'
            elif len(years) != len(set(years)) or end.year not in years or len(values) - 1 != len(years):
                reason = 'ambiguous_year_columns'
            cells_parsed = [parse_signed_cell(v) for v in values[1:]]
            if any(v is None for v in cells_parsed):
                reason = reason or 'ambiguous_sign_or_value'
            evidence = {'url': filing['url'], 'accession': filing['accession_number'],
                        'report_date': str(end), 'table_index': table_index, 'quote': text,
                        'source': 'SEC 10-K HTML table', 'source_field': values[0],
                        'currency': 'USD' if currency else None, 'unit': unit,
                        'evidence_id': f"SEC:{filing['accession_number']}:table:{table_index}:{topics[0]}"}
            if reason:
                result['rejected_events'].append({'topic': topics[0], 'reason': reason, 'evidence': evidence})
                continue
            topic = topics[0]
            amount = cells_parsed[years.index(end.year)] * multiplier
            event = {'topic': topic, 'event_amount': amount, 'event_year': end.year,
                     'period': str(end), 'period_start': str(start), 'year_match': True,
                     'currency': 'USD', 'unit': 'USD', 'availability': 'validated',
                     'confidence': 'validated_table_only', 'weight': NON_CORE_WEIGHTS.get(topic),
                     'item_name': values[0], 'category': topic, 'source': 'SEC 10-K HTML table',
                     'denominator_evidence': result['pretax_evidence'],
                     'evidence': evidence, 'prior_values': dict(zip(years, [v * multiplier for v in cells_parsed]))}
            calc = calculate_event_materiality(amount, denominator)
            event.update(materiality=calc['materiality'], materiality_ratio=calc['absolute_ratio'],
                         direction=calc['direction'], signed_contribution=calc['signed_ratio'])
            identity = (topic, str(end))
            signature = hashlib.sha256(text.encode()).hexdigest()
            if identity in seen:
                prior = seen[identity]
                if prior['event_amount'] == amount and prior['_signature'] == signature:
                    result['duplicates'].append(evidence)
                else:
                    prior['availability'] = 'conflicting_duplicate'
                    result['rejected_events'].append({'topic': topic, 'reason': 'conflicting_duplicate', 'evidence': evidence})
                continue
            event['_signature'] = signature
            seen[identity] = event
            candidates.append(event)
            table_coverage[table_index]['events'].append(event)
    valid = [e for e in candidates if e['availability'] == 'validated']
    for event in candidates:
        event.pop('_signature', None)
    result['validated_events'] = valid
    result['evidence'] = [e['evidence'] for e in valid]
    # Only known weighted topics qualify as identified non-core. Other lines remain evidence, not reclassified.
    positive = [e for e in valid if e['weight'] is not None and e['event_amount'] > 0]
    if positive:
        result['validated_amount'] = sum(e['event_amount'] for e in positive)
        result['validated_ratio'] = result['validated_amount'] / denominator
    if valid:
        result['availability'] = 'partial'
        result['reason'] = 'Validated table subset only; full non-core coverage and accounting reconciliation are not established.'
    # A narrow non-operating table scope can be reconciled. This is never full core/non-core coverage.
    operating = operating or {}
    operating_ok = (operating.get('accession') == pretax.get('accession')
                    and operating.get('start') == pretax.get('start') and operating.get('end') == pretax.get('end')
                    and operating.get('form') == '10-K' and number(operating.get('value')) is not None)
    if operating_ok and not result['rejected_events']:
        for table in table_coverage.values():
            events = table['events']
            totals = [e for e in events if e['topic'] == 'other_income']
            details = [e for e in events if e['topic'] != 'other_income']
            # Net interest/expense sign conventions are intentionally not inferred in V1.
            if (table['unknown_rows'] or len(totals) != 1 or not details
                    or any(e['weight'] is None or e['availability'] != 'validated' for e in details)):
                continue
            total = totals[0]['event_amount']
            tolerance = max(1., abs(denominator) * 1e-6)
            if (abs(sum(e['event_amount'] for e in details) - total) <= tolerance
                    and abs(denominator - operating['value'] - total) <= tolerance):
                result['coverage'] = 'reconciled_nonoperating_scope'
                result['reconciliation'] = 'matched'
                result['availability'] = 'available'
                result['operating_evidence'] = operating
                result['reason'] = ('Recognized detail rows reconcile to the table subtotal and pretax minus operating income. '
                                    'Scope excludes unusual items inside operating income and does not establish recurrence.')
                break
    return result


def _load_structured_evidence(ticker, legacy):
    try:
        return validate_non_core(legacy, get_filing_html(ticker, form_type="10-K"), get_latest_10k(ticker),
                                 get_sec_pretax_income(ticker), get_sec_operating_income(ticker))
    except Exception as error:
        result = validate_non_core(legacy, None, None, None)
        result['reason'] = f'SEC evidence unavailable ({type(error).__name__}).'
        return result


def statement_evidence(inputs):
    """Reported statement observations, not new SEC classifications or scores.

    Other-income subtotal must reconcile to pretax less operating income before
    its sign can support a ratio. Interest income is visible as a reported item
    only: it may overlap the subtotal and is never added to it.
    """
    items = []
    if not inputs['periods']:
        return items
    values = inputs['periods'][0]['values']
    pretax, operating = values.get('pretax_income'), values.get('operating_income')
    for name in ('other_income', 'interest_income'):
        item = values.get(name)
        if not item:
            continue
        valid = aligned(item, pretax, operating)
        reconciled = False
        if valid and name == 'other_income':
            delta = pretax['value'] - operating['value']
            reconciled = abs(item['value'] - delta) <= max(1., abs(pretax['value']) * 1e-6)
        ratio = item['value'] / pretax['value'] if reconciled and pretax['value'] > 0 else None
        items.append({'item_name': 'Other income / expense, net' if name == 'other_income' else 'Interest income',
                      'amount': item['value'] if item['availability'] == 'available' else None,
                      'period': item['period'], 'source': item['source'], 'category': 'reported_statement_observation',
                      'currency': item['currency'], 'unit': item['unit'], 'evidence': item,
                      'availability': 'available' if valid else 'insufficient_evidence',
                      'confidence': 'reconciled_statement_subtotal' if reconciled else 'reported_field_only',
                      'signed_contribution': ratio,
                      'note': ('Reconciles to pretax minus operating income; a net subtotal, not a complete core/non-core decomposition.'
                               if reconciled else 'Insufficient evidence for earnings-share attribution. No sign adjustment, recurrence conclusion or new classification.'),
                      'aggregation': 'Do not sum with other rows or SEC items; scopes may overlap.'})
    return items


def load_non_core_evidence(ticker, legacy):
    """Add narrative evidence without changing structured or legacy outputs."""
    from src.analysis.earnings_quality_narrative_evidence import load_narrative_evidence
    result = _load_structured_evidence(ticker, legacy)
    result.update(load_narrative_evidence(ticker))
    return result
