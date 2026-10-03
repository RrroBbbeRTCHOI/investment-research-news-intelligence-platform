from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


# ============================================================
# CONFIG
# ============================================================

OUTPUT_PATH = Path("data/news/market_reaction/historical_market_reaction_H01_H30_v1.csv")
BENCHMARK = "QQQ"

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class HistoricalCase:
    case_id: str
    ticker: str
    event_date: str
    event_time_utc: str | None
    event_name: str
    event_type: str
    event_subtype: str
    event_engine_status: str
    relationship_type: str
    ml_eligible: bool


# ============================================================
# H01-H30 EVENT-COMPANY PAIRS
# ============================================================

CASES = [
    # H01 has two candidate indirect company pairs.
    HistoricalCase("H01", "NVDA", "2024-04-03", "2024-04-03T14:44:52Z",
                   "TSMC Taiwan earthquake",
                   "natural_disaster", "earthquake",
                   "accepted_conservative_no_match", "candidate_indirect", False),

    HistoricalCase("H01", "AAPL", "2024-04-03", "2024-04-03T14:44:52Z",
                   "TSMC Taiwan earthquake",
                   "natural_disaster", "earthquake",
                   "accepted_conservative_no_match", "candidate_indirect", False),

    HistoricalCase("H02", "NVDA", "2023-10-17", "2023-10-17T23:49:00Z",
                   "U.S. AI-chip export controls",
                   "trade_export_control", "export_controls",
                   "accepted", "direct_exposure_match", True),

    HistoricalCase("H03", "AMZN", "2025-10-20", None,
                   "AWS cloud outage",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_exposure_match", True),

    HistoricalCase("H04", "TSLA", "2024-03-25", None,
                   "Tesla Shanghai production cut",
                   "supply_chain", "production_interruption",
                   "accepted", "direct_exposure_match", True),

    HistoricalCase("H05", "NVDA", "2024-03-29", None,
                   "U.S. export-curb update on AI chips to China",
                   "trade_export_control", "export_controls",
                   "accepted", "direct_exposure_match", True),

    HistoricalCase("H06", "NVDA", "2023-08-30", None,
                   "U.S. licensing restrictions affecting AI-chip exports",
                   "trade_export_control", "export_controls",
                   "accepted_no_qualified_exposure_edge", "direct_mention", False),

    HistoricalCase("H07", "NVDA", "2024-03-17", None,
                   "TSMC CoWoS structural capacity bottleneck / expansion",
                   "boundary", "structural_capacity",
                   "rejected_boundary", "candidate_indirect", False),

    HistoricalCase("H08", "MSFT", "2023-01-25", "2023-01-25T16:41:02Z",
                   "Microsoft Azure global outage",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_mention", True),

    HistoricalCase("H09", "GOOGL", "2025-06-12", None,
                   "Google Cloud global outage",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_mention", True),

    HistoricalCase("H10", "TSLA", "2024-03-05", "2024-03-05T16:45:37Z",
                   "Tesla Berlin power outage",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_mention", True),

    HistoricalCase("H11", "META", "2024-03-05", None,
                   "Facebook / Instagram global outage",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_mention", True),

    HistoricalCase("H12", "TSLA", "2023-12-21", None,
                   "Tesla 4680 battery production bottleneck",
                   "boundary", "structural_manufacturing_constraint",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H13", "AAPL", "2024-03-04", "2024-03-04T18:30:09Z",
                   "Apple EU antitrust fine in Spotify case",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H14", "AAPL", "2024-03-21", "2024-03-21T22:07:47Z",
                   "Apple U.S. antitrust lawsuit",
                   "legal_antitrust", "lawsuit",
                   "accepted", "direct_mention", True),

    HistoricalCase("H15", "AAPL", "2023-09-07", None,
                   "China widening iPhone government-use curbs",
                   "government_policy", "regulation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H16", "MSFT", "2024-06-25", None,
                   "Microsoft Teams EU antitrust charge",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H17", "MSFT", "2024-07-19", "2024-07-19T11:11:27Z",
                   "Global IT outage affecting Microsoft-related services",
                   "infrastructure_outage", "outage",
                   "accepted", "direct_mention", True),

    HistoricalCase("H18", "GOOGL", "2024-08-05", "2024-08-05T22:50:11Z",
                   "Google search antitrust ruling",
                   "legal_antitrust", "ruling",
                   "accepted", "direct_mention", True),

    HistoricalCase("H19", "GOOGL", "2024-11-20", None,
                   "Google Chrome divestiture remedy proposal",
                   "legal_antitrust", "remedy_proposal",
                   "accepted", "direct_mention", True),

    HistoricalCase("H20", "AMZN", "2023-09-26", None,
                   "FTC antitrust complaint against Amazon",
                   "legal_antitrust", "complaint",
                   "accepted", "direct_mention", True),

    HistoricalCase("H21", "AMZN", "2024-01-29", None,
                   "Amazon and iRobot terminate acquisition",
                   "corporate_transaction", "acquisition_terminated",
                   "accepted", "direct_mention", True),

    HistoricalCase("H22", "META", "2023-05-22", None,
                   "Meta EU privacy fine over data transfers",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H23", "META", "2024-05-24", "2024-05-24T21:37:34Z",
                   "Meta UK Marketplace proposal amendments",
                   "boundary", "regulatory_proposal_amendment",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H24", "META", "2024-11-14", None,
                   "Meta EU fine over Facebook Marketplace",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H25", "NVDA", "2024-07-22", "2024-07-22T11:04:46Z",
                   "Nvidia preparing China Blackwell variant",
                   "boundary", "product_strategy",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H26", "NVDA", "2024-11-21", None,
                   "Nvidia Blackwell structural supply constraints",
                   "boundary", "structural_supply_constraint",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H27", "TSLA", "2023-12-13", None,
                   "Tesla Autopilot recall",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H28", "TSLA", "2024-01-11", None,
                   "Tesla Berlin production suspension from Red Sea disruption",
                   "supply_chain", "production_interruption",
                   "accepted", "direct_mention", True),

    HistoricalCase("H29", "TSLA", "2024-04-16", "2024-04-16T14:30:12Z",
                   "Tesla global workforce reduction",
                   "corporate_action", "workforce_reduction",
                   "accepted", "direct_mention", True),

    HistoricalCase("H30", "MSFT", "2024-02-27", "2024-02-27T10:28:57Z",
                   "Microsoft Mistral AI deal faces formal EU scrutiny",
                   "legal_antitrust", "regulatory_scrutiny",
                   "accepted", "direct_mention", True),
]


# ============================================================
# TIME HELPERS
# ============================================================

def _parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"

    dt = datetime.fromisoformat(ts)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)


def effective_event_date(case: HistoricalCase) -> pd.Timestamp:
    """
    Exact timestamp:
      before 16:00 ET  -> same calendar date may be t0
      at/after 16:00 ET -> next calendar date is eligible

    Date-only:
      use the stated event date conservatively.
    """
    if case.event_time_utc:
        local = _parse_utc(case.event_time_utc).astimezone(NY)
        d = local.date()

        if local.time() >= time(16, 0):
            d += timedelta(days=1)

        return pd.Timestamp(d)

    return pd.Timestamp(case.event_date)


# ============================================================
# PRICE HELPERS
# ============================================================

def download_prices(
    tickers: list[str],
    start: str,
    end: str,
) -> dict[str, pd.Series]:

    output: dict[str, pd.Series] = {}

    for ticker in tickers:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
            actions=False,
        )

        if df.empty:
            raise RuntimeError(f"No price data returned for {ticker}")

        if isinstance(df.columns, pd.MultiIndex):
            close = df["Close"][ticker]
        else:
            close = df["Close"]

        close = close.dropna().copy()
        close.index = pd.to_datetime(close.index).tz_localize(None)

        output[ticker] = close

    return output


def locate_sessions(
    close: pd.Series,
    effective_date: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:

    idx = close.index.sort_values()

    future = idx[idx >= effective_date]

    if len(future) < 5:
        raise RuntimeError(
            f"Not enough forward trading sessions after {effective_date.date()}"
        )

    t0 = future[0]
    pos = idx.get_loc(t0)

    if pos < 1:
        raise RuntimeError(
            f"No prior trading session before {t0.date()}"
        )

    prior = idx[pos - 1]
    t3 = idx[pos + 2]
    t5 = idx[pos + 4]

    return prior, t0, t3, t5


def cumulative_return(
    close: pd.Series,
    start_session: pd.Timestamp,
    end_session: pd.Timestamp,
) -> float:

    return float(
        close.loc[end_session] / close.loc[start_session] - 1.0
    )


# ============================================================
# BUILD DATASET
# ============================================================

def build_market_reaction() -> pd.DataFrame:

    tickers = sorted(
        {c.ticker for c in CASES} | {BENCHMARK}
    )

    dates = [
        pd.Timestamp(c.event_date)
        for c in CASES
    ]

    start = (
        min(dates) - pd.Timedelta(days=15)
    ).strftime("%Y-%m-%d")

    end = (
        max(dates) + pd.Timedelta(days=20)
    ).strftime("%Y-%m-%d")

    prices = download_prices(
        tickers,
        start=start,
        end=end,
    )

    rows = []

    for case in CASES:

        effective_date = effective_event_date(case)

        stock = prices[case.ticker]
        qqq = prices[BENCHMARK]

        (
            stock_prior,
            stock_t0,
            stock_t3,
            stock_t5,
        ) = locate_sessions(
            stock,
            effective_date,
        )

        (
            qqq_prior,
            qqq_t0,
            qqq_t3,
            qqq_t5,
        ) = locate_sessions(
            qqq,
            effective_date,
        )

        if not (
            stock_prior == qqq_prior
            and stock_t0 == qqq_t0
            and stock_t3 == qqq_t3
            and stock_t5 == qqq_t5
        ):
            raise RuntimeError(
                f"Trading-session mismatch for "
                f"{case.case_id}/{case.ticker}"
            )

        stock_1d = cumulative_return(
            stock,
            stock_prior,
            stock_t0,
        )

        stock_3d = cumulative_return(
            stock,
            stock_prior,
            stock_t3,
        )

        stock_5d = cumulative_return(
            stock,
            stock_prior,
            stock_t5,
        )

        qqq_1d = cumulative_return(
            qqq,
            qqq_prior,
            qqq_t0,
        )

        qqq_3d = cumulative_return(
            qqq,
            qqq_prior,
            qqq_t3,
        )

        qqq_5d = cumulative_return(
            qqq,
            qqq_prior,
            qqq_t5,
        )

        rel_1d = stock_1d - qqq_1d
        rel_3d = stock_3d - qqq_3d
        rel_5d = stock_5d - qqq_5d

        rows.append({
            "case_id": case.case_id,
            "ticker": case.ticker,
            "event_name": case.event_name,
            "event_type": case.event_type,
            "event_subtype": case.event_subtype,
            "event_engine_status": case.event_engine_status,
            "relationship_type": case.relationship_type,
            "ml_eligible": case.ml_eligible,

            "event_date_reported": case.event_date,
            "event_time_utc": case.event_time_utc,
            "effective_event_date": effective_date.date().isoformat(),

            "prior_trading_session": stock_prior.date().isoformat(),
            "t0_session": stock_t0.date().isoformat(),
            "t3_session": stock_t3.date().isoformat(),
            "t5_session": stock_t5.date().isoformat(),

            "stock_return_1d": stock_1d,
            "stock_return_3d": stock_3d,
            "stock_return_5d": stock_5d,

            "qqq_return_1d": qqq_1d,
            "qqq_return_3d": qqq_3d,
            "qqq_return_5d": qqq_5d,

            "qqq_relative_1d": rel_1d,
            "qqq_relative_3d": rel_3d,
            "qqq_relative_5d": rel_5d,

            # Exploratory labels only.
            "material_3d_2pct": int(abs(rel_3d) > 0.02),
            "material_3d_3pct": int(abs(rel_3d) > 0.03),
            "material_3d_4pct": int(abs(rel_3d) > 0.04),
        })

    df = pd.DataFrame(rows)

    return_cols = [
        c
        for c in df.columns
        if c.startswith("stock_return_")
        or c.startswith("qqq_return_")
        or c.startswith("qqq_relative_")
    ]

    for col in return_cols:
        df[col] = df[col].round(6)

    return df


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = build_market_reaction()

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    display = df[
        [
            "case_id",
            "ticker",
            "event_type",
            "event_subtype",
            "event_engine_status",
            "ml_eligible",
            "t0_session",
            "stock_return_1d",
            "stock_return_3d",
            "stock_return_5d",
            "qqq_relative_1d",
            "qqq_relative_3d",
            "qqq_relative_5d",
            "material_3d_2pct",
        ]
    ].copy()

    pct_cols = [
        c
        for c in display.columns
        if "return_" in c
        or "relative_" in c
    ]

    for col in pct_cols:
        display[col] = (
            display[col] * 100
        ).round(2)

    print("\n" + "=" * 150)
    print("HISTORICAL MARKET REACTION — H01-H30")
    print("=" * 150)
    print(display.to_string(index=False))
    print("=" * 150)

    eligible = df[df["ml_eligible"]].copy()

    print("\nML-ELIGIBLE SUMMARY")
    print("-" * 60)
    print("Rows:", len(eligible))

    for threshold in [
        "material_3d_2pct",
        "material_3d_3pct",
        "material_3d_4pct",
    ]:
        positives = int(eligible[threshold].sum())
        negatives = int(len(eligible) - positives)

        print(
            f"{threshold}: "
            f"{positives} positive / "
            f"{negatives} negative"
        )

    print("\nSaved:")
    print(OUTPUT_PATH)

    print("\nMethod:")
    print("- Baseline = previous U.S. trading-session close")
    print("- 1D = event-session close vs prior-session close")
    print("- 3D = third trading-session close vs prior-session close")
    print("- 5D = fifth trading-session close vs prior-session close")
    print("- QQQ-relative = stock cumulative return - QQQ cumulative return")
    print("- Rejected/boundary events are retained for auditability but ml_eligible=False")
    print("- This is descriptive market reaction, NOT causal abnormal return.")


if __name__ == "__main__":
    main()
