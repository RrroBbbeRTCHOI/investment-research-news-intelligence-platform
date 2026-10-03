"""V2 evidence stages, taxonomy and families; never called by legacy scoring."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import json
import re
from src.data.earnings_quality_inputs import number, iso_date
from src.analysis.earnings_quality_diagnostics import close

RULES = Path(__file__).resolve().parents[2] / 'data' / 'earnings_quality_rules.json'


def load_rules():
    return json.loads(RULES.read_text())


def categories(topics, rules):
    return [category for category, members in rules['taxonomy'].items() if set(topics) & set(members)] or ['unknown']


def event_period(quote, inputs, rules):
    patterns = rules['patterns']
    explicit = set(re.findall(patterns['fiscal_year'], quote, re.I))
    dates = []
    for raw in re.findall(patterns['annual_date'], quote, re.I):
        try:
            dates.append(datetime.strptime(raw.replace(',', ''), '%B %d %Y').date().isoformat())
        except ValueError:
            continue
    all_years = set(re.findall(r'\b20\d{2}\b', quote))
    if re.search(r'\bquarter|\b(?:three|six|nine) months|year.to.date', quote, re.I):
        return (int(next(iter(explicit))) if len(explicit) == 1 else None), None
    if len(explicit) == 1 and all_years == explicit:
        year = next(iter(explicit))
        matches = [p for p in inputs['periods'] if p['values'].get('net_income', {}).get('fiscal_year') == year]
        end = matches[0]['period'] if len(matches) == 1 else None
        if dates and set(dates) != {end}:
            end = None
        return int(year), end
    if len(set(dates)) == 1 and len(all_years) == 1:
        end = dates[0]
        matches = [p for p in inputs['periods'] if p['period'] == end]
        year = matches[0]['values'].get('net_income', {}).get('fiscal_year') if len(matches) == 1 else None
        return int(year) if year else None, end
    return None, None


def linked_amount(quote, keyword, rules):
    """Only a single explicitly dollar-denominated subject-linked gain/charge.

    Unknown dollar jurisdiction is addressed by requiring explicit USD language.
    Amounts elsewhere in the sentence never become the event amount.
    """
    matches = list(re.finditer(rules['patterns']['linked_amount'], quote, re.I))
    currency = 'USD' if re.search(r'\bUSD\b|U\.S\. dollars|US dollars', quote, re.I) else None
    amounts = re.findall(r'\$\s*\d', quote)
    if len(matches) != 1 or len(amounts) != 1 or currency is None:
        return None, None
    m = matches[0]
    label = m.group('label').lower()
    # Keyword must be within the linked noun phrase, not another clause nearby.
    if keyword.lower() not in label:
        return None, None
    value = number(m.group('amount').replace(',', ''))
    if value is None:
        return None, None
    value *= {'billion': 1e9, 'million': 1e6, 'thousand': 1e3}[m.group('scale').lower()]
    negative = bool(re.search(r'\b(loss|charge|expense)\b', label))
    if m.group('sign'):
        return None, None  # Avoid inferring a double negative from signed prose.
    return -value if negative else value, currency


def normalize_evidence(inputs, evidence, rules=None):
    rules = rules or load_rules()
    patterns = rules['patterns']
    normalized = []
    seen = {}
    for candidate in evidence.get('research_candidates', []):
        q = candidate['context']
        filing = candidate.get('filing', {})
        topic = candidate['topic']
        keyword = candidate['keyword']
        source_ok = (candidate.get('source_verified') and filing.get('form') == '10-K'
                     and filing.get('accession_number') and filing.get('url'))
        key = (filing.get('accession_number'), candidate.get('position'), q)
        if key in seen:
            e = seen[key]
            if topic not in e['topics']: e['topics'].append(topic)
            if keyword not in e['matched_keywords']: e['matched_keywords'].append(keyword)
            # A more specific keyword may make the same amount's noun phrase clear.
            if e['amount'] is None and e['validation_level'] >= 3:
                value, currency = linked_amount(q, keyword, rules)
                if value is not None:
                    e.update(amount=value, currency=currency, validation_level=4, amount_confidence='explicit_noun_phrase')
            continue
        stage = 1 if source_ok else 0
        status = 'accounting_policy_context'
        actual = bool(re.search(patterns['actual'], q, re.I))
        blocked = bool(re.search(patterns['hypothetical'], q, re.I))
        policy = bool(re.search(patterns['policy'], q, re.I))
        if stage and actual and not blocked and not policy:
            stage, status = 2, 'actual_event_result'
        year, end = event_period(q, inputs, rules) if stage >= 2 else (None, None)
        if stage >= 2 and end:
            stage = 3
        amount, currency = linked_amount(q, keyword, rules) if stage >= 3 else (None, None)
        if amount is not None:
            stage = 4
        e = {'evidence_id': 'EQ2:' + hashlib.sha256(repr(key).encode()).hexdigest()[:20],
             'ticker': inputs['ticker'], 'topics': [topic], 'matched_keywords': [keyword],
             'filing_type': filing.get('form'), 'filing_date': filing.get('filing_date'),
             'report_date': filing.get('report_date'), 'event_fiscal_year': year, 'period': end,
             'accession': filing.get('accession_number'), 'source_url': filing.get('url'),
             'source': 'SEC 10-K narrative', 'evidence_type': 'narrative', 'raw_text': q,
             'amount': amount, 'currency': currency, 'amount_confidence': 'explicit_noun_phrase' if amount is not None else 'unverified',
             'validation_status': status, 'validation_level': stage, 'position': candidate.get('position'),
             'classifier_level': candidate.get('classifier_level'),
             'validation_reason': 'V2 local factual grammar; legacy classifier/scoring is unchanged.' if stage >= 2 else 'Policy, hypothetical, negated or insufficient local factual support.',
             'scope_warning': 'May overlap other passages, statement subtotals or table items. Never sum automatically.',
             'recurrence_status': 'unknown', 'source_evidence': [candidate]}
        seen[key] = e
        normalized.append(e)
    for e in normalized:
        e['categories'] = categories(e['topics'], rules)
        for t in evidence.get('validated_events', []):
            if (e['validation_level'] >= 4 and t['topic'] in e['topics'] and e['period'] == t['period']
                    and e['currency'] == t['currency'] and close(e['amount'], t['event_amount'])):
                e['validation_level'] = 5
                e['amount_confidence'] = 'matched_structured_item'
                e['reconciled_evidence'] = t['evidence']
                break
    for t in evidence.get('validated_events', []):
        normalized.append({'evidence_id': t['evidence']['evidence_id'], 'ticker': inputs['ticker'],
            'topics': [t['topic']], 'categories': categories([t['topic']], rules), 'source': 'SEC 10-K table',
            'evidence_type': 'structured', 'filing_type': '10-K', 'filing_date': None,
            'report_date': t['period'], 'event_fiscal_year': t['event_year'], 'period': t['period'],
            'accession': t['evidence']['accession'], 'source_url': t['evidence']['url'],
            'raw_text': t['evidence']['quote'], 'amount': t['event_amount'], 'currency': t['currency'],
            'amount_confidence': 'validated_table_row', 'validation_status': 'actual_event_result',
            'validation_level': 4, 'recurrence_status': 'unknown', 'source_evidence': [t],
            'scope_warning': 'Validated row is not proof of independent scope or recurrence.'})
    for s in evidence.get('statement_items', []):
        f = s['evidence']
        normalized.append({'evidence_id': f['evidence_id'], 'ticker': inputs['ticker'],
            'topics': [s['item_name']], 'categories': ['below_operating'], 'source': s['source'],
            'evidence_type': 'statement', 'filing_type': None, 'filing_date': f.get('filing_date'),
            'report_date': s['period'], 'event_fiscal_year': int(f['fiscal_year']) if f.get('fiscal_year') else None,
            'period': s['period'], 'accession': None, 'source_url': f.get('source_url'), 'raw_text': s['note'],
            'amount': s['amount'], 'currency': s['currency'], 'amount_confidence': s['confidence'],
            'validation_level': 5 if s['confidence'] == 'reconciled_statement_subtotal' else 4 if s['availability'] == 'available' else 1,
            'validation_status': 'statement_observation', 'recurrence_status': 'unknown',
            'scope_warning': s['aggregation'], 'source_evidence': [s]})
    return normalized


def group_families(items, rules=None):
    rules = rules or load_rules()
    groups = {}
    for item in items:
        if item['validation_level'] < 2 or item['evidence_type'] == 'statement':
            continue
        match = re.search(rules['patterns']['named_transaction'], item['raw_text'])
        transaction = match.group(0).lower() if match else None
        # Explicit named transaction joins recapitalization/dilution passages.
        # Otherwise only identical disclosures/structured reconciliation may merge.
        scope = transaction or item.get('reconciled_evidence', {}).get('evidence_id') or item['evidence_id']
        key = (item['ticker'], item['event_fiscal_year'], scope)
        groups.setdefault(key, []).append(item)
    families = []
    for key, sources in groups.items():
        topics = sorted({t for e in sources for t in e['topics']})
        cats = sorted({c for e in sources for c in e['categories']})
        amounts = {(e['amount'], e['currency'], e['period']) for e in sources if e['amount'] is not None}
        amount = next(iter(amounts))[0] if len(amounts) == 1 and all(e['amount'] is not None for e in sources) else None
        one_off = any(re.search(rules['patterns']['one_off'], e['raw_text'], re.I) for e in sources)
        family = {'event_family_id': 'FAM:' + hashlib.sha256(repr(key).encode()).hexdigest()[:16],
                  'event_label': key[2] if not str(key[2]).startswith(('EQ2:', 'SEC:')) else ', '.join(topics),
                  'ticker': key[0], 'fiscal_year': key[1], 'categories': cats, 'topics': topics,
                  'recurrence_status': 'explicitly one-off' if one_off else 'unknown',
                  'amount_status': 'supported' if amount is not None else 'conflicting_or_unverified',
                  'validated_amount': amount, 'currency': next(iter(amounts))[1] if amount is not None else None, 'source_evidence': sources,
                  'scope_warning': 'Research grouping only. No family totals or earnings shares are computed.'}
        families.append(family)
    driver_topics = {topic for members in rules['taxonomy'].values() for topic in members}
    driver_topics -= {'other_income_container', 'tax_context', 'marketable_equity'}
    for family in families:
        specific = set(family['topics']) & driver_topics
        related = [f for f in families if set(f['topics']) & specific and f['ticker'] == family['ticker']]

        years = sorted({f['fiscal_year'] for f in related if f['fiscal_year'] is not None})
        family['observed_years'] = years
        if family['recurrence_status'] != 'explicitly one-off':
            family['recurrence_status'] = ('volatile recurring' if 'volatile_market' in family['categories'] else 'historically recurring') if len(years) >= 2 else 'isolated' if family['fiscal_year'] else 'unknown'
        family['recurrence_note'] = 'Observed disclosures only; repetition of a category does not prove the same transaction recurs or forecast future earnings.'
        for e in family['source_evidence']:
            e['recurrence_status'] = family['recurrence_status']
    return families
