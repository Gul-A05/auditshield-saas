from __future__ import annotations

from io import BytesIO
from pathlib import Path
import traceback

import pandas as pd
import streamlit as st


CSV_PATH = Path(__file__).with_name("raw_transactions.csv")
THRESHOLD_AMOUNT = 10_000
HISTORICAL_SPIKE_MULTIPLIER = 5
RISK_TIER_COLORS = {
	"CRITICAL": "#fee2e2",
	"HIGH": "#fef3c7",
	"MEDIUM": "#dbeafe",
	"LOW": "#f8fafc",
}
RISK_REASON_LABELS = {
	"A": "High-Value Transaction (>= $10k Threshold)",
	"B": "Negative or Corrupted Asset Value",
	"C": "Statistical Variance Anomaly (> 5x Baseline Average)",
}


st.set_page_config(
	page_title="AuditShield: Enterprise Ledger Auditor",
	page_icon="🛡️",
	layout="wide",
)

st.markdown(
	"""
	<style>
		.block-container {
			padding-top: 1.5rem;
			padding-bottom: 2rem;
		}
	</style>
	""",
	unsafe_allow_html=True,
)


def load_transactions(csv_path: Path) -> pd.DataFrame:
	"""Load and normalize the transaction data."""
	return pd.read_csv(csv_path)


def log_event(logs: list[str], level: str, message: str) -> None:
	logs.append(f"[{level}] {message}")


def prepare_transactions(df: pd.DataFrame, logs: list[str]) -> tuple[pd.DataFrame, int]:
	"""Normalize types, sort transactions into audit order, and track dirty rows."""
	log_event(logs, "INFO", "Data ingestion initialized...")
	result = df.copy()

	for required_column in ["Transaction_ID", "Employee_ID", "Amount"]:
		if required_column not in result.columns:
			raise KeyError(f"Missing required column: {required_column}")

	corrupted_records = 0
	cleaned_amounts: list[float] = []
	for index, raw_value in result["Amount"].items():
		numeric_value = pd.to_numeric(raw_value, errors="coerce")
		if pd.isna(numeric_value):
			corrupted_records += 1
			log_event(logs, "WARNING", f"Skipped corrupted entry at index {index} due to invalid Amount value {raw_value!r}.")
		cleaned_amounts.append(numeric_value)

	result["Amount"] = cleaned_amounts

	if "Timestamp" in result.columns:
		result["Timestamp"] = pd.to_datetime(result["Timestamp"], errors="coerce")
		sort_columns = ["Employee_ID", "Timestamp", "Transaction_ID"]
	else:
		sort_columns = ["Employee_ID", "Transaction_ID"]

	result = result.sort_values(sort_columns).reset_index(drop=True)
	log_event(logs, "SUCCESS", "Stored baseline variables for transaction ordering and numeric cleanup.")
	return result, corrupted_records



def add_risk_scoring(df: pd.DataFrame, logs: list[str]) -> pd.DataFrame:
	"""Compute cumulative composite risk scores and tiers for each transaction."""
	result = df.copy()
	result["Risk_Score"] = 0
	result["Risk_Reason"] = ""
	result["Risk_Tier"] = "LOW"

	employee_history: dict[str, list[float]] = {}
	log_event(logs, "INFO", "Starting row-by-row composite risk scoring...")

	for index, row in result.iterrows():
		score = 0
		matched_rules: list[str] = []
		employee_id = str(row.get("Employee_ID", "UNKNOWN"))
		amount = row.get("Amount")
		history = employee_history.setdefault(employee_id, [])

		if pd.notna(amount):
			if amount >= THRESHOLD_AMOUNT:
				score += 30
				matched_rules.append(RISK_REASON_LABELS["A"])
			if amount <= 0:
				score += 40
				matched_rules.append(RISK_REASON_LABELS["B"])

			if history:
				baseline_average = sum(history) / len(history)
				if baseline_average > 0:
					if amount > baseline_average * HISTORICAL_SPIKE_MULTIPLIER:
						score += 50
						matched_rules.append(RISK_REASON_LABELS["C"])
				else:
					log_event(logs, "WARNING", f"Skipped Rule C at index {index} due to non-positive historical average for employee {employee_id}.")
			else:
				log_event(logs, "INFO", f"Rule C bypassed at index {index} because employee {employee_id} has no prior baseline history.")
		else:
			log_event(logs, "WARNING", f"Skipped scoring at index {index} because Amount could not be converted to a numeric value.")

		result.at[index, "Risk_Score"] = min(score, 100)
		result.at[index, "Risk_Reason"] = "; ".join(matched_rules)
		if pd.notna(amount):
			history.append(float(amount))

	result["Risk_Tier"] = "LOW"
	result.loc[result["Risk_Score"].between(1, 39, inclusive="both"), "Risk_Tier"] = "MEDIUM"
	result.loc[result["Risk_Score"].between(40, 69, inclusive="both"), "Risk_Tier"] = "HIGH"
	result.loc[result["Risk_Score"].ge(70), "Risk_Tier"] = "CRITICAL"
	return result

	result["Risk_Tier"] = "LOW"
	result.loc[result["Risk_Score"].between(1, 39, inclusive="both"), "Risk_Tier"] = "MEDIUM"
	result.loc[result["Risk_Score"].between(40, 69, inclusive="both"), "Risk_Tier"] = "HIGH"
	result.loc[result["Risk_Score"].ge(70), "Risk_Tier"] = "CRITICAL"
	return result


def to_excel_bytes(df: pd.DataFrame) -> bytes:
	"""Serialize a DataFrame to an Excel workbook in memory."""
	output = BytesIO()
	with pd.ExcelWriter(output, engine="openpyxl") as writer:
		df.to_excel(writer, index=False, sheet_name="High_Risk_Anomalies")
	return output.getvalue()


def render_debug_logs(logs: list[str]) -> None:
	with st.expander("⚙️ System Debug & Pipeline Processing Logs", expanded=False):
		st.code("\n".join(logs) if logs else "[INFO] No pipeline logs were generated.", language="text")


def render_dashboard() -> None:
	st.title("AuditShield: Enterprise Ledger Auditor")
	st.caption("Upload a CSV ledger to scan for compliance anomalies and export the flagged transactions.")

	logs: list[str] = []
	process_succeeded = False
	corrupted_records = 0

	try:
		uploaded_file = st.file_uploader("Upload ledger CSV", type=["csv"])
		if uploaded_file is not None:
			log_event(logs, "INFO", f"User-uploaded ledger detected: {uploaded_file.name}.")
			raw_transactions = pd.read_csv(uploaded_file)
		else:
			log_event(logs, "INFO", f"No upload provided. Loading bundled sample ledger from {CSV_PATH.name}.")
			raw_transactions = load_transactions(CSV_PATH)
			st.info("No file uploaded. Showing the bundled sample ledger for demonstration.")

		if raw_transactions.empty:
			st.warning("The selected ledger has no rows to audit.")
			return

		transactions, corrupted_records = prepare_transactions(raw_transactions, logs)
		audited = add_risk_scoring(transactions, logs)
		high_risk = audited[audited["Risk_Score"].gt(0)].copy()
		high_risk = high_risk.sort_values(["Risk_Score", "Amount", "Transaction_ID"], ascending=[False, False, True]).reset_index(drop=True)

		total_records = len(audited)
		critical_threats = int(audited["Risk_Score"].ge(70).sum())
		total_exposure = float(audited.loc[audited["Risk_Score"].gt(0), "Amount"].fillna(0).sum())

		metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
		metric_col_1.metric(label="Total Ledger Volume Scanned", value=str(total_records))
		metric_col_2.metric(label="Critical Threats Detected", value=str(critical_threats))
		metric_col_3.metric(label="Total Financial Exposure ($)", value=f"${total_exposure:,.2f}")
		metric_col_4.metric(label="Corrupted/Skipped Records Found", value=str(corrupted_records))

		st.divider()

		if high_risk.empty:
			st.success("No high-risk anomalies were detected in the uploaded ledger.")
			process_succeeded = True
			return

		st.subheader("High-Risk Ledger Rows")

		def style_risk_rows(row: pd.Series) -> list[str]:
			tier = row.get("Risk_Tier", "LOW")
			background = RISK_TIER_COLORS.get(str(tier), RISK_TIER_COLORS["LOW"])
			if tier == "CRITICAL":
				text_color = "#991b1b"
			elif tier == "HIGH":
				text_color = "#92400e"
			elif tier == "MEDIUM":
				text_color = "#1d4ed8"
			else:
				text_color = "#0f172a"
			return [f"background-color: {background}; color: {text_color};" for _ in row]

		styled_table = high_risk.style.apply(style_risk_rows, axis=1)
		st.dataframe(styled_table, use_container_width=True, hide_index=True)

		csv_data = high_risk.to_csv(index=False).encode("utf-8")
		excel_data = to_excel_bytes(high_risk)

		download_col_1, download_col_2 = st.columns(2)
		download_col_1.download_button(
			label="Download CSV Report",
			data=csv_data,
			file_name="flagged_high_risk_transactions.csv",
			mime="text/csv",
			use_container_width=True,
		)
		download_col_2.download_button(
			label="Download Excel Report",
			data=excel_data,
			file_name="flagged_high_risk_transactions.xlsx",
			mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
			use_container_width=True,
		)
		process_succeeded = True

	except Exception as exc:
		log_event(logs, "ERROR", f"Pipeline processing failed: {exc}")
		log_event(logs, "ERROR", traceback.format_exc().strip())
		st.error("Audit processing failed due to a data pipeline error. See the system debug log below.")

	finally:
		render_debug_logs(logs)

	if not process_succeeded:
		return


def main() -> None:
	render_dashboard()


if __name__ == "__main__":
	main()