"""One-time deterministic synthetic provider seed; never downloads data."""
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "fixtures"
UNIVERSE = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "TSLA"]


def main():
    if (OUT / "providers.json").exists():
        raise SystemExit("Refusing to replace existing provider fixtures.")
    dates = [f"{year}-12-31" for year in range(2025, 2020, -1)]
    payload = {"yahoo": {}, "sec": {}, "fmp": {}}
    all_tickers = UNIVERSE + ["AMD", "AVGO", "INTC", "GM", "F", "SPY", "QQQ"]
    trading_days = []
    day = date(2021, 1, 1)
    while day <= date(2025, 12, 31):
        if day.weekday() < 5:
            trading_days.append(day.isoformat())
        day += timedelta(days=1)
    for i, ticker in enumerate(all_tickers):
        scale = (i + 2) * 1_000_000_000
        growth = 0.04 + i * 0.012
        revenues = [scale * 10 / (1 + growth) ** j for j in range(5)]
        margin = 0.15 + i * 0.008
        price = 30 + i * 17
        def row(fraction):
            return [v * fraction for v in revenues]
        statements = {
            "financials": {
                "Total Revenue": revenues, "Net Income": row(margin * 0.8),
                "Operating Income": row(margin), "Pretax Income": row(margin * 1.05),
                "Tax Provision": row(margin * 1.05 * 0.21), "Gross Profit": row(0.45),
                "EBITDA": row(margin + 0.04),
                "Diluted EPS": [v * margin * 0.8 / 1_000_000_000 for v in revenues],
            },
            "balance_sheet": {
                "Total Debt": row(0.18), "Net Debt": row(0.10),
                "Cash And Cash Equivalents": row(0.08),
                "Stockholders Equity": row(0.4), "Total Assets": row(0.8),
                "Current Assets": row(0.3), "Current Liabilities": row(0.15),
            },
            "cashflow": {
                "Operating Cash Flow": row(margin * 1.2),
                "Capital Expenditure": row(-0.045),
                "Free Cash Flow": row(margin * 1.2 - 0.045),
                "Depreciation And Amortization": row(0.04),
                "Change In Working Capital": row(-0.01),
            },
        }
        history = [[d, round(price * (0.6 + 0.4 * j / (len(trading_days) - 1))
                             * (1 + 0.012 * math.sin(j * (0.11 + i * 0.01))), 8)]
                   for j, d in enumerate(trading_days)]
        payload["yahoo"][ticker] = {
            "dates": dates, **statements, "history": history,
            "info": {"longName": f"Synthetic {ticker} Research Fixture", "exchange": "TEST",
                     "currentPrice": price, "marketCap": price * 1_000_000_000,
                     "enterpriseValue": price * 1_000_000_000 + revenues[0] * 0.1,
                     "trailingPE": 12 + i * 2, "forwardPE": 11 + i * 1.8,
                     "priceToBook": 3 + i * 0.2, "priceToSalesTrailing12Months": 2 + i * 0.1,
                     "enterpriseToEbitda": 9 + i, "sharesOutstanding": 1_000_000_000,
                     "beta": 0.85 + i * 0.08},
        }
        if ticker not in UNIVERSE:
            continue
        cik = 9000000 + i
        accession = f"{cik:010d}-26-000001"
        facts = {"facts": {"us-gaap": {}}}
        fact_rows = {
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": row(margin * 1.05),
            "Revenues": revenues, "NetIncomeLoss": row(margin * 0.8),
        }
        for name, values in fact_rows.items():
            facts["facts"]["us-gaap"][name] = {"units": {"USD": [
                {"start": f"{2025-j}-01-01", "end": dates[j], "val": value,
                 "fy": 2025-j, "fp": "FY", "form": "10-K",
                 "filed": f"{2026-j}-02-01", "accn": accession}
                for j, value in enumerate(values)]}}
        payload["sec"][ticker] = {
            "cik": cik, "facts": facts,
            "submissions": {"filings": {"recent": {
                "form": ["10-K", "10-Q"],
                "accessionNumber": [accession, f"{cik:010d}-26-000002"],
                "filingDate": ["2026-02-01", "2026-05-01"],
                "reportDate": ["2025-12-31", "2026-03-31"],
                "primaryDocument": ["annual.htm", "quarterly.htm"]}}},
            "html": "<html><body><h1>SYNTHETIC TEST FILING — NOT COMPANY DISCLOSURE</h1>"
                    "<p>Amounts in millions. Years ended December 31, 2025, 2024, 2023.</p>"
                    "<p>We recognized gains on equity securities in net income. "
                    "Gain (loss) on equity securities, net 120 80 40. "
                    "These investment gains were included in other income.</p>"
                    "<script>ignored</script><style>ignored</style></body></html>",
        }
    provenance = []
    for p in sorted((ROOT / "data/cache/historical_financials").glob("*.json")):
        raw = p.read_bytes()
        cached = json.loads(raw)
        key = f"{cached['ticker']}:{cached['endpoint']}:{cached['years']}"
        payload["fmp"][key] = cached["data"]
        provenance.append({"file": str(p.relative_to(ROOT)),
                           "sha256": hashlib.sha256(raw).hexdigest()})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "providers.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    (OUT / "provenance.json").write_text(json.dumps({
        "schema": 1, "as_of": "2025-12-31",
        "yahoo_and_sec": "Deterministic synthetic inputs, NOT real company observations or live captures.",
        "fmp": "Raw data copied from user ZIP caches; authenticity/freshness not independently verified. Never blended into Yahoo inputs.",
        "fmp_source_files": provenance,
        "scope": "Behavior characterization only; not validation of financial methodology or live integrations.",
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
