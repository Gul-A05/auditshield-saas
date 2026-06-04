import unittest

import pandas as pd

import app


class TestAuditShieldRiskEngine(unittest.TestCase):
	def setUp(self) -> None:
		self.logs: list[str] = []
		self.mock_ledger = pd.DataFrame(
			[
				{
					"Transaction_ID": "TX2001",
					"Employee_ID": "EMP10",
					"Amount": 100.00,
					"Location": "Houston",
					"Timestamp": "2026-06-04 08:00:00",
				},
				{
					"Transaction_ID": "TX2002",
					"Employee_ID": "EMP10",
					"Amount": 600.00,
					"Location": "Houston",
					"Timestamp": "2026-06-04 09:00:00",
				},
				{
					"Transaction_ID": "TX2003",
					"Employee_ID": "EMP10",
					"Amount": 15000.00,
					"Location": "Houston",
					"Timestamp": "2026-06-04 10:00:00",
				},
				{
					"Transaction_ID": "TX2004",
					"Employee_ID": "EMP20",
					"Amount": -45.00,
					"Location": "Austin",
					"Timestamp": "2026-06-04 08:30:00",
				},
				{
					"Transaction_ID": "TX2005",
					"Employee_ID": "EMP30",
					"Amount": 12500.00,
					"Location": "Dallas",
					"Timestamp": "2026-06-04 08:45:00",
				},
				{
					"Transaction_ID": "TX2006",
					"Employee_ID": "EMP40",
					"Amount": 55.00,
					"Location": "Plano",
					"Timestamp": "2026-06-04 08:15:00",
				},
			]
		)

	def _run_engine(self) -> pd.DataFrame:
		cleaned, corrupted_records = app.prepare_transactions(self.mock_ledger, self.logs)
		self.assertEqual(corrupted_records, 0)
		return app.add_risk_scoring(cleaned, self.logs)

	def test_cumulative_risk_scores_are_correct(self) -> None:
		scored = self._run_engine().set_index("Transaction_ID")

		expected_scores = {
			"TX2001": 0,
			"TX2002": 50,
			"TX2003": 80,
			"TX2004": 40,
			"TX2005": 30,
			"TX2006": 0,
		}

		for transaction_id, expected_score in expected_scores.items():
			self.assertEqual(int(scored.at[transaction_id, "Risk_Score"]), expected_score)

	def test_risk_tiers_match_thresholds(self) -> None:
		scored = self._run_engine().set_index("Transaction_ID")

		expected_tiers = {
			"TX2001": "LOW",
			"TX2002": "HIGH",
			"TX2003": "CRITICAL",
			"TX2004": "HIGH",
			"TX2005": "MEDIUM",
			"TX2006": "LOW",
		}

		for transaction_id, expected_tier in expected_tiers.items():
			self.assertEqual(str(scored.at[transaction_id, "Risk_Tier"]), expected_tier)

	def test_combined_rule_reason_and_critical_count(self) -> None:
		scored = self._run_engine().set_index("Transaction_ID")

		combined_reason = str(scored.at["TX2003", "Risk_Reason"])
		self.assertEqual(
			combined_reason,
			"High-Value Transaction (>= $10k Threshold); Statistical Variance Anomaly (> 5x Baseline Average)",
		)

		critical_threats = int((scored["Risk_Score"] >= 70).sum())
		self.assertEqual(critical_threats, 1)


if __name__ == "__main__":
	unittest.main(verbosity=2)
