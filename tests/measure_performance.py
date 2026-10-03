import sys,json,time,collections,pathlib
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'tests'))
from support import Replay,TICKERS,TABS
from baseline import route_result
results={}
for ticker in TICKERS:
 for tab in TABS:
  with Replay() as r:
   start=time.perf_counter();route_result(r,ticker,tab);elapsed=time.perf_counter()-start
   cold=dict(collections.Counter(c[0] for c in r.calls));r.calls.clear()
   start=time.perf_counter();route_result(r,ticker,tab);warm=time.perf_counter()-start
   results[ticker+'/'+tab]={'cold_calls':sum(cold.values()),'by_kind':cold,'cold_seconds':elapsed,'warm_calls':len(r.calls),'warm_seconds':warm}
with Replay() as r:
 route_result(r,'AAPL','overview');r.calls.clear();route_result(r,'AAPL','valuation')
 cross={'calls':len(r.calls),'by_kind':dict(collections.Counter(c[0] for c in r.calls))}
pathlib.Path(sys.argv[2]).write_text(json.dumps({'cases':results,'overview_to_valuation':cross},indent=2)+'\n')
