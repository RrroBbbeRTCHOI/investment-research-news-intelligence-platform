"""Live Intake Policy V1: deterministic routing, never final event authority."""
import re
from urllib.parse import urlsplit

POLICY_VERSION = 'live_intake_v1'

def find(pattern, text):
    return re.search(pattern, text, re.I)

COMPANIES = {'MSFT':r'microsoft|msft', 'NVDA':r'nvidia|nvda', 'AAPL':r'apple|aapl',
             'AMZN':r'amazon|amzn', 'GOOGL':r'google|alphabet|googl',
             'META':r'meta', 'TSLA':r'tesla|tsla'}

CONTEXTS = {
    'earnings':r'\bearnings\b',
    'company_event':r'\b(?:product launch|guidance update|semiconductor capacity decision|export-control decision)\b|\b(?:apple|microsoft|nvidia|amazon|google|alphabet|meta|tesla)\s+(?:reports?\s+(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday)|(?:is\s+)?(?:scheduled|set|due)\s+to\s+report)\b',
    'macro_data':r'\b(?:cpi|consumer price index|inflation(?: data| report)?|jobs report|payrolls|unemployment|gdp|economic calendar)\b',
    'monetary_policy':r'\b(?:fed|federal reserve|fomc|rate decision|rate path|rate guidance)\b',
    'regulatory':r'\b(?:export controls?|export restrictions?|import ban|production restrictions?|antitrust|regulatory (?:probe|hearing|decision|approval|ruling)|court (?:hearing|ruling|decision))\b',
    'semiconductor_supply':r'\b(?:tsmc|cowos|semiconductor|advanced packaging|chip capacity)\b',
    'geopolitical_watch':r'\b(?:strait of hormuz|suez canal|red sea shipping|oil embargo)\b',
}

FUTURE = r'\b(?:week ahead|earnings preview|preview|upcoming|economic calendar|what to watch|what to expect|(?:investors|markets|traders) await(?:ing)?|(?:meeting|decision) ahead|(?:cpi|jobs report|guidance) (?:due|expected)|scheduled (?:to|for)|set (?:to|for)|expected to|due to report|due (?:this|next) week|ahead of|(?:reports?|earnings) (?:on )?(?:monday|tuesday|wednesday|thursday|friday)|(?:will|may|could|might) (?:report|cut|raise|hold|halt|expand|impose))\b'

HARD_NOISE = r'\b(?:best (?:shows|movies|sci-fi|series)|to stream|stream(?:ing)? (?:right )?now|tv shows|(?:game|sports|fc) review|ea sports|(?:first )?odi|test match|cricket|songwriters hall of fame|celebrity|horoscope|recipes?|travel guide|gift guide)\b'

THREAT = r'\b(?:threat(?:ens)?|could face|may face|might face|risks|risk of|possible|potential|could be|may be|might be|expected to face|under threat of|faces threat of)\b'

COMPLETED = (
    r'\b(?:us|u\.s\.|regulator|itc|ftc|eu)\s+(?:imposes?|imposed|orders?|ordered|blocks?|blocked|bans?|banned|fines?|fined)\b',
    r'\b(?:ftc|regulator|eu)\s+(?:opens?|opened)\s+(?:an?\s+)?(?:investigation|probe)\b',
)

ACTUAL = (*COMPLETED,
    r'\bcongress\s+(?:passes|passed)\s+(?:an?\s+)?(?:AI\s+)?law\b',
    r'\bFTC\s+(?:opens|opened)\s+(?:an?\s+)?AI\s+(?:probe|investigation)\b',
    r'\bimport ban\s+(?:is\s+|was\s+)?imposed\s+on\s+[\w-]+\b',
    r'\b(?:microsoft|apple|nvidia|amazon|google|alphabet|meta|tesla)\s+to buy\s+(?:[\w-]+\s+){0,4}(?:company|business|firm)\b',
    r'\bCPI\s+(?:was\s+)?released\s+(?:above|below|in line with)\s+expectations\b',
    r'\b(?:announces?|announced)\s+(?:an?\s+)?acquisition\b',
    r'\b(?:acquires?|acquired)\s+(?:(?:a|an|the)\s+)?(?:[\w-]+\s+){0,3}company\b',
    r'\b(?:raises?|raised)\s+(?:revenue|earnings)\s+guidance\b',
    r'\b(?:ramps? up|ramped up)\s+oil shipments\b',
    r'\b(?:fed|federal reserve|fomc)\b.{0,30}\b(?:holds?|held|raises?|raised|cuts?|cut)\b.{0,20}\brates?\b',
    r'\b(?:cpi|inflation|payrolls|jobs report|unemployment|gdp)\b.{0,35}\b(?:rose|fell|increased|decreased|came in|slowed|accelerated|data showed|released)\b',
    r'\b(?:aws|azure|cloud|services?|factory|production|supplier|fab|plant)\b.{0,45}\b(?:outage|disrupts?|disrupted|halts?|halted|shutdown|shuts? down|suspended|interrupted)\b',
    r'\b(?:reports?|reported|posts?|posted|releases?|released)\s+(?:quarterly\s+)?earnings\b',
    r'\b(?:faces?|imposes?|imposed|announces?|announced)\s+(?:new\s+)?(?:us\s+)?export controls?\b',
    r'\b(?:tanker|ship|shipping)\b.{0,25}\b(?:hit|attacked|blocked|disrupted)\b',
    r'\b(?:tsmc|semiconductor|company|apple|microsoft|nvidia)\b.{0,25}\b(?:expands?|expanded|opens?|opened)\b.{0,35}\b(?:capacity|factory|campus|plant|production)\b',
)

def actual_evidence(text):
    for pattern in ACTUAL:
        for match in re.finditer(pattern,text,re.I):
            clause=text[max(0,match.start()-35):match.end()]
            if find(r'\b(?:not|never|no|may|might|could|would|will|expected to|scheduled to|set to|if)\b',clause): continue
            # "reports earnings Thursday" is a scheduled report, not a result.
            if find(r'\breports?\s+earnings\s+(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday|next|tomorrow)\b',text): continue
            return match.group(0)
    return None

# Named, bounded evidence groups; no standalone buy/sell/watch/stock triggers.
EDITORIAL_PATTERNS = {
    'valuation': r'\b(?:PEG|P/E|PE ratio|price-to-earnings|fair value|intrinsic value|valuation|undervalued|overvalued|cheap at|expensive at|(?:current|earnings|forward) multiples?|EV/EBITDA|price-to-sales)\b|\btrad(?:e|es|ing) at\s+(?:just\s+)?\d+(?:\.\d+)?\s*x\b',
    'stock_picking': r'\b(?:stocks? to buy|buy now|sell now|strong buy|hold rating|best stocks|bull case|bear case|why I bought|reasons to (?:buy|sell)|investment thesis|stock analysis|investment case|price target)\b|\bis\b[^?!.;\n]{1,60}\bstock a buy\b',
    'technical_analysis': r'\b(?:technical analysis|support levels?|resistance levels?|chart setup|breakout target|moving average|RSI|MACD)\b',
    'stock_listicle': r'\btop\s+(?:(?:\d+|three|five|ten)\s+)?(?:(?:AI|S&P\s+500)\s+)?stocks?\b|\bstocks? (?:to watch|investors should watch|for the week ahead)\b|\b(?:market|stock) picks\b',
}
RESEARCH_PATTERNS = {
    'technology_adoption': r'\b(?:AI|technology) adoption\b|\badoption (?:trend|curve)\b',
    'policy_advocacy': r'\b(?:calls? for|joins calls for|urges?|warns? lawmakers)\b.{0,100}\b(?:AI safeguards?|legislation|regulation|AI law)\b',
    'policy_debate': r'\b(?:policy|regulatory) debate\b',
    'industry_structure': r'\b(?:semiconductor|packaging|supply.chain|industry)\b.{0,80}\b(?:structural|bottleneck|constraint|structure|long.term)\b',
    'trade_structure': r'\bUS[–-]China\b.{0,100}\b(?:truce|trade uncertainty|long.term)\b',
    'structural_analysis': r'\b(?:industry|strategic) analysis\b|\b(?:demand|capacity|structural) trend\b|\bmarket structure\b',
    'management_commentary': r'\b(?:CEO|management|executive)\b.{0,60}\b(?:discusses|comments on|outlines)\b.{0,80}\b(?:AI|cloud|strategy|supply.chain|demand)\b',
}
SCHEDULED = r'\b(?:tomorrow|next week|expected (?:on|next week)|due|scheduled|set for|on (?:monday|tuesday|wednesday|thursday|friday))\b'
BOUNDED_CATALYSTS = (
    r'\b(?:earnings|CPI|consumer price index|jobs report|payrolls|GDP|inflation (?:data|report)|rate (?:decision|path|guidance)|'
    r'(?:Fed|FOMC|Federal Reserve) (?:meeting|decision)|regulatory (?:ruling|probe|hearing|decision|approval)|'
    r'court (?:decision|ruling|hearing)|import ban|export (?:controls?|restrictions?)|production restrictions?|antitrust action|'
    r'product launch|guidance update|semiconductor capacity decision|export-control decision)\b'
    r'|\b(?:Fed|FOMC|Federal Reserve)\b.{0,30}\b(?:cut|cuts|raise|raises|hold|holds)\s+(?:interest\s+)?rates\b'
)
EDITORIAL_PATH = r'/(?:opinion|commentary|et-commentary|editorial|columns|columnists)(?:/|$)'


def _text(article, field='headline'):
    return str(article.get(field) or '')


def _signals(patterns, text):
    return [name for name, pattern in patterns.items() if find(pattern, text)]


def is_hard_noise(article, prefilter_result):
    if (prefilter_result or {}).get('state') == 'reject':
        return ['frozen_reject']
    match = find(HARD_NOISE, ' '.join(_text(article, k) for k in ('headline', 'summary', 'body')))
    return ['hard_noise', match.group(0)] if match else []


def is_actual_event(article):
    headline = _text(article)
    evidence = actual_evidence(headline)
    relevant = bool(_signals(CONTEXTS, headline) or find(
        r'\b(?:apple|microsoft|nvidia|amazon|google|alphabet|meta|tesla|aws|azure|supplier|congress|FTC|ITC|EU|regulator|US)\b', headline))
    return ['actual_action', evidence] if evidence and relevant else []


def is_investment_editorial(article):
    return bool(_signals(EDITORIAL_PATTERNS, _text(article)))


def is_outlook(article):
    # A future phrase and its catalyst must occur in the same source field.
    fields = ('headline',) if is_investment_editorial(article) else ('headline', 'summary')
    for field in fields:
        text = _text(article, field)
        future = find(THREAT, text) or find(FUTURE, text) or find(SCHEDULED, text)
        catalyst = find(BOUNDED_CATALYSTS, text)
        # Preserve existing direct company-reporting and macro watch contexts.
        if not catalyst:
            catalyst = find(CONTEXTS['company_event'], text)
        if future and catalyst:
            return ['bounded_catalyst', field, future.group(0), catalyst.group(0)]
    return []


def is_research_commentary(article):
    # Headline and short summary only; incidental body terms do not qualify it.
    return _signals(RESEARCH_PATTERNS, _text(article) + ' ' + _text(article, 'summary'))


def _editorial_path(article):
    try:
        return bool(find(EDITORIAL_PATH, urlsplit(_text(article, 'article_url')).path))
    except ValueError:
        return False


def classify_live_intake(article, prefilter_result):
    """Processing intent only. Final event/display authority stays in the backend."""
    def decision(kind, reason, signals):
        return {'content_type': kind, 'reason': reason, 'signals': signals,
                'policy_version': POLICY_VERSION, 'method': POLICY_VERSION}

    noise = is_hard_noise(article, prefilter_result)
    if noise:
        return decision('skip', 'Frozen reject or hard non-research content.', noise)
    action = is_actual_event(article)
    if action:
        return decision('event', 'Explicit actual action/result in research context.', action)
    outlook = is_outlook(article)
    if outlook:
        return decision('outlook', 'Specific future research catalyst.', outlook)
    editorial = _signals(EDITORIAL_PATTERNS, _text(article))
    if editorial:
        return decision('skip', 'Investment editorial, valuation or stock listicle.', editorial)
    research = is_research_commentary(article)
    if research:
        if _editorial_path(article):
            research.append('editorial_path')
        return decision('research', 'Supported research discussion without confirmed action or bounded catalyst.', research)
    if _editorial_path(article):
        return decision('skip', 'Editorial path without supported event, catalyst or research evidence.', ['editorial_path', 'no_supported_research_evidence'])
    # Unresolved modality must never fall through to an Event label.
    if find(THREAT, _text(article)) or find(FUTURE, _text(article)):
        return decision('skip', 'Unresolved future wording without a bounded catalyst.', ['unbounded_future'])
    from .live_runner import live_intake_allow
    if live_intake_allow(article, prefilter_result):
        return decision('research', 'Legacy research eligibility retained; discrete event not established at intake.', ['legacy_eligibility'])
    return decision('skip', 'No supported live research evidence.', ['no_research_evidence'])
