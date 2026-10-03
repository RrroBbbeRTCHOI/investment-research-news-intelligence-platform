"""Explicit one-time recording. Tests NEVER regenerate or accept snapshots."""
import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from support import Replay, ROOT, FIXTURES, TICKERS, TABS, digest
from baseline import route_result, reports, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-initial-baseline", action="store_true")
    args = parser.parse_args()
    if not args.record_initial_baseline:
        parser.error("Pass --record-initial-baseline explicitly; requires review of unchanged production sources.")
    out = FIXTURES / "baseline"
    if out.exists():
        raise SystemExit("Refusing to overwrite baseline. Review changes and preserve the old baseline separately.")
    collected = {}
    for ticker in TICKERS:
        print(f"Recording real pipeline: {ticker}", file=sys.stderr)
        with Replay() as replay:
            routes = {}
            for tab in TABS:
                replay.clear_caches()
                routes[tab] = route_result(replay, ticker, tab)
            collected[ticker] = {"routes": routes, "reports": reports(replay, ticker)}
    with Replay() as replay:
        failure_results = failures(replay)
    # Write only after every collection completed successfully.
    out.mkdir()
    for ticker, result in collected.items():
        (out / f"{ticker}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    (out / "failures.json").write_text(json.dumps(failure_results, indent=2, allow_nan=False) + "\n")
    production = [p for p in ROOT.rglob("*") if p.is_file() and "tests" not in p.relative_to(ROOT).parts
                  and "__pycache__" not in p.parts and p.name != ".env"]
    manifest = {
        "schema": 1, "python": platform.python_version(),
        "description": "Golden outputs from unrefactored production code with synthetic Yahoo/SEC inputs and supplied FMP caches; not live company valuations.",
        "versions": {name: importlib.metadata.version(name) for name in (
            "Flask", "Jinja2", "pandas", "numpy", "yfinance", "requests", "beautifulsoup4", "python-dotenv", "curl_cffi")},
        "source_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sorted(production)},
        "fixture_sha256": {str(p.relative_to(FIXTURES)): digest(p.read_bytes()) for p in sorted(FIXTURES.rglob("*")) if p.is_file()},
    }
    (FIXTURES / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Baseline recorded. Normal test runs are read-only.", file=sys.stderr)


if __name__ == "__main__":
    main()
