"""Research intelligence V2. V1 analytical contracts remain available for replay."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from .research_intelligence import analyze_article, DIRECTION
from .constants import ENTITY_ALIASES, MAG7, WEIGHTS
from .event_gate import clauses, assertion_status, HISTORICAL
from .event_geography import geography
from .research_policy import severity, priority, PRIORITY_SCORES
from .pipeline import ROOT, _resolve_prediction_time
from .exposure_matcher import load_exposure_edges
from .historical_context import load_archive


def company_links(article):
    """Bounded headline/company action links, separately recording mere mention."""
    links={}
    for ticker,names in ENTITY_ALIASES.items():
        if ticker not in MAG7:continue
        company=r'(?<!\w)(?:'+'|'.join(re.escape(n) for n in sorted(names,key=len,reverse=True))+r')(?!\w)'
        mention=None
        for field,_,clause in clauses(article):
            m=re.search(company,clause,re.I)
            if not m:continue
            if mention is None:mention=dict(relationship_type='direct_mention',evidence=clause,source_field=field)
            if HISTORICAL.search(clause):continue
            years=re.findall(r'\b(?:19|20)\d{2}\b',clause)
            year=str(article.get('published_at') or '')[:4]
            if years and year.isdigit() and max(map(int,years))<int(year):continue
            if re.search(r'\b(?:compared?|example|in focus|preview|prediction|whether|might|could|may)\b',clause,re.I):continue
            # Require a subject beginning a headline/sentence, not a name in a roundup.
            start=r'^\s*(?:Report:\s*)?'+company
            action=re.search(start+r"(?:[’']s)?\s+(?:(?:[\w+]+)\s+){0,3}(?:cuts? jobs|layoffs? (?:reported|announced)|announces? layoffs|lays? off)\b",clause,re.I)
            comment=re.search(start+r"(?:[’']s)?\s+(?:(?:CEO|boss|chief executive)\s+)?(?:says?|said|rejects?|discusses|discussed|comments? on)\b",clause,re.I)
            match=action or comment
            if match and assertion_status(clause,match.start(),match.end())=='affirmed':
                links[ticker]=dict(relationship_type='direct_event_subject' if action else 'direct_company_subject',
                                   evidence=clause,source_field=field,
                                   channel='workforce_reduction' if action else None)
                break
        if ticker not in links and mention:links[ticker]=mention
    return links


def usable(article):
    return (isinstance(article,dict) and isinstance(article.get('article_id'),str)
            and isinstance(article.get('headline'),str) and len(article['headline'].strip())>5
            and isinstance(article.get('body'),str) and len(article['body'].split())>=6
            and not re.fullmatch(r'(?:home|menu|sign in|subscribe|privacy|contact|\W|\s)+',article['body'],re.I))


def analyze_v2(article,edges,*,archive=None,now=None,prediction_time=None):
    if not usable(article):
        return dict(article_id=article.get('article_id') if isinstance(article,dict) else None,
                    headline=article.get('headline') if isinstance(article,dict) else None,
                    usable=False,status='unusable_content',classification='unrelated_noise',
                    gate={'is_event':False,'gate_reason':'Malformed or no substantive body.'},event=None,
                    ticker_analysis=[],direction=DIRECTION,severity=severity({},'unrelated_noise'))
    # Reuse all existing affirmed-event and point-in-time matching safeguards.
    result=analyze_article(article,edges,archive=archive,now=now,prediction_time=prediction_time)
    links=company_links(article)
    at=_resolve_prediction_time(article,explicit_prediction_time=prediction_time)
    if result['gate']['is_event']:
        kind=(result.get('event') or {}).get('event_type')
        classification={'macro_monetary':'macro_event','geopolitical_conflict':'geopolitical_event'}.get(kind,'actionable_event')
    elif any(x['relationship_type']=='direct_company_subject' for x in links.values()):classification='commentary'
    elif any(x.get('channel')=='workforce_reduction' for x in links.values()):classification='low_severity_event'
    elif re.search(r'\b(?:opinion|comment|column|analysis|prediction|in focus)\b',article['headline'],re.I):classification='opinion'
    else:classification='general_news'
    result.update(usable=True,classification=classification,status=classification,published_at=article.get('published_at'))
    result['geography']=geography(article)
    result['severity']=severity(article,classification)
    event=result['event'] or dict(event_id='article_'+hashlib.sha256(article['article_id'].encode()).hexdigest()[:20],
                                  event_type=classification,event_subtype=classification,
                                  published_at_first=article.get('published_at'))
    # Geography is presentation evidence, never fed back into exposure matching.
    event.update(country=result['geography']['event_country'],region=result['geography']['event_region'],
                 city=result['geography']['event_city'],latitude=result['geography']['latitude'],longitude=result['geography']['longitude'],
                 location_basis=result['geography']['location_basis'],coordinate_precision=result['geography']['coordinate_precision'])
    result['event']=event
    analyses={x['ticker']:x for x in result['ticker_analysis']}
    for ticker,link in links.items():
        t=analyses.setdefault(ticker,dict(ticker=ticker,qualification='candidate_requires_review',relationship_type='direct_mention',
            relevance_score=WEIGHTS['direct_mention'],relevance_level='Mention only',evidence=[],economic_channels=[],relationship_paths=[],
            evidence_strength={'relationship_level':'Mention only'},materiality={'level':'Unknown'},
            historical_reaction={'status':'unavailable','reason':'No compatible archived event binding.','predictions':[]},
            explanation='Company is mentioned; no qualified relationship established.',next_questions=[]))
        if link['relationship_type']!='direct_mention' and at is not None:
            t.update(relationship_type=link['relationship_type'],qualification='qualified_'+link['relationship_type'],
                     direct_event_evidence=link,explanation=f"{ticker} is the explicit company/action subject of the cited article clause.",
                     next_questions=['Verify the original report and any company confirmation.','Determine event-specific scale and financial exposure.'])
            if not t.get('evidence'):t['evidence_strength']={'relationship_level':'Direct article evidence','basis':'Explicit company subject; no independent confirmation inferred.'}
            if link.get('channel'):t['economic_channels']=sorted(set(t.get('economic_channels',[])+[link['channel']]))
    for t in analyses.values():
        relation=t['relationship_type'];strong=any(e.get('evidence_status')=='verified' for e in t.get('evidence',[]))
        level='High' if relation in ('direct_event_subject','direct_company_subject') or strong else 'Medium' if t.get('evidence') else 'Mention only'
        evidence_level='Strong' if strong else 'Moderate' if relation in ('direct_event_subject','direct_company_subject') else 'Partial' if t.get('evidence') else 'Mention only'
        t['relevance']=dict(level=level,relationship_score=t.get('relevance_score'),reason=t.get('explanation'),
                            interpretation='Uncalibrated relationship policy score; not probability or expected return.')
        t['evidence_assessment']=dict(level=evidence_level,reason=t.get('evidence_strength',{}).get('basis') or 'Curated relationship evidence; article confirmation remains separate.')
        # Existing Unknown is not upgraded from a severity label or an exposure band.
        t['financial_materiality']=dict(level='Insufficient evidence' if level=='Mention only' else 'Not yet quantified',reason='No validated event-specific financial amount/denominator established.',legacy=deepcopy(t.get('materiality')))
        t['research_priority']=priority(level,result['severity']['level'],evidence_level)
        context=deepcopy(t.get('historical_reaction') or {'status':'unavailable'})
        t['historical_context']=dict(available=context.get('status') not in ('unavailable',None),
                                     disclosure='Retrospective context only; not a live directional prediction.',details=context)
        t['direction']=DIRECTION
    result['ticker_analysis']=list(analyses.values())
    result['research_priority']=priority('None',result['severity']['level'],'Unavailable') if not analyses else max(
        (x['research_priority'] for x in analyses.values()),key=lambda p:PRIORITY_SCORES[p['level']] or .3)
    return result


def build_research_output_v2(articles,edges,*,knowledge=None,archive=None,now=None,prediction_time=None):
    if not isinstance(articles,list):raise ValueError('Expected article list')
    edge_ids=[e.get('edge_id') for e in edges]
    if any(not i for i in edge_ids) or len(set(edge_ids))!=len(edge_ids):raise ValueError('Unique nonempty edge IDs required')
    now=now or datetime.now(timezone.utc).isoformat();results=[];seen=set()
    for index,article in enumerate(articles):
        item=analyze_v2(article,edges,archive=archive,now=now,prediction_time=prediction_time)
        if not item.get('article_id'):item['article_id']=f'unusable_{index}'
        if not isinstance(item.get('headline'),str):item['headline']='Unusable article'
        aid=item.get('article_id')
        if aid in seen and aid is not None:item.update(usable=False,status='duplicate',ticker_analysis=[],event=None)
        seen.add(aid);results.append(item)
    queue=[dict(article_id=a['article_id'],event_id=a['event']['event_id'],ticker=t['ticker'],
                qualification=t['qualification'],priority=t['research_priority']['level'],direction=DIRECTION)
           for a in results if a['usable'] for t in a['ticker_analysis']]
    order={'Urgent':0,'High':1,'Medium':2,'Review':3,'Low':4};queue.sort(key=lambda q:(order[q['priority']],q['article_id'],q['ticker']))
    return dict(schema_version='news_research_v2',generated_at=now,knowledge=knowledge or {},
                policies={'direction':DIRECTION,'severity':'article_severity_policy_v2','priority':'attention_policy_v2','historical_ml_role':'optional_retrospective_context_only'},
                articles=results,research_queue=queue,
                summary=dict(articles=len(results),usable=sum(a['usable'] for a in results),
                    discrete_events=sum(a['usable'] and a['gate']['is_event'] for a in results),
                    rejected=sum(not a['usable'] for a in results),
                    qualified_pairs=sum(q['qualification'].startswith('qualified_') for q in queue),
                    review_candidates=sum(q['qualification']=='candidate_requires_review' for q in queue)))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--historical-map',type=Path);parser.add_argument('--historical-dir',type=Path)
    args=parser.parse_args();edges,knowledge=load_exposure_edges(ROOT)
    archive=load_archive(ROOT,args.historical_map,args.historical_dir)
    result=build_research_output_v2(json.loads(args.input.read_text())['articles'],edges,knowledge=knowledge,archive=archive)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False)
    print(json.dumps(result['summary'],indent=2))

if __name__=='__main__':main()
