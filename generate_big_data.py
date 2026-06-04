import pandas as pd
import random
from datetime import datetime, timedelta

# Configurations for realistic generation
num_records = 500
employees = [f"EMP{i:02d}" for i in range(1, 15)] # 14 active employees
locations = ["Houston", "Stafford", "The Woodlands", "Katy", "Sugar Land"]

data = []
start_time = datetime(2026, 6, 1, 8, 0, 0)

# 1. Generate 490 rows of clean, operational baseline data
for i in range(1, 491):
    tx_id = f"TX{1000 + i}"
    emp = random.choice(employees)
    # Most employees average around $20 - $150 per transaction
    amount = round(random.uniform(15.00, 150.00), 2)
    loc = random.choice(locations)
    timestamp = start_time + timedelta(minutes=i * 7) # transactions spaced out
    
    data.append([tx_id, emp, amount, loc, timestamp.strftime("%Y-%m-%d %H:%M:%S")])

# 2. Inject intentional corporate threats and messy data spikes
# A. Critical Threat: Over $10k AND massive baseline spike (Should score 80)
data.append(["TX2491", "EMP02", 15450.00, "Houston", "2026-06-03 14:22:00"])

# B. High Threat: Massive spike variance compared to their regular $50 entries
data.append(["TX2492", "EMP05", 950.00, "Katy", "2026-06-03 15:45:00"])

# C. High Threat: Negative value audit breach
data.append(["TX2493", "EMP09", -120.00, "Sugar Land", "2026-06-03 16:10:00"])

# D. Medium Threat: Straight $11k threshold trigger (Normal baseline)
data.append(["TX2494", "EMP12", 11000.00, "Stafford", "2026-06-03 17:01:00"])

# E. Edge Case: Brand new employee with NO historical baseline (Tests zero division prevention)
data.append(["TX2495", "EMP99", 75.00, "The Woodlands", "2026-06-03 18:00:00"])

# F. Corrupted Pipeline Files (Tests your exception catching and logging metrics)
data.append(["TX2496", "EMP04", "MALFORMED_STRING", "Houston", "ERROR_DATE"])
data.append(["TX2497", "EMP06", "NULL", "Sugar Land", "NaN"])
data.append(["TX2498", "EMP11", "", "Katy", "2026-06-03 19:12:00"])

# Compile into a DataFrame and export
df = pd.DataFrame(data, columns=["Transaction_ID", "Employee_ID", "Amount", "Location", "Timestamp"])
df.to_csv("enterprise_scale_ledger.csv", index=False)
print("[SUCCESS] Created 'enterprise_scale_ledger.csv' with 500 rows of high-volume corporate transaction logs!")