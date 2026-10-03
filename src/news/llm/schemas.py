"""One strict schema shared by providers and local validation."""
import math

VERSION='news_semantic_v3_1'
CLASSES=['company_event','commentary','opinion','macro_event','geopolitical_event','supply_chain_event','regulatory_event','technology_event','general_news','unrelated_noise']
FIELDS=['summary_short','summary_full','primary_country','event_type','event_subtype','article_class','economic_channels','severity_candidate','operational_event','fundamental_change_detected','direct_ticker_candidates']

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def nullable(kind):return {'type':[kind,'null']}
def strings():return {'type':'array','items':{'type':'string'}}
PROPERTIES={
 'article_class':{'type':'string','enum':CLASSES},'is_relevant_candidate':{'type':'boolean'},
 'summary_short':{'type':'string'},'summary_full':{'type':'string'},
 **{k:nullable('string') for k in ['primary_country','event_type','event_subtype']},
 **{k:strings() for k in ['countries','entities','companies_mentioned','direct_ticker_candidates','economic_channels','candidate_indirect_tickers','missing_information','research_questions']},
 'severity_candidate':{'type':['string','null'],'enum':['Unknown','Low','Medium','High','Critical',None]},
 'severity_reason':{'type':'string'},'severity_confidence':nullable('number'),
 'operational_event':nullable('boolean'),'fundamental_change_detected':nullable('boolean'),'llm_confidence':nullable('number'),
 'citations':{'type':'array','items':obj({'field':{'type':'string','enum':FIELDS},'quote':{'type':'string'},'source_field':{'type':'string','enum':['headline','summary','body']}})}
}
SCHEMA=obj(PROPERTIES)

class SchemaError(ValueError):pass

def validate(value):
    def check(v,s,path):
        types=s.get('type');types=types if isinstance(types,list) else [types]
        good=any((t=='null' and v is None) or (t=='string' and isinstance(v,str)) or (t=='boolean' and type(v)is bool) or (t=='number' and type(v)in(int,float) and math.isfinite(v)) or (t=='array' and isinstance(v,list)) or (t=='object' and isinstance(v,dict)) for t in types)
        if not good:raise SchemaError('Invalid type: '+path)
        if 'enum'in s and v not in s['enum']:raise SchemaError('Invalid enum: '+path)
        if isinstance(v,dict):
            if set(v)!=set(s['properties']):raise SchemaError('Invalid keys: '+path)
            for k,x in v.items():check(x,s['properties'][k],path+'.'+k)
        elif isinstance(v,list):
            if len(v)>100:raise SchemaError('Oversized list')
            for x in v:check(x,s['items'],path)
        elif isinstance(v,str) and len(v)>12000:raise SchemaError('Oversized text')
    check(value,SCHEMA,'result')
    for k in ('llm_confidence','severity_confidence'):
        if value[k] is not None and not 0<=value[k]<=1:raise SchemaError('Confidence out of range')
    if len(value['summary_short'])>600 or len(value['summary_full'])>5000:raise SchemaError('Summary too long')
    return value
