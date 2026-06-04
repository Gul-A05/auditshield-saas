from __future__ import annotations

from io import BytesIO
from pathlib import Path

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
	df = pd.read_csv(csv_path)
	return prepare_transactions(df)


def prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
	"""Normalize types and sort transactions into audit order."""
	df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

	if "Timestamp" in df.columns:
		df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
		sort_columns = ["Employee_ID", "Timestamp", "Transaction_ID"]
	else:
		sort_columns = ["Employee_ID", "Transaction_ID"]

	return df.sort_values(sort_columns).reset_index(drop=True)


def add_risk_reason(df: pd.DataFrame) -> pd.DataFrame:
	"""Annotate each transaction with the compliance rule(s) it violates."""
	result = df.copy()

	historical_average = (
		result.groupby("Employee_ID", group_keys=False)["Amount"]
		.apply(lambda amounts: amounts.expanding().mean().shift(1))
		.reset_index(level=0, drop=True)
	)

	rule_a = result["Amount"].ge(THRESHOLD_AMOUNT)
	rule_b = result["Amount"].le(0)
	rule_c = historical_average.notna() & result["Amount"].gt(historical_average * HISTORICAL_SPIKE_MULTIPLIER)

	reasons = []
	for is_rule_a, is_rule_b, is_rule_c in zip(rule_a, rule_b, rule_c):
		matched_rules = []
		if is_rule_a:
			matched_rules.append("Rule A: Amount >= $10,000")
		if is_rule_b:
			matched_rules.append("Rule B: Amount <= 0")
		if is_rule_c:
			matched_rules.append("Rule C: Amount > 5x employee historical average")
		reasons.append("; ".join(matched_rules))

	result["Risk_Reason"] = reasons
	return result


def add_risk_scoring(df: pd.DataFrame) -> pd.DataFrame:
	"""Compute weighted composite risk scores and tiers for each transaction."""
	result = add_risk_reason(df)
	result["Risk_Score"] = 0

	rule_a = result["Amount"].ge(THRESHOLD_AMOUNT)
	rule_b = result["Amount"].le(0)
	rule_c = result["Risk_Reason"].str.contains("Rule C", na=False)

	result.loc[rule_a, "Risk_Score"] += 30
	result.loc[rule_b, "Risk_Score"] += 40
	result.loc[rule_c, "Risk_Score"] += 50
	result["Risk_Score"] = result["Risk_Score"].clip(upper=100)

	conditions = [
		result["Risk_Score"].ge(70),
		result["Risk_Score"].between(40, 69, inclusive="both"),
		result["Risk_Score"].between(1, 39, inclusive="both"),
	]
	choices = ["CRITICAL", "HIGH", "MEDIUM"]
	result["Risk_Tier"] = pd.Series(pd.NA, index=result.index, dtype="object")
	result.loc[:, "Risk_Tier"] = pd.Series(pd.cut(result["Risk_Score"], bins=[-1, 0, 39, 69, 100], labels=["LOW", "MEDIUM", "HIGH", "CRITICAL"], include_lowest=True), index=result.index)
	result["Risk_Tier"] = result["Risk_Tier"].astype(str).str.upper().replace({"NAN": "LOW"})
	result.loc[result["Risk_Score"].eq(0), "Risk_Tier"] = "LOW"
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


def render_dashboard() -> None:
	st.title("AuditShield: Enterprise Ledger Auditor")
	st.caption("Upload a CSV ledger to scan for compliance anomalies and export the flagged transactions.")

	uploaded_file = st.file_uploader("Upload ledger CSV", type=["csv"])
	if uploaded_file is not None:
		transactions = prepare_transactions(pd.read_csv(uploaded_file))
	else:
		transactions = load_transactions(CSV_PATH)
		st.info("No file uploaded. Showing the bundled sample ledger for demonstration.")

	if transactions.empty:
		st.warning("The selected ledger has no rows to audit.")
		return

	audited = add_risk_scoring(transactions)
	high_risk = audited[audited["Risk_Score"].gt(0)].copy()
	high_risk = high_risk.sort_values(["Risk_Score", "Amount", "Transaction_ID"], ascending=[False, False, True]).reset_index(drop=True)

	total_records = len(audited)
	critical_threats = int(audited["Risk_Score"].ge(70).sum())
	total_exposure = float(audited.loc[audited["Risk_Score"].gt(0), "Amount"].fillna(0).sum())

	metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
	metric_col_1.metric(label="Total Ledger Volume Scanned", value=str(total_records))
	metric_col_2.metric(label="Critical Threats Detected", value=str(critical_threats))
	metric_col_3.metric(label="Total Financial Exposure ($)", value=f"${total_exposure:,.2f}")

	st.divider()

	if high_risk.empty:
		st.success("No high-risk anomalies were detected in the uploaded ledger.")
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


def main() -> None:
	render_dashboard()


if __name__ == "__main__":
	main()