# Backend V1.2 stress-test correction

## Validation

- All 128 news tests pass: all 94 previous tests preserved and 34 new regression
  tests added in `tests/news/test_qa_v12.py`.
- Stress input: 8 articles; 7 accepted; 1 rejected; 12 candidate channels; 3
  positive exposure-backed event/company pairs.
- This task does not claim a new full stock-research suite run. Previous V1/V1.1
  validation reports are historical. The workbook, matcher, Event Schema,
  existing tests, provider modules and all unrelated application files are
  preserved byte for byte against the supplied ZIP.

Run from this project directory:

```sh
python3 -m src.news.pipeline --input data/news/normalized/stress_test_articles.json
python3 -m unittest discover -s tests/news -t tests -v
```

## Accepted events

| Event | Type / subtype | Candidate channels | Positive exposure matches |
|---|---|---|---|
| Azure expansion | product_technology / capacity_expansion | technology_demand; cloud_services; datacenter_infrastructure | MSFT, score 0.95, edge 11 |
| Japan earthquake, no reported disruption | natural_disaster / earthquake | None | None |
| Taiwan consumer-goods port disruption | supply_chain / port_disruption | logistics | None |
| Google AI-model announcement | product_technology / product_launch | technology_demand | None; direct GOOGL mention only, score 0.15 |
| TSMC interruption | supply_chain / production_interruption | manufacturing; supply_chain; advanced_semiconductors | NVDA, score 0.80, edges 1/2; AAPL, score 0.40, edge 6 |
| Amazon retail distribution center | supply_chain / distribution_center_opening | logistics; ecommerce_demand | None; direct AMZN mention only, score 0.15 |
| China online-ad rules | government_policy / regulation | regulatory_general; digital_advertising | None |

Rejected: `stress_008`, **Tesla CEO comments on long-term electric vehicle demand**.
No current discrete action is asserted; its explicit negative list cannot create
a shutdown, financing, earnings or regulatory event.

## Corrections and boundaries

Only existing gate, extraction, channel-generation modules and extraction's
central location constants changed. The shared assertion helper lives in the
existing gate module; there is no new architecture or model. Texas is mapped
to United States as a region, not mislabeled as a city.

Negation is scoped to a clause and the matched claim. Lists retain their negation;
contrast markers such as `but` reset scope. A negative condition after an
earthquake does not negate the earthquake itself. Explicit `no power disruption`
is false; `no reports of power disruption` and `no evidence of ...` are unknown,
not proof of absence. Contradictory positive and negative claims remain null.
`unaffected` and `remained operational` supply explicit negative evidence.

Factual claims retain short evidence plus an assertion status inside the
existing `evidence_fields` object. No Event fields or Event types were added.
New subtypes describe accepted interruption, expansion and distribution-center
opening actions under existing types. Root-cause precedence remains intact.

Entities and topics appearing only in explicitly excluded or negated descriptions
are not promoted to affirmative extraction outputs. For example, `does not
describe NVIDIA supply problems` is not a positive NVIDIA mention/channel input.
This makes those lists conservative relevant mentions, not an exhaustive index
of every literal name in the raw article. The normalized article remains intact.

The generator consumes true flags, supported affirmative topics and valid event
classifications. False/null flags cannot generate their disruption channels.
Explicit negative/unknown disruption evidence also suppresses the generic
disaster supply-chain fallback. This prevents mere industry mentions from
overriding non-disruption evidence. An earthquake without such contrary evidence
still retains the existing conservative generic supply-chain hypothesis.

Additional action vocabulary covers interrupted production, Azure/cloud capacity
expansion, port disruption delaying shipments, AI-model announcements, retail
distribution-center openings and new government requirements. Assertions still
need an action/object relationship; discussion of capacity expansion and generic
educational content are rejected. Tests include paraphrases, passive wording,
negated actions and paired positive/negative clauses, not headline equality checks.

## Remaining ambiguity

- Google: directly identified as GOOGL, but the article supplies no event location
  in its text and this workbook has no matching product-launch/technology-demand
  edge. Publisher `countries` metadata is not silently substituted for event
  geography. Direct relevance is not an exposure-backed match.
- Amazon retail: directly identified as AMZN. The event is in Texas/United States;
  the existing retail-demand edge is North America, not an exact United States
  edge. Existing country matching is unchanged. AWS edge 17 is not used.
- TSMC: indirect matches reuse existing supplier relationships and the unchanged
  V1.1 production-channel refinement. The article does not identify the exact
  facility or prove every fabrication/packaging operation was affected. These are
  possible exposure links, not confirmed damage to NVIDIA or Apple.
- China advertising rules have no eligible China-specific MAG7 advertising edge;
  global advertising business models do not establish a China match.
- Negation remains deterministic English logic. Complex quotations, co-reference,
  multiple unrelated events and ambiguous report language can require review.
  Scores remain uncalibrated heuristic priors; neither methodology nor weights
  changed. No ML, UI changes or new exposure knowledge were introduced.

See `NEWS_BACKEND_V1_2_VALIDATION.json` for machine-readable event results and
preservation checks. The three generated news outputs are from the stress run.
