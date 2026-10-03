"""Human-reviewed benchmark tooling; never promotes AI candidates to ground truth."""
import argparse
import hashlib
import json
from pathlib import Path
from .llm.analyzer import atomic_json

FIELDS=('should_surface','article_class','country','event_type','direct_tickers','indirect_tickers','economic_channels','severity','expected_exposure_paths')
SCHEMA={'schema_version':'news_benchmark_v3','review_status':['pending_human_review','human_verified'],
        'expected_fields':list(FIELDS),'label_rule':'null = unlabelled; [] = explicitly no labels. Human verification requires reviewer and reviewed_at.'}

def fraction(n,d):return {'numerator':n,'denominator':d,'value':n/d if d else None}

def evaluate(benchmark,predictions):
    rows=benchmark['articles'];eligible=[r for r in rows if r.get('review_status')=='human_verified']
    for row in eligible:
        if not row.get('reviewer') or not row.get('reviewed_at'):raise ValueError('Human verification requires reviewer and review time')
        if not isinstance(row.get('expected'),dict) or set(row['expected'])!=set(FIELDS):raise ValueError('Invalid benchmark expected schema')
        e=row['expected']
        if e['should_surface'] is not None and type(e['should_surface'])is not bool:raise ValueError('Invalid surface label')
        for key in ('direct_tickers','indirect_tickers','economic_channels'):
            if e[key] is not None and (not isinstance(e[key],list) or any(not isinstance(x,str) for x in e[key])):raise ValueError('Invalid set label')
        for key in ('article_class','country','event_type','severity'):
            if e[key] is not None and not isinstance(e[key],str):raise ValueError('Invalid categorical label')
        if e['severity'] not in (None,'Unknown','Low','Medium','High','Critical'):raise ValueError('Invalid severity label')
        if e['expected_exposure_paths'] is not None and (not isinstance(e['expected_exposure_paths'],list) or any(not isinstance(x,dict) or not x.get('ticker') or x.get('edge_id') is None for x in e['expected_exposure_paths'])):raise ValueError('Invalid exposure path label')
    ids=[r['article_id'] for r in eligible]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate verified identities')
    predicted=predictions['articles'];pids=[r['article_id'] for r in predicted]
    if len(pids)!=len(set(pids)):raise ValueError('Duplicate prediction identities')
    by_id={r['article_id']:r for r in predicted};missing=[i for i in ids if i not in by_id]
    # Never silently evaluate only the easy subset of a declared benchmark.
    if missing:raise ValueError('Missing predictions for verified benchmark articles: '+','.join(missing))
    stats={k:[0,0] for k in ['noise_rejection_precision','noise_rejection_recall','event_classification_accuracy','country_accuracy','event_type_accuracy','severity_accuracy','severity_coverage','exposure_path_validation_rate']}
    sets={k:{'tp':0,'fp':0,'fn':0,'labelled_articles':0} for k in ['direct_ticker','indirect_exposure','economic_channel']}
    for r in eligible:
        p=by_id[r['article_id']];e=r['expected'];analyses=p.get('ticker_analysis',[])
        direct={t['ticker'] for t in analyses if t.get('relationship_type') in ('direct_event_subject','direct_company_subject') and t.get('qualification','').startswith('qualified_')}
        indirect={t['ticker'] for t in analyses if t.get('relationship_type')=='indirect_exposure_match' and t.get('qualification','').startswith('qualified_')}
        channels={c for t in analyses for c in t.get('economic_channels',[])}
        for key,field,actual in [('direct_ticker','direct_tickers',direct),('indirect_exposure','indirect_tickers',indirect),('economic_channel','economic_channels',channels)]:
            if e[field] is None:continue
            if not isinstance(e[field],list):raise ValueError('Set labels must be arrays or null')
            truth=set(e[field]);v=sets[key];v['tp']+=len(actual&truth);v['fp']+=len(actual-truth);v['fn']+=len(truth-actual);v['labelled_articles']+=1
        if e['should_surface'] is not None and p.get('feed',{}).get('state') in ('surface','background','reject'):
            if type(e['should_surface'])is not bool:raise ValueError('should_surface must be bool/null')
            rejected=p.get('feed',{}).get('state')!='surface';noise=not e['should_surface']
            stats['noise_rejection_precision'][0]+=int(rejected and noise);stats['noise_rejection_precision'][1]+=int(rejected)
            stats['noise_rejection_recall'][0]+=int(rejected and noise);stats['noise_rejection_recall'][1]+=int(noise)
        final={'article_class':p.get('classification'),'country':p.get('geography',{}).get('event_country'),'event_type':(p.get('event') or {}).get('event_type'),'severity':p.get('severity',{}).get('level')}
        for field,key in [('article_class','event_classification_accuracy'),('country','country_accuracy'),('event_type','event_type_accuracy'),('severity','severity_accuracy')]:
            if e[field] is not None:stats[key][0]+=int(final[field]==e[field]);stats[key][1]+=1
        if e['severity'] is not None:
            stats['severity_coverage'][0]+=int(final['severity'] not in (None,'Unknown'));stats['severity_coverage'][1]+=1
        if e['expected_exposure_paths'] is not None:
            expected={(x['ticker'],str(x['edge_id'])) for x in e['expected_exposure_paths']}
            paths={(t['ticker'],str(x['edge_id'])) for t in analyses for x in t.get('relationship_paths',[])}
            stats['exposure_path_validation_rate'][0]+=len(paths&expected);stats['exposure_path_validation_rate'][1]+=len(paths)
    result={k:fraction(*v) for k,v in stats.items()}
    for name,v in sets.items():
        result[name+'_precision']=fraction(v['tp'],v['tp']+v['fp']);result[name+'_recall']=fraction(v['tp'],v['tp']+v['fn']);result[name+'_labelled_articles']=v['labelled_articles']
    return {'human_verified_articles':len(eligible),'pending_articles':len(rows)-len(eligible),'predictions_without_feed_state':sum(by_id[r['article_id']].get('feed',{}).get('state') not in ('surface','background','reject') for r in eligible),'metrics':result,'interpretation':'Null denominator is no estimate. Noise = not surface (background or reject). No aggregate score. Paths use exact ticker/edge identity; reviewed labels must verify the economic chain.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--input',type=Path,required=True);init.add_argument('--output',type=Path,required=True)
    ev=sub.add_parser('evaluate');ev.add_argument('--benchmark',type=Path,required=True);ev.add_argument('--predictions',type=Path,nargs='+',required=True);ev.add_argument('--output',type=Path,required=True)
    candidate=sub.add_parser('candidates');candidate.add_argument('--input',type=Path,required=True);candidate.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if a.command=='init':
        data=json.loads(a.input.read_text());out={'schema_version':'news_benchmark_v3','articles':[{'article_id':x['article_id'],'headline':x['headline'],'source_url':x.get('article_url'),'input_file':str(a.input),'expected':dict.fromkeys(FIELDS),'review_status':'pending_human_review','reviewer':None,'reviewed_at':None} for x in data['articles']]}
        if a.output.exists():raise SystemExit('Refusing to overwrite labels')
    elif a.command=='candidates':
        from .llm.analyzer import Analyzer
        from .v3_config import Config
        analyzer=Analyzer(Config.from_env());out={'schema_version':'ai_benchmark_candidates_v3','ground_truth':False,'articles':[{'article_id':x['article_id'],'candidate':analyzer.analyze_article(x),'review_status':'ai_candidate_only'} for x in json.loads(a.input.read_text())['articles']]}
    else:
        truth=json.loads(a.benchmark.read_text());out={'benchmark_sha256':hashlib.sha256(a.benchmark.read_bytes()).hexdigest(),'runs':{str(p):{'prediction_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**evaluate(truth,json.loads(p.read_text()))} for p in a.predictions}}
    atomic_json(a.output,out);print(json.dumps(out if a.command=='evaluate' else {'articles':len(out['articles']),'output':str(a.output)},indent=2))
if __name__=='__main__':main()
