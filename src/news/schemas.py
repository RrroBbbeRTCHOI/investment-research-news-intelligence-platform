"""Frozen event_v1 field contract. Unknown factual values remain None."""
from dataclasses import asdict, dataclass, field
from typing import Any

EVENT_TYPES = ('natural_disaster', 'geopolitical_conflict', 'government_policy',
 'trade_export_control', 'macro_monetary', 'energy_commodity', 'supply_chain',
 'infrastructure_outage', 'cybersecurity', 'labor_disruption', 'corporate_earnings',
 'corporate_financing', 'product_technology', 'legal_antitrust',
 'management_governance', 'corporate_transaction', 'corporate_action')
FACT_FLAGS = ('physical_damage production_disruption capacity_disruption '
 'logistics_disruption port_disruption power_disruption network_disruption '
 'cloud_service_disruption labor_disruption supply_shortage regulatory_change '
 'export_restriction import_restriction price_change_explicit demand_change_explicit').split()
ARTICLE_CHANNELS = ('supply_channel demand_channel cost_channel revenue_channel '
 'margin_channel capex_channel financing_channel interest_rate_channel fx_channel '
 'commodity_channel logistics_channel energy_channel regulatory_channel legal_channel '
 'technology_channel competition_channel').split()
ENTITY_FIELDS = ('companies_mentioned tickers_mentioned suppliers_mentioned '
 'customers_mentioned industries_mentioned products_mentioned technologies_mentioned '
 'commodities_mentioned government_entities regulators people_mentioned').split()

@dataclass
class Event:
    event_id: str
    canonical_event_id: str
    article_ids: list[str]
    source_count: int = 1
    independent_source_count: int = 1
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    published_at_first: str | None = None
    event_start_at: str | None = None
    event_end_at: str | None = None
    time_precision: str = 'unknown'
    event_status: str = 'developing'
    primary_country: str | None = None
    affected_countries: list[str] = field(default_factory=list)
    primary_region: str | None = None
    affected_regions: list[str] = field(default_factory=list)
    city: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_confidence: float | None = None
    event_type: str | None = None
    event_subtype: str | None = None
    severity_score: float | None = None
    severity_confidence: float | None = None
    scope: str | None = None
    duration_class: str = 'unknown'
    event_novelty: str | None = None
    physical_damage: bool | None = None
    production_disruption: bool | None = None
    capacity_disruption: bool | None = None
    logistics_disruption: bool | None = None
    port_disruption: bool | None = None
    power_disruption: bool | None = None
    network_disruption: bool | None = None
    cloud_service_disruption: bool | None = None
    labor_disruption: bool | None = None
    supply_shortage: bool | None = None
    regulatory_change: bool | None = None
    export_restriction: bool | None = None
    import_restriction: bool | None = None
    price_change_explicit: bool | None = None
    demand_change_explicit: bool | None = None
    companies_mentioned: list[str] = field(default_factory=list)
    tickers_mentioned: list[str] = field(default_factory=list)
    suppliers_mentioned: list[str] = field(default_factory=list)
    customers_mentioned: list[str] = field(default_factory=list)
    industries_mentioned: list[str] = field(default_factory=list)
    products_mentioned: list[str] = field(default_factory=list)
    technologies_mentioned: list[str] = field(default_factory=list)
    commodities_mentioned: list[str] = field(default_factory=list)
    government_entities: list[str] = field(default_factory=list)
    regulators: list[str] = field(default_factory=list)
    people_mentioned: list[str] = field(default_factory=list)
    supply_channel: bool | None = None
    demand_channel: bool | None = None
    cost_channel: bool | None = None
    revenue_channel: bool | None = None
    margin_channel: bool | None = None
    capex_channel: bool | None = None
    financing_channel: bool | None = None
    interest_rate_channel: bool | None = None
    fx_channel: bool | None = None
    commodity_channel: bool | None = None
    logistics_channel: bool | None = None
    energy_channel: bool | None = None
    regulatory_channel: bool | None = None
    legal_channel: bool | None = None
    technology_channel: bool | None = None
    competition_channel: bool | None = None
    source_quality: str | None = None
    extraction_confidence: float | None = None
    confirmation_level: str = 'single_source'
    evidence_fields: dict[str, Any] = field(default_factory=dict)
    canonical_headline: str | None = None
    event_summary: str | None = None
    keywords: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    schema_version: str = 'event_v1'

    def to_dict(self) -> dict:
        result = asdict(self)
        validate_event(result)
        return result

def validate_event(event: dict) -> None:
    if set(event) != set(Event.__dataclass_fields__):
        raise ValueError('Event must contain exactly the frozen event_v1 fields')
    enums = {'event_type': EVENT_TYPES, 'time_precision': ('exact', 'approximate', 'date_only', 'unknown'),
             'event_status': ('breaking', 'developing', 'confirmed', 'resolved', 'retracted'),
             'scope': (None, 'local', 'national', 'regional', 'global'),
             'duration_class': ('hours', 'days', 'weeks', 'months', 'structural', 'unknown'),
             'confirmation_level': ('single_source', 'multi_source', 'officially_confirmed', 'disputed', 'unverified'),
             'schema_version': ('event_v1',)}
    for key, allowed in enums.items():
        if event[key] not in allowed:
            raise ValueError(f'Invalid {key}: {event[key]!r}')
    for key in FACT_FLAGS + ARTICLE_CHANNELS:
        if event[key] is not None and type(event[key]) is not bool:
            raise ValueError(f'{key} must be true, false or null')
    for key in ('severity_score', 'severity_confidence', 'extraction_confidence', 'location_confidence'):
        value = event[key]
        if value is not None and (type(value) not in (int, float) or not 0 <= value <= 1):
            raise ValueError(f'{key} must be null or between 0 and 1')
