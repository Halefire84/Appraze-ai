import tempfile
import unittest
from pathlib import Path

from crtc_learning import OpportunityOutcome, append_outcome, learning_report, load_outcomes


class TestCRTCLearning(unittest.TestCase):
    def test_outcomes_round_trip_and_profit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learning.jsonl"
            append_outcome(
                OpportunityOutcome(
                    listing_id="x1",
                    source="eBay",
                    title="old receiver",
                    predicted_score=91,
                    decision="BUY",
                    acquisition_cost=40,
                    resale_price=200,
                    signal_codes=["weak_title", "brand_hidden_in_description"],
                ),
                path,
            )
            rows = load_outcomes(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].realized_profit(), 160)
            report = learning_report(rows)
            self.assertEqual(report["positive_outcomes"], 1)
            self.assertEqual(report["win_rate"], 1.0)
            self.assertEqual(report["signal_performance"]["weak_title"]["observations"], 1)


if __name__ == "__main__":
    unittest.main()
