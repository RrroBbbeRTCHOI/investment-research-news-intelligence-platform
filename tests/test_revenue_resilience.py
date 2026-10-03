import os
import unittest
from unittest.mock import patch

from support import Replay
from src.services.revenue_resilience_service import get_revenue_resilience


class RevenueResilienceV14Tests(unittest.TestCase):
    EXPECTED = {
        "AAPL": 77.94363464150553, "MSFT": 75.39859521909781,
        "GOOGL": 76.95830542843694, "AMZN": 84.2360402804893,
        "META": 41.17379702351418, "NVDA": 50.87677428896605,
        "TSLA": 66.06295544273004,
    }

    def test_exact_v14_outputs_and_weight_formula(self):
        for ticker, expected in self.EXPECTED.items():
            with self.subTest(ticker=ticker):
                result = get_revenue_resilience(ticker)
                self.assertEqual(result["model_version"], "REVENUE-RESILIENCE-V1.4")
                self.assertAlmostEqual(result["revenue_resilience_score"], expected, places=10)
                self.assertAlmostEqual(
                    result["revenue_resilience_score"],
                    .60 * result["diversification"]["score"] + .40 * result["persistence"]["score"],
                    places=12,
                )

    def test_three_year_gate_and_provisional_values_are_not_zeroed(self):
        for ticker in self.EXPECTED:
            result = get_revenue_resilience(ticker)
            if ticker in {"AAPL", "META"}:
                self.assertTrue(result["production_ready"])
                self.assertGreaterEqual(result["persistence"]["history_years_present"], 3)
            else:
                self.assertFalse(result["production_ready"])
                self.assertEqual(result["status"], "PROVISIONAL_2Y")
                self.assertIsNotNone(result["revenue_resilience_score"])
                self.assertNotEqual(result["revenue_resilience_score"], 0)

    def test_formal_eq_inclusion_only_after_gate(self):
        with Replay():
            from src.services.earnings_quality_service import build_earnings_quality
            for ticker in ("AAPL", "MSFT"):
                result = build_earnings_quality(ticker)
                component = result["components"][-1]
                self.assertEqual(component["formal_eligible"], ticker == "AAPL")
                self.assertEqual(component["effective_weight"] is not None, ticker == "AAPL")
                self.assertEqual(result["legacy_quality_summary"]["Core Revenue Score"], None)

    def test_analyst_summary_fallback_is_immediate_and_evidence_only(self):
        from src.services.analyst_summary_service import get_analyst_summary
        financials = {"period": {"current": "2025", "prior": "2024"},
                      "analyst_interpretation": {"positive_observation": "Cash conversion improved.",
                                                  "main_concern": "Margins compressed."}}
        quality = {"revenue_resilience": get_revenue_resilience("MSFT")}
        with patch.dict(os.environ, {"RESEARCH_GEMINI_ENABLED": "false"}, clear=False):
            result = get_analyst_summary("MSFT", financials, quality)
        self.assertEqual(result["source"], "Deterministic evidence fallback")
        self.assertIn("Cash conversion improved.", result["text"])
        self.assertIn("provisional and excluded from the formal score", result["text"])

    def test_analyst_summary_fallback_removes_internal_diagnostic_jargon(self):
        from src.services.analyst_summary_service import get_analyst_summary
        financials = {"period": {"current": "2025", "prior": "2024"},
                      "analyst_interpretation": {
                          "positive_observation": "Unknown: no supported positive structural observation.",
                          "main_concern": "Review the bridge (arithmetic_supported).",
                      }}
        quality = {"revenue_resilience": get_revenue_resilience("AAPL")}
        with patch.dict(os.environ, {"RESEARCH_GEMINI_ENABLED": "false"}, clear=False):
            result = get_analyst_summary("AAPL", financials, quality)
        self.assertNotIn("Unknown:", result["text"])
        self.assertNotIn("arithmetic_supported", result["text"])
        self.assertIn("evidence-backed", result["text"])
        self.assertIn("statement-level arithmetic reconciliation", result["text"])


if __name__ == "__main__":
    unittest.main()
