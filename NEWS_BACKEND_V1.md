# News Intelligence Backend V1

> Current version: V1.2. See `NEWS_BACKEND_V1_2_QA_REPORT.md` for scoped negation,
> action vocabulary and stress-test results. V1/V1.1 reports below are historical.

> V1.1 QA correction: see `NEWS_BACKEND_V1_1_QA_REPORT.md` for the current
> precedence, geography and entity-specific matching rules and positive-control
> results. The supplied V1.1 project includes the unchanged Exposure Knowledge
> workbook. The V1 implementation notes below and `NEWS_BACKEND_VALIDATION.md`
> describe the earlier delivery; their missing-workbook and first-clause
> limitations are superseded by the V1.1 report.

This adds an offline deterministic backend to the supplied UI project. It does
not connect outputs to the UI, contact a news provider, change financial scores,
or train a model. Existing files, including normalized articles and provider
modules, are preserved byte for byte.

## Run

From the project directory, with Python 3.13:

```sh
python3 -m src.news.pipeline
python3 -m unittest discover -s tests/news -t tests -v
python3 tests/run.py
```

The offline pipeline without an exposure workbook uses Python's standard library.
For a new environment, install existing application requirements with
`python3 -m pip install -r requirements.txt`. XLSX reading additionally needs
`python3 -m pip install -r src/news/requirements.txt` (openpyxl). No new packages
were installed during this implementation. The archive excludes `.env`; supply
your own local credentials only if invoking existing provider functions. News
backend execution does not require credentials.

## Flow and files

`normalized_article_v2` → `event_gate` → `event_extractor` →
`channel_generator` → `exposure_matcher` → JSON. `schemas.py` freezes all event_v1
keys and validates enums, tri-state flags and score ranges. `constants.py` owns
aliases, channel taxonomy and heuristic weights. The existing `__init__.py`,
normalizer and FreeNewsAPI providers are unchanged.

Inputs default to `data/news/normalized/freenewsapi_articles_normalized.json`.
An explicit `--input PATH` is available. Outputs are:

- `data/news/events/events_v1.json`: accepted events and gate rejections.
- `data/news/events/candidate_channels_v1.json`: separate hypotheses with basis
  fields, never written back into article facts.
- `data/news/matches/event_company_matches_v1.json`: seven company rows per
  accepted event, exposure-load status and rejected-edge reasons.

The command prints *qualifying exposure matches*, not all rows or direct mentions.
`matched=false` can coexist with a small direct-mention score. Missing exposure
knowledge does not prevent event extraction. Zero events and zero matches are
valid results. Repeated runs preserve deterministic event IDs and decisions;
administrative generation timestamps change. No multi-article clustering occurs.

## Extraction boundaries

The English gate requires a specific event object and action within 110
characters in an asserted clause. It filters hypothetical, negated, clearly
historical and off-topic contexts. This is a transparent high-precision starting
point, not an evaluated general news classifier. It can miss paraphrases,
indirect reporting and genuine announced future plans. Newsworthiness alone does
not force an article to pass.

The extractor takes the first supported event. Unknown facts remain JSON null;
explicit non-disruption can be false. Contradictory statements retain snippets
and null. Dates are extracted only when one unambiguous ISO calendar date appears
in the accepted clause; other dates, coordinates, duration, severity and source
quality are left unknown. Publication is never substituted for event start.
`developing`, `single_source`, and counts of one are documented administrative
defaults, not claims of independent verification. Extraction and location
confidence are heuristic constants, not calibrated probabilities.

Names and countries are conservative dictionary matches with word boundaries.
The event location is taken only from the accepted event clause, not the
publisher's country. Multiple mentioned countries have no automatic primary.
There is no city geocoding, relationship inference or assertion that a named
supplier/customer relationship exists. Entity lists report mentions, not affected
parties. Unrecognized names remain absent. Person, supplier and customer fields
are retained in the frozen schema but not inferred in this version.

Non-null substantive facts carry short evidence and source fields. Entity lists
retain multiple supporting snippets. Historical and different-country disruption
clauses are filtered. Complex co-reference, quotations and multiple simultaneous
events can still require human review; one article maps to at most one event.
Do not treat the rule tests as a measured precision/recall benchmark.

## Candidate channels and knowledge

A Taiwan earthquake alone can suggest a generic supply-chain hypothesis. It
does not manufacture TSMC, chips, NVIDIA, Apple or actual production disruption.
Generic semiconductors do not become advanced-semiconductor facts. Candidate
channels use `unspecified` subtypes unless more specific support is implemented;
they cannot automatically match a narrow edge subtype. Some taxonomy families
therefore need additional article coverage before they appear regularly.

Searches within the project find exactly:
`MAG7_News_Intelligence_Exposure_Knowledge_Layer_V1.xlsx`, sheet `Exposure Edges`.
All requested edge columns must be present; a title before the header is allowed.
Use `--exposure-workbook PATH` to select explicitly. Multiple workbooks, malformed
files, missing readers and duplicate IDs are reported with zero loaded edges.
The supplied ZIP has no such workbook. No alternative ordinal matrix or
synthetic exposure file is added to production data. Test-only edges use
`example.invalid` and do not describe real company exposure.

Positive exposure matches require: MAG7 ticker; recognized channel; `verified`
or `partial`; source URL and locator; exact normalized country; compatible
channel family/subtype; and valid timestamps. No country-only match is sufficient.
`blocked` and `hypothesis` rows never contribute exposure. Source URLs are
preserved, not fetched or independently verified by this backend. Maintainers
remain responsible for correctly classifying the workbook's evidence.

Edges marked planned/proposed/construction/pilot are excluded. A facility/route
edge also requires an explicitly operating stage. This deliberately may exclude
some legitimate but insufficiently documented rows. To use newly operating
capacity, add an evidenced operating version with its actual effective and
knowledge dates; never advance a planned record merely because time has passed.

## Time and leakage rules

Each edge must satisfy `known_at_utc <= prediction_time`,
`valid_from <= prediction_time`, and, if present,
`prediction_time <= valid_to`. Missing `known_at_utc`, missing `valid_from`,
invalid times and expired rows are excluded with explicit reasons.

By default prediction time is the later of publication and full-text ingestion.
If ingestion is absent, knowledge matching is disabled; publication alone does
not establish availability of this article version. An explicit
`--prediction-time ISO_TIMESTAMP` cannot precede input availability. Missing
times never fall back to the computer's current time. All comparisons use UTC.
Timezone-less spreadsheet values are interpreted as UTC because the schema's
field is `known_at_utc`; data owners must normalize local source times first.
Date-only known-at values become the end of that day; date-only validity starts
begin at midnight and validity ends include the whole day. Boundaries are inclusive.

The command does not reconstruct historical article revisions. Historical
research additionally requires versioned article bodies and genuinely
point-in-time exposure snapshots. Ingestion timestamps alone do not solve that.

## Relevance formula

Weights live only in `src/news/constants.py`. Let D be direct mention (0 or 1),
M a qualifying edge (0 or 1), Q the strongest matched evidence quality
(verified 1.0; partial 0.5), and S known event severity in [0,1]. Unknown severity
remains null in output and contributes no bonus:

`score = 0.15 D + M Q (0.30 + 0.15 + 0.15 + 0.20 + 0.05 S)`

The terms are edge match, country match, channel match, evidence quality and
severity, respectively. Every exposure term is gated by a valid edge. Multiple
duplicate/equivalent edges do not compound the score. Output is bounded [0,1]
and rounded to three decimals for reproducibility, not statistical precision.
Current extraction leaves severity unknown, so it normally has no bonus.

This is an uncalibrated review-ranking prior. It is not return, probability,
economic magnitude, causal impact, materiality, sentiment, rating or a trade
recommendation. Country and company 0–5 matrices are never multiplied.

## Extension points

`evaluate_gate`, `extract_event`, `generate_channels`, `load_exposure_edges` and
`match_exposures` are independent functions with plain-dict contracts. Future
extractors can replace rule modules while preserving schema and provenance
validation. No LLM APIs, ML dependencies, embeddings or return labels are added.
See `NEWS_BACKEND_VALIDATION.md` for actual test results and known input issues.
