# News Intelligence Stress Test v1

This directory contains the frozen benchmark for the News Intelligence pipeline.

## Files

- `source_articles.json`
  Frozen input articles.

- `ground_truth.json`
  Human-defined expected behavior.

- `manifest.json`
  Benchmark metadata and SHA-256 hashes.

## Important

`ground_truth.json` is evaluation-only.

It must NEVER be passed to Gemini, another LLM, the normalizer, or the research pipeline as source context.

The benchmark articles must remain unchanged after v1 is frozen.

If the benchmark needs new or changed cases, create a new benchmark version instead of silently changing v1.

## Benchmark structure

ST01 — Federal Reserve rate decision

ST02 — US CPI release

ST03 — Nvidia / China export controls

ST04 — Export-control enforcement / smuggling

ST05 — TSMC packaging infrastructure

ST06 — CoWoS / MAG7 dependency

ST07 — AWS outage

ST08 — Azure / Microsoft outage

ST09 — Strait of Hormuz blockade

ST10 — Strait of Hormuz tanker incident

ST11 — Nvidia CEO commentary control

ST12 — Irrelevant noise control
