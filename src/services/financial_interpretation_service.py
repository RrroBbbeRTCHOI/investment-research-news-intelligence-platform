"""Independent Financials interpretation; reuse providers and optional upstream EQ."""
import logging
from src.data import historical_financial_data as fmp
from src.data.earnings_quality_inputs import _load_history
from src.data.reuse import scoped,reuse
from src.services.cache import cached
from src.analysis.financial_statement_bridges import normalize
from src.analysis.financial_statement_diagnostics import interpret



def _history_failure(kind, error):
    """Expose actionable loader failures without logging URLs or credentials.

    Loading already uses the same cache-miss path for all three statements.
    Do not misreport missing configuration as a missing accounting field.
    """
    reason = f"{type(error).__name__}; data unavailable."
    if isinstance(error, RuntimeError):
        message = str(error)
        if message.startswith("FMP API key is not configured."):
            reason = ("FMP API key is not configured and no valid annual cache is available. "
                      "Set FINANCIAL_API_KEY locally and restart the application; "
                      "the existing loader will fetch and cache this statement.")
        elif message.startswith("FMP returned HTTP "):
            import re
            match = re.match(r"FMP returned HTTP (\d{3}) for ", message)
            if match:
                reason = (f"FMP returned HTTP {match.group(1)}; annual data unavailable. "
                          "Check provider access or retry after the provider issue is resolved.")
        elif message.startswith("FMP request failed for "):
            reason = "FMP request failed; annual data unavailable. Check connectivity and retry."
        elif message.startswith(("FMP returned invalid JSON ", "Unexpected FMP response ")):
            reason = "FMP returned an unusable response; annual data unavailable."
    return f"{kind}: {reason}"


def _build(ticker,moat1):
    datasets={};errors=[]
    for kind,endpoint,loader in (
        ('income','income-statement',fmp.get_historical_income_statement),
        ('balance','balance-sheet-statement',fmp.get_historical_balance_sheet),
        ('cash','cash-flow-statement',fmp.get_historical_cash_flow_statement)):
        try:
            datasets[kind]=_load_history(ticker,endpoint,loader)
        except Exception as error:
            datasets[kind]=[]
            errors.append(_history_failure(kind, error))
    if moat1 is None:
        # Read through the existing service cache without initiating an EQ load.
        moat1=cached(('eq-diagnostics-v2-final',ticker),lambda:None,acceptable=lambda r:False)
    return interpret(ticker,normalize(ticker,datasets),moat1,errors)


@scoped
def build_financial_interpretation(ticker,moat1=None):
    ticker=ticker.strip().upper()
    try:
        if moat1 is not None:return _build(ticker,moat1)
        return reuse(('financial-interpretation-v1',ticker),lambda:_build(ticker,None))
    except Exception:
        logging.getLogger(__name__).exception('Financial interpretation unavailable for %s',ticker)
        return interpret(ticker,[],errors=['Interpretation service failed; legacy financial cards remain available.'])
