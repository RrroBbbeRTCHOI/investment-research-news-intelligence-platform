"""English V1: bounded event/action evidence, assertion and context checks.

Deliberately conservative; not general-language understanding. evaluate_gate and
extract_event can later be replaced independently without changing event_v1.
"""
import re
from .constants import HEURISTICS, COMPANY_ALIASES

# V1.2.2: bounded financial wording, sharing the existing event taxonomy.
EXPORT_OBJECT = r'(?:export[- ](?:(?:license|licensing)[- ])?(?:controls?|curbs?|restrictions?|rules?|requirements?)|export licensing requirements?|(?:additional |expanded )?licensing requirements?|(?:new )?export license rule|license requirement|restrictions on (?:advanced (?:AI )?chips|semiconductor exports))'
EXPORT_ACTION = r'(?:imposes?|imposed|announces?|announced|issued|updates?|updated|revises?|revised|expands?|expanded|tightens?|tightened|disclosed|introduced)'
EXPORT_WORDING = (
    EXPORT_ACTION + r'\b.{0,90}?\b' + EXPORT_OBJECT
    + r'|' + EXPORT_OBJECT + r'\b.{0,60}?\b' + EXPORT_ACTION
    + r'|\b(?:restricts?|restricted|curbs?|curbed)\s+(?:[\w-]+\s+){0,5}exports?\b'
)
PRODUCTION_REDUCTION = (
    r'\b(?:cuts?|reduces?|reduced|trims?|trimmed)\s+(?:(?:its|their|vehicle|factory|daily|weekly)\s+){0,3}(?:production|output)\b'
    r'|\b(?:production|output)\s+(?:cuts?|reductions?)\b'
    r'|\b(?:production|output)\s+(?:was|were|has been)\s+(?:cut|reduced|trimmed)\b'
)


def financial_wording_allowed(clause: str, kind: str) -> bool:
    """Require a reported action, not a forecast, proposal or generic discussion."""
    if re.search(r'\b(?:forecasts?|forecasted|expects?|expected|predicts?|predicted|'
                 r'propos\w*|plans?|planning|consider\w*|discuss\w*|commentary|'
                 r'outlook|should|urges?|recommends?)\b', clause, re.I):
        return False
    if kind == 'export':
        # Domestic licensing alone is not an export restriction.
        return bool(re.search(r'\bexports?\b|\bcross-border\b', clause, re.I))
    return (bool(re.search(r'\b(?:factory|factories|plant|manufacturer|manufacturing|'
                          r'Gigafactory|company|automaker|supplier|TSMC)\b', clause, re.I))
            or any(re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', clause,
                             re.I if name == 'NVIDIA' else 0) for name in COMPANY_ALIASES))

# Digital service incidents, including reports of recovery from the same incident.
SERVICE_OUTAGE = (
    r'\b(?:global service|services?|technical|platform|cloud|network|IT|Office 365) (?:outage|disruption)\b'
    r'|\b(?:services?|systems?|platform) (?:were |was |are |is )?(?:unavailable|went down|down)\b'
    r'|\b(?:back up|services? restored|operations restored) after (?:a |the )?(?:global )?(?:outage|disruption)\b'
    r'|\bservices? (?:was |were )?restored\b'
    r'|\b(?:services|Azure-backed workloads) (?:were |are )?(?:disrupted|unavailable)\b'
)
DIGITAL_CONTEXT = r'\b(?:cloud|network|platform|technical|online|digital|IT|Office 365|Google|Microsoft|Azure|AWS|Meta|Facebook|Instagram)\b'


def service_context_allowed(clause):
    return not re.search(r'\b(?:analysts?|discuss\w*|risk|future|resilience|example|forecast\w*|plans?|should|could|might|may|would|hypothetical)\b', clause, re.I)


def service_outage_matches(clause):
    if not re.search(DIGITAL_CONTEXT, clause, re.I) or not service_context_allowed(clause):
        return []
    return [m for m in re.finditer(SERVICE_OUTAGE, clause, re.I)
            if assertion_status(clause, m.start(), m.end()) == 'affirmed']

# Lifecycle actions are events in their own right, not findings of liability.
AUTHORITY = (r'European Commission|Federal Trade Commission|FTC|Justice Department|'
             r'Department of Justice|DOJ|prosecutors?|court|judge|regulators?|'
             r'Competition and Markets Authority|Data Protection Commission|NHTSA|'
             r'EU regulatory|EU competition')
LIFECYCLE_RULES = (
 ('legal_antitrust', 'lawsuit', r'\b(?:files?|filed) (?:an? |the )?(?:antitrust )?lawsuit\b|\blawsuit (?:was |has been )?filed\b|\b(?:sues?|sued)\b'),
 ('legal_antitrust', 'complaint', r'\b(?:files?|filed) (?:an? |the )?(?:antitrust |formal )?complaint\b|\b(?:antitrust |formal )?complaint (?:was |has been )?filed\b'),
 ('legal_antitrust', 'charge', r'\b(?:charges?|charged)\b.{0,65}\b(?:antitrust|violations?|bundling)\b|\b(?:brings?|brought|filed) formal charges\b'),
 ('legal_antitrust', 'investigation', r'\b(?:opened|opens?|launched|launches?|began) (?:an? |the )?(?:formal |regulatory |competition )?(?:investigation|probe|review)\b|\bfaces formal (?:EU )?(?:regulatory )?scrutiny\b|\b(?:formally (?:examines?|examining|reviews?|reviewing)|opened a formal competition review)\b'),
 ('legal_antitrust', 'regulatory_scrutiny', r'\bsaid it would (?:analyze|review|examine)\b.{0,150}\b(?:deal|transaction|partnership|investment)\b'),
 ('legal_antitrust', 'remedy_proposal', r'\b(?:propose[sd]?|proposed)\b.{0,80}\b(?:remedies|divest\w*|sell|commitments)\b|\basked (?:a |the )?(?:federal )?(?:judge|court) to require\b'),
 ('legal_antitrust', 'ruling', r'\b(?:judge|court) ruled\b|\bordered to divest\b|\bissued (?:a )?binding compliance order\b'),
 ('legal_antitrust', 'fine', r'\b(?:fined|penalized)\b|\bimposed\b.{0,60}\b(?:fine|penalty)\b'),
 ('legal_antitrust', 'settlement', r'\bsettled\b.{0,60}\b(?:lawsuit|case|charges|litigation)\b|\bagreed to (?:legally binding )?commitments\b'),
 ('legal_antitrust', 'regulatory_scrutiny', r'\bprovisionally (?:accepted|rejected)\b.{0,40}\bcommitments\b'),
 ('corporate_transaction', 'acquisition_terminated', r'\b(?:terminate[sd]?|terminated|abandoned|withdrew)\b.{0,35}\b(?:acquisition|merger|transaction|deal)\b|\b(?:acquisition|merger|transaction|deal) (?:was |is |has been )?(?:terminated|abandoned|withdrawn)\b'),
 ('corporate_action', 'recall', r'\brecalls?\s+(?:(?:over|more than|nearly|about)\s+)?(?:\d[\d,.]*|two|three|four|five)\b.{0,40}\b(?:vehicles?|products?|devices?|units?|cars?)\b|\b(?:announced|announces?|initiated|orders?|ordered) (?:an? |the )?(?:safety )?recall\b|\brecall (?:was )?initiated\b|\brecalled\b.{0,50}\b(?:vehicles?|products?|devices?|cars?)\b'),
 ('corporate_action', 'workforce_reduction', r'\b(?:cuts?|reduced)\s+(?:(?:more than|over|about)\s+)?\d+(?:\.\d+)?%\s+of\s+(?:its |the )?(?:workforce|employees)\b|\b(?:lays?|laid) off (?:employees|workers|staff)\b|\b(?:began|announced|announces?|implemented) (?:global )?(?:layoffs|job cuts|workforce reductions?)\b'),
 ('government_policy', 'regulation', r'\b(?:restrict\w*|bans?|barred|prohibited)\b.{0,60}\b(?:use|using)\b|\b(?:widened|expanded)\b.{0,35}\b(?:restrictions|curbs)\b.{0,40}\buse\b|\bproduct use (?:was )?prohibited\b'),
)


# A legal topic near an unrelated verb is not an asserted ruling. Keep this
# check local to ruling evidence; analysis elsewhere must not veto real news.
RULING_ACTION = re.compile(
    r'\b(?:court|judge|regulator|authority)\s+'
    r'(?:(?:has|have)\s+)?(?:just\s+)?'
    r'(?:rules?|ruled|orders?|ordered|blocks?|blocked|dismisses|dismissed|upholds?|upheld|'
    r'issues?|issued|imposes?|imposed)\b'
    r'|\b(?:formal ruling|binding compliance order)\s+(?:was |has been )?issued\b'
    r'|\bissued (?:a )?binding compliance order\b|\bordered to divest\b', re.I)


def ruling_action_matches(clause):
    """Require connected legal action, excluding locally embedded background."""
    for match in RULING_ACTION.finditer(clause):
        prefix = clause[:match.start()]
        if re.search(r'\b(?:issues?|issued|imposes?|imposed)$', match.group(), re.I) and not re.search(
                r'\b(?:ruling|judgment|judgement|order|injunction|penalty|fine|sanction|remedy|remedies)\b',
                clause[match.start():match.end() + 80], re.I):
            continue
        # Relative descriptions (e.g. signage where a court ordered removal)
        # describe a setting, not a newly reported legal action.
        if re.search(r'\b(?:where|which|who)\s+(?:(?:a|the|federal|appeals|supreme)\s+)*$', prefix, re.I):
            continue
        if re.search(r'\b(?:revisits?|recalls?|looking back|history of|discussion of|'
                     r'commentary on|what if|whether|previously|earlier)\b', prefix, re.I):
            continue
        if re.search(r'\bwhat\b.*$', prefix, re.I) and re.search(r'\bmeans?\b', clause, re.I):
            continue
        if assertion_status(clause, match.start(), match.end()) == 'affirmed':
            yield match


def lifecycle_matches(clause):
    for kind, subtype, pattern in LIFECYCLE_RULES:
        authority = bool(re.search(AUTHORITY, clause, re.I))
        if kind == 'legal_antitrust':
            if not authority and not re.search(r'\b(?:lawsuit|antitrust|litigation|formal charges)\b', clause, re.I):
                continue
            if subtype in ('investigation', 'regulatory_scrutiny', 'remedy_proposal') and not authority:
                continue
        if kind == 'government_policy' and not re.search(r'\b(?:government|ministries|state employees|government departments|government agency)\b', clause, re.I):
            continue
        if subtype == 'ruling' and not any(ruling_action_matches(clause)):
            continue
        for match in re.finditer(pattern, clause, re.I):
            claim = clause[:match.end()]
            # An authority's reported commitment to review is the event; this
            # does not assert that a formal investigation or ruling occurred.
            if subtype == 'regulatory_scrutiny' and authority:
                claim = re.sub(r'said it would (?=analyze|review|examine)', 'announced review: ', claim, flags=re.I)
            if re.search(r'\b(?:analysts?|rumou?rs?|speculat\w*|expects?|expected|forecasts?|possible|potential|considering|might|could|may|would|will|plans?|planning)\b', claim, re.I):
                continue
            if assertion_status(claim, 0, len(claim)) != 'affirmed':
                continue
            # Trailing negation belongs to the action, not merely its object.
            if assertion_status(clause, match.start(), match.end()) != 'affirmed' and not (
                    subtype == 'regulatory_scrutiny' and 'said it would' in clause.lower()):
                continue
            yield kind, subtype, match

# Additional action forms: require an observed action, not a topic mention.
RECALL_AUTHORITY = AUTHORITY + r'|Competition Commission|Competition Board|competition authority|antitrust authority'
ACTION_RECALL_RULES = (
 ('legal_antitrust', 'investigation', r'\b(?:opens?|opened|launches?|launched|began) (?:an? |the )?(?:formal )?(?:DMA |non-compliance |competition |Section 6\(b\) )?(?:investigation|inquiry|probe)\b|\b(?:issued|issuing) compulsory (?:information requests|orders)\b|\bcompetition investigation (?:was )?opened\b'),
 ('government_policy', 'regulation', r'\bdesignated\b.{0,100}\bgatekeeper\b|\bissued (?:a )?(?:formal |regulatory )?designation\b'),
 ('legal_antitrust', 'investigation_finding', r'\b(?:investigations? unit|competition investigation|antitrust probe)\b.{0,30}\b(?:found|finds|concluded)\b'),
 ('legal_antitrust', 'charge', r'\b(?:issues?|issued|sent|sends)\b.{0,45}\b(?:statement of objections|formal objections|preliminary findings|formal compliance finding)\b'),
 ('legal_antitrust', 'fine', r'\b(?:fines?|penalty|penalties) (?:was |were )?imposed\b|\bimposed fines\b|\bfined\b|\b(?:' + RECALL_AUTHORITY + r')\s+fines\s+\w+'),
 ('legal_antitrust', 'settlement', r'\b(?:agrees?|agreed) to (?:pay\b.{0,65}?\bto )?settle\b.{0,65}\blawsuit\b|\b(?:regulatory )?settlement (?:was )?announced\b'),
 ('corporate_action', 'workforce_reduction', r'\b(?:lays?|laid) off\b.{0,40}\b(?:employees|staff|workers)\b|\beliminated\b.{0,40}\broles\b|\b(?:cuts?|cut) staff\b|\breduced headcount\b'),
 ('trade_export_control', 'export_controls', r'\b(?:requires?|required|imposed)\b.{0,35}\b(?:export licenses?|licenses? for exports|(?:indefinite )?licensing requirements?|license requirements?)\b|\b(?:export )?licenses? (?:was |were |is |are )?required for exports\b|\bexports (?:were |are )?restricted\b|\bsales require (?:an? )?export license\b'),
 ('corporate_action', 'pricing_change', r'\b(?:cuts?|cut|reduces?|reduced|raises?|raised)\s+(?:(?:vehicle|product|retail|subscription)\s+)?prices\b|\b(?:implemented|announced) (?:an? )?price (?:increase|reduction)\b|\bdiscounted products\b'),
 ('supply_chain', 'production_constraint', r'\bdesign flaw\b.{0,40}\bcaused low (?:production )?yields\b|\bproduction yields fell\b|\bmanufacturing (?:issue|problem|bottleneck)\b.{0,45}\bdelayed shipments\b|\byield (?:issue|problem) (?:has been |was )?(?:fixed|resolved)\b'),
)


def action_recall_matches(clause):
    authority = bool(re.search(RECALL_AUTHORITY, clause, re.I))
    company = any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)', clause,
                           re.I if name == 'NVIDIA' else 0) for name in COMPANY_ALIASES)
    for kind, subtype, pattern in ACTION_RECALL_RULES:
        if kind == 'legal_antitrust' and not authority and not (
                subtype == 'settlement' and re.search(r'\blawsuit\b', clause, re.I)):
            continue
        if kind == 'government_policy' and not re.search(r'\b(?:DMA|Digital Markets Act|regulator|government)\b',clause,re.I):
            continue
        if kind == 'trade_export_control' and not re.search(r'\bexports?\b', clause, re.I):
            continue
        if kind == 'corporate_action' and not company:
            continue
        if subtype == 'pricing_change' and re.search(r'\b(?:price targets?|share prices?|stock prices?|market prices?)\b',clause,re.I):
            continue
        for match in re.finditer(pattern,clause,re.I):
            claim = clause[:match.end()]
            if re.search(r'\b(?:analysts?|expects?|expected|forecasts?|possible|potential|considering|plans?|planning|rumou?rs?|speculat\w*)\b',claim,re.I):
                continue
            if assertion_status(clause,match.start(),match.end()) != 'affirmed':
                continue
            # A trailing modal often describes a hypothetical action, whereas
            # "could lead to penalties" after an opened probe is a consequence.
            if re.match(r'\s+(?:may|might|could|would|will)\s+(?:occur|happen|be announced)\b',clause[match.end():],re.I):
                continue
            yield kind, subtype, match

# Each rule needs both a specific event object and an asserted action in one clause.
RULES = (
 ('natural_disaster', 'earthquake', r'earthquake|quake', r'struck|strikes?|hit|occurred|shook|rocks?|was reported'),
 ('natural_disaster', 'typhoon', r'typhoon|hurricane|cyclone', r'hit|struck|made landfall|shut|damaged'),
 ('natural_disaster', 'flood', r'flood(?:s|ing)?', r'hit|struck|inundated|damaged|forced|submerged'),
 ('geopolitical_conflict', 'conflict', r'ceasefire|missile|military attack|war|airstrike|troops|army|invasion', r'agreed|signed|launched|attacked|escalated|began|struck'),
 ('trade_export_control', 'export_controls', r'export controls?|export ban|export restrictions?', r'imposes?|imposed|announces?|announced|enacted|tightens?|tightened|lifted|issued'),
 ('trade_export_control', 'tariffs', r'tariffs?|sanctions|import ban', r'imposed|announced|enacted|raised|lifted|signed'),
 ('macro_monetary', 'rate_cut', r'interest rates?|policy rate|benchmark rate', r'cuts?|reduced|reduces?|lowered|lowers?|reduction'),
 ('macro_monetary', 'rate_decision', r'interest rates?|policy rate|benchmark rate', r'raised|raises?|held|holds?|kept|increased'),
 ('government_policy', 'regulation', r'regulations?|legislation|rules?|requirements?|law', r'enacted|signed|passed|issued|adopted|introduces?|introduced|announces?|announced'),
 ('energy_commodity', 'supply_decision', r'oil output|oil production|gas supply|OPEC', r'cut|halted|raised|reduced|announced|increased'),
 ('supply_chain', 'factory_shutdown', r'factory|plant|production line', r'shut down|shutdown|halts?|halted|closed|suspended'),
 ('supply_chain', 'production_halt', r'production', r'halts?|halted|suspended|stopped|outage'),
 ('supply_chain', 'production_interruption', r'production|operations?', r'interrupted|interrupts?'),
 ('supply_chain', 'production_interruption', r'production interruption|operational interruption', r'reports?|reported|confirmed|announced|caused'),
 ('supply_chain', 'port_disruption', r'ports?|harbou?rs?|terminals?', r'suspended|closed|halted|disrupted|disruption|blocked|closure|delays?|delayed'),
 ('supply_chain', 'transport_disruption', r'transport|logistics|shipping|rail services|freight', r'suspended|closed|halted|disrupted|blocked|delays'),
 ('infrastructure_outage', 'outage', r'power|electricity|grid|cloud|datacenter|data center|network|AWS|Azure', r'outage|went down|failed|lost power|loses? power|disrupted'),
 ('cybersecurity', 'cyberattack', r'cyberattack|ransomware|data breach', r'hit|suffered|reported|disclosed|confirmed|detected'),
 ('labor_disruption', 'strike', r'workers|union|employees', r'went on strike|began a strike|walked out|launched a strike'),
 ('corporate_earnings', 'earnings_release', r'earnings|quarterly results|annual results|quarterly revenue', r'reported|released|posted|announced'),
 ('corporate_financing', 'financing', r'funding|financing|bond offering|capital|debt offering', r'raised|secured|issued|completed|announced'),
 ('product_technology', 'product_launch', r'chips?|processors?|software|devices?|satellite|spacecraft|rocket|(?:AI|artificial intelligence) models?', r'launches?|launched|unveils?|unveiled|releases?|released|deployed|successfully tested|announces?|announced|introduces?|introduced'),
 ('product_technology', 'capacity_expansion', r'(?:cloud|Azure|datacenter|data.center).{0,30}(?:capacity|expansion)|capacity.{0,30}(?:cloud|Azure|datacenter)', r'expands?|expanded|added|adds?|increased|announces?|announced'),
 ('supply_chain', 'distribution_center_opening', r'(?:retail )?distribution cent(?:er|re)|fulfil(?:l)?ment cent(?:er|re)|retail warehouse', r'opens?|opened|inaugurates?|inaugurated'),
 ('legal_antitrust', 'ruling', r'antitrust|court|judge|regulator|authority|formal ruling', r'rules?|ruled|fined|blocks?|blocked|orders?|ordered|dismisses|dismissed|upholds?|upheld|issued|imposed|sued'),
 ('management_governance', 'executive_departure', r'CEO|chief executive|CFO|chief financial officer', r'resigned|stepped down|was dismissed|departed'),
 ('corporate_transaction', 'acquisition', r'acquisition|merger|acquire|acquired|buyout', r'announced|agreed|completed|signed|approved|acquired'),
 # Keep established rules first so existing classifications retain precedence.
 # Operational nouns and disruption actions must share an affirmed clause;
 # a company name or an announcement alone cannot satisfy this rule.
 ('supply_chain', 'production_interruption',
  r'production|manufacturing|(?:wafer )?fabrication|(?:advanced )?packaging|CoWoS|capacity|assembly|shipments?|operations?|operational',
  r'interruptions?|interrupted|interrupts?|disruptions?|disrupted|disrupts?|halts?|halted|suspensions?|suspended|stopped'),
)
NONASSERTED = re.compile(r'\b(?:if|could|might|may|would|will|likely|potential|hypothetical|scenario|simulation|drill|rumou?r|denied|not|never|no evidence|didn.t)\b', re.I)
HISTORICAL = re.compile(r'\b(?:years? ago|last year|anniversary|historically|looking back|in retrospect)\b', re.I)
OFF_TOPIC = re.compile(r'\b(?:football|soccer|field hockey|NFL|album|band|nutrition|vitamins|collagen|Prince Harry|Taylor Swift|Tom Cruise)\b', re.I)

def assertion_status(text: str, start: int, end: int) -> str:
    """Scope a matched claim within a clause; absence of reports is not absence of harm.

    Negation propagates through coordinated lists until a contrast/sentence boundary.
    A later independent negative condition cannot negate an earlier positive event.
    """
    prefix=text[:end].replace('’',"'")
    suffix=text[end:]
    if re.search(r'\b(?:if|could|might|may|would|will|likely|potential|hypothetical|scenario|simulation|drill|rumou?r)\b',prefix,re.I):
        return 'hypothetical'
    if re.search(r'\b(?:no (?:reports?|evidence|confirmation) (?:of|that)|(?:does|did|do) not (?:mention|describe|involve|confirm)|unrelated to|denied|unconfirmed)\b',prefix,re.I):
        return 'unknown'
    if re.search(r"\b(?:no(?!\.)|not(?! only\b)|without|never|didn't|doesn't|wasn't|weren't|unaffected|undamaged)\b",prefix,re.I):
        return 'negated'
    if re.match(r'\s+(?:(?:was|were|is|are|did|does|has|have)\s+not\b|(?:was |were |remained )?unaffected\b|remained operational\b)',suffix,re.I):
        return 'negated'
    return 'affirmed'

def _contrast_clauses(text: str, offset: int):
    start=0
    for boundary in re.finditer(r'\b(?:but|however|whereas|while)\b|,\s*unlike\b',text,re.I):
        value=text[start:boundary.start()].strip()
        if value:
            yield offset+start,value
        start=boundary.end()
    if text[start:].strip():
        yield offset+start,text[start:].strip()

def text_parts(article: dict) -> list[tuple[str, str]]:
    return [(k, str(article[k])) for k in ('headline', 'summary', 'body') if article.get(k)]

def clauses(article: dict):
    for field, text in text_parts(article):
        protected = set()
        for abbreviation in re.finditer(r'\b(?:[A-Za-z]\.){2,}',text):
            protected.update(range(abbreviation.start(),abbreviation.end()))
        start = 0
        for boundary in re.finditer(r'[.!?;\n]',text):
            index = boundary.start()
            decimal = (text[index]=='.' and index>0 and index+1<len(text)
                       and text[index-1].isdigit() and text[index+1].isdigit())
            if decimal or index in protected:
                continue
            clause=text[start:boundary.end()].strip()
            if clause:
                for offset,value in _contrast_clauses(clause,start):
                    yield field,offset,value
            start=boundary.end()
        if text[start:].strip():
            for offset,value in _contrast_clauses(text[start:].strip(),start):
                yield field,offset,value

def event_evidence(article: dict) -> dict | None:
    headline = str(article.get('headline') or '')
    # Business actions must be explicit even when the article's surrounding genre is nonbusiness.
    genre = bool(OFF_TOPIC.search(headline))
    published_year = str(article.get('published_at') or '')[:4]
    supported = []
    for source, offset, clause in clauses(article):
        if HISTORICAL.search(clause) or re.search(r'\b(?:guide to|what is|educational overview|history of)\b',clause,re.I):
            continue
        years = re.findall(r'\b(?:19|20)\d{2}\b', clause)
        if years and published_year.isdigit() and max(map(int, years)) < int(published_year):
            continue
        if not genre:
            for kind, subtype, match in lifecycle_matches(clause):
                supported.append((-1, dict(event_type=kind, event_subtype=subtype,
                    evidence=clause[:240], clause=clause, source_field=source,
                    clause_offset=offset, wording_family='lifecycle')))
        if not genre:
            for kind, subtype, match in action_recall_matches(clause):
                supported.append((len(RULES) + 1 if kind == 'trade_export_control' else 0, dict(event_type=kind, event_subtype=subtype,
                    evidence=clause[:240], clause=clause, source_field=source,
                    clause_offset=offset, wording_family='action_recall')))
        for rank, (event_type, subtype, obj, action) in enumerate(RULES):
            objects = list(re.finditer(r'\b(?:'+obj+r')\b', clause, re.I))
            actions = list(re.finditer(r'\b(?:'+action+r')\b', clause, re.I))
            pair = next(((a, b) for a in objects for b in actions if abs(a.start()-b.start()) <= 110
                         and assertion_status(clause,min(a.start(),b.start()),max(a.end(),b.end()))=='affirmed'), None)
            if pair and subtype == 'ruling' and not any(ruling_action_matches(clause)):
                pair = None
            if (pair and event_type == 'infrastructure_outage'
                    and re.fullmatch(r'cloud|network|AWS|Azure', pair[0].group(), re.I)
                    and not service_context_allowed(clause)):
                pair = None
            if pair and (not genre or event_type in ('corporate_transaction', 'corporate_earnings', 'corporate_financing')):
                start = max(0, min(x.start() for x in pair)-35)
                end = min(len(clause), max(x.end() for x in pair)+80)
                supported.append((rank, dict(event_type=event_type, event_subtype=subtype, evidence=clause[start:end][:240],
                            clause=clause, source_field=source, clause_offset=offset)))
        if not genre:
            for match in service_outage_matches(clause):
                supported.append((len(RULES), dict(event_type='infrastructure_outage',
                    event_subtype='outage', evidence=clause[:240], clause=clause,
                    source_field=source, clause_offset=offset, wording_family='service_outage')))
        # Additional wording does not reorder established rules. Export controls
        # still outrank generic government-policy consequences below.
        for kind, pattern, event_type, subtype in (
                ('export', EXPORT_WORDING, 'trade_export_control', 'export_controls'),
                ('production', PRODUCTION_REDUCTION, 'supply_chain', 'production_interruption')):
            if genre or not financial_wording_allowed(clause, kind):
                continue
            match = next((m for m in re.finditer(pattern, clause, re.I)
                          if assertion_status(clause, m.start(), m.end()) == 'affirmed'), None)
            if match:
                start, end = max(0, match.start()-35), min(len(clause), match.end()+80)
                supported.append((len(RULES), dict(event_type=event_type, event_subtype=subtype,
                    evidence=clause[start:end][:240], clause=clause,
                    source_field=source, clause_offset=offset, wording_family=kind)))
    # Root causes across the article outrank earlier consequence sentences.
    # An infrastructure outage outranks a generic transport consequence, but not a disaster/policy cause.
    def priority(item):
        rank, item = item
        category = {'natural_disaster': 0, 'trade_export_control': 1, 'macro_monetary': 2,
                    'infrastructure_outage': 3}.get(item['event_type'], 4)
        # A tied full-body assertion usually names the operator/place omitted by a short headline.
        return category, rank, {'body':0,'summary':1,'headline':2}[item['source_field']]
    return min(supported,key=priority)[1] if supported else None

def evaluate_gate(article: dict) -> dict:
    evidence = event_evidence(article)
    if evidence:
        reason = f"Asserted {evidence['event_subtype']} event: {evidence['evidence']}"
    else:
        reason = 'Opinion/commentary or other content without a supported discrete current market-relevant event.'
    return dict(article_id=article.get('article_id'), is_event=evidence is not None,
                gate_reason=reason, gate_confidence=HEURISTICS['gate_accept' if evidence else 'gate_reject'])
