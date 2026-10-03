"""Conservative SEC narrative routing. No scoring, amount attribution or totals."""
from bisect import bisect_right
import hashlib
import re
from src.analysis import filing_classifier as classifier
from bs4 import BeautifulSoup
from src.data.sec_filings import get_filing_html, get_latest_10k, clean_filing_text

WARNING = ('Evidence only; not included in legacy EQ scoring. A keyword does not '
           'prove causation or a core/non-core split. Do not sum overlapping '
           'narrative, table or statement observations.')


def _sentence(text, position, keyword, boundaries):
    """Localize the hit so nearby unrelated results cannot lend it support."""
    if not isinstance(position, int) or position < 0:
        return None
    if text[position:position + len(keyword)].casefold() != keyword.casefold():
        return None
    index = bisect_right(boundaries, position) - 1
    if index < 0 or index + 1 >= len(boundaries):
        return None
    start, end = boundaries[index:index + 2]
    quote = text[start:end].strip()
    if len(quote) > 1800:
        return None  # No safe local disclosure boundary; do not guess.
    return start, quote


def narrative_evidence(ticker, results, filing, text):
    """Consume classifier matches directly, independent of financial row patterns."""
    output = {'narrative_events': [], 'rejected_narrative_events': [], 'research_candidates': [],
              'narrative_availability': 'insufficient_evidence',
              'narrative_reason': 'No qualifying narrative disclosure.',
              'narrative_aggregation_warning': WARNING}
    filing = filing or {}
    if (filing.get('form') != '10-K' or not filing.get('accession_number')
            or not filing.get('url') or not text):
        output['narrative_reason'] = 'Missing 10-K, accession, filing URL or source text.'
        return output
    boundaries = [0] + [m.end() for m in re.finditer(r'[.!?]\s+(?=[A-Z])', text)] + [len(text)]
    accepted = {}
    for result in results:
        for match in result.get('validated_matches', []):
            keyword = match.get('keyword', '')
            local = _sentence(text, match.get('position'), keyword, boundaries) if keyword else None
            reason = None
            if match.get('final_level', 0) < 2 or not match.get('evidence_passed'):
                reason = 'classifier_gate_not_passed'
            elif local is None:
                reason = 'source_position_or_local_disclosure_unverified'
            quote = local[1] if local else match.get('context', '')
            if local is not None:
                output['research_candidates'].append({
                    'ticker': ticker.upper().strip(), 'topic': result['topic'],
                    'category': result.get('category'), 'keyword': keyword,
                    'context': quote, 'position': local[0], 'source_verified': True,
                    'filing': dict(filing), 'classifier_level': match.get('final_level'),
                    'classifier_reasons': match.get('reasons', [])})
            local_result = classifier.classify_context(
                result['topic'], result.get('category'), result.get('original_level', 0), quote)
            # Keep legacy deferred-tax and other hard caps. No promotion of Level 1.
            if reason is None and (local_result['final_level'] < 2 or not local_result['evidence_passed']):
                reason = 'local_classifier_gate_not_passed'
            if reason is None and (classifier.contains_any(quote, classifier.RISK_FACTOR_SIGNALS)
                                   or classifier.contains_any(quote, classifier.HYPOTHETICAL_SIGNALS)
                                   or re.search(r'\b(?:may|might|could|would|if)\b', quote, re.I)):
                reason = 'hypothetical_or_risk_only'
            if reason is None and re.search(r'\b(?:not|no|never|without)\b', quote, re.I):
                reason = 'negated_event'
            actual = classifier.detect_actual_event(quote)['actual']
            financial = classifier.contains_any(quote, ['increased by', 'decreased by',
                'included gains', 'included losses', 'included net gains', 'primarily due to',
                'primarily related to'])
            if reason is None and not (actual or financial):
                reason = 'no_local_actual_event_or_result_discussion'
            if reason is None and classifier.contains_any(quote, classifier.ACCOUNTING_POLICY_SIGNALS) and not actual:
                reason = 'accounting_policy_only'
            if reason:
                output['rejected_narrative_events'].append({
                    'topic': result['topic'], 'matched_keyword': keyword,
                    'classifier_level': match.get('final_level'), 'reason': reason,
                    'context': quote, 'evidence_type': 'narrative',
                    'accession_number': filing['accession_number']})
                continue
            start = local[0]
            identity = (filing['accession_number'], start, re.sub(r'\s+', ' ', quote).casefold())
            if identity in accepted:
                event = accepted[identity]
                for field, value in (('matched_keywords', keyword), ('topics', result['topic']),
                                     ('categories', result.get('category'))):
                    if value not in event[field]:
                        event[field].append(value)
                event['classifier_matches'].append(match)
                continue
            # A filing report date is metadata, not proof of the event period.
            years = set(re.findall(r'\bfiscal year\s+(20\d{2})\b', quote, re.I))
            all_years = set(re.findall(r'\b20\d{2}\b', quote))
            fiscal_year = int(next(iter(years))) if len(years) == 1 and years == all_years else None
            event = {'ticker': ticker.upper().strip(), 'topic': result['topic'],
                     'topics': [result['topic']], 'category': result.get('category'),
                     'categories': [result.get('category')], 'matched_keyword': keyword,
                     'matched_keywords': [keyword], 'final_classifier_level': match['final_level'],
                     'event_type': local_result['event_type'], 'evidence_score': local_result['evidence_score'],
                     'evidence_status': 'validated_narrative', 'form': '10-K',
                     'accession_number': filing['accession_number'], 'filing_url': filing['url'],
                     'report_date': filing.get('report_date'), 'source': 'SEC 10-K narrative',
                     'evidence_type': 'narrative', 'context': quote, 'position': start,
                     'detected_amounts': classifier.extract_amounts(quote), 'event_amount': None,
                     'amount_linkage': 'unverified', 'fiscal_year': fiscal_year, 'period': None,
                     'materiality': None, 'confidence': 'qualitative_disclosure_only',
                     'validation_reason': 'Classifier and local actual-event/result gates passed; numerical linkage is not validated.',
                     'aggregation_warning': WARNING, 'classifier_matches': [match],
                     'evidence_id': 'SEC-narrative:' + hashlib.sha256(repr(identity).encode()).hexdigest()[:24]}
            accepted[identity] = event
    output['narrative_events'] = list(accepted.values())
    if accepted:
        output['narrative_availability'] = 'validated_narrative'
        output['narrative_reason'] = 'Qualifying qualitative disclosures only; numerical coverage remains separate.'
    return output


def load_narrative_evidence(ticker):
    """Existing memoized SEC readers reuse the same 10-K within data_scope."""
    try:
        filing = get_latest_10k(ticker)
        html = get_filing_html(ticker, form_type='10-K')
        if not html:
            return narrative_evidence(ticker, [], filing, None)
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(['table', 'script', 'style']):
            tag.decompose()
        text = clean_filing_text(soup.get_text(separator='\n'))
        results = classifier.classify_filing_text(text)

        return narrative_evidence(ticker, results, filing, text)
    except Exception as error:
        output = narrative_evidence(ticker, [], None, None)
        output['narrative_reason'] = f'Narrative source unavailable ({type(error).__name__}).'
        return output
