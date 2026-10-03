"""Additive analyst-attention policy. Never changes frozen qualifications/scores."""
from copy import deepcopy
from datetime import datetime
import math

NOTICE='Internal research relevance score; not probability, expected return or financial impact.'

def relevance(ticker):
    qualification=ticker.get('qualification') or ''
    relation=ticker.get('relationship_type')
    qualified=qualification.startswith('qualified_') or qualification=='direct_company_subject'
    if qualified and relation in ('direct_event_subject','direct_company_subject'): base,level=80,'High'
    elif qualified: base,level=60,'High'
    elif qualification=='candidate_requires_review': base,level=20,'Review'
    elif relation=='direct_mention': base,level=10,'Mention only'
    else: base,level=0,'No Match'
    old=(ticker.get('quantitative') or {}).get('relevance') or {}
    value=old.get('value')
    supported=max(0,min(1,value)) if type(value) in (int,float) and math.isfinite(value) else 0
    bonus=round(10*supported,2) if base else 0
    return {'level':level,'score':base+bonus,'components':{'qualification_band':base,'existing_supported_terms_bonus':bonus,
            'existing_relevance':old},'method':'qualified_relationship_bands_v1','interpretation':NOTICE}

def attention(article, as_of):
    tickers=article.get('ticker_analysis') or []
    scores=[relevance(t) for t in tickers]
    rel=max(scores,key=lambda r:r['score']) if scores else relevance({})
    severity=(article.get('severity') or {}).get('level','Unknown')
    s={'Critical':100,'High':80,'Medium':50,'Low':20}.get(severity,0)
    priority=(article.get('research_priority') or {}).get('level')
    p={'Urgent':100,'High':80,'Medium':50,'Low':20}.get(priority,0)
    decay=None
    try:
        age=(datetime.fromisoformat(as_of.replace('Z','+00:00'))-datetime.fromisoformat(article['published_at'].replace('Z','+00:00'))).total_seconds()/3600
        if age>=0: decay=math.exp(-math.log(2)*age/72)
    except (KeyError,TypeError,ValueError,OverflowError): pass
    base=max(s*.75,rel['score']*.4,p*.5)
    blocked=(article.get('feed') or {}).get('state')!='surface'
    score=round(base*(.75+.25*(decay or 0)),2) if not blocked else 0
    level='High' if score>=60 else 'Medium' if score>=30 else 'Low' if score>0 else 'Review' if not blocked else 'Not surfaced'
    return {'relevance':rel,'urgency':{'level':level,'score':score,
            'components':{'severity_points':s,'relevance_score':rel['score'],'existing_priority_points':p,'age_decay':decay,'surface':not blocked},
            'method':'analyst_attention_v1','interpretation':'Analyst inspection priority, not stock-price direction or expected return; Unknown severity contributes no established severity points.'},
            'as_of':as_of}

def decorate(payload):
    result=deepcopy(payload)
    for article in result.get('articles',[]):
        if article.get('content_type')=='outlook':
            article['product_scores']=outlook_attention(article,result.get('generated_at') or '')
            continue
        article['product_scores']=attention(article,result.get('generated_at') or '')
        for ticker in article.get('ticker_analysis',[]): ticker['product_relevance']=relevance(ticker)
    return result

def outlook_attention(article, as_of):
    outlook=article.get('outlook') or {}
    category=outlook.get('category')
    context=60 if category in ('macro_data','monetary_policy') else 55 if category in ('earnings','regulatory','semiconductor_supply','geopolitical_watch','company_event') else 40
    direct=15 if any(t.get('relationship')=='direct_catalyst_subject' for t in outlook.get('related_tickers',[])) else 0
    relevance_score=context+direct
    hours=None
    try:
        hours=(datetime.fromisoformat(outlook['scheduled_at_utc'].replace('Z','+00:00'))-datetime.fromisoformat(as_of.replace('Z','+00:00'))).total_seconds()/3600
    except (KeyError,TypeError,ValueError,AttributeError): pass
    timing_bonus=10 if hours is not None and 0<=hours<=168 else 0
    common='Internal upcoming-catalyst attention score; not event severity, a probability, expected return or direction.'
    def score(value,components,method):
        return {'score':value,'level':'High' if value>=75 else 'Medium' if value>=50 else 'Low',
                'components':components,'method':method,'interpretation':common}
    return {'relevance':score(relevance_score,{'research_context':context,'direct_watchlist_catalyst':direct},'outlook_relevance_v1'),
            'watch_priority':score(relevance_score+timing_bonus,{'relevance':relevance_score,'resolved_upcoming_week_bonus':timing_bonus,'hours_to_catalyst':hours},'outlook_watch_v1'),
            'as_of':as_of}
