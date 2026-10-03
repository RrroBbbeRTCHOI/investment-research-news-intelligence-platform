"""Local visual QA only. Uses frozen provider replay, never live/mock Figma data."""
from copy import deepcopy
import sys
from unittest.mock import patch
from support import Replay

def main():
    saved = {}
    with Replay() as replay:
        app_module = replay.app_module
        from src.data.reuse import data_scope
        from src.ui.research_dossier import build_research_dossier_context
        for ticker in ("AAPL", "NVDA", "MSFT"):
            with data_scope(persistent=True):
                saved[ticker] = build_research_dossier_context(ticker)
        rows = [{"ticker": ticker} for ticker in saved]
    app_module.build_research_dossier_context = lambda ticker: deepcopy(saved.get(ticker, saved["AAPL"]))
    app_module.get_company_context_cached = lambda ticker, active_tab: deepcopy(saved.get(ticker, saved["AAPL"])["company"])
    app_module.get_screener_rows_cached = lambda: rows
    app_module.app.config["TEMPLATES_AUTO_RELOAD"] = True
    app_module.app.jinja_env.auto_reload = True
    # Visual QA must not start live News ingestion. This preview reports unavailable.
    from flask import jsonify
    @app_module.app.route("/qa/viewport")
    def viewport_harness():
        from flask import request, render_template_string
        from urllib.parse import urlencode
        width = 390 if request.args.get("width") == "390" else 1440
        height = 844 if width == 390 else 900
        ticker = request.args.get("ticker", "AAPL")
        if ticker not in saved:
            ticker = "AAPL"
        target = ("http://127.0.0.1:5092/" if request.args.get("target") == "figma"
                  else "/research?" + urlencode({"ticker":ticker,"tab":request.args.get("tab","overview")}))
        return render_template_string(
            '<!doctype html><html><head><title>Offline responsive QA</title></head>'
            '<body style="margin:0"><iframe title="Reference viewport" src="{{ target }}" '
            'width="{{ width }}" height="{{ height }}" style="display:block;border:0"></iframe></body></html>',
            target=target, width=width, height=height)

    @app_module.app.before_request
    def offline_news():
        from flask import request
        if request.path.startswith("/api/news"):
            return jsonify(error="Offline visual QA — News ingestion disabled"), 503
    print("OFFLINE FIXTURE PREVIEW: http://127.0.0.1:5091/research", file=sys.stderr)
    app_module.app.run(host="127.0.0.1", port=5091, use_reloader=False)

if __name__ == "__main__":
    main()
