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

OUTPUT_PATH = Path("data/news/market_reaction/historical_market_reaction_H01_H120_v4.csv")
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
# H01-H90 EVENT-COMPANY PAIRS
# ============================================================

CASES = [
    # ========================================================
    # H01-H30 — PRESERVED
    # ========================================================
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

    # ========================================================
    # H31-H60 — PRESERVED
    # ========================================================
    HistoricalCase("H31", "AAPL", "2024-03-25", None,
                   "Apple targeted in EU's first Digital Markets Act probe",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H32", "AAPL", "2024-04-29", None,
                   "Apple iPadOS designated gatekeeper under EU tech rules",
                   "government_policy", "regulation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H33", "AAPL", "2024-06-24", None,
                   "Apple charged with breaching EU tech rules",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H34", "AAPL", "2024-07-12", None,
                   "India antitrust investigation finds Apple abused position",
                   "legal_antitrust", "investigation_finding",
                   "accepted", "direct_mention", True),

    HistoricalCase("H35", "MSFT", "2023-07-27", None,
                   "EU opens antitrust investigation into Microsoft Teams and Office bundling",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H36", "MSFT", "2023-04-26", None,
                   "UK blocks Microsoft's Activision acquisition",
                   "legal_antitrust", "ruling",
                   "accepted", "direct_mention", True),

    HistoricalCase("H37", "MSFT", "2023-10-13", None,
                   "Microsoft closes Activision acquisition after UK clearance",
                   "corporate_transaction", "acquisition",
                   "accepted", "direct_mention", True),

    HistoricalCase("H38", "MSFT", "2023-11-20", None,
                   "Sam Altman announced to join Microsoft advanced AI team",
                   "boundary", "leadership_hiring",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H39", "MSFT", "2024-01-25", None,
                   "FTC launches inquiry into Microsoft's generative-AI partnership investments",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H40", "GOOGL", "2023-01-24", None,
                   "U.S. Justice Department sues Google over digital advertising technology",
                   "legal_antitrust", "lawsuit",
                   "accepted", "direct_mention", True),

    HistoricalCase("H41", "GOOGL", "2023-06-14", None,
                   "Google faces EU antitrust charge over ad-tech practices",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H42", "GOOGL", "2024-01-25", None,
                   "FTC launches inquiry into Alphabet generative-AI partnership investments",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H43", "GOOGL", "2024-03-25", None,
                   "Google targeted in EU's first Digital Markets Act probe",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H44", "GOOGL", "2025-04-17", None,
                   "Google holds illegal monopolies in ad tech, U.S. judge finds",
                   "legal_antitrust", "ruling",
                   "accepted", "direct_mention", True),

    HistoricalCase("H45", "AMZN", "2023-01-25", None,
                   "Amazon workers walk out in first UK strike",
                   "labor_disruption", "strike",
                   "accepted", "direct_mention", True),

    HistoricalCase("H46", "AMZN", "2023-06-21", None,
                   "FTC sues Amazon over Prime enrollment and cancellation practices",
                   "legal_antitrust", "complaint",
                   "accepted", "direct_mention", True),

    HistoricalCase("H47", "AMZN", "2023-11-27", None,
                   "EU sends Amazon statement of objections over iRobot acquisition",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H48", "AMZN", "2024-01-25", None,
                   "FTC launches inquiry into Amazon generative-AI partnership investments",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H49", "AMZN", "2024-04-03", None,
                   "Amazon Web Services lays off several hundred staff",
                   "corporate_action", "workforce_reduction",
                   "accepted", "direct_mention", True),

    HistoricalCase("H50", "META", "2024-03-13", None,
                   "FTC can reopen Meta privacy case, court rules",
                   "legal_antitrust", "ruling",
                   "accepted", "direct_mention", True),

    HistoricalCase("H51", "META", "2024-03-25", None,
                   "Meta targeted in EU's first Digital Markets Act probe",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H52", "META", "2024-05-08", None,
                   "Turkey fines Meta over data-sharing practices",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H53", "META", "2024-07-01", None,
                   "Meta charged with failing to comply with EU tech rules",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H54", "META", "2024-07-30", None,
                   "Meta settles Texas facial-recognition lawsuit for $1.4 billion",
                   "legal_antitrust", "settlement",
                   "accepted", "direct_mention", True),

    HistoricalCase("H55", "META", "2024-09-27", None,
                   "EU privacy regulator fines Meta over password storage",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H56", "NVDA", "2024-09-04", None,
                   "U.S. Justice Department questions Nvidia business practices",
                   "boundary", "ambiguous_regulatory_status",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H57", "NVDA", "2024-10-23", None,
                   "Nvidia Blackwell design flaw caused low yields and shipment delays",
                   "supply_chain", "production_constraint",
                   "accepted", "direct_mention", True),

    HistoricalCase("H58", "NVDA", "2025-04-15", None,
                   "U.S. imposes export-license requirement on Nvidia H20 sales to China",
                   "trade_export_control", "export_controls",
                   "accepted", "direct_mention", True),

    HistoricalCase("H59", "TSLA", "2023-01-13", None,
                   "Tesla cuts vehicle prices in U.S. and Europe",
                   "corporate_action", "pricing_change",
                   "accepted", "direct_mention", True),

    HistoricalCase("H60", "TSLA", "2024-04-19", None,
                   "Tesla recalls Cybertrucks over faulty accelerator pedal",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    # ========================================================
    # H61-H90 — FROZEN V1.3.1 OUTCOMES
    # ========================================================
    HistoricalCase("H61", "AAPL", "2025-04-23", None,
                   "EU fines Apple 500 million euros for Digital Markets Act breach",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H62", "AAPL", "2025-03-19", None,
                   "EU orders Apple to improve interoperability with rival devices and apps",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H63", "AAPL", "2024-09-10", None,
                   "EU top court confirms Apple must pay Ireland 13 billion euros in back taxes",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H64", "AAPL", "2023-12-26", None,
                   "US trade tribunal blocks imports of certain Apple Watch models",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H65", "MSFT", "2023-01-18", None,
                   "Microsoft announces about 10,000 job cuts",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H66", "MSFT", "2022-12-08", None,
                   "FTC sues to block Microsoft's acquisition of Activision Blizzard",
                   "legal_antitrust", "complaint",
                   "accepted", "direct_mention", True),

    HistoricalCase("H67", "MSFT", "2023-07-11", None,
                   "US judge rejects FTC request to block Microsoft Activision deal",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H68", "MSFT", "2024-07-16", None,
                   "UK launches formal probe into Microsoft's Inflection AI hiring deal",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H69", "GOOGL", "2023-01-20", None,
                   "Alphabet announces about 12,000 job cuts",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H70", "GOOGL", "2024-03-20", None,
                   "French competition watchdog fines Google 250 million euros",
                   "legal_antitrust", "fine",
                   "accepted", "direct_mention", True),

    HistoricalCase("H71", "GOOGL", "2024-10-09", None,
                   "US Justice Department outlines remedies in Google search monopoly case",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H72", "GOOGL", "2025-03-19", None,
                   "EU charges Google with two Digital Markets Act breaches",
                   "legal_antitrust", "charge",
                   "accepted", "direct_mention", True),

    HistoricalCase("H73", "AMZN", "2023-01-04", None,
                   "Amazon expands layoffs to more than 18,000 roles",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H74", "AMZN", "2023-02-22", None,
                   "Amazon completes acquisition of One Medical",
                   "corporate_transaction", "acquisition",
                   "accepted", "direct_mention", True),

    HistoricalCase("H75", "AMZN", "2023-03-20", None,
                   "Amazon announces another 9,000 job cuts",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H76", "AMZN", "2023-05-31", None,
                   "FTC charges Amazon Ring over privacy and security failures",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H77", "META", "2022-11-09", None,
                   "Meta announces more than 11,000 job cuts",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H78", "META", "2023-03-14", None,
                   "Meta announces another 10,000 job cuts",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H79", "META", "2023-10-24", None,
                   "Dozens of US states sue Meta over alleged harm to children",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H80", "META", "2024-04-30", None,
                   "EU opens Digital Services Act investigation into Meta over election disinformation",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H81", "META", "2024-05-16", None,
                   "EU opens investigation into Meta over child safety risks",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H82", "NVDA", "2022-08-31", None,
                   "US imposes license requirement on Nvidia A100 and H100 chip exports to China",
                   "trade_export_control", "export_controls",
                   "accepted", "direct_mention", True),

    HistoricalCase("H83", "NVDA", "2024-12-04", None,
                   "EU scrutinizes Nvidia bundling practices during Run:ai review",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H84", "NVDA", "2024-12-09", None,
                   "China opens antitrust investigation into Nvidia",
                   "legal_antitrust", "investigation",
                   "accepted", "direct_mention", True),

    HistoricalCase("H85", "NVDA", "2024-12-30", None,
                   "Nvidia completes acquisition of Run:ai after regulatory reviews",
                   "corporate_transaction", "acquisition",
                   "accepted", "direct_mention", True),

    HistoricalCase("H86", "TSLA", "2023-02-16", None,
                   "Tesla recalls more than 362,000 US vehicles over Full Self-Driving software",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H87", "TSLA", "2023-05-12", None,
                   "Tesla recalls more than 1.1 million vehicles in China",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H88", "TSLA", "2024-02-02", None,
                   "Tesla recalls about 2.2 million US vehicles over warning-light font size",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H89", "TSLA", "2024-04-05", None,
                   "Reuters reports Tesla cancelled low-cost car project; Musk disputes report",
                   "boundary", "product_strategy",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H90", "TSLA", "2024-10-18", None,
                   "US opens investigation into Tesla Full Self-Driving after crashes",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),
    # ========================================================
    # H91-H120 — FROZEN V1.3.1 OUTCOMES
    # ========================================================
    HistoricalCase("H91", "AAPL", "2025-01-02", None,
                   "Apple agrees to pay $95 million to settle Siri privacy lawsuit",
                   "legal_antitrust", "settlement",
                   "accepted", "direct_mention", True),

    HistoricalCase("H92", "AAPL", "2023-04-24", None,
                   "US appeals court largely upholds Apple victory in Epic Games antitrust case",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H93", "AAPL", "2024-01-16", None,
                   "US Supreme Court declines Epic and Apple appeals in App Store dispute",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H94", "AAPL", "2024-02-27", None,
                   "Apple ends decade-long electric-car effort, reports say",
                   "boundary", "product_strategy",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H95", "MSFT", "2023-05-15", None,
                   "EU clears Microsoft Activision Blizzard acquisition with remedies",
                   "legal_antitrust", "remedy_proposal",
                   "accepted", "direct_mention", True),

    HistoricalCase("H96", "MSFT", "2024-09-04", None,
                   "UK clears Microsoft partnership and hiring deal with Inflection AI",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H97", "MSFT", "2025-05-13", None,
                   "Microsoft announces layoffs affecting about 6,000 employees",
                   "corporate_action", "workforce_reduction",
                   "accepted", "direct_mention", True),

    HistoricalCase("H98", "MSFT", "2025-07-02", None,
                   "Microsoft announces another round of layoffs affecting about 4 percent of workforce",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H99", "GOOGL", "2023-12-19", None,
                   "Google agrees to 700 million dollar Play Store antitrust settlement",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H100", "GOOGL", "2023-12-11", None,
                   "Epic Games wins antitrust jury verdict against Google Play",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H101", "GOOGL", "2024-09-10", None,
                   "EU top court upholds Google Shopping antitrust fine",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H102", "GOOGL", "2025-04-15", None,
                   "Japan orders Google to stop anticompetitive Android practices",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H103", "AMZN", "2023-05-31", None,
                   "Amazon agrees to Alexa children privacy settlement",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H104", "AMZN", "2022-03-17", None,
                   "Amazon completes MGM acquisition",
                   "corporate_transaction", "acquisition",
                   "accepted", "direct_mention", True),

    HistoricalCase("H105", "AMZN", "2022-12-20", None,
                   "Amazon settles EU antitrust investigations with binding commitments",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H106", "AMZN", "2024-05-28", None,
                   "US judge allows FTC Prime enrollment case against Amazon to proceed",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H107", "META", "2022-12-23", None,
                   "Meta agrees to Cambridge Analytica privacy settlement",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H108", "META", "2023-01-04", None,
                   "Irish regulator fines Meta over Facebook and Instagram advertising practices",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H109", "META", "2024-07-19", None,
                   "Nigeria fines Meta over consumer and data-law violations",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H110", "META", "2022-06-21", None,
                   "US Justice Department settles housing-ad discrimination case with Meta",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H111", "NVDA", "2022-02-07", None,
                   "Nvidia and SoftBank terminate Arm acquisition",
                   "corporate_transaction", "acquisition_terminated",
                   "accepted", "direct_mention", True),

    HistoricalCase("H112", "NVDA", "2023-09-28", None,
                   "French competition authority raids Nvidia offices in cloud-computing inquiry",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H113", "NVDA", "2024-07-15", None,
                   "French competition authority confirms Nvidia antitrust investigation",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H114", "NVDA", "2022-05-06", None,
                   "Nvidia settles SEC crypto-mining disclosure charges",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H115", "TSLA", "2024-07-30", None,
                   "Tesla recalls about 1.8 million US vehicles over hood-latch issue",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H116", "TSLA", "2024-04-26", None,
                   "US opens investigation into effectiveness of Tesla Autopilot recall",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H117", "TSLA", "2024-01-30", None,
                   "Delaware judge voids Elon Musk Tesla compensation package",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H118", "TSLA", "2024-04-08", None,
                   "Tesla settles fatal Autopilot crash lawsuit before trial",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

    HistoricalCase("H119", "TSLA", "2022-11-19", None,
                   "Tesla recalls more than 321,000 US vehicles over tail-light software issue",
                   "corporate_action", "recall",
                   "accepted", "direct_mention", True),

    HistoricalCase("H120", "TSLA", "2023-03-08", None,
                   "US opens investigation into Tesla Model Y steering-wheel detachments",
                   "boundary", "rejected_by_frozen_engine",
                   "rejected_boundary", "direct_mention", False),

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
      before 16:00 ET   -> same calendar date may be t0
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

        stock_prior, stock_t0, stock_t3, stock_t5 = locate_sessions(
            stock, effective_date
        )
        qqq_prior, qqq_t0, qqq_t3, qqq_t5 = locate_sessions(
            qqq, effective_date
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

        stock_1d = cumulative_return(stock, stock_prior, stock_t0)
        stock_3d = cumulative_return(stock, stock_prior, stock_t3)
        stock_5d = cumulative_return(stock, stock_prior, stock_t5)

        qqq_1d = cumulative_return(qqq, qqq_prior, qqq_t0)
        qqq_3d = cumulative_return(qqq, qqq_prior, qqq_t3)
        qqq_5d = cumulative_return(qqq, qqq_prior, qqq_t5)

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
    print("HISTORICAL MARKET REACTION — H01-H120")
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
