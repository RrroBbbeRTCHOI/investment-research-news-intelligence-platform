"""Reproducible offline timings. These are NOT live-provider latency estimates."""
import json
import sys
from time import perf_counter
from support import Replay
from src.data.reuse import data_scope
from src.ui.research_dossier import build_research_dossier_context

def timed(action):
    start = perf_counter()
    result = action()
    return result, round((perf_counter() - start) * 1000, 2)

def main():
    rows = []
    for ticker in ("AAPL", "NVDA", "MSFT"):
        with Replay() as replay:
            def dossier():
                with data_scope(persistent=True):
                    return build_research_dossier_context(ticker)
            _, cold = timed(dossier)
            replay.calls.clear()
            _, warm = timed(dossier)
            warm_calls = len(replay.calls)
            replay.clear_caches()
            client = replay.app_module.app.test_client()
            response, route_cold = timed(lambda: client.get("/research?ticker=" + ticker))
            assert response.status_code == 200
            replay.calls.clear()
            response, route_warm = timed(lambda: client.get("/research?ticker=" + ticker + "&tab=historical-trends"))
            assert response.status_code == 200
            rows.append(dict(ticker=ticker, dossier_cold_ms=cold, dossier_warm_ms=warm,
                             route_cold_ms=route_cold, route_warm_ms=route_warm,
                             warm_dossier_provider_calls=warm_calls,
                             warm_route_provider_calls=len(replay.calls)))
    print(json.dumps({"environment":"Frozen offline provider replay; no network latency; perf_counter wall clock", "results":rows},indent=2))

if __name__ == "__main__":
    main()
