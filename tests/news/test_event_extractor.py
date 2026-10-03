import hashlib
import unittest
from src.news.constants import COMPANY_ALIASES
from src.news.event_extractor import extract_event
from src.news.schemas import Event, validate_event
from .helpers import article

class ExtractionTests(unittest.TestCase):
    def test_example_does_not_fabricate_supply_chain(self):
        e=extract_event(article())
        self.assertIn('6.8',e['event_summary'])
        self.assertEqual(e['primary_country'],'Taiwan')
        self.assertIs(e['logistics_disruption'],True)
        self.assertIsNone(e['production_disruption'])
        self.assertEqual(e['tickers_mentioned'],[])
        self.assertEqual(e['suppliers_mentioned'],[])
        self.assertEqual(e['technologies_mentioned'],[])
        self.assertIsNone(e['severity_score'])
        self.assertIsNone(e['event_start_at'])

    def test_null_differs_from_explicit_false(self):
        e=extract_event(article('An earthquake struck Taiwan. Production was not disrupted.'))
        self.assertIs(e['production_disruption'],False)
        self.assertIsNone(e['power_disruption'])
        self.assertIn('production_disruption',e['evidence_fields'])

    def test_hypothetical_negative_is_not_false(self):
        e=extract_event(article('An earthquake struck Taiwan. There may be no production disruption.'))
        self.assertIsNone(e['production_disruption'])

    def test_conflicting_claims_are_unknown(self):
        e=extract_event(article('An earthquake struck Taiwan. Production was halted. Production was unaffected.'))
        self.assertIsNone(e['production_disruption'])
        self.assertEqual(len(e['evidence_fields']['production_disruption']['conflicting_evidence']),2)

    def test_historical_damage_not_attached(self):
        e=extract_event(article('An earthquake struck Taiwan. In 1999 production was halted.'))
        self.assertIsNone(e['production_disruption'])

    def test_direct_mentions(self):
        for alias,ticker in COMPANY_ALIASES.items():
            with self.subTest(alias=alias):
                e=extract_event(article(f'{alias} reported quarterly results.'))
                self.assertIn(ticker,e['tickers_mentioned'])

    def test_deterministic_id_and_frozen_schema(self):
        e=extract_event(article())
        self.assertEqual(e['event_id'],'evt_'+hashlib.sha256(b'uuid_1|natural_disaster').hexdigest()[:24])
        self.assertEqual(e['event_id'],e['canonical_event_id'])
        self.assertEqual(set(e),set(Event.__dataclass_fields__))
        self.assertEqual(e['event_id'],extract_event(article())['event_id'])
        validate_event(e)

    def test_evidence_snippets_are_short_and_present(self):
        a=article()
        e=extract_event(a)
        for key in ('event_type','event_subtype','primary_country','logistics_disruption'):
            evidence=e['evidence_fields'][key]
            self.assertLessEqual(len(evidence['evidence']),240)
            self.assertIn(evidence['evidence'],a[evidence['source_field']])

    def test_rejected_article_produces_no_event(self):
        self.assertIsNone(extract_event(article('Bananas are rich in potassium.')))

    def test_source_counts_not_invented(self):
        e=extract_event(article())
        self.assertEqual((e['source_count'],e['independent_source_count']),(1,1))
        self.assertEqual(e['confirmation_level'],'single_source')

    def test_provider_country_is_not_event_location(self):
        e=extract_event(article('Microsoft reported quarterly results.',countries=['Taiwan']))
        self.assertIsNone(e['primary_country'])

    def test_schema_rejects_numeric_boolean(self):
        e=extract_event(article()); e['production_disruption']=0
        with self.assertRaises(ValueError): validate_event(e)

    def test_explicit_date_not_publication_inferred_date(self):
        e=extract_event(article('An earthquake struck Taiwan on 2026-09-16.'))
        self.assertEqual(e['event_start_at'],'2026-09-16')
        self.assertEqual(e['time_precision'],'date_only')

    def test_future_disruption_not_actual_fact(self):
        e=extract_event(article('An earthquake struck Taiwan. Production will be halted tomorrow.'))
        self.assertIsNone(e['production_disruption'])

    def test_other_country_disruption_not_attached(self):
        e=extract_event(article('An earthquake struck Taiwan. Production in Japan was halted.'))
        self.assertIsNone(e['production_disruption'])

    def test_abbreviated_country_not_split(self):
        e=extract_event(article('An earthquake struck the U.S. overnight.'))
        self.assertEqual(e['primary_country'],'United States')
