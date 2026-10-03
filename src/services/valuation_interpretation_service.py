"""Isolated additive Valuation interpretation: never writes a rating or legacy model."""
import logging
from src.data.reuse import scoped,reuse
from src.data.valuation_inputs import load_valuation_inputs
from src.analysis.valuation_interpretation import build_interpretation


@scoped
def build_valuation_interpretation(ticker,basic=None):
    ticker=ticker.strip().upper()
    try:
        return reuse(('moat3-interpretation',ticker),lambda:build_interpretation(load_valuation_inputs(ticker),basic))
    except Exception as error:
        logging.getLogger(__name__).warning('Moat 3 unavailable for %s (%s)',ticker,type(error).__name__)
        return {'ticker':ticker,'status':'Insufficient Evidence',
                'error':'Moat 3 input/configuration failed validation; legacy valuation remains available.'}
