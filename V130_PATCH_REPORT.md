# V1.3.0 Equity Research Event Lifecycle Expansion

## Scope
Product files changed: src/news/event_gate.py, src/news/event_extractor.py, src/news/schemas.py.
New tests: tests/news/test_event_lifecycle_v130.py (22 methods, including wording variants).
No changes to matcher, exposure workbook, constants, channel generator, pipeline or historical replay.
Original project is untouched. This patch requires the already-applied V1.2.3 project and its historical fixtures.

## Taxonomy and extraction
Only one event type was added: corporate_action (recall, workforce_reduction).
Acquisition termination uses corporate_transaction/acquisition_terminated.
Legal stages: lawsuit, complaint, charge, investigation, regulatory_scrutiny, remedy_proposal, ruling, fine, settlement.
No Event V1 fields were added or removed. The permitted event_type enum was extended.
A proposed legal remedy is not a final ruling. H30 is an authority's announced review, not an asserted opened investigation.
Government product-use restrictions remain government_policy/regulation; no national consumer ban is inferred.
Explicit global IT/Office 365/service-unavailability wording uses infrastructure_outage/outage.
Existing infrastructure flags generate channels; no Microsoft/CrowdStrike causal relationship is invented.
Legal/regulatory channels carry the source evidence, without inferred guilt, harm or severity.

## Validation
Full suite: 202 test methods executed; 201 passed, one existing method has TWO failed subcases (H02, H03).
All 22 new methods passed. The same two failures were reproduced with unmodified V1.2.3 source and the current workbook (180 methods).
Existing tests and expected values were NOT weakened or updated to conceal these failures.
H01-H12: exact pre/post equality for events, channels, matcher pairs and exclusions (fixed administrative extraction timestamp).
No newly introduced regression was observed.

Existing H02 failure: NVDA Edge 5 known_at_utc is date-only 2023-10-17. Existing end-of-day interpretation places it after replay time 2023-10-17T23:49:00Z; excluded as future_known_at.
Existing H03 failure: AMZN Edge 17 known_at_utc=2026-02-05, later than replay 2025-10-20; excluded as future_known_at.
Neither date nor time-safety logic was changed. These current inputs cannot honestly be reported as matching PASS.

## Historical H13-H30
H13 accepted legal_antitrust/fine
H14 accepted legal_antitrust/lawsuit
H15 accepted government_policy/regulation
H16 accepted legal_antitrust/charge
H17 accepted infrastructure_outage/outage
H18 accepted legal_antitrust/ruling
H19 accepted legal_antitrust/remedy_proposal
H20 accepted legal_antitrust/complaint
H21 accepted corporate_transaction/acquisition_terminated
H22 accepted legal_antitrust/fine
H23 rejected (boundary unchanged)
H24 accepted legal_antitrust/fine
H25 rejected (unchanged)
H26 rejected (unchanged)
H27 accepted corporate_action/recall
H28 accepted supply_chain/production_interruption (existing behavior)
H29 accepted corporate_action/workforce_reduction
H30 accepted legal_antitrust/regulatory_scrutiny

H13-H30: 18 loaded, 15 accepted, 3 rejected, 0 qualified exposure matches. Acceptance is not exposure coverage.
All 30: 25 accepted, 5 rejected (H07, H12, H23, H25, H26).

## Apply and verify
Extract this patch into a COPY of the V1.2.3 project root, replacing the included files.
Run:
python3 -m unittest discover -s tests/news -t tests -v
python3 -m src.news.pipeline --input data/news/normalized/historical_validation_H01_H03.json
python3 -m src.news.pipeline --input data/news/normalized/historical_validation_H04_H06.json
python3 -m src.news.pipeline --input data/news/normalized/historical_validation_H07_H12.json
python3 -m src.news.pipeline --input data/news/normalized/historical_validation_H13_H30.json

Pipeline runs replace the existing generated news outputs as before.
