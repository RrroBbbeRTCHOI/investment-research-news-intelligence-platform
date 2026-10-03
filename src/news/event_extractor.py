"""Article facts only: no exposure data, inferred suppliers or ticker impacts."""
import hashlib
import re
from datetime import datetime, timezone
from .constants import (COMPANY_ALIASES, COUNTRY_ALIASES, HEURISTICS, MAG7,
                        LOCATION_COUNTRIES, LOCATION_KINDS, INSTITUTION_COUNTRIES)
from .event_gate import (HISTORICAL, assertion_status, clauses, event_evidence,
                         EXPORT_WORDING, financial_wording_allowed)
from .schemas import Event

FLAG_PATTERNS = {
 'physical_damage': r'(?:buildings?|factories|infrastructure).{0,35}(?:damaged|destroyed)|physical damage',
 'production_disruption': r'production.{0,25}(?:halted|suspended|disrupt\w*|stopped|outage|interruption)|(?:halts?|halted|suspended|interrupts?|interrupted).{0,20}production|\bfactory shutdowns?\b|\bindustrial disruptions?\b',
 'capacity_disruption': r'capacity.{0,25}(?:lost|reduced|disrupt\w*)',
 'logistics_disruption': r'(?:rail services|rail|shipping|freight|transport|logistics).{0,30}(?:suspended|suspensions|halted|disrupted|blocked|delays|delayed)|(?:delays?|delayed) .{0,35}\bshipments\b',
 'port_disruption': r'\b(?:ports?|harbou?rs?|terminals?)\b.{0,30}(?:closed|closures?|blocked|disrupt\w*|shut)',
 'power_disruption': r'(?:power|electricity).{0,20}(?:outages?|disrupt\w*|lost)|lost power',
 'network_disruption': r'network.{0,20}(?:outage|disruption|failed)',
 'cloud_service_disruption': r'(?:cloud|AWS|Azure).{0,30}(?:outage|disrupted|went down)',
 'labor_disruption': r'(?:workers|union|employees).{0,40}(?:strike|walked out)',
 'supply_shortage': r'(?:supply|chip|fuel|component).{0,20}shortage',
 'regulatory_change': r'(?:enacted|adopted|passed|issued|introduces?|introduced|announced).{0,30}(?:regulations?|law|rules|requirements)',
 'export_restriction': r'(?:imposed|tightens?|tightened|announced|enacted|issued).{0,35}export (?:controls?|ban|restrictions?)',
 'import_restriction': r'(?:imposed|tightened|enacted|issued).{0,35}import (?:controls?|ban|restrictions?)',
 'price_change_explicit': r'prices?.{0,20}(?:rose|fell|increased|decreased|dropped)',
 'demand_change_explicit': r'demand.{0,20}(?:rose|fell|increased|decreased|dropped)',
}
# Explicit fabrication actions are production evidence, independent of packaging.
FABRICATION = r'(?:wafer fabrication|semiconductor fabrication|foundry production|fab production|fabrication|production)'
FLAG_PATTERNS['production_disruption'] += (
    r'|' + FABRICATION + r'.{0,25}(?:interrupt\w*|halts?|halted|suspension|suspended|disrupt\w*)'
    r'|(?:interrupted|interrupts?|halted|suspended|disrupted).{0,25}' + FABRICATION)

FAB_TECHNOLOGIES = ('wafer fabrication', 'logic wafer', 'logic wafers', 'leading-edge logic',
                    'semiconductor fabrication', 'foundry production', 'fab production',
                    'leading-edge semiconductor manufacturing', '3nm', '4nm', '5nm')
PACKAGING_TECHNOLOGIES = ('CoWoS', 'CoWoS-L', 'CoWoS-S', 'advanced packaging',
                          'chip packaging', 'packaging capacity')


def technology_affirmed(text, start, end):
    """Include the technology's trailing predicate (including parenthetical names)."""
    # Semicolons and coordinated technology subjects delimit independent claims.
    boundary = r';|(?:,\s*|\band\s+)(?=(?:wafer|fab|CoWoS|advanced packaging|chip packaging))'
    cuts = list(re.finditer(boundary, text, re.I))
    left = max((m.end() for m in cuts if m.end() <= start), default=0)
    right = min((m.start() for m in cuts if m.start() >= end), default=len(text))
    text, start, end = text[left:right], start-left, end-left
    if assertion_status(text, start, end) != 'affirmed':
        return False
    tail = text[end:]
    return not re.search(
        r'\b(?:not (?:affected|disrupted|interrupted|halted)|unaffected|'
        r'continu(?:ed|ing|es?) (?:operating |to operate )?normally|'
        r'operat(?:ing|ed|es?) normally|remained (?:operational|unaffected)|'
        r'no (?:reported )?(?:disruption|impact))\b', tail, re.I)


NEGATIVE_PATTERNS = {
 'physical_damage': r'no (?:physical )?damage|(?:buildings?|factories) (?:were|was) undamaged',
 'production_disruption': r'no production disruption|(?:production|factories|operations) (?:was |were |remained )?(?:unaffected|operational)|production (?:was )?not (?:halted|disrupted|suspended)',
 'capacity_disruption': r'capacity (?:was |remained )?unaffected|no capacity (?:loss|disruption)',
 'logistics_disruption': r'no logistics disruption|(?:rail services|shipping|logistics|transportation systems) (?:were |remained )?(?:unaffected|operational)',
 'port_disruption': r'(?:ports?|harbours?|harbors?) (?:remained|was|were) (?:open|operational|unaffected)|no port disruption',
 'power_disruption': r'no power outage|(?:power(?: supply)?|electricity|grid) (?:was |remained )?(?:unaffected|operational)',
 'network_disruption': r'no network outage|network (?:was |remained )?unaffected',
 'cloud_service_disruption': r'no cloud outage|cloud services (?:were |remained )?unaffected',
}
NEGATIVE_PATTERNS['production_disruption'] += (
    r'|' + FABRICATION + r'.{0,80}\b(?:continued (?:operating )?normally|remained operational)')

CHANNEL_PATTERNS = {
 'supply_channel': r'production|supply shortage|factory',
 'demand_channel': r'demand', 'cost_channel': r'costs?', 'revenue_channel': r'revenue',
 'margin_channel': r'profit margins?', 'capex_channel': r'capital expenditure|capex',
 'financing_channel': r'financing|bond offering|funding',
 'interest_rate_channel': r'interest rates?|policy rate|benchmark rate',
 'fx_channel': r'exchange rate|currency', 'commodity_channel': r'oil|natural gas|copper|lithium',
 'logistics_channel': r'rail services|shipping|port|logistics|distribution cent(?:er|re)|fulfil(?:l)?ment cent(?:er|re)',
 'energy_channel': r'electricity|power outage|oil output|gas supply',
 'regulatory_channel': r'export controls?|regulations?|tariffs?|sanctions|rules|requirements',
 'legal_channel': r'antitrust|court', 'technology_channel': r'chips?|processor|software|(?:AI|artificial intelligence) models?|spacecraft|Azure|cloud capacity',
 'competition_channel': r'merger|acquisition',
}
VOCABULARY = {
 'companies_mentioned': ('TSMC', 'Taiwan Semiconductor Manufacturing Company', 'Boeing', 'SpaceX', 'Samsung', 'Micron', 'Foxconn'),
 'industries_mentioned': ('semiconductors', 'automotive', 'banking', 'aviation'),
 'technologies_mentioned': ('HBM', 'advanced packaging', 'advanced semiconductors', 'advanced semiconductor chips', 'semiconductors', 'AI'),
 'products_mentioned': ('Starliner', 'Dragon', 'iPhone', 'Azure', 'AWS', 'vehicle', 'vehicles'),
 'commodities_mentioned': ('oil', 'natural gas', 'copper', 'lithium', 'nickel'),
 'government_entities': ('NASA', 'Federal Reserve', 'European Commission'),
 'regulators': ('FTC', 'SEC', 'Federal Reserve'),
}

VOCABULARY['technologies_mentioned'] += FAB_TECHNOLOGIES + tuple(
    t for t in PACKAGING_TECHNOLOGIES if t not in VOCABULARY['technologies_mentioned'])

def _search(term: str, text: str, flags=0):
    return re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)', text, flags)

def extract_event(article: dict, *, now: str | None = None) -> dict | None:
    support = event_evidence(article)
    if support is None:
        return None
    if not article.get('provider_article_id') or not article.get('article_id'):
        raise ValueError('Accepted article requires provider_article_id and article_id')
    now = now or datetime.now(timezone.utc).isoformat()
    identity = f"{article['provider_article_id']}|{support['event_type']}"
    event_id = 'evt_' + hashlib.sha256(identity.encode()).hexdigest()[:24]
    e = Event(event_id, event_id, [article['article_id']],
              first_seen_at=article.get('fetched_at'), last_seen_at=article.get('fetched_at'),
              published_at_first=article.get('published_at'), event_type=support['event_type'],
              event_subtype=support['event_subtype'], canonical_headline=article.get('headline'),
              event_summary=support['evidence'], extraction_confidence=HEURISTICS['extraction'],
              keywords=[support['event_subtype']], created_at=now, updated_at=now)

    def record(key, value, quote, source='body', kind='article_text'):
        old = e.evidence_fields.get(key)
        setattr(e, key, value)
        e.evidence_fields[key] = dict(value=value, evidence=quote[:240], source_field=source, basis=kind)
        if isinstance(value, list):
            supports = list(old.get('supporting_snippets', [])) if old else []
            item = dict(evidence=quote[:240], source_field=source)
            if item not in supports:
                supports.append(item)
            e.evidence_fields[key]['supporting_snippets'] = supports

    for key in ('event_type', 'event_subtype', 'event_summary', 'keywords'):
        record(key, getattr(e, key), support['evidence'], support['source_field'])
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b',support['clause'])
    if len(set(dates)) == 1:
        try:
            explicit_date = datetime.strptime(dates[0],'%Y-%m-%d').date().isoformat()
        except ValueError:
            explicit_date = None
        if explicit_date:
            record('event_start_at',explicit_date,dates[0],support['source_field'])
            record('time_precision','date_only',dates[0],support['source_field'])
    record('canonical_headline', e.canonical_headline, str(e.canonical_headline or ''), 'headline')
    for key in ('source_count', 'independent_source_count', 'event_status', 'confirmation_level', 'extraction_confidence'):
        record(key, getattr(e, key), 'V1 single-article extraction default; not independent verification.', 'pipeline', 'administrative_default')
    for key, source in [('published_at_first','published_at'),('first_seen_at','fetched_at'),('last_seen_at','fetched_at')]:
        if getattr(e, key):
            record(key, getattr(e, key), str(article[source]), source, 'provider_metadata')

    # Location is restricted to the accepted event clause, not publisher metadata or all article countries.
    locations = []
    geography = {**COUNTRY_ALIASES, **LOCATION_COUNTRIES, **INSTITUTION_COUNTRIES}
    for alias, country in geography.items():
        found = _search(alias, support['clause'])
        if found:
            locations.append((found.start(), country))
    countries = list(dict.fromkeys(c for _, c in sorted(locations)))
    if countries:
        record('affected_countries', countries, support['evidence'], support['source_field'])
        primary = countries[0] if len(countries) == 1 else None
        if e.event_type in ('trade_export_control','government_policy'):
            # Identify the policy actor, not the destination. Require an explicit action relation.
            for alias,country in COUNTRY_ALIASES.items():
                actor = re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)(?: government)?\s+(?:has\s+)?(?:announc\w*|impos\w*|tighten\w*|issu\w*|enact\w*|updates?|updated|revises?|revised|expands?|expanded|restricts?|restricted|curbs?|curbed)\b',support['clause'])
                passive = re.search(r'\bby (?:the )?'+re.escape(alias)+r'(?!\w)',support['clause'])
                if actor or passive:
                    primary = country
                    break
        if primary:
            record('primary_country', primary, support['clause'][:240], support['source_field'], 'article_location_or_policy_actor')
        for city,country in LOCATION_COUNTRIES.items():
            if _search(city,support['clause']):
                record(LOCATION_KINDS[city],city,city,support['source_field'])
        # Derived geographic mappings retain the stated location/institution as evidence.
        e.evidence_fields['affected_countries']['mapping_basis'] = [
            {'stated': alias, 'country':country} for alias,country in geography.items()
            if _search(alias,support['clause'])]
        record('location_confidence', HEURISTICS['location'], support['evidence'], support['source_field'], 'heuristic_from_article')

    # Outage reports can put their explicit location outside the selected clause.
    # Use named countries only; never turn a city or "global" into a country.
    if not countries and e.event_type == 'infrastructure_outage':
        explicit = []
        for source, _, text in clauses(article):
            if HISTORICAL.search(text):
                continue
            for alias, country in COUNTRY_ALIASES.items():
                m = _search(alias, text)
                if m and assertion_status(text, m.start(), m.end()) == 'affirmed':
                    explicit.append((country, text, source))
        if not explicit:
            metadata = article.get('countries')
            if isinstance(metadata, list):
                explicit = [(COUNTRY_ALIASES[c], c, 'countries') for c in metadata
                            if isinstance(c, str) and c in COUNTRY_ALIASES]
        countries = list(dict.fromkeys(c for c, _, _ in explicit))
        if countries:
            for _, quote, source in explicit:
                record('affected_countries', countries, quote, source,
                       'normalized_country_metadata' if source == 'countries' else 'explicit_article_country')
            if len(countries) == 1:
                _, quote, source = explicit[0]
                record('primary_country', countries[0], quote, source,
                       'normalized_country_metadata' if source == 'countries' else 'explicit_article_country')

    # Scan explicit clauses for facts. Contradictory claims remain unknown, with both snippets retained.
    all_clauses = list(clauses(article))
    for key, pattern in FLAG_PATTERNS.items():
        claims = []
        for source, _, clause in all_clauses:
            if HISTORICAL.search(clause):
                continue
            years = re.findall(r'\b(?:19|20)\d{2}\b', clause)
            year = str(article.get('published_at') or '')[:4]
            if years and year.isdigit() and max(map(int,years)) < int(year):
                continue
            clause_countries = {country for alias,country in COUNTRY_ALIASES.items() if _search(alias,clause)}
            if countries and clause_countries and not clause_countries.issubset(set(countries)):
                continue
            for m in re.finditer(pattern,clause,re.I):
                status=assertion_status(clause,m.start(),m.end())
                if status!='hypothetical':
                    claims.append(({'affirmed':True,'negated':False,'unknown':None}[status],clause,source,status))
            if (key == 'export_restriction' and support.get('wording_family') == 'export'
                    and financial_wording_allowed(clause, 'export')):
                for m in re.finditer(EXPORT_WORDING, clause, re.I):
                    status = assertion_status(clause, m.start(), m.end())
                    if status != 'hypothetical':
                        claims.append(({'affirmed':True,'negated':False,'unknown':None}[status],
                                       clause,source,status))
            negative=NEGATIVE_PATTERNS.get(key)
            if negative:
                for m in re.finditer(negative,clause,re.I):
                    status=assertion_status(clause,m.start(),m.end())
                    if status!='hypothetical':
                        claims.append((None if status=='unknown' else False,clause,source,
                                       'unknown' if status=='unknown' else 'negated'))
        if claims:
            values={c[0] for c in claims if c[0] is not None}
            value=next(iter(values)) if len(values)==1 else None
            chosen=next((c for c in claims if c[0] is value),claims[0])
            record(key,value,chosen[1],chosen[2])
            e.evidence_fields[key]['assertion']='conflicting' if len(values)>1 else chosen[3]
            if len(values)>1:
                e.evidence_fields[key]['conflicting_evidence']=list(dict.fromkeys(c[1][:180] for c in claims))

    if support.get('wording_family') == 'service_outage':
        # Existing flags already feed cloud_services / datacenter_infrastructure.
        cloud = re.search(r'\b(?:cloud|AWS|Azure)\b', support['clause'], re.I)
        key = 'cloud_service_disruption' if cloud else 'network_disruption'
        if getattr(e, key) is None and key not in e.evidence_fields:
            record(key, True, support['evidence'], support['source_field'])
            e.evidence_fields[key]['assertion'] = 'affirmed'

    # Channels refer only to the accepted clause; hypotheses live in a separate object.
    for key, pattern in CHANNEL_PATTERNS.items():
        if any(assertion_status(support['clause'],m.start(),m.end())=='affirmed'
               for m in re.finditer(r'\b(?:'+pattern+r')\b',support['clause'],re.I)):
            record(key, True, support['evidence'], support['source_field'])
            e.evidence_fields[key]['assertion']='affirmed'

    if support.get('wording_family') == 'export' and e.export_restriction is True:
        record('regulatory_channel', True, support['evidence'], support['source_field'])
        e.evidence_fields['regulatory_channel']['assertion'] = 'affirmed'

    if support.get('wording_family') in ('lifecycle', 'action_recall'):
        # Record the action channel, not guilt, a final remedy, or financial harm.
        if e.event_type == 'legal_antitrust':
            record('legal_channel', True, support['evidence'], support['source_field'])
            e.evidence_fields['legal_channel']['assertion'] = 'affirmed'
        elif e.event_type == 'government_policy':
            for key in ('regulatory_change', 'regulatory_channel'):
                record(key, True, support['evidence'], support['source_field'])
                e.evidence_fields[key]['assertion'] = 'affirmed'

    if support.get('wording_family') == 'action_recall':
        key = ('export_restriction' if e.event_type == 'trade_export_control' else
               'price_change_explicit' if e.event_subtype == 'pricing_change' else None)
        if key and key not in e.evidence_fields:
            record(key, True, support['evidence'], support['source_field'])
            e.evidence_fields[key]['assertion'] = 'affirmed'
        if e.event_type == 'trade_export_control' and e.export_restriction is True:
            record('regulatory_channel', True, support['evidence'], support['source_field'])
            e.evidence_fields['regulatory_channel']['assertion'] = 'affirmed'

    for source, _, text in all_clauses:
        if HISTORICAL.search(text):
            continue
        for alias, ticker in COMPANY_ALIASES.items():
            # Case-sensitive names avoid treating apple fruit or generic meta as corporations.
            m = _search(alias, text, re.I if alias == 'NVIDIA' else 0)
            if m and assertion_status(text,m.start(),m.end())=='affirmed':
                snippet = text[max(0,m.start()-30):m.end()+70]
                for key, value in [('companies_mentioned', alias), ('tickers_mentioned', ticker)]:
                    current = getattr(e,key)
                    if value not in current:
                        record(key, current+[value], snippet, source)
        for ticker in MAG7:
            m = _search(ticker, text)
            if m and assertion_status(text,m.start(),m.end())=='affirmed' and ticker not in e.tickers_mentioned:
                record('tickers_mentioned', e.tickers_mentioned+[ticker], text[max(0,m.start()-30):m.end()+70], source)
        for key, terms in VOCABULARY.items():
            for term in terms:
                m = _search(term,text,re.I)
                if m and assertion_status(text,m.start(),m.end())=='affirmed' and term not in getattr(e,key):
                    if key == 'technologies_mentioned' and not technology_affirmed(text, m.start(), m.end()):
                        continue
                    record(key,getattr(e,key)+[term],text if key == 'technologies_mentioned' else text[max(0,m.start()-30):m.end()+70],source)
    return e.to_dict()
