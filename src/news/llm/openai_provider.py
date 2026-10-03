import json
from .base import PROMPT,content,post,ProviderError
from .schemas import SCHEMA

class OpenAIProvider:
    def __init__(self,config):self.config=config
    def generate(self,article):
        c=self.config
        result=post('https://api.openai.com/v1/responses',{'Authorization':'Bearer '+c.api_key},
            {'model':c.model,'store':False,'instructions':PROMPT,'input':content(article),
             'text':{'format':{'type':'json_schema','name':'news_semantics','strict':True,'schema':SCHEMA}}},c.timeout)
        try:
            if result.get('status')!='completed':raise ValueError()
            blocks=[b for o in result['output'] if o.get('type')=='message' for b in o.get('content',[]) if b.get('type')=='output_text']
            value=json.loads(''.join(b['text'] for b in blocks))
        except (KeyError,TypeError,ValueError,AttributeError):raise ProviderError('invalid_or_incomplete_response') from None
        usage=result.get('usage');usage=usage if isinstance(usage,dict) else {}
        return value,{k:usage.get(k) for k in ['input_tokens','output_tokens','total_tokens']}
