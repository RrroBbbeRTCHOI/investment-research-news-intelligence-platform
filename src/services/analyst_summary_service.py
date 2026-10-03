"""Non-blocking, evidence-grounded analyst summary for Research Financials."""
import hashlib
import json
import os
import re
import threading

from src.news.llm.base import post


PROMPT_VERSION = "research_analyst_summary_v1"
_CACHE = {}
_PENDING = set()
_LOCK = threading.Lock()


def _analyst_readable(text, *, positive=False):
    """Translate deterministic diagnostic labels without changing their meaning."""
    value = str(text or "").strip()
    if positive and value.lower().startswith("unknown:"):
        return "No evidence-backed positive structural observation is available for the aligned periods."
    replacements = {
        "arithmetic_supported": "supported by a statement-level arithmetic reconciliation",
        "reconciled_arithmetic": "supported by a statement-level arithmetic reconciliation",
        "insufficient_evidence": "insufficient supporting evidence",
    }
    for internal, readable in replacements.items():
        value = re.sub(rf"\b{internal}\b", readable, value, flags=re.IGNORECASE)
    return value.replace("_", " ")


def _fallback(ticker, financials, earnings_quality):
    interpretation = (financials or {}).get("analyst_interpretation", {})
    positive = _analyst_readable(
        interpretation.get("positive_observation") or "No positive observation is currently available.",
        positive=True,
    )
    concern = _analyst_readable(
        interpretation.get("main_concern") or "No principal concern is currently available."
    )
    resilience = (earnings_quality or {}).get("revenue_resilience", {})
    resilience_score = resilience.get("revenue_resilience_score")
    resilience_text = ""
    if resilience_score is not None:
        qualifier = "formal" if resilience.get("production_ready") else "provisional and excluded from the formal score"
        resilience_text = f" {ticker}'s Revenue Resilience V1.4 score is {resilience_score:.1f}, {qualifier}."
    return f"{positive} {concern}{resilience_text}"


def _generate(key, ticker, evidence):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    try:
        payload = {
            "model": model,
            "input": (
                "Write a concise 2-4 sentence institutional analyst summary using only the supplied JSON. "
                "Do not add facts, forecasts, price targets, recommendations, or alter any score. "
                "State provisional status when present. Return JSON only.\n\n" + json.dumps(evidence, ensure_ascii=False)
            ),
            "response_format": {
                "type": "text", "mime_type": "application/json",
                "schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
            },
        }
        result = post("https://generativelanguage.googleapis.com/v1/interactions",
                      {"x-goog-api-key": api_key}, payload,
                      min(float(os.getenv("LLM_TIMEOUT_SECONDS", "30")), 30.0))
        parts = []
        for step in result.get("steps", []):
            if step.get("type") == "model_output":
                parts.extend(item.get("text", "") for item in step.get("content", []) if item.get("type") == "text")
        summary = json.loads("".join(parts)).get("summary", "").strip()
        if summary:
            with _LOCK:
                _CACHE[key] = {"text": summary, "source": "Gemini", "prompt_version": PROMPT_VERSION}
    except Exception:
        pass
    finally:
        with _LOCK:
            _PENDING.discard(key)


def get_analyst_summary(ticker, financials, earnings_quality):
    """Return immediately; optionally warm a Gemini result for a subsequent request."""
    period = (financials or {}).get("period", {})
    interpretation = (financials or {}).get("analyst_interpretation", {})
    resilience = (earnings_quality or {}).get("revenue_resilience", {})
    evidence = {
        "ticker": ticker, "period": period, "financial_interpretation": interpretation,
        "revenue_resilience": {
            key: resilience.get(key) for key in (
                "model_version", "revenue_resilience_score", "status", "confidence", "production_ready"
            )
        },
    }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
    key = (ticker, period.get("current"), PROMPT_VERSION, digest)
    with _LOCK:
        if key in _CACHE:
            return dict(_CACHE[key])
        enabled = (os.getenv("RESEARCH_GEMINI_ENABLED", "false").lower() == "true"
                   and bool(os.getenv("GEMINI_API_KEY", "").strip()))
        if enabled and key not in _PENDING:
            _PENDING.add(key)
            threading.Thread(target=_generate, args=(key, ticker, evidence), daemon=True).start()
    return {"text": _fallback(ticker, financials, earnings_quality),
            "source": "Deterministic evidence fallback", "prompt_version": PROMPT_VERSION}
