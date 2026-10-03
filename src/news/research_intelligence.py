"""Relevance-first research contract over the frozen News backend; no provider calls."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from .constants import WEIGHTS, ENTITY_ALIASES
from .event_gate import evaluate_gate, clauses, assertion_status, HISTORICAL
from .event_extractor import extract_event
from .channel_generator import generate_channels
from .exposure_matcher import load_exposure_edges, match_exposures, parse_time
from .pipeline import ROOT, _resolve_prediction_time
from .historical_context import load_archive, context_for

DIRECTION = 'Analyst judgment required'
METHOD = 'relationship_components_v1'
PRIORITY_METHOD = 'evidence_first_attention_v1'
PRIORITY_ORDER = {'High': 0, 'Medium': 1, 'Review': 2}


def direct_event_subjects(article, event):
    """Bounded action/participant links; mere mentions never qualify here."""
    subtype = event['event_subtype']
    result = {}
    for ticker in event.get('tickers_mentioned', []):
        names = ENTITY_ALIASES.get(ticker, (ticker,))
        company = r'(?<!\w)(?:' + '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r')(?!\w)'
        passive = company + r'\s+(?:(?:was|were|is|has been|had been|is being)\s+)?'
        if subtype == 'fine':
            patterns = [r'\b(?:fines?|fined)\s+' + company,
                        r'\b(?:fine|penalty)\s+on\s+' + company, passive + r'fined\b']
        elif subtype in ('investigation', 'regulatory_scrutiny'):
            patterns = [r'\binvestigat(?:es?|ed|ing)\s+' + company,
                        r'\b(?:investigation|probe|inquiry)\s+(?:into|of)\s+' + company,
                        passive + r'investigated\b']
        elif subtype == 'recall':
            patterns = [company + r'\s+(?:has\s+)?recall(?:s|ed)?\b']
        elif subtype == 'pricing_change':
            patterns = [company + r'\s+(?:has\s+)?(?:raises?|raised|cuts?|reduced|reduces?)\s+(?:(?:vehicle|product|retail|subscription)\s+)?prices\b']
        elif subtype == 'workforce_reduction':
            patterns = [company + r'\s+(?:(?:announced|announces)\s+(?:\w+\s+){0,3}layoffs|'
                        r'(?:lays?|laid) off|(?:cuts?|cut) (?:jobs|staff)|reduced headcount)\b']
        elif event['event_type'] == 'trade_export_control':
            patterns = [r'\b(?:restrictions|controls|rules)\b.{0,75}?\b(?:directly )?affect(?:s|ed)?\s+' + company,
                        r'\b(?:restrictions|controls)\s+(?:on|targeting)\s+' + company,
                        company + r'\s+(?:is|was)(?:\s+\w+){0,4}\s+(?:because|as)\s+(?:the )?(?:restrictions|controls|rules)\s+(?:cover|affect|apply to)\s+(?:its|products in its)\b',
                        company + r"(?:'s|’s)\s+(?:products|chips|exports)\s+(?:are|were)\s+(?:restricted|subject to (?:export|license))\b"]
        else:
            continue
        for source, _, text in clauses(article):
            if HISTORICAL.search(text) or re.search(r'\b(?:analysts?|compared?|comparison|background|example|commentary|discuss\w*|propos\w*|consider\w*|plans?|expects?)\b', text, re.I):
                continue
            years = re.findall(r'\b(?:19|20)\d{2}\b', text)
            published_year = str(article.get('published_at') or '')[:4]
            if years and published_year.isdigit() and max(map(int, years)) < int(published_year):
                continue
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match and assertion_status(text, match.start(), match.end()) == 'affirmed':
                    result[ticker] = dict(ticker=ticker, evidence=text, source_field=source,
                                          basis='explicit_event_action_participant', event_subtype=subtype)
                    break
            if ticker in result:
                break
    return result


def relationship_score(pair):
    """Only existing relationship terms; no severity, quality multiplier or ML."""
    edge = bool(pair['matched'])
    components = dict(direct_mention=float(pair['direct_mention']), edge_match=float(edge),
                      country_match=float(edge), channel_match=float(edge))
    weighted = {key: round(value * WEIGHTS[key], 3) for key, value in components.items()}
    return round(sum(weighted.values()), 3), dict(values=components, contributions=weighted)


def _evidence(article, event, edges):
    verified = any(e['evidence_status'] == 'verified' for e in edges)
    level = 'Strong (curated)' if verified else 'Partial' if edges else 'Mention only'
    return dict(relationship_level=level, basis='existing exposure-record curation status',
                independently_verified=False, article_confirmation=event['confirmation_level'],
                article_source_quality=event.get('source_quality'),
                article_source=article.get('source'), article_url=article.get('article_url'),
                note='Curator-verified relationship is not independent confirmation of this event or its financial impact.')


def _priority(edges):
    if any(e['evidence_status'] == 'verified' for e in edges):
        level, reason = 'High', 'Qualified relationship with curator-verified supporting exposure evidence.'
    elif edges:
        level, reason = 'Medium', 'Qualified relationship supported by partial exposure evidence; verify its scope.'
    else:
        level, reason = 'Review', 'Company mentioned; a qualifying economic exposure has not been established.'
    return dict(level=level, reasons=[reason], method=PRIORITY_METHOD,
                interpretation='Analyst attention only; not magnitude, direction or recommendation.')


def _ticker_analysis(article, event, pair, at, archive):
    edges = deepcopy(pair['matched_edges'])
    score, components = relationship_score(pair)
    relation = ('direct_exposure_match' if pair['direct_mention'] else 'indirect_exposure_match') if edges else 'direct_mention'
    channels = sorted({e['channel_family'] for e in edges})
    paths = [dict(edge_id=e['edge_id'], ticker=pair['ticker'], role=e.get('role'),
                  counterparty=e.get('counterparty'), business=e.get('product_or_business'),
                  channel=e['channel_family'], country=e['country'], match_reasons=e['match_reasons']) for e in edges]
    questions = ['Verify the original event report and whether later updates changed the facts.']
    if edges:
        questions += ['Verify the cited relationship and that each supporting fact was known at the analysis time.',
                      'Determine the affected business segment, exposure amount, duration and mitigating capacity.']
    else:
        questions += ['Determine whether the named company is an affected party or merely an observer.',
                      'Find a sourced, temporally valid economic relationship before treating this as qualified exposure.']
    explanation = (f"{pair['ticker']} has {len(edges)} qualified exposure record(s) through "
                   f"{', '.join(channels)}; inspect the attached relationship paths and sources.") if edges else (
                   f"{pair['ticker']} is mentioned in the article; no qualified exposure match was found.")
    result = dict(ticker=pair['ticker'], qualification='qualified_exposure' if edges else 'candidate_requires_review',
                relationship_type=relation, direct_mention=pair['direct_mention'],
                relevance_score=score, relevance_level='Qualified exposure' if edges else 'Mention only',
                relevance_components=components, score_method=METHOD,
                legacy_relevance_score=pair['relevance_score'],
                score_interpretation='Uncalibrated relationship policy score, not a probability or impact estimate.',
                economic_channels=channels, relationship_paths=paths, evidence=edges,
                evidence_strength=_evidence(article, event, edges),
                article_evidence=deepcopy(event['evidence_fields']),
                temporal_status=dict(status='eligible_by_record_metadata' if edges else 'no_qualified_edge',
                                     as_of=at, article_availability_known=at is not None,
                                     source_dates_independently_verified=False,
                                     note='Composite or revised sources require per-fact historical provenance review.'),
                materiality=dict(level='Unknown', status='unquantified',
                                 factors=dict(event_severity=event.get('severity_score'),
                                              exposure=[{k:e.get(k) for k in ('edge_id','exposure_value','exposure_unit','exposure_band')} for e in edges]),
                                 missing_evidence=['Validated event-specific exposure scale and segment impact'],
                                 note='Severity, exposure band and research priority do not establish financial materiality.'),
                historical_reaction=context_for(archive, article, event, pair['ticker']),
                research_priority=_priority(edges), direction=DIRECTION,
                explanation=explanation, next_questions=questions)
    direct = pair.get('direct_event_subject_evidence')
    if direct:
        result.update(qualification='qualified_direct_event_subject', relationship_type='direct_event_subject',
                      relevance_level='Direct event subject', direct_event_evidence=deepcopy(direct),
                      explanation=f"{pair['ticker']} is explicitly linked to the accepted event action in the article.",
                      next_questions=['Verify the original action report and any official confirmation.',
                                      'Determine event-specific financial scale, scope and mitigating factors.'])
        if not edges:
            result['evidence_strength'].update(relationship_level='Direct article evidence',
                                              basis='explicit event action/participant link; not external exposure verification')
            result['temporal_status']['status'] = 'article_available_at_analysis_time'
            result['research_priority'].update(level='Medium', reasons=[
                'Explicit direct event subject supported by article text; independent confirmation and materiality require review.'])
    return result


def analyze_article(article, edges, *, prediction_time=None, archive=None, now=None):
    """Only the frozen gate/matcher decide what is accepted and qualified."""
    output = dict(article_id=article.get('article_id'), headline=article.get('headline'),
                  source=article.get('source'), article_url=article.get('article_url'),
                  gate=evaluate_gate(article), event=None, candidate_channels=[], ticker_analysis=[],
                  edge_exclusions=[], status='rejected', direction=DIRECTION)
    if not output['gate']['is_event']:
        return output
    event = extract_event(article, now=now)
    candidates = generate_channels(event)
    prediction = _resolve_prediction_time(article, explicit_prediction_time=prediction_time)
    at = prediction.isoformat() if prediction else None
    pairs, excluded = match_exposures(event, candidates, edges, prediction_time=at)
    subjects = direct_event_subjects(article, event) if at is not None else {}
    for pair in pairs:
        pair['direct_event_subject_evidence'] = subjects.get(pair['ticker'])
    analyses = [_ticker_analysis(article, event, pair, at, archive) for pair in pairs
                if pair['matched'] or pair['direct_mention']]
    output.update(event=event, candidate_channels=candidates['candidate_channels'],
                  ticker_analysis=analyses, edge_exclusions=excluded,
                  status='qualified_matches' if subjects or any(p['matched'] for p in pairs) else 'no_qualified_match')
    return output


def build_research_output(articles, edges, *, knowledge=None, prediction_time=None, archive=None, now=None):
    if not isinstance(articles, list) or any(not isinstance(a, dict) for a in articles):
        raise ValueError('Expected an articles list of objects')
    ids = [a.get('article_id') for a in articles]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Unique nonempty article IDs required')
    edge_ids = [e.get('edge_id') for e in edges]
    if any(not i for i in edge_ids) or len(edge_ids) != len(set(edge_ids)):
        raise ValueError('Unique nonempty edge IDs required')
    now = now or datetime.now(timezone.utc).isoformat()
    results = [analyze_article(a, edges, prediction_time=prediction_time, archive=archive, now=now) for a in articles]
    event_ids = [r['event']['event_id'] for r in results if r['event']]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError('Duplicate event identity; curate duplicate reports before ranking')
    queue = []
    for result in results:
        for item in result['ticker_analysis']:
            queue.append(dict(article_id=result['article_id'], event_id=result['event']['event_id'],
                              ticker=item['ticker'], qualification=item['qualification'],
                              priority=item['research_priority']['level'], relevance_score=item['relevance_score'],
                              published_at=result['event']['published_at_first'], direction=DIRECTION))
    def key(row):
        published = parse_time(row['published_at'])
        return (PRIORITY_ORDER[row['priority']], -row['relevance_score'],
                -(published.timestamp() if published else float('-inf')), row['event_id'], row['ticker'])
    queue.sort(key=key)
    return dict(schema_version='news_research_v1', generated_at=now,
                knowledge=deepcopy(knowledge or {'status':'provided_edges','edge_count':len(edges)}),
                policies=dict(relevance=METHOD, priority=PRIORITY_METHOD,
                              historical_ml_role='optional_retrospective_context_only',
                              queue_order='priority, relationship relevance, publication recency, stable IDs',
                              direction=DIRECTION),
                articles=results, research_queue=queue,
                summary=dict(articles=len(articles), accepted=len(event_ids), rejected=len(articles)-len(event_ids),
                             qualified_pairs=sum(r['qualification'].startswith('qualified_') for r in queue),
                             review_candidates=sum(r['qualification']=='candidate_requires_review' for r in queue)))


def run_research(root=ROOT, *, input_path=None, output_path=None, exposure_workbook=None,
                 prediction_time=None, historical_map=None, historical_dir=None):
    root = Path(root)
    source = Path(input_path) if input_path else root/'data/news/normalized/freenewsapi_articles_normalized.json'
    destination = Path(output_path) if output_path else root/'data/news/research/news_research_v1.json'
    if destination.exists():
        raise FileExistsError(f'Preserving existing artifacts; choose a new --output: {destination}')
    articles = json.loads(source.read_text())['articles']
    edges, knowledge = load_exposure_edges(root, exposure_workbook)
    archive = load_archive(root, historical_map, historical_dir)
    result = build_research_output(articles, edges, knowledge=knowledge,
                                   prediction_time=prediction_time, archive=archive)
    serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as f:
        f.write(serialized)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--exposure-workbook', type=Path)
    parser.add_argument('--prediction-time')
    parser.add_argument('--historical-map', type=Path, help='JSON with explicit article_to_case mapping')
    parser.add_argument('--historical-dir', type=Path, help='Existing archived ML output directory')
    args = parser.parse_args()
    try:
        result = run_research(input_path=args.input, output_path=args.output,
                              exposure_workbook=args.exposure_workbook, prediction_time=args.prediction_time,
                              historical_map=args.historical_map, historical_dir=args.historical_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f'Research intelligence failed: {exc}\n')
    print(json.dumps(result['summary'], indent=2))
    print(DIRECTION)
    print('Historical ML is optional retrospective context; no direction or rating is produced.')


if __name__ == '__main__':
    main()
