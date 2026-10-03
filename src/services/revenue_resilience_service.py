"""Production adapter for the approved Revenue Resilience V1.4 model."""
from pathlib import Path
from dataclasses import asdict

import pandas as pd

from scripts.revenue_resilience_v1_4 import MODEL_VERSION, calculate_company
from src.data.reuse import scoped
from src.services.cache import cached


ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "reports/revenue_resilience_v1/revenue_segment_history_mag7.csv"


def _build(ticker):
    history = pd.read_csv(HISTORY_PATH)
    ticker = ticker.upper().strip()
    company_history = history[history["ticker"].str.upper() == ticker]
    if company_history.empty:
        return {
            "ticker": ticker,
            "model_version": MODEL_VERSION,
            "revenue_resilience_score": None,
            "status": "INSUFFICIENT_HISTORY",
            "confidence": "NONE",
            "production_ready": False,
            "reasons": ["No approved segment-history observations are available."],
        }
    latest_fiscal_year = int(company_history["fiscal_year"].max())
    result, segment_details = calculate_company(history, ticker, latest_fiscal_year)
    return {**result, "model_version": MODEL_VERSION,
            "segment_details": [asdict(item) for item in segment_details]}


@scoped
def get_revenue_resilience(ticker):
    """Return V1.4 output; 2Y values remain visible but are not formal scores."""
    ticker = ticker.upper().strip()
    return cached(
        ("revenue-resilience", MODEL_VERSION, ticker, HISTORY_PATH.stat().st_mtime_ns),
        lambda: _build(ticker),
        acceptable=lambda result: result.get("status") != "NOT_SCORED",
    )
