# AuditShield — Enterprise Ledger Auditor

AuditShield is a production-oriented prototype for automated ledger auditing and risk detection. It applies a defensive ingestion pipeline and a cumulative risk-scoring engine to flag high-priority financial anomalies, produce corporate audit reports, and provide transparent processing logs for compliance reviewers.

**Key highlights**
- Fast, deterministic scanning of full ledgers (100% coverage).
- Cumulative, weighted risk scoring (0–100) with clear `Risk_Tier` bands.
- Robust dirty-data handling and in-memory processing logs for auditability.
- Exportable, auditor-ready CSV / Excel reports for downstream review.

**Files of interest**
- Dashboard & engine: [app.py](app.py)
- Sample ledger: [raw_transactions.csv](raw_transactions.csv)

---

## Features

- Defensive ingestion: cleans and normalizes errant entries (e.g., textual garbage in numeric columns) and logs all corrections.
- Rule-based, cumulative scoring:
  - High-Value Transaction (>= $10k) — adds 30 points
  - Negative or Corrupted Asset Value — adds 40 points
  - Statistical Variance Anomaly (> 5x baseline) — adds 50 points
  - Scores are capped at 100; tiers: LOW / MEDIUM / HIGH / CRITICAL
- Interactive Streamlit UI with metrics, sortable/styled flagged rows, and report downloads (.csv, .xlsx).

---

## Quickstart — Local (developer)

1. Create & activate a Python virtual environment in the project root:

```bash
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

2. Install runtime dependencies from the lockfile:

```bash
pip install -r requirements.txt
```

3. Run the Streamlit dashboard (development):

```bash
streamlit run app.py
```

Open the shown URL in your browser to interact with the AuditShield UI.

---

## Using the App

- Upload a CSV ledger via the UI, or inspect the bundled `raw_transactions.csv` sample.
- Top-line metrics show total rows scanned, detected critical threats, total financial exposure, and corrupted/skipped records.
- The high-risk table is sorted by `Risk_Score` and highlighted by `Risk_Tier` for instant triage.
- Export flagged results with the CSV or Excel download buttons in the UI.

---

## Operational Notes

- The engine is defensive by design: any non-numeric `Amount` values are coerced to `NaN` and logged rather than crashing the pipeline.
- Rule C (variance anomaly) is evaluated only when an employee has prior historical transactions and the baseline average is positive; otherwise it is bypassed and logged.
- All ingestion and scoring events write brief messages to an in-memory debug log that can be expanded from the UI for compliance review.

---

## Developer / Contribution

1. Follow the Quickstart above to prepare your environment.
2. Run the dashboard and iterate on `app.py` for algorithm tuning or UI improvements.
3. Submit pull requests with clear test data and short changelog notes.
4. Run the automated enterprise test suite:
   ```bash
   python -m unittest test_engine.py
---
---
*Developed as an enterprise-grade CIS portfolio project demonstrating automated data validation, statistical anomaly detection, and fault-tolerant business intelligence frameworks.*