# Moat 1 V2 architecture

This complete project continues from STOCK_SCREENER_MOAT1_PIPELINE_V1. Existing rating, valuation, scoring weights and legacy frontend score fields are preserved. V2 adds an evidence-only research_analysis output to the existing Earnings Quality service.

Flow: existing cached financial inputs and verified narrative candidates -> earnings_quality_research_evidence (validation and family grouping) -> earnings_quality_attribution (arithmetic bridges) -> earnings_quality_research (assembly and interpretation) -> existing Earnings Quality template.

The external earnings_quality_rules.json defines evidence taxonomy and validation parameters. research_keywords.json retains the expanded supplied keyword set and adds operating revenue mix phrases. The legacy scoring keyword file is unchanged. No ticker-specific branches, replacement provider layer or cache architecture was introduced. The service cache namespace is versioned to prevent old diagnostic payloads being reused as V2 outputs.

Existing top scores remain intact. Additive UI sections present attribution, grouped evidence, core revenue evidence, margin/ROIC diagnostics and free cash flow attribution. Original documents describe prior phases; the four MOAT1_V2 documents describe this upgrade.

Run from this directory after installing dependencies with `python3 -m pip install -r tests/requirements.txt`, then `python3 app.py`. Live provider access requires the existing application configuration; secrets are not included. Offline regression verification: `PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py`.
