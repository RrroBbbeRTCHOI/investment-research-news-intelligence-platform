"""Independent Earnings Quality producer. Never imports valuation or recommendation."""
from src.analysis.company_metrics import safe_float
from src.analysis import quality
from src.analysis.fundamentals import calculate_cash_conversion, calculate_roic
from src.analysis.earnings_quality_diagnostics import build_diagnostics
from src.analysis.earnings_quality_evidence import load_non_core_evidence, statement_evidence
from src.data.earnings_quality_inputs import load_eq_inputs
from src.analysis.earnings_quality_research import build_research, roic_history
from src.data.reuse import scoped
from src.services.cache import cached
from src.services.revenue_resilience_service import get_revenue_resilience


COMPONENTS = (
    ("cash_conversion", "Cash Conversion", "Cash Conversion Score",
     "Existing model score based on operating cash flow / net income."),
    ("accrual_quality", "Accrual Quality", "Accrual Quality Score",
     "Existing model score based on (net income - operating cash flow) / total assets."),
    ("margin_stability", "Margin Stability", "Margin Stability Score",
     "Existing operating-margin stability score; it does not identify an improving or deteriorating trend."),
    ("roic_quality", "ROIC Quality", "ROIC Score",
     "Existing ROIC component score, not a new capital-efficiency calculation."),
    ("non_core_earnings", "Non-Core Earnings", "Non-Core Earnings Score",
     "Existing score for the model's identified positive non-core items; evidence coverage may be incomplete."),
    ("revenue_resilience", "Revenue Resilience", "Revenue Resilience Score",
     "Approved V1.4 model: 60% revenue diversification and 40% segment persistence."),
)
CLASSIFICATIONS = {
    "Very Strong", "Strong", "Moderate", "Weak", "Very Weak", "Unknown"
}



def _score_bundle(ticker):
    legacy_components = quality.get_quality_components(ticker)
    legacy_summary = quality.get_quality_summary(ticker, components=legacy_components)
    resilience = get_revenue_resilience(ticker)
    components = {name: dict(component) for name, component in legacy_components.items()}
    components["Core Revenue"]["score"] = (
        safe_float(resilience.get("revenue_resilience_score"))
        if resilience.get("production_ready") else None
    )
    observed = {}
    for name, loader in (("cash_conversion", calculate_cash_conversion),
                         ("accrual_ratio", quality.calculate_accrual_ratio),
                         ("margin_history", quality.calculate_margin_history), ("roic", calculate_roic)):
        try:
            value = loader(ticker)
            observed[name] = [safe_float(v) for v in value] if isinstance(value, list) else safe_float(value)
        except Exception:
            observed[name] = None
    summary = quality.get_quality_summary(ticker, components=components)
    return {"summary": summary, "legacy_summary": legacy_summary,
            "components": components, "legacy_components": legacy_components,
            "model_inputs": observed, "revenue_resilience": resilience}


@scoped
def get_scoring_bundle(ticker):
    ticker = ticker.upper().strip()
    return cached(("eq-scoring-v1-revenue-resilience-v1.4", ticker), lambda: _score_bundle(ticker),
                  acceptable=lambda r: r["summary"].get("Earnings Quality Score") is not None)


@scoped
def get_scoring_summary(ticker):
    return get_scoring_bundle(ticker)["summary"]


def expose_scores(summary, source_components=None):
    detail = summary if isinstance(summary, dict) else {}
    classification = detail.get("Earnings Quality")
    if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
        classification = "Unknown"
    components = []
    sources = ("Cash Conversion", "Accrual Quality", "Margin Stability", "ROIC", "Non-Core Earnings", "Core Revenue")
    resilience = source_components if isinstance(source_components, dict) else {}
    for (key, label, source, note), component_name in zip(COMPONENTS, sources):
        value = safe_float(resilience.get("revenue_resilience_score")) if key == "revenue_resilience" else safe_float(detail.get(source))
        eligible = bool(resilience.get("production_ready")) if key == "revenue_resilience" else value is not None
        components.append({"key": key, "label": label, "score_raw": value, "note": note,
                           "weight": quality.QUALITY_WEIGHTS[component_name], "formal_eligible": eligible,
                           "model_detail": resilience if key == "revenue_resilience" else None})
    available_weight = sum(c["weight"] for c in components if c["score_raw"] is not None and c["formal_eligible"])
    for c in components:
        c["effective_weight"] = c["weight"] / available_weight if c["score_raw"] is not None and c["formal_eligible"] and available_weight else None
        c["weighted_score_contribution"] = c["effective_weight"] * c["score_raw"] if c["effective_weight"] is not None else None
    return {"score_raw": safe_float(detail.get("Earnings Quality Score")), "classification": classification,
            "components": components, "available_components": sum(c["score_raw"] is not None for c in components),
            "formal_available_components": sum(c["score_raw"] is not None and c["formal_eligible"] for c in components),
            "total_components": len(components), "revenue_resilience": resilience,
            "weighted_positive_non_core_raw": safe_float(detail.get("Weighted Non-Core Contribution"))}


def _build(ticker):
    scoring_error = None
    try:
        bundle = get_scoring_bundle(ticker)
    except Exception as error:
        bundle = {"summary": {}, "legacy_summary": {}, "components": {}, "revenue_resilience": {}}
        scoring_error = type(error).__name__
    legacy = bundle["components"].get("Non-Core Earnings", {}).get("details")
    inputs = load_eq_inputs(ticker)
    evidence = load_non_core_evidence(ticker, legacy)
    evidence["statement_items"] = statement_evidence(inputs)
    return {"ticker": ticker, **expose_scores(bundle["summary"], bundle.get("revenue_resilience")),
            "legacy_quality_summary": bundle.get("legacy_summary", {}),
            "integrated_quality_summary": bundle["summary"], "scoring_error": scoring_error,
            "legacy_model_inputs": {"values": bundle.get("model_inputs", {}), "source": "Yahoo annual statements",
                                    "period_alignment": "legacy_latest_available",
                                    "note": "Exact existing-model calculations. Legacy cash/accrual/ROIC do not enforce common periods; use the aligned diagnostic section for conclusions."},
            "inputs": inputs, "identified_non_core_items": evidence, "non_core_evidence": evidence,
            "research_analysis": build_research(inputs, evidence, roic_history(ticker)),
            **build_diagnostics(inputs, evidence)}


@scoped
def build_earnings_quality(ticker, peers=None):
    """peers is retained for caller compatibility; EQ analysis is peer-independent."""
    ticker = ticker.upper().strip()
    return cached(("eq-diagnostics-v2-revenue-resilience-v1.4", ticker), lambda: _build(ticker),
                  acceptable=lambda r: not r["scoring_error"] and not r["inputs"]["errors"]
                  and r["inputs"]["availability"] == "available")
