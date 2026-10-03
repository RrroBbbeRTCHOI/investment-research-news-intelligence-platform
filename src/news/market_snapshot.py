"""Background Yahoo quote sampling and read-only Flask snapshot access."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
from .llm.analyzer import atomic_json

MARKETS=[('Hang Seng','^HSI','HKD'),('Shanghai A','000002.SS','CNY'),('Crude Oil','CL=F','USD'),
         ('Dow','^DJI','USD'),('S&P 500','^GSPC','USD'),('Nasdaq','^IXIC','USD')]
DEFAULT_STOCKS=['AAPL','MSFT','GOOGL','NVDA','AMZN','META','TSLA']

def finite(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError): return None

def yahoo_quote(symbol,currency):
    from src.data.yahoo_provider import history
    frame=history(symbol,period='5d',interval='1m',auto_adjust=False)
    if frame is None or frame.empty or 'Close' not in frame: return None
    close=frame['Close'].dropna()
    if close.empty: return None
    latest=close.index[-1];price=finite(close.iloc[-1])
    if latest.tzinfo is None or price is None or price<=0: return None
    # Compare with the last observed close of a prior exchange-local session.
    prior=close[[stamp.date()<latest.date() for stamp in close.index]]
    previous=finite(prior.iloc[-1]) if not prior.empty else None
    change=price-previous if previous is not None else None
    return {'symbol':symbol,'value':price,'change':change,'change_percent':change/previous*100 if previous else None,
            'timestamp':latest.to_pydatetime().astimezone(timezone.utc).isoformat(),'currency':currency,
            'source':'Yahoo Finance via existing yahoo_provider','status':'delayed',
            'definition':'Latest available unadjusted one-minute close; change versus prior observed session close. Not exchange real-time.'}

def refresh_markets(config, loader=yahoo_quote, now=None):
    path=config.state_dir/'market_snapshot.json'
    if not config.market_enabled: return {'status':'disabled'}
    now=now or datetime.now(timezone.utc).isoformat()
    try: old=json.loads(path.read_text())
    except (OSError,ValueError): old={}
    quotes={};failures=0
    # Fixed configured symbols prevent browser requests from causing provider work.
    stocks=os.getenv('NEWS_MARKET_TICKERS',','.join(DEFAULT_STOCKS)).split(',')[:30]
    symbols={symbol:currency for _,symbol,currency in MARKETS}
    symbols.update({s.strip().upper():'USD' for s in stocks if s.strip() and s.strip().isalnum()})
    for symbol,currency in symbols.items():
        try:
            q=loader(symbol,currency)
            if not q or finite(q.get('value')) is None or q['value']<=0: raise ValueError()
            stamp=datetime.fromisoformat(q['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError()
            quotes[symbol]={**q,'status':'delayed'}
        except Exception:
            failures+=1
            cached=old.get('quotes',{}).get(symbol)
            quotes[symbol]={**cached,'status':'stale'} if cached else {'symbol':symbol,'value':None,'status':'unavailable','currency':currency}
    snapshot={'generated_at':now,'status':'degraded' if failures else 'delayed','quotes':quotes}
    atomic_json(path,snapshot)
    return snapshot

def read_market_snapshot(root, config, now=None):
    path=config.state_dir/'market_snapshot.json'
    if not path.is_absolute(): path=Path(root)/path
    try: result=json.loads(path.read_text())
    except (OSError,ValueError): result={'status':'unavailable','quotes':{},'generated_at':None}
    at=now or datetime.now(timezone.utc)
    for quote in result.get('quotes',{}).values():
        if quote.get('value') is None: continue
        try:
            age=(at-datetime.fromisoformat(quote['timestamp'].replace('Z','+00:00'))).total_seconds()
            if age>config.market_interval*2 or age<0: quote['status']='stale'
        except (ValueError,TypeError,KeyError): quote['status']='stale'
    result['markets']=[{'name':name,**result.get('quotes',{}).get(symbol,{'symbol':symbol,'value':None,'status':'unavailable','currency':currency})} for name,symbol,currency in MARKETS]
    if any(q.get('status')=='stale' for q in result.get('quotes',{}).values()): result['status']='stale'
    result['poll_seconds']=max(60,config.market_interval)
    return result

def run_market_loop(config, stop):
    while not stop.is_set():
        try: refresh_markets(config)
        except (OSError,ValueError): pass
        stop.wait(config.market_interval)

if __name__=='__main__':
    from .live_config import LiveConfig
    config=LiveConfig.from_env()
    if config.market_enabled:
        while True:
            refresh_markets(config);time.sleep(config.market_interval)
    else: print('Market sampling disabled.')
