# V1.2 legal-action precision QA patch

## Root cause audited before editing

The complete supplied article, not just its headline, was reproduced from `data/news/normalized/mag7_live_sample21_20260921.json`.

Headline: “In Washington, temples to Trump’s ego lie ruined. And another is on the way”.

The exact winning evidence was: “Scaffolding covers the signage where a court ordered the Trump administration to remove Donald Trump’s name.” This is an embedded background description. The old generic RULES entry paired `court` with `ordered` within 110 characters; it did not require the sentence to report a current legal action. The shared `event_evidence` function drove both Event Gate acceptance and extractor `legal_antitrust/ruling` classification. Constants supplied taxonomy/confidence, not an independent trigger.

Crucially, the full article actually contains references to legal action, including a recent judge and an older order. This was not merely the noun “ruling” or a metaphor matching accidentally. Requiring only the literal words “court ordered” would not fix it. The selected evidence lacked current-action framing and appeared in a relative background clause.

## Minimal implementation

Only one production file changed: `src/news/event_gate.py`.

- Adds local connected legal-subject/action evidence for the ruling subtype, rather than legal vocabulary and any nearby action.
- Recognizes explicit present-tense rulings, court blocks/dismissals/upholding and formal ruling issuance; issued/imposed additionally require a legal-action object.
- Rejects ruling evidence embedded in relative background descriptions and explicit revisiting/discussion/what-it-means contexts.
- Reuses existing assertion/negation and historical/year checks. No blanket rejection of articles containing analysis, politics or world coverage.
- Applies the same ruling check to the generic and existing lifecycle ruling paths. The extractor already consumes the shared helper and needs no edit.

New regression file: `tests/news/test_legal_ruling_precision.py` (8 methods with subcases). It tests the exact full article, both requested genuine headlines, commentary, historical references, valid action variants, negation, disconnected words, nonlegal issuance and real action inside an analysis article.

New artifacts: this report, test log, replay differences, integrity manifest, root delivery note and live sample run2 JSON. Existing tests and archived data outputs are preserved.

## Results

`python3 -m unittest discover -s tests/news -t tests`

**296 tests passed.** See `docs/legal_qa_v1_2/news_tests.txt`. The requested full News suite was run; non-News suites were not rerun.

```sh
python3 -m src.news.research_intelligence --input data/news/normalized/mag7_live_sample21_20260921.json --output data/news/research/mag7_live_sample21_run2_legal_fix.json
```

| Supplied live QA | Before | After |
| --- | ---: | ---: |
| Articles | 21 | 21 |
| Accepted | 5 | 4 |
| Rejected | 16 | 17 |
| Qualified pairs | 0 | 0 |
| Review candidates | 0 | 0 |

Exact false positive: accepted `legal_antitrust/ruling` → rejected, extractor returns no event. No ticker match is introduced.

## Legacy replay side effects

Compared gate, extractor, channels and exposure matches at a fixed timestamp for 167 article occurrences (146 legacy + 21 live; the separate previous round2 fixture is covered by the existing News tests). 163 are identical. Four differ:

- Live political feature: accepted → rejected (intended fix).
- H36: still accepted ruling; evidence changes from the competition-regulator sentence to the connected Competition and Markets Authority action. No acceptance or exposure-match change.
- H63: rejected → accepted. Its top court explicitly issued a final judgment; this is supported legal action.
- H101: rejected → accepted. Its top court explicitly upholds the Google Shopping antitrust fine; this is supported legal action.

These are generic semantic consequences, not tuning to historical price outcomes. Full before/after structures are in `docs/legal_qa_v1_2/replay_differences.json`. Archived historical datasets, labels, outputs and models have not been regenerated.

## Existing safeguards and feed audit

Existing Event Gate safeguards include clause-level negation/hypothetical checks, historical wording and older explicit years, educational/history framing, a small OFF_TOPIC headline rule, and action-family discussion guards. There is no unified commentary/opinion/analysis/feature classifier; adding one is unnecessary for this local fix. An explicit supported legal action can still pass even in an analysis article.

`src/news/providers/freenewsapi.py` already allows caller-supplied listing parameters and cached listings. `freenewsapi_details.py::fetch_all_details` iterates listings and fetches/reuses details; it skips missing UUIDs but has no category/genre prefilter before full-text detail retrieval. Gate OFF_TOPIC checks happen later, so they do not save detail calls.

Optional proposal for live QA only (NOT implemented): place an opt-in wrapper between listing and detail fetch. Skip only listings with explicit, exclusively low-value metadata categories such as sports, celebrity, entertainment, lifestyle or royal-family; retain mixed or unknown classifications. Log UUID/category/skip reason and preserve the raw listing for replay. Keep world, politics, business, finance, economy, technology and energy. Do not exclude gaming wholesale (gaming companies, chips and transactions can be relevant). Treat explicit commentary-only metadata as an optional QA filter, not a title-based fact claim; retain it if a discrete action is visible, or when uncertain. Default off. This would reduce noise without ticker-name-only selection or modifying core eligibility.

## Unchanged scope and limitations

Hash verification confirms every copied original file is unchanged except `src/news/event_gate.py`. In particular, Relevance Engine implementation, weights, materiality/direction logic, Exposure Matcher/workbook, historical ML code/data/models/labels/features/validation, Research Mode, valuation, ratings, earnings quality, SEC logic, UI, extractor and constants were untouched. Original ZIP/project was not overwritten. Direction remains Analyst judgment required.

This remains a bounded English rule system, not general discourse understanding. The relative-clause safeguard can conservatively miss a genuine action reported only as background; unusual named-judge or long-distance wording may still be unsupported. Conversely, a feature with an independently asserted legal action can still qualify; article genre alone is not a veto. The patch does not prove that every commentary article is filtered, or independently verify article truth.

The complete project archive excludes environment secrets, virtual environments, macOS metadata and Python bytecode. Use the existing dependency/setup instructions; no credentials are bundled. Earlier V1/V1.1 reports describe their own releases; this report records the current changes.
