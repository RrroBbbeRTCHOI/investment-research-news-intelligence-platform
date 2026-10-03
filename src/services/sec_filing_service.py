"""SEC presentation service using the existing EDGAR metadata provider."""
import logging

from src.services.company_service import get_company_data
from src.data.reuse import scoped
from src.services.cache import cached


def _build_sec_filing(ticker, peers):
    result = {"basic": get_company_data(ticker), "sec_filings": []}
    try:
        from src.data.sec_filings import get_filing_by_form

        result["sec_filings"] = [
            filing
            for form in ("10-K", "10-Q", "8-K")
            if (filing := get_filing_by_form(ticker, form)) is not None
        ]
    except Exception as error:
        logging.getLogger(__name__).exception(
            "SEC filing metadata unavailable for %s", ticker
        )
        result["sec_error"] = (
            "SEC filing metadata is temporarily unavailable. "
            "Existing research data remains available."
        )
    return result


@scoped
def build_sec_filing(ticker, peers):
    """Reuse EDGAR metadata across dossier and legacy section URLs."""
    return cached(
        ("research-sec-metadata-v1", ticker),
        lambda: _build_sec_filing(ticker, peers),
        acceptable=lambda result: not result.get("sec_error") and bool(result["sec_filings"]),
    )


@scoped
def get_filing_evidence(ticker, form_type="10-K"):
    from src.data.sec_filings import get_filing_by_form, get_filing_text
    from src.analysis.filing_classifier import classify_filing_text

    filing = get_filing_by_form(ticker, form_type)
    text = get_filing_text(ticker, form_type)
    return {
        "filing": filing,
        "text": text,
        "classification": classify_filing_text(text) if text else [],
    }
