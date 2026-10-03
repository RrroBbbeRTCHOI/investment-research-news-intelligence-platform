"""News-only vocabulary and transparent, uncalibrated heuristic weights."""

MAG7 = ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA')
COMPANY_ALIASES = {
    'Apple': 'AAPL', 'Microsoft': 'MSFT', 'Alphabet': 'GOOGL',
    'Google': 'GOOGL', 'Amazon': 'AMZN', 'AWS': 'AMZN', 'NVIDIA': 'NVDA',
    'Meta Platforms': 'META', 'Meta': 'META', 'Facebook': 'META', 'Tesla': 'TSLA',
}
COUNTRY_ALIASES = {
    'US': 'United States',
    'Taiwan': 'Taiwan', 'China': 'China', 'Hong Kong': 'Hong Kong',
    'United States': 'United States', 'U.S.': 'United States', 'USA': 'United States',
    'United Kingdom': 'United Kingdom', 'UK': 'United Kingdom',
    **{x: x for x in ('Canada', 'Mexico', 'Japan', 'South Korea', 'India',
       'Singapore', 'Malaysia', 'Vietnam', 'Thailand', 'Indonesia', 'Philippines',
       'Ireland', 'Netherlands', 'Germany', 'France', 'Italy', 'Spain',
       'Switzerland', 'Israel', 'Saudi Arabia', 'United Arab Emirates',
       'Australia', 'Brazil', 'Chile', 'South Africa', 'Ukraine', 'Russia', 'Iran')},
}
LOCATION_COUNTRIES = {'Shanghai': 'China', 'Texas': 'United States'}
LOCATION_KINDS = {'Shanghai': 'city', 'Texas': 'primary_region'}
INSTITUTION_COUNTRIES = {'Federal Reserve': 'United States'}
# Canonical relationship identities, not exposure edges or inferred customers.
ENTITY_ALIASES = {
    'AMZN': ('Amazon Web Services', 'AWS', 'Amazon', 'AMZN'),
    'MSFT': ('Microsoft', 'Azure', 'Microsoft 365', 'MSFT'),
    'GOOGL': ('Google Cloud', 'Google', 'Alphabet', 'GOOGL'),
    'META': ('Meta Platforms', 'Meta', 'Facebook', 'META'),
    'AAPL': ('Apple', 'AAPL'), 'NVDA': ('NVIDIA', 'NVDA'),
    'TSLA': ('Tesla', 'TSLA'), 'TSMC': ('TSMC', 'Taiwan Semiconductor Manufacturing', 'Taiwan Semiconductor Manufacturing Company'),
}
SERVICE_ALIASES = {
    'AWS': ('AWS', 'Amazon Web Services'),
    'Azure': ('Azure', 'Microsoft Azure'),
    'Google Cloud': ('Google Cloud',),
}
SERVICE_OWNERS = {'AWS':'AMZN', 'Azure':'MSFT', 'Google Cloud':'GOOGL'}
DEPENDENCY_ROLES = {'buyer', 'customer', 'input_dependency', 'dependent', 'procurement'}
PRODUCTION_EDGE_CHANNELS = {'manufacturing','advanced_semiconductors','advanced_packaging','memory_hbm'}
CHANNEL_FAMILIES = (
    'supply_chain', 'manufacturing', 'advanced_semiconductors', 'advanced_packaging',
    'memory_hbm', 'datacenter_infrastructure', 'electricity_grid', 'cloud_services',
    'digital_advertising', 'consumer_demand', 'ecommerce_demand', 'automotive',
    'battery_materials', 'logistics', 'energy', 'regulatory_export',
    'regulatory_general', 'interest_rates', 'foreign_exchange', 'commodity_inputs',
    'technology_demand', 'legal_antitrust', 'corporate_financing',
)
WEIGHTS = dict(direct_mention=0.15, edge_match=0.30, country_match=0.15,
               channel_match=0.15, evidence_quality=0.20, event_severity=0.05)
EVIDENCE_QUALITY = {'verified': 1.0, 'partial': 0.5}
HEURISTICS = dict(gate_accept=0.8, gate_reject=0.7, explicit_channel=0.75,
                  potential_channel=0.35, extraction=0.7, location=0.65)
