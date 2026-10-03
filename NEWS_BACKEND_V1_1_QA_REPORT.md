# Backend V1.1 — targeted QA correction

This copy continues from the supplied `STOCK_SCREENER_NEWS_INTELLIGENCE_BACKEND_V1 2.zip`.
No architecture, frozen Event Schema, UI, research/rating logic, score weights,
provider fetching or Exposure Knowledge Layer was replaced. No ML was added.

## What was fixed

1. The gate evaluates all asserted clauses before selecting an event. A supported
   root disaster or policy cause outranks downstream transport/production effects.
   Tied event rules prefer body evidence over a shorter summary/headline, so an
   abbreviated headline does not discard the operator or location in the body.
   Generic rail/freight disruption uses `transport_disruption`, not `port_disruption`.
2. Monetary cut/reduction wording includes present-tense `cuts`, `reduces`,
   `lowers` and a reported reduction. The subtype is `rate_cut`.
3. Geography aliases are centralized. `US`, `U.S.` and `United States` normalize
   together; explicit Shanghai maps to China, and Federal Reserve jurisdiction
   maps to the United States. Bilateral policy distinguishes the explicit policy
   actor from the destination, including passive `announced by` wording.
   Evidence retains the stated location/institution and the mapping basis.
4. Port flags require whole-word port/harbor/terminal evidence. Generic transport,
   logistics delays and the word `reported` cannot satisfy a port flag.
5. Candidate hypotheses cover explicit logistics, cloud-service infrastructure,
   vehicle production and export policy. Generic semiconductor mentions remain
   generic supply-chain hypotheses; they do not assert advanced fabrication.
6. Matching determines semantic eligibility before assigning any exposure score.
   Operational subjects are drawn from the supported event summary/headline.
   A mentioned observer or unaffected peer is not automatically an affected owner.
   The directly identified owner must have a compatible edge; known AWS/Azure/
   Google Cloud business descriptions are checked. A production shutdown does
   not become a country-level sales/demand edge.
7. Non-mentioned companies need an explicit upstream relationship and a dependency
   role. Counterparty/facility/input fields must link them to the affected entity,
   service, evidenced facility or explicitly scarce commodity. Merely owning a
   data center in the same country does not qualify. AWS requires an AWS service
   relationship, not an unrelated Amazon retail relationship.
8. A named supplier production disruption can refine a broad production candidate
   into a compatible manufacturing/semiconductor edge when that edge explicitly
   names the supplier as counterparty. This is recorded as
   `named_supplier_production_channel_refinement` in match reasons. It cannot be
   triggered by an unnamed factory or a country-only overlap, cannot satisfy an
   unsupported narrow subtype, and adds no semiconductor/ticker facts to Event.
9. Regional grid outages and root disasters retain the regional path. They may
   have several compatible company exposures. Shared upstream dependency tests
   demonstrate that excluding unrelated peers does not block legitimate indirect
   TSMC → NVDA/AAPL relationships.

Existing evidence-status, source provenance, planned-capacity and time checks
remain in force. `blocked` and `hypothesis` edges cannot become positive evidence;
unknown flags remain null. Scoring weights and the heuristic formula are unchanged.

## Positive-control rerun

```sh
python3 -m src.news.pipeline --input data/news/normalized/positive_control_articles.json
```

Result: **5 articles, 5 accepted, 0 rejected, 10 candidate channels, 3 positive
company exposure matches**. Knowledge workbook: **loaded**, 26 input edges.

| Control | Event type / subtype | Primary country | Positive company match | Score | Edge IDs |
|---|---|---|---|---:|---|
| Taiwan earthquake | natural_disaster / earthquake | Taiwan | None | — | — |
| US AI-chip export controls | trade_export_control / export_controls | United States | NVDA | 0.95 | 5 |
| AWS outage | infrastructure_outage / outage | United States | AMZN | 0.95 | 17 |
| Tesla Shanghai production halt | supply_chain / factory_shutdown | China | TSLA | 0.55 | 23 |
| Federal Reserve cut | macro_monetary / rate_cut | United States | None | — | — |

- Earthquake: logistics disruption is true; port disruption remains null. No
  company/ticker or production damage is invented. The current edge workbook
  has Taiwan advanced-chip/packaging exposures but no compatible generic
  transport/logistics edge. The generic article does not establish advanced
  chip/facility disruption, so those edges are not forced into a match.
- Export controls: affected countries contain both United States and China;
  NVIDIA is explicitly mentioned. Edge 5 describes regulatory export exposure.
- AWS: MSFT, GOOGL and META have **no positive match**, no matched edge and zero
  edge/country/channel score components. Edge 17 identifies Amazon Web Services.
- Tesla: edge 23 is a partial operational Shanghai exposure. China demand edge
  24 is excluded; unrelated China-exposed companies are excluded.
- Fed: interest-rate channel is true and Federal Reserve appears in government
  entities/regulators. There is no eligible interest-rate edge in this workbook;
  zero company matches is valid.

The five articles are synthetic positive controls, not evidence that these
events actually occurred. Scores are uncalibrated relevance priors, not
probabilities, impact magnitudes or expected returns.

## Tests and preserved files

```sh
python3 -m unittest discover -s tests/news -t tests -v
python3 tests/run.py
```

All **94 news backend tests passed**: the prior 51 plus 43 QA regressions.
Coverage includes the requested 24 checks, word-order and tense variations,
passive bilateral policy, generic transport vs ports, coordinated services,
unaffected peer mentions, direct business mismatches, genuine upstream/facility
links, unnamed-factory rejection, unchanged temporal restrictions and the
actual supplied workbook's matched edge IDs.

Full-suite results are recorded in `NEWS_BACKEND_V1_1_VALIDATION.json` after the
final run. Existing historical-cache hash failures, if present, are not repaired
by altering unrelated data or refreshing frozen baselines.

Unchanged SHA-256 values:

- Exposure workbook: `8a2a8637525cef0f30766349d7a88cdb1cbd605eb526fb69d863c5ed2f1b5d11`
- Frozen `src/news/schemas.py`: `29c00df826a097c59098f4799c2b5f7aef278903b2278bb445117417bd078f0e`

Modified product code is confined to these existing modules:
`src/news/constants.py`, `event_gate.py`, `event_extractor.py`,
`channel_generator.py`, and `exposure_matcher.py`.
Added tests: `tests/news/test_qa_v11.py`.
Documentation is updated and the three existing generated news JSON outputs
are regenerated with the positive-control run. Both original normalized input
files and the workbook remain unchanged.

## Remaining ambiguity

This is English deterministic QA, not a general event parser. One article still
maps to one event. If several unrelated current events occur in one article,
priority rules are not proof of causality; source review may be needed. Entity
and location aliases are finite. Unknown operational subjects fail conservatively.
The loader trusts the workbook's supplied evidence status; this task did not
independently fact-check its source URLs or reinterpret partial evidence as verified.
Country-wide matching does not establish which undisclosed factory was physically
affected. Indirect matches rank documented possible dependencies, not demonstrated
damage. Existing unknowns and narrow-subtype restrictions remain valid.

The default command still processes the original ten mostly non-event articles:
**10 loaded, 0 accepted, 10 rejected**, now with `Exposure knowledge: loaded`.
Use the explicit `--input` command above for the five positive controls. Both
commands overwrite the same generated output paths; the packaged outputs are
from the positive-control run.
