"""Live intake compatibility plus source-extractive Outlook assembly."""
from datetime import datetime
import re
from .live_intake_policy import (
    find, COMPANIES, CONTEXTS, FUTURE, HARD_NOISE, THREAT, COMPLETED, ACTUAL,
    actual_evidence, classify_live_intake, is_investment_editorial,
)


def classify_live_content(article, prefilter_result):
    return classify_live_intake(article, prefilter_result)


def is_live_commentary_or_valuation(article):
    return is_investment_editorial(article)


def display_type(record):
    """Final presentation status, independent of processing lane."""
    if record.get('content_type') == 'outlook': return 'outlook'
    return 'event' if (record.get('gate') or {}).get('is_event') is True else 'research'

def build_outlook_record(article, decision, now):
    """Source-extractive record. No guessed dates, geography, exposure or event score."""
    headline=str(article.get('headline') or '')
    fields=[(field,str(article.get(field) or '')) for field in ('headline','summary','body')]
    text=' '.join(value for _,value in fields)
    categories=[name for name,pattern in CONTEXTS.items() if find(pattern,text)]
    category=categories[0] if categories else 'other_research_outlook'
    basis=[];catalysts=[]
    for field,value in fields:
        for name,pattern in CONTEXTS.items():
            for match in re.finditer(pattern,value,re.I):
                evidence={'source_field':field,'quote':match.group(0),'start':match.start(),'end':match.end()}
                if not any(c['name'].lower()==match.group(0).lower() for c in catalysts):
                    catalysts.append({'name':match.group(0),'category':name,'source_basis':evidence});basis.append(evidence)
    related=[]
    for ticker,aliases in COMPANIES.items():
        # Direct catalyst subject, not any mention in an article containing earnings.
        pattern=rf'\b(?:{aliases})(?:\s*[’\x27]s)?\s+(?:(?:q[1-4]|quarterly)\s+)?(?:earnings|(?:is\s+)?(?:set|scheduled|due)\s+to\s+report|reports?\s+(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday))\b'
        for field,value in fields[:2]:
            match=find(pattern,value)
            if match:
                evidence={'source_field':field,'quote':match.group(0),'start':match.start(),'end':match.end()}
                related.append({'ticker':ticker,'relationship':'direct_catalyst_subject','source_basis':evidence});basis.append(evidence);break
    timing=find(r'\b(?:next week|this week|tomorrow|monday|tuesday|wednesday|thursday|friday|week ahead)\b',headline)
    scheduled=None
    # Only an explicitly scheduled, timezone-qualified ISO timestamp is resolved.
    for field,value in fields:
        match=find(r'(?:scheduled for|due at)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))',value)
        if match:
            try:
                from datetime import timezone
                stamp=datetime.fromisoformat(match.group(1).replace('Z','+00:00'))
                if stamp>datetime.fromisoformat(now.replace('Z','+00:00')):
                    scheduled=stamp.astimezone(timezone.utc).isoformat()
                    basis.append({'source_field':field,'quote':match.group(0),'start':match.start(),'end':match.end()})
            except ValueError: pass
            break
    return {'article_id':article['article_id'],'headline':headline,'source':article.get('source'),
            'article_url':article.get('article_url'),'published_at':article.get('published_at'),
            'content_type':'outlook','display_type':'outlook','intake':decision,'usable':True,'status':'upcoming',
            'gate':{'is_event':False,'reason':'Upcoming catalyst; not an occurred event.'},
            'event':None,'ticker_analysis':[],'candidate_channels':[],'geography':None,
            'severity':{'level':'N/A — Upcoming','score':None,'kind':'not_applicable'},
            'feed':{'state':'surface','reason':'Evidence-backed upcoming research catalyst.'},
            'enrichment':{'status':'deterministic','reason':'source_extractive_outlook','cache_hit':False},
            'outlook':{'status':'upcoming','category':category,'catalysts':catalysts,
                       'scheduled_at_utc':scheduled,'expected_window':timing.group(0) if timing else None,
                       'watch_reasons':[headline],'related_tickers':related,
                       'related_macro_topics':[c['name'] for c in catalysts if c['category'] in ('macro_data','monetary_policy')],
                       'source_basis':[{'source_field':'headline','quote':headline,'start':0,'end':len(headline)},*basis],
                       'method':'deterministic_extract_v1','notice':'Source describes an upcoming catalyst. Timing is not an independently verified calendar; no price-direction or event-impact inference.'}}
