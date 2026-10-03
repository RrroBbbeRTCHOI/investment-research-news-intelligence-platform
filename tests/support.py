"""Offline provider boundary replay. Production analysis and routes remain real."""
import copy
import hashlib
import importlib
import io
import json
import math
import os
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "TSLA"]
TABS = ["overview", "financials", "valuation", "historical-trends", "earnings-quality", "sec-filing"]
HEAVY = {"overview", "valuation", "earnings-quality"}

# Additive provider metadata used only by the Level-5 Research presentation.
# Legacy golden tests remove these fields before comparing the unchanged
# analytical context and calculations.
RESEARCH_UI_COMPANY_FIELDS = {
    "enterprise_value_raw", "enterprise_value", "daily_change_raw",
    "daily_change", "daily_change_percent_raw", "daily_change_percent",
    "sector", "industry", "description",
}


def strip_research_ui_company_fields(company):
    for key in RESEARCH_UI_COMPANY_FIELDS:
        company.pop(key, None)
    return company


def normalize(value):
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return {"__dataframe__": {"index": normalize(list(value.index)),
                "columns": normalize(list(value.columns)), "data": normalize(value.values.tolist())}}
    if isinstance(value, pd.Series):
        return {"__series__": {"index": normalize(list(value.index)), "data": normalize(value.tolist())}}
    if isinstance(value, pd.Timestamp):
        return {"__timestamp__": value.isoformat()}
    if hasattr(value, "item"):
        return normalize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {"__nonfinite__": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unrecordable result type: {type(value)}")


def first_difference(expected, actual, path="$"):
    if type(expected) is not type(actual):
        return f"{path}: type {type(expected).__name__} != {type(actual).__name__}"
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return f"{path}: missing={expected.keys()-actual.keys()}, added={actual.keys()-expected.keys()}"
        for key in expected:
            diff = first_difference(expected[key], actual[key], f"{path}.{key}")
            if diff:
                return diff
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: length {len(expected)} != {len(actual)}"
        for i, (left, right) in enumerate(zip(expected, actual)):
            diff = first_difference(left, right, f"{path}[{i}]")
            if diff:
                return diff
    elif expected != actual:
        return f"{path}: expected {expected!r}, got {actual!r}"
    return None


class OfflineViolation(BaseException):
    """Cannot be swallowed by production's broad except Exception handlers."""


class Replay:
    def __init__(self):
        self.raw = json.loads((FIXTURES / "providers.json").read_text())
        # Supplemental synthetic Treasury quote; original golden provider recordings stay immutable.
        self.raw["yahoo"].update(json.loads((ROOT / "tests/moat3_market_fixture.json").read_text()))
        self.calls = []
        self.failures = set()
        self.now = 1_800_000_000.0
        self.stack = ExitStack()

    def __enter__(self):
        try:
            return self._enter()
        except BaseException:
            self.stack.close()
            raise

    def _enter(self):
        self.stack.enter_context(patch.dict(os.environ, {
            "FINANCIAL_API_KEY": "offline-fixture-only", "SEC_USER_AGENT": "offline-test@example.invalid",
            "HISTORICAL_TREND_YEARS": "5", "DEFAULT_BENCHMARK": "SPY", "DEFAULT_TECH_BENCHMARK": "QQQ",
        }))
        self.stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
        self.stack.enter_context(patch("socket.create_connection", side_effect=self.block))
        self.stack.enter_context(patch("socket.getaddrinfo", side_effect=self.block))
        self.stack.enter_context(patch("socket.gethostbyname", side_effect=self.block))
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=self.block))
        self.stack.enter_context(patch.object(socket.socket, "connect_ex", side_effect=self.block))
        self.stack.enter_context(patch("requests.sessions.Session.request", side_effect=self.block))
        self.stack.enter_context(patch("requests.get", side_effect=self.get))
        self.stack.enter_context(patch("yfinance.Ticker", side_effect=self.ticker))
        self.stack.enter_context(patch("curl_cffi.requests.Session.request", side_effect=self.block))
        self.stack.enter_context(patch("time.time", side_effect=lambda: self.now))
        self.logs = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.logs))
        self.app_module = importlib.import_module("app")
        self.context = importlib.import_module("src.ui.research_context")
        self.fmp = importlib.import_module("src.data.historical_financial_data")
        # Tests may import pure EQ helpers before Replay enters its environment.
        self.stack.enter_context(patch.object(self.fmp, "FINANCIAL_API_KEY", "offline-fixture-only"))
        temp = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="screener-baseline-"))
        self.cache_dir = Path(temp)
        self.stack.enter_context(patch.object(self.fmp, "HISTORICAL_CACHE_DIR", self.cache_dir))
        save = self.fmp._save_cache
        def save_with_controlled_mtime(endpoint, ticker, years, data):
            result = save(endpoint, ticker, years, data)
            # The OS clock is not patched: match real file mtimes to the test clock.
            path = self.fmp._build_cache_path(endpoint, ticker, years)
            if path.exists():
                os.utime(path, (self.now, self.now))
            return result
        self.stack.enter_context(patch.object(self.fmp, "_save_cache", side_effect=save_with_controlled_mtime))
        self.clear_caches()
        return self

    def __exit__(self, *args):
        self.clear_caches()
        return self.stack.__exit__(*args)

    def clear_caches(self):
        # New service cache is part of application state, not a golden fixture.
        from src.services.cache import clear
        clear()
        self.app_module.COMPANY_CACHE.clear()
        self.app_module.SCREENER_COMPANY_CACHE.clear()
        self.app_module.SCREENER_CACHE.update(data=None, timestamp=0)

    @staticmethod
    def block(*args, **kwargs):
        raise OfflineViolation("Network is forbidden in regression tests")

    def record(self, kind, ticker, detail=""):
        self.calls.append((kind, ticker, detail))
        if (kind, ticker) in self.failures:
            raise requests.Timeout(f"Injected {kind} failure for {ticker}")

    def ticker(self, symbol):
        symbol = symbol.upper().strip()
        if symbol not in self.raw["yahoo"]:
            raise OfflineViolation(f"No Yahoo fixture for {symbol}")
        replay = self
        class Ticker:
            def __getattr__(self, name):
                if name not in {"info", "financials", "balance_sheet", "cashflow"}:
                    raise OfflineViolation(f"Unrecorded Yahoo property {name}")
                replay.record(name, symbol)
                raw = replay.raw["yahoo"][symbol]
                if name == "info":
                    return copy.deepcopy(raw[name])
                return pd.DataFrame(raw[name], index=pd.to_datetime(raw["dates"])).T

            def history(self, period=None, start=None, end=None):
                replay.record("history", symbol, str(period or (str(start), str(end))))
                rows = replay.raw["yahoo"][symbol]["history"]
                frame = pd.DataFrame(rows, columns=["Date", "Close"])
                frame.index = pd.to_datetime(frame.pop("Date"))
                if start is not None and end is not None:
                    return frame[(frame.index >= pd.Timestamp(start)) & (frame.index < pd.Timestamp(end))].copy()
                counts = {"5d": 5, "6mo": 126, "1y": 252, "5y": len(frame)}
                if period not in counts:
                    raise OfflineViolation(f"Unrecorded Yahoo history period {period}")
                return frame.tail(counts[period]).copy()
        return Ticker()

    def get(self, url, **kwargs):
        sec = self.raw["sec"]
        result = None
        if url == "https://www.sec.gov/files/company_tickers.json":
            self.record("sec_cik", "ALL")
            result = {str(i): {"ticker": ticker, "cik_str": row["cik"]} for i, (ticker, row) in enumerate(sec.items())}
        elif url.startswith("https://financialmodelingprep.com/stable/"):
            p = kwargs.get("params", {})
            ticker = p.get("symbol")
            endpoint = url.rsplit("/", 1)[-1]
            self.record("fmp", ticker, endpoint)
            key = f"{ticker}:{endpoint}:{p.get('limit')}"
            # V1.5 adds the existing balance endpoint to EQ. Phase 1 recorded
            # only AAPL balance data. Explicit unavailable responses for those
            # six known missing recordings; never synthesize financial facts.
            if (endpoint == "balance-sheet-statement" and ticker in TICKERS
                    and p.get("period") == "annual" and p.get("limit") == 5
                    and key not in self.raw["fmp"]):
                response = requests.Response()
                response.status_code = 503
                response._content = b'{"error":"Balance statement not recorded in frozen fixtures"}'
                return response
            if p.get("period") != "annual" or key not in self.raw["fmp"]:
                raise OfflineViolation(f"Unrecorded FMP request {key}")
            result = self.raw["fmp"][key]
        else:
            for ticker, row in sec.items():
                cik = f"{row['cik']:010d}"
                if url == f"https://data.sec.gov/submissions/CIK{cik}.json":
                    self.record("sec_submissions", ticker)
                    result = row["submissions"]
                elif url == f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json":
                    self.record("sec_facts", ticker)
                    result = row["facts"]
                else:
                    recent = row["submissions"]["filings"]["recent"]
                    valid = [f"https://www.sec.gov/Archives/edgar/data/{row['cik']}/{acc.replace('-', '')}/{doc}"
                             for acc, doc in zip(recent["accessionNumber"], recent["primaryDocument"])]
                    if url in valid:
                        self.record("sec_html", ticker)
                        result = row["html"]
                if result is not None:
                    break
        if result is None:
            raise OfflineViolation(f"Unrecorded HTTP URL: {url}")
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.encoding = "utf-8"
        response._content = (result if isinstance(result, str) else json.dumps(result)).encode()
        return response


def digest(content):
    return hashlib.sha256(content).hexdigest()
