"""Normalized heuristic, qualitative confidence evidence and configurable exponential age decay."""
import math
from .v3_config import SOURCE_POLICY_NOTICE
from .exposure_matcher import parse_time

WEIGHTS={'mention':.10,'direct_subject':.35,'eligible_edge':.35,'channel':.10,'country':.05,'counterparty':.05}

def confidence_components(quality, extraction, evidence):
    return {'value':None,'kind':'qualitative_evidence_components','source_quality_policy_notice':SOURCE_POLICY_NOTICE,'source_quality':quality,'extraction_self_assessment':extraction,'relationship_evidence_quality':evidence,'interpretation':'Qualitative source policy and relationship evidence; extraction confidence is uncalibrated model self-assessment, not factual accuracy. No composite probability or confidence score is computed.'}

def quantify(article,ticker,record,config,as_of):
    edges=ticker.get('evidence') or []
    direct=ticker.get('relationship_type') in ('direct_event_subject','direct_company_subject')
    values={'mention':float(bool(ticker.get('direct_mention') or direct or ticker.get('relationship_type')=='direct_mention')),
        'direct_subject':float(direct),'eligible_edge':float(bool(edges)),
        'channel':float(bool(ticker.get('economic_channels'))),'country':float(any(e.get('country') for e in edges)),
        'counterparty':float(any(e.get('counterparty') for e in edges))}
    contributions={k:values[k]*w for k,w in WEIGHTS.items()};relevance=round(sum(contributions.values()),6)
    quality=config.source_tier(article.get('source'))
    # Only an accepted source-grounded enrichment carries model self-assessment.
    enrichment=record.get('enrichment') or {};semantic=enrichment.get('semantic') or {}
    extraction=semantic.get('llm_confidence') if record.get('semantic_validation',{}).get('accepted') else None
    evidence=(ticker.get('evidence_assessment') or {}).get('level') or ('Strong' if any(e.get('evidence_status')=='verified' for e in edges) else 'Partial' if edges else 'Moderate' if direct else 'Mention only')
    decay=None;age=None;half=config.class_half_lives.get(record.get('classification'),config.half_life_hours)
    try:
        published=parse_time(article.get('published_at'));at=parse_time(as_of)
        if published and at and published<=at:
            age=(at-published).total_seconds()/3600;decay=math.exp(-math.log(2)*age/half)
    except (ValueError,TypeError,OverflowError):pass
    return {'relevance':{'value':relevance,'kind':'normalized_heuristic','method':'weighted_supported_relationship_terms_v3','weights':WEIGHTS,'inputs':values,'contributions':contributions,'interpretation':'Not P(relevant); not calibrated or a financial-impact estimate.'},
        'confidence':confidence_components(quality,extraction,evidence),
        'time_decay':{'value':decay,'age_hours':age,'half_life_hours':half,'lambda_per_hour':math.log(2)/half,'as_of':as_of,'interpretation':'Recency factor, not causal impact; future/invalid publication time gives null.'},
        'impact':{'value':None,'magnitude':None,'directional_exposure':None,'surprise':None,'reason':'Event-specific magnitude, direction and surprise not established.'}}
