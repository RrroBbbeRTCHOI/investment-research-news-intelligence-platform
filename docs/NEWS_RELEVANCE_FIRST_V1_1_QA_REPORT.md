# News Relevance First V1.1 — targeted functional QA patch

## Scope and root causes

This is an independent copy of STOCK_SCREENER_NEWS_RELEVANCE_FIRST_V1. The original project was not edited.

1. Direct subjects: qualification previously required an exposure edge even when an accepted article explicitly described the company as the affected event participant. Mere mentions and affected participants shared the same result.
2. Unaffected technologies: the existing local negation check missed “were reported as continuing normally” and could attach another technology's negation to positive evidence.
3. Export actions: export-license/licensing object variants were missing from the existing action pattern. The isolated present-tense “regulator fines Meta” also needed the existing fine rule to recognize authority + fines + object.

## Files changed

- `src/news/research_intelligence.py`: bounded action/participant rules, stored direct-event evidence, direct-subject qualification and a Medium single-source research priority without requiring an exposure edge. Availability timestamps remain required. Background, hypothetical, negated and clearly older mentions are excluded.
- `src/news/event_extractor.py`: local technology clause scope and unaffected/normal-operation wording. Positive wafer-fabrication evidence remains supported. The existing channel generator reuses this helper.
- `src/news/event_gate.py`: explicit export-license/licensing restriction variants under the existing action and speculation safeguards; a narrow authority-fines-object form under the existing fine subtype.
- `tests/news/test_research_intelligence.py`: replace the old mere-mention fixture (which actually described Tesla taking a pricing action) with a genuine background comparison. Existing mention-only expectations remain unchanged.
- `tests/news/test_relevance_qa_round2.py`: 10 new test methods with positive and negative subcases for the three defects, article availability, local technology scope and ML independence.
- New delivery artifacts: this report, root delivery note, test log, integrity manifest, legacy replay differences and `data/news/research/relevance_qa_round2_run2.json`.

No changes to `channel_generator.py`, `exposure_matcher.py`, constants, Event Schema, exposure workbook, UI, Research Mode, valuation, rating, financial analysis, Earnings Quality, SEC logic or historical ML code/data/models/thresholds/features/labels. Relevance score weights and matching temporal checks remain unchanged. Original recorded historical outputs are preserved.

## Validation

`python3 -m unittest discover -s tests/news -t tests`

Result: **288 tests passed**, 17.515 seconds. Full captured output: `docs/qa_v1_1/news_tests.txt`. This is the complete News suite requested; the non-News suite was not rerun for this patch.

Actual CLI rerun:

```sh
python3 -m src.news.research_intelligence --input data/news/normalized/relevance_engine_qa_round2.json --output data/news/research/relevance_qa_round2_run2.json
```

| Metric | Before | After |
| --- | ---: | ---: |
| Articles | 4 | 4 |
| Accepted | 3 | 4 |
| Rejected | 1 | 0 |
| Qualified event/ticker pairs | 2 | 3 |
| Review candidates | 1 | 0 |

| Case | Before | After |
| --- | --- | --- |
| QA001 Meta fine | META mention-only / Review | META qualified_direct_event_subject, no exposure edge required; Medium priority |
| QA002 CoWoS disruption | NVDA plus false-positive AAPL wafer exposure | NVDA Edge 2 advanced_packaging only; unaffected wafer fabrication does not qualify AAPL |
| QA003 small Malaysian supplier outage | Accepted, no supported MAG7 match | Same; no unsupported match |
| QA004 export-license restrictions | Rejected | Accepted trade_export_control/export_controls; export_restriction=true; NVDA direct subject plus existing Edge 5 evidence |

Direction remains **Analyst judgment required**. Materiality remains Unknown where no defensible materiality evidence exists.

## Legacy replay differences

Recomputed gate, extraction, candidate channels and exposure matching against the original source for 146 article occurrences in 11 existing normalized fixture files, with identical extraction timestamps. **144 identical; 2 differ**:

- H82: export_restriction remains true; its supporting evidence/source_field now uses the qualifying headline instead of body. No change to acceptance or exposure matching.
- H108: “Irish regulator fines Meta over Facebook and Instagram advertising practices” changes from rejected to accepted legal_antitrust/fine, through the same general authority-fines rule required by QA001. No qualified exposure edges are invented; future-known edges remain ineligible.

These are semantic consequences of the prospective patch, not price-outcome tuning. Full differences are in `docs/qa_v1_1/legacy_replay_differences.json`. Historical input files, archived outputs and ML artifacts were not regenerated. Earlier V1 frozen-behavior documentation describes that prior release; this report records V1.1 changes and supersedes any implication that the patched engine is bit-for-bit identical.

## Remaining limitations

- Direct-subject recognition is a bounded English rule set, not a full grammatical or coreference parser. Unrecognized phrasing can remain Review rather than being assumed relevant.
- Direct qualification does not fabricate an exposure edge or change relevance weights. Thus a no-edge direct subject such as META still has numeric relevance_score 0.15; its relationship, qualification, evidence label and research priority now distinguish it from a mere mention. The score remains the existing component score, not a probability or materiality measure.
- Technology scope handles tested local clauses; complex long-distance references can require further prospective QA. Mention alone is not proof of impact.
- This patch does not independently verify article truth or infer materiality, stock direction or future returns. Historical ML remains optional retrospective context and cannot determine qualification or priority.

## Integrity and packaging

Compared every copied original file with its pre-edit SHA-256: exactly three production files and one existing test changed; all other copied originals are unchanged. One new regression file was added. See `docs/qa_v1_1/integrity.json`.

The complete standalone source, templates, tests and project data are packaged. Secrets/environment files, version-control metadata, virtual environments and Python bytecode are excluded. Install the project's documented dependencies in your own environment; no virtual environment or credentials are bundled.
