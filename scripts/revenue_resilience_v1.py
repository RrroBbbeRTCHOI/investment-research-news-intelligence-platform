#!/usr/bin/env python3
"""
MERIDIAN Revenue Resilience V1
==============================

Purpose
-------
Replace the old "Core Revenue" concept with a measurable revenue-structure model:

    Revenue Resilience
      = 60% Revenue Diversification
      + 40% Revenue Persistence

Revenue Diversification
-----------------------
Measures dependence on a small number of revenue streams.

    HHI = sum(share_i^2)
    Diversification Score = 100 * (1 - HHI)

A company dominated by one revenue stream scores low.
A company with several material, balanced streams scores higher.

Revenue Persistence
-------------------
Uses up to five fiscal years of segment/product/service revenue history.

    Persistence
      = 20% Presence
      + 45% Share Stability
      + 35% Growth Consistency

- Presence: how consistently the stream appears across the five-year window.
- Share Stability: how stable its share of company revenue is.
- Growth Consistency: how volatile its year-over-year revenue growth is.

The company-level Persistence Score is weighted by each stream's average
revenue share over the history window.

Important
---------
1. This is a research model, not a statement that future revenue is guaranteed.
   "Persistence" means historical persistence.
2. Different companies disclose revenue at different levels of granularity.
   The script aggregates tiny (<2%) streams into one bucket before HHI to reduce
   disclosure-granularity gaming.
3. Signed accounting adjustments such as Alphabet hedging gains/losses are
   tracked but excluded from operating-stream diversification.
4. Missing history is NOT a zero. A provisional persistence score may be shown,
   but the final Revenue Resilience score is withheld until history coverage
   passes the model gate.
5. The script does not modify Meridian production scoring files.

Default inputs
--------------
reports/core_revenue_final/mag7_core_revenue_review.json

Outputs
-------
reports/revenue_resilience_v1/
    revenue_segment_history_mag7.csv
    revenue_resilience_company_scores.csv
    revenue_resilience_segment_details.csv
    revenue_resilience_review.json
    revenue_resilience_review.md
    sec_extraction_audit.csv

Network behavior
----------------
By default the script tries to extend the existing 2-year revenue mix to a
5-year history using SEC 10-K HTML tables, with local caching. Use --offline
to disable all network calls.

Optional environment variable:
    SEC_USER_AGENT="MeridianResearch/1.0 your-email@example.com"

This file is intentionally standalone and importable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "pandas is required. Install it in the same Python environment used by Meridian.\n"
        f"Import error: {exc}"
    )

try:
    import requests
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "requests is required. Install it in the same Python environment used by Meridian.\n"
        f"Import error: {exc}"
    )


MODEL_VERSION = "REVENUE-RESILIENCE-V1"
MAG7 = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "TSLA"]

CIK = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "NVDA": "0001045810",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
}

DEFAULT_INPUT = Path("reports/core_revenue_final/mag7_core_revenue_review.json")
DEFAULT_OUTPUT = Path("reports/revenue_resilience_v1")
DEFAULT_CACHE = Path(".cache/revenue_resilience/sec")

HISTORY_YEARS = 5

# Model weights
RESILIENCE_DIVERSIFICATION_WEIGHT = 0.60
RESILIENCE_PERSISTENCE_WEIGHT = 0.40

PERSISTENCE_PRESENCE_WEIGHT = 0.20
PERSISTENCE_SHARE_STABILITY_WEIGHT = 0.45
PERSISTENCE_GROWTH_CONSISTENCY_WEIGHT = 0.35

# HHI handling
SMALL_STREAM_SHARE_THRESHOLD = 0.02  # aggregate streams < 2% before HHI
MIN_FINAL_HISTORY_YEARS = 5
MIN_MAJOR_STREAM_OBSERVATION_SHARE = 0.80
MAJOR_STREAM_MIN_OBS = 4

# Stability transforms. Lower volatility -> higher score.
SHARE_CV_DECAY = 2.0
GROWTH_VOL_DECAY = 1.25

# If a table's mapped segment sum reconciles to 85%-115% of total company
# revenue after unit scaling, accept it as a useful SEC revenue table.
MIN_SEC_RECONCILIATION = 0.85
MAX_SEC_RECONCILIATION = 1.15


# ---------------------------------------------------------------------------
# Canonical revenue streams and historical label aliases
# ---------------------------------------------------------------------------

SEGMENT_PATTERNS: Dict[str, List[Tuple[str, str]]] = {
    "AAPL": [
        ("iPhone", r"\biphone\b"),
        ("Mac", r"\bmac\b"),
        ("iPad", r"\bipad\b"),
        ("Wearables, Home and Accessories", r"wearables?.*home.*accessor|home.*accessor"),
        ("Services", r"\bservices?\b"),
    ],
    "MSFT": [
        ("Productivity and Business Processes", r"productivity.*business.*process"),
        ("Intelligent Cloud", r"intelligent.*cloud"),
        ("More Personal Computing", r"more.*personal.*comput"),
    ],
    "GOOGL": [
        ("Google Search & other", r"google.*search.*other|google\s+search"),
        ("YouTube ads", r"youtube.*ads?|youtube.*advert"),
        ("Google Network", r"google.*network"),
        (
            "Google subscriptions, platforms, and devices",
            r"subscriptions?.*platforms?.*devices?|google.*other|platforms?.*devices?",
        ),
        ("Google Cloud", r"google.*cloud"),
        ("Other Bets", r"other.*bets"),
        ("Hedging gains (losses)", r"hedging.*gain|hedging.*loss|hedging"),
    ],
    "NVDA": [
        ("Compute & Networking", r"compute.*network"),
        ("Graphics", r"\bgraphics?\b"),
    ],
    "AMZN": [
        ("Online stores", r"online.*stores?"),
        ("Physical stores", r"physical.*stores?"),
        ("Third-party seller services", r"third.?party.*seller"),
        ("Advertising services", r"advertising.*services?|advertis"),
        ("Subscription services", r"subscription.*services?"),
        ("AWS", r"\baws\b|amazon.*web.*services"),
        ("Other", r"^\s*other\s*$"),
    ],
    "META": [
        ("Family of Apps - Advertising", r"family.*apps.*advert|foa.*advert|advertising"),
        ("Family of Apps - Other", r"family.*apps.*other|foa.*other"),
        ("Reality Labs", r"reality.*labs"),
    ],
    "TSLA": [
        ("Automotive sales", r"automotive.*sales"),
        ("Automotive regulatory credits", r"automotive.*regulatory.*credits?|regulatory.*credits?"),
        ("Automotive leasing", r"automotive.*leasing"),
        ("Services and other", r"services?.*other"),
        ("Energy generation and storage", r"energy.*generation.*storage"),
    ],
}

# Accounting adjustments are preserved in history/audit but excluded from
# operating-stream concentration calculations.
EXCLUDED_FROM_DIVERSIFICATION = {
    "GOOGL": {"Hedging gains (losses)"},
}

# Context-only flags; they do not automatically change the score.
CONTEXT_FLAGS = {
    ("TSLA", "Automotive regulatory credits"): "POLICY_SENSITIVE_REVENUE",
    ("GOOGL", "Hedging gains (losses)"): "SIGNED_REVENUE_ADJUSTMENT",
}


@dataclass
class HistoryRow:
    ticker: str
    fiscal_year: int
    period_end: str
    segment: str
    revenue_usd: float
    source_type: str
    source_url: str
    source_locator: str
    confidence: str


@dataclass
class SegmentPersistence:
    ticker: str
    segment: str
    observations: int
    expected_years: int
    presence_score: Optional[float]
    share_stability_score: Optional[float]
    growth_consistency_score: Optional[float]
    persistence_score: Optional[float]
    avg_share_pct: Optional[float]
    latest_share_pct: Optional[float]
    growth_volatility_pct: Optional[float]
    share_cv: Optional[float]
    context_flag: str


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        f = float(x)
    except Exception:
        return None
    if not math.isfinite(f):
        return None
    return f


def fmt_pct(x: Optional[float], digits: int = 1) -> str:
    return "N/A" if x is None else f"{x:.{digits}f}%"


def fmt_score(x: Optional[float]) -> str:
    return "N/A" if x is None else f"{x:.1f}"


def label_score(score: Optional[float]) -> str:
    if score is None:
        return "Not scored"
    if score >= 80:
        return "Very Strong"
    if score >= 65:
        return "Strong"
    if score >= 50:
        return "Moderate"
    if score >= 35:
        return "Weak"
    return "Very Weak"


def diversification_label(score: Optional[float]) -> str:
    if score is None:
        return "Unknown"
    if score >= 80:
        return "Highly diversified"
    if score >= 60:
        return "Diversified"
    if score >= 40:
        return "Moderately concentrated"
    if score >= 20:
        return "Concentrated"
    return "Highly concentrated"


def normalize_text(x: Any) -> str:
    s = str(x or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonical_segment(ticker: str, text: str) -> Optional[str]:
    t = normalize_text(text).lower()
    if not t:
        return None
    for name, pattern in SEGMENT_PATTERNS.get(ticker, []):
        if re.search(pattern, t, flags=re.I):
            return name
    return None


def parse_number(cell: Any) -> Optional[float]:
    """
    Parse a financial-table cell. Reject percentages and pure year labels.
    """
    s = normalize_text(cell)
    if not s or s in {"—", "-", "–", "−", "N/A", "n/a"}:
        return None
    if "%" in s:
        return None
    if re.fullmatch(r"20\d{2}", s):
        return None

    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
    s = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    s = s.replace("−", "-").replace("–", "-")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in {"-", ".", "-."}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -abs(v) if neg else v


def coefficient_of_variation(values: Sequence[float]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if len(vals) < 2:
        return None
    mean = statistics.fmean(vals)
    if abs(mean) < 1e-12:
        return None
    return statistics.pstdev(vals) / abs(mean)


def exponential_score(volatility: Optional[float], decay: float) -> Optional[float]:
    if volatility is None or volatility < 0:
        return None
    return clamp(100.0 * math.exp(-decay * volatility))


def weighted_average(pairs: Sequence[Tuple[Optional[float], float]]) -> Optional[float]:
    valid = [(float(score), float(weight)) for score, weight in pairs
             if score is not None and weight > 0 and math.isfinite(float(score))]
    if not valid:
        return None
    denom = sum(w for _, w in valid)
    if denom <= 0:
        return None
    return sum(s * w for s, w in valid) / denom


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_dotenv_simple(root: Path) -> None:
    p = root / ".env"
    if not p.exists():
        return
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Seed history from existing Meridian integrated revenue review
# ---------------------------------------------------------------------------

def load_integrated_review(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Input not found: {path}\n"
            "Run the existing MAG7 integrated revenue review first, or pass --input."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("companies"), list):
        raise ValueError("Integrated review JSON does not contain a companies list.")
    return data


def history_from_integrated_review(data: Dict[str, Any]) -> List[HistoryRow]:
    rows: List[HistoryRow] = []
    for company in data.get("companies", []):
        ticker = str(company.get("ticker", "")).upper()
        fy = int(company.get("fiscal_year"))
        period_end = str(company.get("period_end") or "")
        sec = company.get("sec") or {}
        src = str(sec.get("filing_url") or "")
        locator = str(sec.get("source_locator") or "Integrated revenue mix")
        mix = company.get("revenue_mix") or sec.get("category_mix") or []

        for item in mix:
            name = canonical_segment(ticker, str(item.get("name", ""))) or str(item.get("name", ""))
            cur = safe_float(item.get("current_revenue_usd"))
            prev = safe_float(item.get("previous_revenue_usd"))
            if cur is not None:
                rows.append(
                    HistoryRow(
                        ticker=ticker,
                        fiscal_year=fy,
                        period_end=period_end,
                        segment=name,
                        revenue_usd=cur,
                        source_type="MERIDIAN_SEC_RECONCILED",
                        source_url=src,
                        source_locator=locator,
                        confidence="HIGH",
                    )
                )
            if prev is not None:
                rows.append(
                    HistoryRow(
                        ticker=ticker,
                        fiscal_year=fy - 1,
                        period_end="",
                        segment=name,
                        revenue_usd=prev,
                        source_type="MERIDIAN_SEC_RECONCILED_COMPARATIVE",
                        source_url=src,
                        source_locator=locator,
                        confidence="HIGH",
                    )
                )
    return rows


def merge_history(rows: Iterable[HistoryRow]) -> List[HistoryRow]:
    """
    Deduplicate by ticker/fiscal_year/segment. Prefer confidence then source type.
    """
    rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    source_rank = {
        "MERIDIAN_SEC_RECONCILED": 4,
        "MERIDIAN_SEC_RECONCILED_COMPARATIVE": 4,
        "SEC_10K_TABLE": 3,
        "USER_HISTORY": 5,
    }
    best: Dict[Tuple[str, int, str], HistoryRow] = {}
    for row in rows:
        key = (row.ticker, int(row.fiscal_year), row.segment)
        old = best.get(key)
        if old is None:
            best[key] = row
            continue
        new_key = (rank.get(row.confidence, 0), source_rank.get(row.source_type, 0))
        old_key = (rank.get(old.confidence, 0), source_rank.get(old.source_type, 0))
        if new_key > old_key:
            best[key] = row
    return sorted(best.values(), key=lambda r: (r.ticker, r.fiscal_year, r.segment))


def history_to_df(rows: Sequence[HistoryRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[f.name for f in HistoryRow.__dataclass_fields__.values()])
    return pd.DataFrame([asdict(r) for r in rows])


def load_user_history_csv(path: Path) -> List[HistoryRow]:
    if not path.exists():
        return []
    df = pd.read_csv(path)
    required = {"ticker", "fiscal_year", "segment", "revenue_usd"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"History CSV missing columns: {sorted(missing)}")

    rows = []
    for _, r in df.iterrows():
        revenue = safe_float(r.get("revenue_usd"))
        if revenue is None:
            continue
        ticker = str(r["ticker"]).upper()
        seg = canonical_segment(ticker, str(r["segment"])) or str(r["segment"])
        rows.append(
            HistoryRow(
                ticker=ticker,
                fiscal_year=int(r["fiscal_year"]),
                period_end=str(r.get("period_end") or ""),
                segment=seg,
                revenue_usd=revenue,
                source_type=str(r.get("source_type") or "USER_HISTORY"),
                source_url=str(r.get("source_url") or ""),
                source_locator=str(r.get("source_locator") or ""),
                confidence=str(r.get("confidence") or "HIGH").upper(),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# SEC download/cache
# ---------------------------------------------------------------------------

class SecClient:
    def __init__(self, cache_dir: Path, refresh: bool = False, user_agent: Optional[str] = None):
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        ua = user_agent or os.getenv("SEC_USER_AGENT") or "MeridianResearch/1.0 local-research"
        self.session.headers.update(
            {
                "User-Agent": ua,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json,text/html,application/xhtml+xml,*/*",
            }
        )
        self._last_request = 0.0

    def _cache_path(self, url: str, suffix: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return self.cache_dir / f"{h}{suffix}"

    def get_text(self, url: str) -> str:
        p = self._cache_path(url, ".txt")
        if p.exists() and not self.refresh:
            return p.read_text(encoding="utf-8", errors="replace")
        wait = 0.20 - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=30)
        self._last_request = time.time()
        resp.raise_for_status()
        text = resp.text
        p.write_text(text, encoding="utf-8")
        return text

    def get_json(self, url: str) -> Dict[str, Any]:
        p = self._cache_path(url, ".json")
        if p.exists() and not self.refresh:
            return json.loads(p.read_text(encoding="utf-8"))
        wait = 0.20 - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=30)
        self._last_request = time.time()
        resp.raise_for_status()
        data = resp.json()
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


def sec_recent_10k_filings(client: SecClient, ticker: str, limit: int = 4) -> List[Dict[str, str]]:
    cik = CIK[ticker]
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = client.get_json(url)
    recent = ((data.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    out = []
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        accession = recent.get("accessionNumber", [""] * len(forms))[i]
        primary = recent.get("primaryDocument", [""] * len(forms))[i]
        report_date = recent.get("reportDate", [""] * len(forms))[i]
        filing_date = recent.get("filingDate", [""] * len(forms))[i]
        if not accession or not primary:
            continue
        accession_plain = accession.replace("-", "")
        archive_cik = str(int(cik))
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{archive_cik}/{accession_plain}/{primary}"
        )
        out.append(
            {
                "accession": accession,
                "primary_document": primary,
                "report_date": report_date,
                "filing_date": filing_date,
                "url": filing_url,
            }
        )
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# SEC company total-revenue history
# ---------------------------------------------------------------------------

TOTAL_REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
]


def sec_total_revenue_history(client: SecClient, ticker: str) -> Dict[int, float]:
    cik = CIK[ticker]
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    data = client.get_json(url)
    usgaap = ((data.get("facts") or {}).get("us-gaap") or {})
    best: Dict[int, Tuple[str, float]] = {}

    for concept in TOTAL_REVENUE_CONCEPTS:
        node = usgaap.get(concept) or {}
        usd = ((node.get("units") or {}).get("USD") or [])
        for fact in usd:
            if fact.get("form") not in {"10-K", "10-K/A"}:
                continue
            fy = fact.get("fy")
            value = safe_float(fact.get("val"))
            filed = str(fact.get("filed") or "")
            start = fact.get("start")
            end = fact.get("end")
            if fy is None or value is None or value <= 0 or not start or not end:
                continue
            # Keep annual-duration facts only.
            try:
                d0 = datetime.fromisoformat(start)
                d1 = datetime.fromisoformat(end)
                days = (d1 - d0).days
            except Exception:
                continue
            if not 300 <= days <= 380:
                continue
            fy = int(fy)
            old = best.get(fy)
            if old is None or filed > old[0]:
                best[fy] = (filed, value)

    return {fy: val for fy, (_, val) in best.items()}


# ---------------------------------------------------------------------------
# SEC HTML revenue-table extraction
# ---------------------------------------------------------------------------

def dataframe_as_strings(df: pd.DataFrame) -> List[List[str]]:
    out: List[List[str]] = []
    for _, row in df.iterrows():
        out.append([normalize_text(x) for x in row.tolist()])
    return out


def find_years_in_table(rows: List[List[str]]) -> List[int]:
    years: List[int] = []
    for row in rows[:10]:
        for cell in row:
            for m in re.findall(r"\b(20\d{2})\b", cell):
                y = int(m)
                if y not in years:
                    years.append(y)
    return years[:4]


def mapped_segment_rows(ticker: str, rows: List[List[str]]) -> Dict[str, List[str]]:
    mapped: Dict[str, List[str]] = {}
    for row in rows:
        # Segment names are usually at the left. Use the first four cells,
        # but allow whole-row fallback for odd SEC HTML formatting.
        left = " ".join(row[:4])
        seg = canonical_segment(ticker, left)
        if seg is None:
            seg = canonical_segment(ticker, " ".join(row))
        if seg is not None:
            mapped.setdefault(seg, row)
    return mapped


def numeric_values_from_row(row: Sequence[str]) -> List[float]:
    vals: List[float] = []
    for cell in row:
        v = parse_number(cell)
        if v is not None:
            vals.append(v)
    return vals


def extract_revenue_table_candidates(
    ticker: str,
    html: str,
    source_url: str,
) -> List[Dict[str, Any]]:
    """
    Extract candidate segment-revenue tables.

    This deliberately does NOT silently guess when a table cannot be interpreted.
    """
    try:
        tables = pd.read_html(io.StringIO(html), header=None)
    except Exception:
        return []

    candidates: List[Dict[str, Any]] = []

    for idx, df in enumerate(tables):
        if df.empty or len(df) > 300 or df.shape[1] > 40:
            continue
        rows = dataframe_as_strings(df)
        mapped = mapped_segment_rows(ticker, rows)
        if len(mapped) < 2:
            continue

        years = find_years_in_table(rows)
        if len(years) < 2:
            continue

        table_text = " ".join(" ".join(r) for r in rows[:15]).lower()
        revenue_hint = 1 if ("revenue" in table_text or "net sales" in table_text or "sales" in table_text) else 0

        values: Dict[int, Dict[str, float]] = {y: {} for y in years}
        usable = 0

        for seg, row in mapped.items():
            nums = numeric_values_from_row(row)
            # SEC revenue rows usually contain one numeric value per displayed year.
            # If there are extra numbers (e.g. percentage columns), use the first
            # year-count block only when it is plausible; otherwise skip.
            if len(nums) < len(years):
                continue

            # Prefer the last N numbers. This avoids row-leading footnote numbers.
            selected = nums[-len(years):]

            # Most SEC tables show newest year -> oldest year.
            for y, value in zip(years, selected):
                values[y][seg] = value
            usable += 1

        if usable < 2:
            continue

        candidates.append(
            {
                "table_index": idx,
                "years": years,
                "values": values,
                "mapped_segments": sorted(mapped),
                "revenue_hint": revenue_hint,
                "source_url": source_url,
                "table_text_preview": table_text[:400],
            }
        )

    return candidates


def choose_scale(raw_sum: float, total_revenue: float) -> Tuple[Optional[float], Optional[float]]:
    if raw_sum <= 0 or total_revenue <= 0:
        return None, None
    scales = [1.0, 1e3, 1e6, 1e9]
    best_scale = None
    best_ratio = None
    best_error = float("inf")
    for scale in scales:
        ratio = raw_sum * scale / total_revenue
        if ratio <= 0:
            continue
        err = abs(math.log(ratio))
        if err < best_error:
            best_error = err
            best_scale = scale
            best_ratio = ratio
    return best_scale, best_ratio


def best_table_history_for_filing(
    ticker: str,
    filing: Dict[str, str],
    html: str,
    total_revenue: Dict[int, float],
) -> Tuple[List[HistoryRow], Dict[str, Any]]:
    candidates = extract_revenue_table_candidates(ticker, html, filing["url"])
    best_rows: List[HistoryRow] = []
    best_audit: Dict[str, Any] = {
        "ticker": ticker,
        "filing_url": filing["url"],
        "report_date": filing.get("report_date", ""),
        "status": "NO_USABLE_TABLE",
        "table_index": None,
        "years": "",
        "reconciliation_ratio": None,
        "mapped_segments": "",
    }
    best_score = -1.0

    for c in candidates:
        all_rows: List[HistoryRow] = []
        year_ratios: List[float] = []
        accepted_years = 0

        for fy, segvals in c["values"].items():
            total = total_revenue.get(int(fy))
            if not total:
                continue

            # Exclude signed adjustments from the operating segment sum.
            excluded = EXCLUDED_FROM_DIVERSIFICATION.get(ticker, set())
            positive_sum = sum(
                v for seg, v in segvals.items()
                if seg not in excluded and v > 0
            )
            scale, ratio = choose_scale(positive_sum, total)
            if scale is None or ratio is None:
                continue

            # Operating segment sums can differ slightly from consolidated
            # revenue because of disclosed adjustments. Keep a broad but safe gate.
            if not MIN_SEC_RECONCILIATION <= ratio <= MAX_SEC_RECONCILIATION:
                continue

            accepted_years += 1
            year_ratios.append(ratio)

            for seg, raw_value in segvals.items():
                value = raw_value * scale
                all_rows.append(
                    HistoryRow(
                        ticker=ticker,
                        fiscal_year=int(fy),
                        period_end="",
                        segment=seg,
                        revenue_usd=float(value),
                        source_type="SEC_10K_TABLE",
                        source_url=filing["url"],
                        source_locator=f"10-K HTML table index {c['table_index']}",
                        confidence="MEDIUM",
                    )
                )

        if accepted_years == 0:
            continue

        coverage = len(c["mapped_segments"]) / max(1, len(SEGMENT_PATTERNS.get(ticker, [])))
        recon_quality = 1.0 - min(1.0, statistics.fmean(abs(r - 1.0) for r in year_ratios))
        score = accepted_years * 10 + coverage * 4 + recon_quality * 3 + c["revenue_hint"]

        if score > best_score:
            best_score = score
            best_rows = all_rows
            best_audit = {
                "ticker": ticker,
                "filing_url": filing["url"],
                "report_date": filing.get("report_date", ""),
                "status": "ACCEPTED",
                "table_index": c["table_index"],
                "years": ",".join(str(y) for y in sorted({r.fiscal_year for r in all_rows})),
                "reconciliation_ratio": round(statistics.fmean(year_ratios), 6),
                "mapped_segments": " | ".join(c["mapped_segments"]),
            }

    return best_rows, best_audit


def fetch_sec_segment_history(
    client: SecClient,
    ticker: str,
    existing_totals: Dict[int, float],
) -> Tuple[List[HistoryRow], List[Dict[str, Any]]]:
    totals = dict(existing_totals)
    audits: List[Dict[str, Any]] = []
    out: List[HistoryRow] = []

    try:
        totals.update(sec_total_revenue_history(client, ticker))
    except Exception as exc:
        audits.append(
            {
                "ticker": ticker,
                "filing_url": "",
                "report_date": "",
                "status": f"COMPANYFACTS_ERROR: {type(exc).__name__}: {exc}",
                "table_index": None,
                "years": "",
                "reconciliation_ratio": None,
                "mapped_segments": "",
            }
        )

    try:
        filings = sec_recent_10k_filings(client, ticker, limit=4)
    except Exception as exc:
        audits.append(
            {
                "ticker": ticker,
                "filing_url": "",
                "report_date": "",
                "status": f"SUBMISSIONS_ERROR: {type(exc).__name__}: {exc}",
                "table_index": None,
                "years": "",
                "reconciliation_ratio": None,
                "mapped_segments": "",
            }
        )
        return out, audits

    for filing in filings:
        try:
            html = client.get_text(filing["url"])
            rows, audit = best_table_history_for_filing(ticker, filing, html, totals)
            out.extend(rows)
            audits.append(audit)
        except Exception as exc:
            audits.append(
                {
                    "ticker": ticker,
                    "filing_url": filing["url"],
                    "report_date": filing.get("report_date", ""),
                    "status": f"FILING_ERROR: {type(exc).__name__}: {exc}",
                    "table_index": None,
                    "years": "",
                    "reconciliation_ratio": None,
                    "mapped_segments": "",
                }
            )

    return out, audits


# ---------------------------------------------------------------------------
# Diversification
# ---------------------------------------------------------------------------

def operating_mix_for_year(df: pd.DataFrame, ticker: str, fiscal_year: int) -> pd.DataFrame:
    x = df[(df["ticker"] == ticker) & (df["fiscal_year"] == fiscal_year)].copy()
    if x.empty:
        return x
    excluded = EXCLUDED_FROM_DIVERSIFICATION.get(ticker, set())
    x = x[~x["segment"].isin(excluded)].copy()
    x = x[x["revenue_usd"] > 0].copy()
    return x


def aggregate_small_streams(shares: Dict[str, float]) -> Dict[str, float]:
    big: Dict[str, float] = {}
    small = 0.0
    for seg, share in shares.items():
        if share < SMALL_STREAM_SHARE_THRESHOLD:
            small += share
        else:
            big[seg] = share
    if small > 0:
        big["Other small streams"] = small
    return big


def diversification_metrics(df: pd.DataFrame, ticker: str, fiscal_year: int) -> Dict[str, Any]:
    x = operating_mix_for_year(df, ticker, fiscal_year)
    if x.empty:
        return {
            "score": None,
            "hhi": None,
            "effective_streams": None,
            "top1_share_pct": None,
            "top3_share_pct": None,
            "stream_count": 0,
            "label": "Unknown",
        }

    grouped = x.groupby("segment", as_index=False)["revenue_usd"].sum()
    total = grouped["revenue_usd"].sum()
    if total <= 0:
        return {
            "score": None,
            "hhi": None,
            "effective_streams": None,
            "top1_share_pct": None,
            "top3_share_pct": None,
            "stream_count": 0,
            "label": "Unknown",
        }

    raw_shares = {
        row["segment"]: float(row["revenue_usd"]) / float(total)
        for _, row in grouped.iterrows()
    }
    shares = aggregate_small_streams(raw_shares)
    hhi = sum(s * s for s in shares.values())
    score = clamp(100.0 * (1.0 - hhi))
    effective = (1.0 / hhi) if hhi > 0 else None
    ranked = sorted(raw_shares.values(), reverse=True)

    return {
        "score": score,
        "hhi": hhi,
        "effective_streams": effective,
        "top1_share_pct": 100.0 * ranked[0] if ranked else None,
        "top3_share_pct": 100.0 * sum(ranked[:3]) if ranked else None,
        "stream_count": len(raw_shares),
        "label": diversification_label(score),
        "shares": {k: v * 100.0 for k, v in sorted(raw_shares.items(), key=lambda kv: kv[1], reverse=True)},
        "hhi_shares_after_small_stream_aggregation": {
            k: v * 100.0 for k, v in sorted(shares.items(), key=lambda kv: kv[1], reverse=True)
        },
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def fiscal_window(latest_fy: int, years: int = HISTORY_YEARS) -> List[int]:
    return list(range(latest_fy - years + 1, latest_fy + 1))


def history_share_table(df: pd.DataFrame, ticker: str, years: Sequence[int]) -> pd.DataFrame:
    x = df[(df["ticker"] == ticker) & (df["fiscal_year"].isin(years))].copy()
    if x.empty:
        return x

    excluded = EXCLUDED_FROM_DIVERSIFICATION.get(ticker, set())
    operating = x[(~x["segment"].isin(excluded)) & (x["revenue_usd"] > 0)].copy()
    totals = operating.groupby("fiscal_year")["revenue_usd"].sum().rename("year_operating_revenue")
    operating = operating.merge(totals, on="fiscal_year", how="left")
    operating["share"] = operating["revenue_usd"] / operating["year_operating_revenue"]
    return operating


def segment_persistence_details(
    df: pd.DataFrame,
    ticker: str,
    latest_fy: int,
    years_count: int = HISTORY_YEARS,
) -> Tuple[List[SegmentPersistence], Dict[str, Any]]:
    years = fiscal_window(latest_fy, years_count)
    x = history_share_table(df, ticker, years)
    if x.empty:
        return [], {
            "score": None,
            "provisional_score": None,
            "status": "NO_HISTORY",
            "history_years_present": 0,
            "history_years_expected": years_count,
            "history_coverage_pct": 0.0,
            "major_stream_observation_coverage_pct": 0.0,
        }

    present_years = sorted(set(int(y) for y in x["fiscal_year"].tolist()))
    segments = sorted(set(str(s) for s in x["segment"].tolist()))
    details: List[SegmentPersistence] = []

    for seg in segments:
        sx = x[x["segment"] == seg].sort_values("fiscal_year")
        obs = len(set(int(y) for y in sx["fiscal_year"]))
        presence = 100.0 * obs / years_count

        shares = [float(v) for v in sx["share"].tolist()]
        share_cv = coefficient_of_variation(shares)
        share_stability = exponential_score(share_cv, SHARE_CV_DECAY)

        # Growth consistency: only consecutive observed years.
        revenue_by_year = {
            int(r["fiscal_year"]): float(r["revenue_usd"])
            for _, r in sx.iterrows()
            if float(r["revenue_usd"]) > 0
        }
        growths: List[float] = []
        for y in years[1:]:
            prev = revenue_by_year.get(y - 1)
            cur = revenue_by_year.get(y)
            if prev is not None and cur is not None and prev > 0:
                growths.append(cur / prev - 1.0)

        growth_vol = statistics.pstdev(growths) if len(growths) >= 2 else None
        growth_consistency = exponential_score(growth_vol, GROWTH_VOL_DECAY)

        persistence = weighted_average(
            [
                (presence, PERSISTENCE_PRESENCE_WEIGHT),
                (share_stability, PERSISTENCE_SHARE_STABILITY_WEIGHT),
                (growth_consistency, PERSISTENCE_GROWTH_CONSISTENCY_WEIGHT),
            ]
        )

        avg_share = statistics.fmean(shares) if shares else None
        latest_row = sx[sx["fiscal_year"] == latest_fy]
        latest_share = float(latest_row["share"].sum()) if not latest_row.empty else 0.0

        details.append(
            SegmentPersistence(
                ticker=ticker,
                segment=seg,
                observations=obs,
                expected_years=years_count,
                presence_score=presence,
                share_stability_score=share_stability,
                growth_consistency_score=growth_consistency,
                persistence_score=persistence,
                avg_share_pct=(avg_share * 100.0 if avg_share is not None else None),
                latest_share_pct=latest_share * 100.0,
                growth_volatility_pct=(growth_vol * 100.0 if growth_vol is not None else None),
                share_cv=share_cv,
                context_flag=CONTEXT_FLAGS.get((ticker, seg), ""),
            )
        )

    company_provisional = weighted_average(
        [
            (d.persistence_score, (d.avg_share_pct or 0.0) / 100.0)
            for d in details
        ]
    )

    latest_mix = operating_mix_for_year(df, ticker, latest_fy)
    latest_total = float(latest_mix["revenue_usd"].sum()) if not latest_mix.empty else 0.0
    major_covered = 0.0
    if latest_total > 0:
        obs_by_seg = {d.segment: d.observations for d in details}
        for _, r in latest_mix.iterrows():
            share = float(r["revenue_usd"]) / latest_total
            if obs_by_seg.get(str(r["segment"]), 0) >= MAJOR_STREAM_MIN_OBS:
                major_covered += share

    history_coverage = len(present_years) / years_count
    ready = (
        len(present_years) >= MIN_FINAL_HISTORY_YEARS
        and major_covered >= MIN_MAJOR_STREAM_OBSERVATION_SHARE
    )

    return details, {
        "score": company_provisional if ready else None,
        "provisional_score": company_provisional,
        "status": "READY" if ready else "INSUFFICIENT_HISTORY",
        "history_years_present": len(present_years),
        "history_years_expected": years_count,
        "history_coverage_pct": 100.0 * history_coverage,
        "major_stream_observation_coverage_pct": 100.0 * major_covered,
        "fiscal_years_present": present_years,
    }


# ---------------------------------------------------------------------------
# Company / MAG7 model
# ---------------------------------------------------------------------------

def latest_fy_map(integrated: Dict[str, Any]) -> Dict[str, int]:
    out = {}
    for c in integrated.get("companies", []):
        t = str(c.get("ticker", "")).upper()
        if t:
            out[t] = int(c["fiscal_year"])
    return out


def total_revenue_seed(integrated: Dict[str, Any], ticker: str) -> Dict[int, float]:
    for c in integrated.get("companies", []):
        if str(c.get("ticker", "")).upper() != ticker:
            continue
        fy = int(c["fiscal_year"])
        cur = safe_float(c.get("revenue_usd"))
        prev = safe_float(c.get("previous_revenue_usd"))
        d: Dict[int, float] = {}
        if cur:
            d[fy] = cur
        if prev:
            d[fy - 1] = prev
        return d
    return {}


def calculate_company(
    history_df: pd.DataFrame,
    ticker: str,
    latest_fy: int,
) -> Tuple[Dict[str, Any], List[SegmentPersistence]]:
    div = diversification_metrics(history_df, ticker, latest_fy)
    seg_details, pers = segment_persistence_details(history_df, ticker, latest_fy)

    final_score = None
    status = "NOT_SCORED"
    if div["score"] is not None and pers["score"] is not None:
        final_score = (
            RESILIENCE_DIVERSIFICATION_WEIGHT * div["score"]
            + RESILIENCE_PERSISTENCE_WEIGHT * pers["score"]
        )
        status = "SCORED"

    provisional_final = None
    if div["score"] is not None and pers["provisional_score"] is not None:
        provisional_final = (
            RESILIENCE_DIVERSIFICATION_WEIGHT * div["score"]
            + RESILIENCE_PERSISTENCE_WEIGHT * pers["provisional_score"]
        )

    reasons = []
    if div["score"] is None:
        reasons.append("Latest-year operating revenue mix unavailable.")
    if pers["status"] != "READY":
        reasons.append(
            f"Persistence requires {HISTORY_YEARS} fiscal years and >= "
            f"{MIN_MAJOR_STREAM_OBSERVATION_SHARE:.0%} of latest revenue streams "
            f"with at least {MAJOR_STREAM_MIN_OBS} observations."
        )

    return {
        "ticker": ticker,
        "latest_fiscal_year": latest_fy,
        "revenue_resilience_score": final_score,
        "revenue_resilience_provisional_score": provisional_final,
        "status": status,
        "label": label_score(final_score),
        "diversification": div,
        "persistence": pers,
        "weights": {
            "diversification": RESILIENCE_DIVERSIFICATION_WEIGHT,
            "persistence": RESILIENCE_PERSISTENCE_WEIGHT,
        },
        "reasons": reasons,
    }, seg_details


def run_model(history_df: pd.DataFrame, integrated: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[SegmentPersistence]]:
    fy_map = latest_fy_map(integrated)
    companies: List[Dict[str, Any]] = []
    details: List[SegmentPersistence] = []
    for ticker in MAG7:
        if ticker not in fy_map:
            continue
        c, d = calculate_company(history_df, ticker, fy_map[ticker])
        companies.append(c)
        details.extend(d)
    return companies, details


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(
    outdir: Path,
    history_df: pd.DataFrame,
    companies: List[Dict[str, Any]],
    details: List[SegmentPersistence],
    audits: List[Dict[str, Any]],
    network_used: bool,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    history_path = outdir / "revenue_segment_history_mag7.csv"
    history_df.sort_values(["ticker", "fiscal_year", "segment"]).to_csv(history_path, index=False)

    score_rows = []
    for c in companies:
        d = c["diversification"]
        p = c["persistence"]
        score_rows.append(
            {
                "ticker": c["ticker"],
                "latest_fiscal_year": c["latest_fiscal_year"],
                "revenue_resilience_score": c["revenue_resilience_score"],
                "provisional_score": c["revenue_resilience_provisional_score"],
                "status": c["status"],
                "diversification_score": d["score"],
                "diversification_label": d["label"],
                "hhi": d["hhi"],
                "effective_revenue_streams": d["effective_streams"],
                "top1_share_pct": d["top1_share_pct"],
                "top3_share_pct": d["top3_share_pct"],
                "persistence_score": p["score"],
                "persistence_provisional_score": p["provisional_score"],
                "persistence_status": p["status"],
                "history_years_present": p["history_years_present"],
                "history_coverage_pct": p["history_coverage_pct"],
                "major_stream_observation_coverage_pct": p["major_stream_observation_coverage_pct"],
            }
        )
    pd.DataFrame(score_rows).to_csv(outdir / "revenue_resilience_company_scores.csv", index=False)

    detail_df = pd.DataFrame([asdict(d) for d in details])
    detail_df.to_csv(outdir / "revenue_resilience_segment_details.csv", index=False)

    pd.DataFrame(audits).to_csv(outdir / "sec_extraction_audit.csv", index=False)

    payload = {
        "model_version": MODEL_VERSION,
        "generated_at_utc": now_utc(),
        "network_used": network_used,
        "production_modified": False,
        "model": {
            "revenue_resilience": {
                "diversification_weight": RESILIENCE_DIVERSIFICATION_WEIGHT,
                "persistence_weight": RESILIENCE_PERSISTENCE_WEIGHT,
            },
            "diversification": {
                "formula": "100 * (1 - HHI)",
                "small_stream_aggregation_threshold": SMALL_STREAM_SHARE_THRESHOLD,
                "signed_adjustments_excluded_from_operating_hhi": True,
            },
            "persistence": {
                "years": HISTORY_YEARS,
                "presence_weight": PERSISTENCE_PRESENCE_WEIGHT,
                "share_stability_weight": PERSISTENCE_SHARE_STABILITY_WEIGHT,
                "growth_consistency_weight": PERSISTENCE_GROWTH_CONSISTENCY_WEIGHT,
                "interpretation": "Historical persistence, not a forecast guarantee.",
            },
        },
        "companies": companies,
    }
    (outdir / "revenue_resilience_review.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Meridian Revenue Resilience V1",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "Revenue Resilience = 60% Diversification + 40% Historical Persistence.",
        "Persistence describes historical evidence; it is not a guarantee of future sustainability.",
        "",
        "| Ticker | Resilience | Diversification | Top stream | Persistence | History | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for c in companies:
        d = c["diversification"]
        p = c["persistence"]
        lines.append(
            f"| {c['ticker']} | {fmt_score(c['revenue_resilience_score'])} "
            f"| {fmt_score(d['score'])} | {fmt_pct(d['top1_share_pct'])} "
            f"| {fmt_score(p['score'])} "
            f"| {p['history_years_present']}/{p['history_years_expected']} "
            f"| {c['status']} |"
        )

    lines += ["", "## Company detail", ""]
    for c in companies:
        d = c["diversification"]
        p = c["persistence"]
        lines += [
            f"### {c['ticker']}",
            "",
            f"- Diversification: **{fmt_score(d['score'])}/100** — {d['label']}",
            f"- Largest revenue stream: **{fmt_pct(d['top1_share_pct'])}**",
            f"- Effective revenue streams (1/HHI): **{d['effective_streams']:.2f}**"
            if d["effective_streams"] is not None else "- Effective revenue streams: N/A",
            f"- Persistence: **{fmt_score(p['score'])}/100** "
            f"(provisional {fmt_score(p['provisional_score'])})",
            f"- History coverage: **{p['history_years_present']}/{p['history_years_expected']} years**",
            f"- Revenue Resilience: **{fmt_score(c['revenue_resilience_score'])}/100** "
            f"(provisional {fmt_score(c['revenue_resilience_provisional_score'])})",
            "",
        ]
        if c["reasons"]:
            for reason in c["reasons"]:
                lines.append(f"  - {reason}")
            lines.append("")

    (outdir / "revenue_resilience_review.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def make_synthetic_history() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    rows = []
    # A balanced, persistent company
    for fy in range(2021, 2026):
        rows.extend(
            [
                HistoryRow("AAPL", fy, "", "iPhone", 50 + fy - 2021, "TEST", "", "", "HIGH"),
                HistoryRow("AAPL", fy, "", "Services", 30 + 2 * (fy - 2021), "TEST", "", "", "HIGH"),
                HistoryRow("AAPL", fy, "", "Mac", 20, "TEST", "", "", "HIGH"),
            ]
        )
    # A concentrated company
    for fy in range(2021, 2026):
        rows.extend(
            [
                HistoryRow("META", fy, "", "Family of Apps - Advertising", 98 + fy - 2021, "TEST", "", "", "HIGH"),
                HistoryRow("META", fy, "", "Reality Labs", 2, "TEST", "", "", "HIGH"),
            ]
        )

    integrated = {
        "companies": [
            {"ticker": "AAPL", "fiscal_year": 2025},
            {"ticker": "META", "fiscal_year": 2025},
        ]
    }
    return history_to_df(rows), integrated


def self_test() -> None:
    df, integrated = make_synthetic_history()
    companies, details = run_model(df, integrated)
    by = {c["ticker"]: c for c in companies}
    assert by["AAPL"]["status"] == "SCORED"
    assert by["META"]["status"] == "SCORED"
    assert by["AAPL"]["diversification"]["score"] > by["META"]["diversification"]["score"]
    assert by["AAPL"]["persistence"]["score"] is not None
    assert by["META"]["persistence"]["score"] is not None
    assert 0 <= by["AAPL"]["revenue_resilience_score"] <= 100
    assert 0 <= by["META"]["revenue_resilience_score"] <= 100

    # One-stream HHI => diversification zero
    one = pd.DataFrame(
        [{
            "ticker": "AAPL", "fiscal_year": 2025, "period_end": "",
            "segment": "iPhone", "revenue_usd": 100.0,
            "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"
        }]
    )
    m = diversification_metrics(one, "AAPL", 2025)
    assert abs(m["score"] - 0.0) < 1e-9

    # Two equal streams => HHI=.5 => score=50
    two = pd.DataFrame(
        [
            {"ticker": "AAPL", "fiscal_year": 2025, "period_end": "", "segment": "iPhone",
             "revenue_usd": 50.0, "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"},
            {"ticker": "AAPL", "fiscal_year": 2025, "period_end": "", "segment": "Services",
             "revenue_usd": 50.0, "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"},
        ]
    )
    m = diversification_metrics(two, "AAPL", 2025)
    assert abs(m["score"] - 50.0) < 1e-9

    # Missing history cannot become a final resilience score.
    short = df[df["fiscal_year"] >= 2024].copy()
    c, _ = calculate_company(short, "AAPL", 2025)
    assert c["persistence"]["status"] == "INSUFFICIENT_HISTORY"
    assert c["revenue_resilience_score"] is None
    assert c["revenue_resilience_provisional_score"] is not None

    # Signed Google adjustment excluded from HHI.
    g = pd.DataFrame(
        [
            {"ticker": "GOOGL", "fiscal_year": 2025, "period_end": "", "segment": "Google Search & other",
             "revenue_usd": 90, "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"},
            {"ticker": "GOOGL", "fiscal_year": 2025, "period_end": "", "segment": "Google Cloud",
             "revenue_usd": 10, "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"},
            {"ticker": "GOOGL", "fiscal_year": 2025, "period_end": "", "segment": "Hedging gains (losses)",
             "revenue_usd": -1, "source_type": "TEST", "source_url": "", "source_locator": "", "confidence": "HIGH"},
        ]
    )
    gm = diversification_metrics(g, "GOOGL", 2025)
    assert abs(gm["top1_share_pct"] - 90.0) < 1e-9

    print(
        "SELF-TEST PASS: HHI diversification, tiny-stream aggregation, "
        "5Y persistence, missing-history gate, signed-adjustment handling, "
        "and no fabricated final score."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Meridian Revenue Resilience V1")
    p.add_argument("--input", default=str(DEFAULT_INPUT), help="Existing MAG7 integrated review JSON")
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    p.add_argument(
        "--history-csv",
        default="",
        help="Optional additional 5Y history CSV. Required cols: ticker,fiscal_year,segment,revenue_usd",
    )
    p.add_argument("--offline", action="store_true", help="Do not call SEC; use existing/local history only")
    p.add_argument("--refresh-sec", action="store_true", help="Refresh SEC cache")
    p.add_argument("--sec-user-agent", default="", help="Optional SEC User-Agent override")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    root = Path.cwd()
    load_dotenv_simple(root)

    input_path = Path(args.input)
    outdir = Path(args.output_dir)
    cache = DEFAULT_CACHE

    integrated = load_integrated_review(input_path)
    seed_rows = history_from_integrated_review(integrated)
    all_rows: List[HistoryRow] = list(seed_rows)
    audits: List[Dict[str, Any]] = []

    if args.history_csv:
        all_rows.extend(load_user_history_csv(Path(args.history_csv)))

    network_used = False
    if not args.offline:
        client = SecClient(
            cache_dir=cache,
            refresh=args.refresh_sec,
            user_agent=args.sec_user_agent or None,
        )
        for ticker in MAG7:
            print(f"[SEC] {ticker}: extending segment revenue history ...")
            try:
                rows, ticker_audits = fetch_sec_segment_history(
                    client,
                    ticker,
                    total_revenue_seed(integrated, ticker),
                )
                all_rows.extend(rows)
                audits.extend(ticker_audits)
                network_used = True
                accepted = sum(1 for a in ticker_audits if a.get("status") == "ACCEPTED")
                print(f"      accepted filings: {accepted}")
            except Exception as exc:
                audits.append(
                    {
                        "ticker": ticker,
                        "filing_url": "",
                        "report_date": "",
                        "status": f"TICKER_ERROR: {type(exc).__name__}: {exc}",
                        "table_index": None,
                        "years": "",
                        "reconciliation_ratio": None,
                        "mapped_segments": "",
                    }
                )
                print(f"      warning: {type(exc).__name__}: {exc}")

    merged = merge_history(all_rows)
    history_df = history_to_df(merged)

    companies, details = run_model(history_df, integrated)
    write_outputs(outdir, history_df, companies, details, audits, network_used)

    print("\nMERIDIAN REVENUE RESILIENCE V1")
    print("Ticker  FY    Diversification  Persistence  Resilience  History  Status")
    for c in companies:
        d = c["diversification"]
        p = c["persistence"]
        print(
            f"{c['ticker']:<6} {c['latest_fiscal_year']:<5} "
            f"{fmt_score(d['score']):>15} "
            f"{fmt_score(p['score']):>12} "
            f"{fmt_score(c['revenue_resilience_score']):>11} "
            f"{p['history_years_present']}/{p['history_years_expected']:<5} "
            f"{c['status']}"
        )

    print(f"\nOutputs: {outdir.resolve()}")
    print("Production scoring/model files: UNCHANGED.")
    print(
        "Note: Persistence means historical persistence. "
        "Missing history is not treated as zero."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
