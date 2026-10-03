"""Central News V3 configuration; keys are never serialized."""
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path

SOURCE_POLICY_NOTICE = ('Qualitative source-quality policy tier; not a calibrated probability, '
                        'truth probability, statistical accuracy estimate, or model confidence.')
DEFAULT_SOURCE_QUALITY = {'bbc': 'High'}

def configured_source_quality():
    return json.loads(os.environ['NEWS_SOURCE_QUALITY_JSON']) if 'NEWS_SOURCE_QUALITY_JSON' in os.environ else dict(DEFAULT_SOURCE_QUALITY)

def source_key(value):
    return ' '.join(str(value or '').strip().casefold().split())

@dataclass
class Config:
    provider: str = 'none'
    model: str = ''
    fallback_model: str = ''
    api_key: str = field(default='', repr=False)
    max_articles: int = 10
    reprocess: bool = False
    timeout: float = 30
    cache_dir: Path = Path('data/news/llm_enriched')
    half_life_hours: float = 72
    class_half_lives: dict = field(default_factory=dict)
    source_quality: dict = field(default_factory=lambda: dict(DEFAULT_SOURCE_QUALITY))
    input_price: float | None = None
    output_price: float | None = None

    def __post_init__(self):
        if self.provider not in ('none','gemini','openai'): raise ValueError('Unsupported LLM_PROVIDER')
        if not 0 <= self.max_articles <= 1000: raise ValueError('Invalid LLM_MAX_ARTICLES_PER_RUN')
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 120: raise ValueError('Invalid LLM_TIMEOUT_SECONDS')
        if not isinstance(self.class_half_lives,dict) or not isinstance(self.source_quality,dict):raise ValueError('Configuration maps must be JSON objects')
        for v in [self.half_life_hours,*self.class_half_lives.values()]:
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0: raise ValueError('Invalid decay half-life')
        for v in self.source_quality.values():
            if v not in ('High','Medium','Low','Unknown'): raise ValueError('Source quality must be High, Medium, Low or Unknown; numeric weights are no longer supported')
        for v in (self.input_price,self.output_price):
            if v is not None and (not math.isfinite(v) or v<0): raise ValueError('Invalid price')

    def source_tier(self, source):
        # Rebuild normalized keys so programmatic policy edits remain supported.
        return {source_key(k): v for k, v in self.source_quality.items()}.get(source_key(source), 'Unknown')

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(override=False)
        p=os.getenv('LLM_PROVIDER','none').lower()
        optional=lambda k:float(os.environ[k]) if os.getenv(k) else None
        return cls(provider=p,model=os.getenv('GEMINI_MODEL' if p=='gemini' else 'OPENAI_MODEL',''),
            api_key=os.getenv('GEMINI_API_KEY' if p=='gemini' else 'OPENAI_API_KEY','') if p!='none' else '',
            fallback_model=os.getenv('GEMINI_FALLBACK_MODEL','').strip() if p=='gemini' else '',
            max_articles=int(os.getenv('LLM_MAX_ARTICLES_PER_RUN','10')),
            reprocess=os.getenv('LLM_REPROCESS_EXISTING','false').lower()=='true',
            timeout=float(os.getenv('LLM_TIMEOUT_SECONDS','30')),cache_dir=Path(os.getenv('LLM_CACHE_DIR','data/news/llm_enriched')),
            half_life_hours=float(os.getenv('NEWS_DECAY_HALF_LIFE_HOURS','72')),
            class_half_lives=json.loads(os.getenv('NEWS_CLASS_HALF_LIVES_JSON','{}')),
            source_quality=configured_source_quality(),
            input_price=optional('LLM_INPUT_USD_PER_MILLION'),output_price=optional('LLM_OUTPUT_USD_PER_MILLION'))
