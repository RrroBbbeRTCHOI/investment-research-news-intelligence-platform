"""Read-only presentation boundary. Never fetches providers or runs analysis."""
import json
from pathlib import Path
from .v3_config import Config, configured_source_quality
from .v3_scoring import confidence_components

DEFAULT_OUTPUT = 'data/news/research/stress_test_v1_v316_final_replay.json'

def read_product_intelligence(root, configured_path, config):
    """Read-only product wrapper; never import ingestion/provider workers."""
    from datetime import datetime, timezone
    from .product_scores import decorate
    payload,status=read_intelligence(root,configured_path)
    if status!=200 or payload['schema_version']!='news_ui_v3': return payload,status
    if status==200 and payload['schema_version']=='news_ui_v3': payload=decorate(payload)
    operational={'pipeline_status':'demo','reason':'Frozen benchmark snapshot'}
    if config.enabled:
        path=config.state_dir/'status.json'
        if not path.is_absolute(): path=Path(root)/path
        try:
            raw=json.loads(path.read_text())
            fields=('pipeline_status','generated_at_utc','last_successful_fetch_utc','provider_fetch_at_utc',
                    'new_article_count','duplicate_count','cheap_reject_count','gemini_cache_hits','gemini_calls_this_cycle','quota_deferred_count','pending_count','article_count','event_count','outlook_count','skip_count')
            operational={k:raw.get(k) for k in fields}
            at=datetime.fromisoformat((raw.get('generated_at_utc') or '').replace('Z','+00:00'))
            if (datetime.now(timezone.utc)-at).total_seconds()>config.interval*2:
                operational['pipeline_status']='stale'
        except (OSError,ValueError,TypeError): operational={'pipeline_status':'degraded'}
        operational['reason']={'live':'Live research snapshot','stale':'Last update is stale; showing cached results',
                               'degraded':'Update incomplete or provider unavailable; showing completed research'}.get(operational.get('pipeline_status'),'Live update unavailable')
    payload['operational']=operational
    payload['poll_seconds']=max(30,config.poll)
    return payload,status

ARTICLE_FIELDS = ('article_id', 'headline', 'source', 'article_url', 'published_at',
                  'status', 'direction', 'gate', 'candidate_channels', 'ticker_analysis')
EVENT_FIELDS = ('event_id', 'event_type', 'event_subtype', 'published_at_first',
                'primary_country', 'affected_countries', 'latitude', 'longitude',
                'location_name', 'event_summary', 'evidence_fields')


def read_intelligence(root, configured_path):
    """Use one explicitly selected snapshot, never glob arbitrary QA outputs."""
    path = Path(configured_path)
    if not path.is_absolute():
        path = Path(root) / path
    try:
        with path.open(encoding='utf-8') as stream:
            value = json.load(stream, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
        if not isinstance(value.get('schema_version'), str) or not isinstance(value.get('summary'), dict):
            raise ValueError()
        if not isinstance(value.get('articles'), list) or not isinstance(value.get('research_queue'), list):
            raise ValueError()
        source_policy = Config(source_quality=configured_source_quality()) if value['schema_version']=='news_research_v3' else None
        articles = []
        for item in value['articles']:
            if not isinstance(item, dict) or not isinstance(item.get('article_id'), str):
                raise ValueError()
            if not isinstance(item.get('headline'), str) or not isinstance(item.get('ticker_analysis'), list):
                raise ValueError()
            if not isinstance(item.get('gate'), dict) or not isinstance(item['gate'].get('is_event'), bool):
                raise ValueError()
            event = item.get('event')
            if event is not None and not isinstance(event, dict):
                raise ValueError()
            for ticker in item['ticker_analysis']:
                if not isinstance(ticker, dict) or not isinstance(ticker.get('ticker'), str):
                    raise ValueError()
                for field in ('materiality', 'research_priority', 'historical_reaction', 'evidence_strength'):
                    if ticker.get(field) is not None and not isinstance(ticker[field], dict):
                        raise ValueError()
                for field in ('economic_channels', 'evidence', 'relationship_paths', 'next_questions'):
                    if ticker.get(field) is not None and not isinstance(ticker[field], list):
                        raise ValueError()
            row = {key: item.get(key) for key in ARTICLE_FIELDS}
            row['event'] = {key: event.get(key) for key in EVENT_FIELDS} if event else None
            if value['schema_version'] in ('news_research_v2','news_research_v3'):
                row.update({key:item.get(key) for key in ('usable','classification','geography','severity','research_priority')})
                if event:row['event'].update({key:event.get(key) for key in ('country','region','city','location_basis','coordinate_precision')})
            if value['schema_version']=='news_research_v3':
                row.update({key:item.get(key) for key in ('feed','article_summary','enrichment','semantic_validation','severity_assessment','classification_assessment')})
                from .live_content import display_type
                row['content_type']=item.get('content_type','event')
                row['display_type']=display_type(item)
                if row['content_type'] not in ('event','outlook','skip'): raise ValueError()
                if 'intake' in item: row['intake']=item['intake']
                if row['content_type']=='outlook':
                    outlook=item.get('outlook')
                    if not isinstance(outlook,dict) or item.get('event') is not None or item['ticker_analysis'] or item['gate']['is_event']: raise ValueError()
                    for field in ('catalysts','watch_reasons','related_tickers','related_macro_topics','source_basis'):
                        if not isinstance(outlook.get(field),list): raise ValueError()
                    row['outlook']=outlook
                    row['severity']={'level':'N/A — Upcoming','score':None,'kind':'not_applicable'}
            if source_policy is not None:
                # Adapt old stored confidence products at the read-only boundary;
                # do not rewrite snapshots, enrichment caches or analytical fields.
                for ticker in row['ticker_analysis']:
                    quantitative=ticker.get('quantitative')
                    if not isinstance(quantitative,dict):continue
                    old=quantitative.get('confidence') or {}
                    old=old if isinstance(old,dict) else {}
                    relationship=(ticker.get('evidence_assessment') or {}).get('level','Unknown')
                    quantitative['confidence']=confidence_components(
                        source_policy.source_tier(item.get('source')),
                        old.get('extraction_self_assessment'),relationship)
            articles.append(row)
        if any(not isinstance(q, dict) for q in value['research_queue']):
            raise ValueError()
        return dict(schema_version={'news_research_v3':'news_ui_v3','news_research_v2':'news_ui_v2'}.get(value['schema_version'],'news_ui_v1'), generated_at=value.get('generated_at'),
                    **({'presentation_policy':{'primary_numeric_relevance':'ticker_analysis[].quantitative.relevance', 'legacy_relationship_score':'compatibility/audit only'}} if value['schema_version']=='news_research_v3' else {}),
                    summary=value['summary'], queue=value['research_queue'], articles=articles), 200
    except FileNotFoundError:
        message, code = 'News intelligence output is not available.', 503
    except (ValueError, TypeError, UnicodeError):
        message, code = 'News intelligence output is malformed.', 503
    except OSError:
        message, code = 'News intelligence output cannot be read.', 503
    return dict(schema_version='news_ui_v1', generated_at=None, summary={}, queue=[], articles=[], error=message), code
