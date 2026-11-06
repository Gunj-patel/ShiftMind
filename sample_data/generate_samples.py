"""Generate synthetic sample shift logs (NOT real factory data).

    python sample_data/generate_samples.py

Creates: history_week.csv, daily_report_morning.xlsx, evening_notes.txt, night_report.pdf
The scenario has deliberately planted problems so the anomaly engine has something to find:
  * M-102 repeated motor overheating, maintenance left pending
  * M-104 reject spike on the night shift
  * M-103 data-entry error (downtime longer than the shift)
  * M-105 missing from the evening report
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent
random.seed(42)
MACHINES = {"M-101": ("Tablet A", 500), "M-102": ("Tablet B", 500), "M-103": ("Capsule C", 400),
            "M-104": ("Syrup D", 300), "M-105": ("Packing E", 600)}
SHIFTS = ["morning", "evening", "night"]
start = date(2026, 10, 26)

rows = []
for d in range(7):
    day = start + timedelta(days=d)
    for shift in SHIFTS:
        for m, (prod, target) in MACHINES.items():
            actual = int(target * random.uniform(0.94, 1.04))
            down = random.choice([0, 0, 5, 10, 15])
            reason = "Changeover" if down else ""
            rejected = int(actual * random.uniform(0.005, 0.02))
            kg = round(actual * 0.12 * random.uniform(0.97, 1.03), 1)
            maint, notes = "none", ""
            if m == "M-102" and d in (3, 5, 6) and shift == "evening":
                down, reason, maint = 70 + d * 5, "Motor overheating", "pending"
                actual = int(target * 0.78)
                notes = "Motor casing hot to touch"
            if m == "M-104" and d == 6 and shift == "night":
                rejected, notes = int(actual * 0.11), "Viscosity out of range"
            if m == "M-103" and d == 5 and shift == "morning":
                down, reason = 900, "Power failure"  # data entry error
            rows.append(dict(Date=day.isoformat(), Shift=shift, Machine=m, Product=prod, Target=target,
                             Actual=actual, Downtime=down, Rejected=rejected, **{"Raw Material (kg)": kg},
                             Reason=reason, Maintenance=maint, Remarks=notes, Operator=random.choice(["Ravi", "Meera", "Imran"])))

with open(OUT / "history_week.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# --- messy Excel (different headers, units, shift names) for the latest morning
latest = date(2026, 11, 2)
xl = pd.DataFrame([
    {"Report Date": "02/11/2026", "Shift Name": "Morning", "Equipment ID": "M-101", "Item": "Tablet A", "Planned Qty": 500,
     "Produced": 492, "Stoppage": "10 min", "Scrap": 8, "Material Used": 59.0, "Stoppage Reason": "Changeover", "PM Status": "", "Comments": ""},
    {"Report Date": "02/11/2026", "Shift Name": "Morning", "Equipment ID": "m-102", "Item": "Tablet B", "Planned Qty": 500,
     "Produced": 320, "Stoppage": "1.5 hrs", "Scrap": 6, "Material Used": 38.0, "Stoppage Reason": "Motor overheating", "PM Status": "Pending", "Comments": "Third time this week"},
    {"Report Date": "02/11/2026", "Shift Name": "Morning", "Equipment ID": "M-103", "Item": "Capsule C", "Planned Qty": 400,
     "Produced": 401, "Stoppage": "0", "Scrap": 5, "Material Used": 48.0, "Stoppage Reason": "", "PM Status": "", "Comments": ""},
    {"Report Date": "02/11/2026", "Shift Name": "Morning", "Equipment ID": "M-104", "Item": "Syrup D", "Planned Qty": 300,
     "Produced": 298, "Stoppage": "5", "Scrap": 3, "Material Used": 36.0, "Stoppage Reason": "Changeover", "PM Status": "", "Comments": ""},
    {"Report Date": "02/11/2026", "Shift Name": "Morning", "Equipment ID": "M-105", "Item": "Packing E", "Planned Qty": 600,
     "Produced": 590, "Stoppage": "0", "Scrap": 7, "Material Used": 70.0, "Stoppage Reason": "", "PM Status": "", "Comments": ""},
])
xl.to_excel(OUT / "daily_report_morning.xlsx", index=False)

# --- handwritten-style notes typed up (evening). M-105 is missing on purpose.
(OUT / "evening_notes.txt").write_text("""Date: 2026-11-02
Shift: Evening

Machine: M-101
Product: Tablet A
Target: 500
Actual: 505
Downtime: 0
Rejected: 6

Machine: M-102
Product: Tablet B
Target: 500
Actual: 340
Downtime: 110
Reason: Motor overheating
Maintenance: Pending
Notes: Motor smells burnt, kept running at low speed

Machine: M-103
Product: Capsule C
Target: 400
Actual: 395
Downtime: 5
Reason: Changeover

Machine: M-104
Product: Syrup D
Target: 300
Actual: 301
Downtime: 0
Rejected: 4
""")

# --- night PDF
import pymupdf

pdf_text = """NIGHT SHIFT REPORT
Date: 2026-11-02
Shift: Night

Machine: M-101
Product: Tablet A
Target: 500
Actual: 498
Downtime: 5
Reason: Changeover
Rejected: 5

Machine: M-102
Product: Tablet B
Target: 500
Actual: 210
Downtime: 240
Reason: Motor overheating
Maintenance: Pending
Notes: Machine stopped by operator, smoke smell

Machine: M-103
Product: Capsule C
Target: 400
Actual: 402
Downtime: 0
Rejected: 4

Machine: M-104
Product: Syrup D
Target: 300
Actual: 290
Downtime: 0
Rejected: 35
Quality Issue: Viscosity out of range, batch on hold

Machine: M-105
Product: Packing E
Target: 600
Actual: 596
Downtime: 0
Rejected: 6
"""
doc = pymupdf.open()
page = doc.new_page()
page.insert_text((50, 60), pdf_text, fontsize=10)
doc.save(OUT / "night_report.pdf")
print("sample data written to", OUT)
