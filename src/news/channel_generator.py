"""Potential channels are hypotheses; never write them back into Event facts."""
from .constants import CHANNEL_FAMILIES, HEURISTICS
import re
from .event_gate import assertion_status
from .event_extractor import FAB_TECHNOLOGIES, PACKAGING_TECHNOLOGIES, technology_affirmed

FLAG_CHANNELS = {
 'production_disruption': 'manufacturing', 'capacity_disruption': 'manufacturing',
 'logistics_disruption': 'logistics', 'port_disruption': 'logistics',
 'power_disruption': 'electricity_grid', 'network_disruption': 'datacenter_infrastructure',
 'cloud_service_disruption': 'cloud_services', 'supply_shortage': 'supply_chain',
 'export_restriction': 'regulatory_export', 'import_restriction': 'regulatory_export',
 'regulatory_change': 'regulatory_general',
 'supply_channel': 'supply_chain', 'demand_channel': 'consumer_demand',
 'financing_channel': 'corporate_financing', 'interest_rate_channel': 'interest_rates',
 'fx_channel': 'foreign_exchange', 'commodity_channel': 'commodity_inputs',
 'logistics_channel': 'logistics', 'energy_channel': 'energy',
 'regulatory_channel': 'regulatory_general', 'legal_channel': 'legal_antitrust',
 'technology_channel': 'technology_demand',
}
DOMAIN_CHANNELS = {
 'advanced semiconductors':'advanced_semiconductors', 'advanced semiconductor chips':'advanced_semiconductors', 'HBM':'memory_hbm',
 'advanced packaging':'advanced_packaging', 'Azure':'cloud_services', 'AWS':'cloud_services',
 'automotive':'automotive', 'vehicle':'automotive', 'vehicles':'automotive',
 'lithium':'battery_materials', 'nickel':'battery_materials',
 'semiconductors':'supply_chain',
}

DOMAIN_CHANNELS.update(dict.fromkeys(FAB_TECHNOLOGIES, 'advanced_semiconductors'))
DOMAIN_CHANNELS.update(dict.fromkeys(PACKAGING_TECHNOLOGIES, 'advanced_packaging'))

def generate_channels(event: dict) -> dict:
    channels = {}
    evidence=event.get('evidence_fields',{})
    def positive_flag(key):
        return event.get(key) is True and evidence.get(key,{}).get('assertion','affirmed')=='affirmed'
    def positive_term(text,term):
        return any(assertion_status(text,m.start(),m.end())=='affirmed'
                   for m in re.finditer(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text,re.I))
    def supported_term(field,term):
        record=evidence.get(field,{})
        return any(
            (any(technology_affirmed(s.get('evidence',''), m.start(), m.end())
                 for m in re.finditer(r'(?<!\w)'+re.escape(term)+r'(?!\w)', s.get('evidence',''), re.I))
             if field == 'technologies_mentioned' else positive_term(s.get('evidence',''),term))
            for s in record.get('supporting_snippets',[])+[record])
    def add(family, basis, explicit=True):
        assert family in CHANNEL_FAMILIES
        item = channels.setdefault(family, dict(channel_family=family, channel_subtype='unspecified',
            confidence=HEURISTICS['explicit_channel' if explicit else 'potential_channel'],
            basis=[], status='candidate'))
        item['basis'] = sorted(set(item['basis']+basis))
    for key, family in FLAG_CHANNELS.items():
        if positive_flag(key):
            add(family,[key])
    if event.get('event_type') == 'trade_export_control':
        add('regulatory_export',['event_type','event_subtype'])
    if positive_flag('cloud_service_disruption'):
        # Cloud service dependencies may be represented as operating infrastructure edges.
        # The matcher must still require service/relationship compatibility before scoring.
        add('datacenter_infrastructure',['cloud_service_disruption'],False)
    negative_disruption = any(event.get(k) is False or evidence.get(k,{}).get('assertion') in ('negated','unknown','conflicting')
        for k in ('production_disruption','capacity_disruption','logistics_disruption','port_disruption',
                  'power_disruption','network_disruption','cloud_service_disruption'))
    if (event.get('event_type') in ('natural_disaster','geopolitical_conflict')
            and event.get('affected_countries') and not negative_disruption):
        # A general disruption hypothesis, not a claim that a factory or named company was hit.
        add('supply_chain',['event_type','affected_countries'],False)
    for field in ('technologies_mentioned','industries_mentioned','products_mentioned','commodities_mentioned'):
        for term in event.get(field,[]):
            if term in DOMAIN_CHANNELS and supported_term(field,term):
                if (negative_disruption and event.get('event_type') in ('natural_disaster','geopolitical_conflict')
                        and DOMAIN_CHANNELS[term] in ('supply_chain','manufacturing','advanced_semiconductors',
                                                      'advanced_packaging','memory_hbm')):
                    continue
                add(DOMAIN_CHANNELS[term],[field,'event_type'],False)
    # Remaining families require explicit topic evidence, not a country-level prior.
    summary = (event.get('event_summary') or '').lower()
    for term,family in [('data center','datacenter_infrastructure'),('data centers','datacenter_infrastructure'),
                        ('datacenter','datacenter_infrastructure'),('datacenters','datacenter_infrastructure'),
                        ('advertising','digital_advertising'),('ecommerce','ecommerce_demand')]:
        if positive_term(summary,term):
            add(family,['event_summary'],False)
    if event.get('event_subtype')=='capacity_expansion' and positive_flag('technology_channel'):
        if any(positive_term(summary,t) for t in ('cloud','Azure','datacenter','data center')):
            add('datacenter_infrastructure',['event_type','event_subtype','technology_channel'],False)
    return dict(event_id=event['event_id'], candidate_channels=list(channels.values()))
