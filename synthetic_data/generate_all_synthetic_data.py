"""Generate synthetic test data for all 26 AI Audit Engineer modules.

Run: python synthetic_data/generate_all_synthetic_data.py
Output: 15+ CSV files in synthetic_data/ folder
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

np.random.seed(42)
OUT = Path("synthetic_data")
OUT.mkdir(exist_ok=True)

N = 500  # default rows

# ── P1: Vendor Payments ───────────────────────────────────────────
vendors = [f"VENDOR_{i:03d}" for i in range(1, 51)]
categories = ["Raw Material", "Packing Material", "Consumables", "AMC", "Capex", "Services"]
df = pd.DataFrame({
    "vendor_name": np.random.choice(vendors, N),
    "amount": np.random.lognormal(mean=12, sigma=1.5, size=N).round(2),
    "days_overdue": np.random.choice([0, 15, 45, 75, 120, 180], N, p=[0.3, 0.2, 0.2, 0.15, 0.1, 0.05]),
    "category": np.random.choice(categories, N),
    "plant_code": np.random.choice(["P01", "P02", "P03"], N),
    "related_party": np.random.choice([0, 1], N, p=[0.92, 0.08]),
    "credit_terms_days": np.random.choice([30, 45, 60, 90], N),
    "tolerance_override_flag": np.random.choice([0, 1], N, p=[0.97, 0.03]),
    "invoice_number": [f"INV{datetime(2024,1,1) + timedelta(days=i):%Y%m%d}{i:04d}" for i in range(N)],
    "posting_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 365, N)],
    "document_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 365, N)],
})
# Inject anomalies
df.loc[np.random.choice(df.index, 25, replace=False), "amount"] *= np.random.uniform(5, 15, 25)
df.loc[np.random.choice(df.index, 20, replace=False), "days_overdue"] = np.random.randint(90, 365, 20)
df.to_csv(OUT / "P1_vendor_payments.csv", index=False)

# ── P5: Bank Statement + GL Extract ──────────────────────────────
bank = pd.DataFrame({
    "bank_date": pd.date_range("2024-01-01", periods=N, freq="D").strftime("%Y-%m-%d"),
    "bank_amount": np.random.normal(50000, 20000, N).round(2),
    "bank_narration": np.random.choice(["CHQ DEP", "NEFT IN", "CASH DEP", "SWEEP", "IMPS"], N),
    "bank_chq_no": [f"CHQ{i:06d}" for i in range(N)],
})
# Some unmatched items
bank.loc[np.random.choice(bank.index, 30, replace=False), "bank_amount"] += np.random.uniform(1000, 5000, 30)
bank.to_csv(OUT / "P5_bank_statement.csv", index=False)

gl = pd.DataFrame({
    "gl_date": pd.date_range("2024-01-01", periods=N, freq="D").strftime("%Y-%m-%d"),
    "gl_amount": np.random.normal(50000, 20000, N).round(2),
    "gl_narration": np.random.choice(["CHQ DEP", "NEFT IN", "CASH DEP", "SWEEP", "IMPS"], N),
    "gl_chq_no": [f"CHQ{i:06d}" for i in range(N)],
})
gl.to_csv(OUT / "P5_gl_extract.csv", index=False)

# ── P6: Customer Outstanding ─────────────────────────────────────
customers = [f"CUST_{i:03d}" for i in range(1, 31)]
cust = pd.DataFrame({
    "customer_name": np.random.choice(customers, N),
    "amount": np.random.lognormal(mean=11, sigma=1.2, size=N).round(2),
    "days_overdue": np.random.choice([0, 10, 30, 60, 90, 150, 250], N, p=[0.25, 0.2, 0.2, 0.15, 0.1, 0.07, 0.03]),
    "credit_limit": np.random.choice([50000, 100000, 200000, 500000], N),
})
cust.to_csv(OUT / "P6_customer_outstanding.csv", index=False)

# ── P8: GST GSTR-2A + Books + TDS ────────────────────────────────
gstr = pd.DataFrame({
    "invoice_no": [f"INV{20240000+i}" for i in range(N)],
    "taxable_amount": np.random.lognormal(mean=11, sigma=1, size=N).round(2),
    "gst_rate": np.random.choice([5, 12, 18, 28], N),
    "vendor_gstin": [f"27AABCU{i:05d}A1Z5" for i in range(N)],
})
gstr.to_csv(OUT / "P8_gstr2a.csv", index=False)

books = pd.DataFrame({
    "invoice_no": [f"INV{20240000+i}" for i in range(N)],
    "taxable_amount": np.random.lognormal(mean=11, sigma=1, size=N).round(2),
    "gst_rate": np.random.choice([5, 12, 18, 28], N),
})
# Mismatches
books.loc[np.random.choice(books.index, 20, replace=False), "taxable_amount"] += np.random.uniform(100, 5000, 20)
books.to_csv(OUT / "P8_books_data.csv", index=False)

tds = pd.DataFrame({
    "section": np.random.choice(["194C", "194I", "194J", "194H", "194A", "192", "195"], N),
    "payment_amount": np.random.lognormal(mean=10, sigma=1.3, size=N).round(2),
    "tds_rate_pct": np.random.choice([1.0, 2.0, 5.0, 10.0, 10.0, 0.0, 0.0], N),
    "payee_type": np.random.choice(["individual", "company"], N),
})
tds.to_csv(OUT / "P8_tds_ledger.csv", index=False)

# ── P9: Vendor Master ────────────────────────────────────────────
vm = pd.DataFrame({
    "vendor_name": [f"VENDOR_{i:03d}" for i in range(1, 101)],
    "pan": [f"ABCDE{i:04d}F" for i in range(1, 101)],
    "bank_account": [f"{np.random.randint(10000000, 99999999):08d}" for _ in range(100)],
    "address": [f"Plot {i}, Industrial Area, City {i%10}" for i in range(1, 101)],
    "related_party": np.random.choice([0, 1], 100, p=[0.9, 0.1]),
    "total_spend": np.random.lognormal(mean=12, sigma=1.5, size=100).round(2),
})
# Duplicate PANs for ghost vendor detection
vm.loc[5, "pan"] = vm.loc[6, "pan"]
vm.loc[15, "bank_account"] = vm.loc[16, "bank_account"]
vm.to_csv(OUT / "P9_vendor_master.csv", index=False)

# ── P10: Invoice / Payment Register ──────────────────────────────
inv = pd.DataFrame({
    "invoice_no": [f"INV{20240000+i}" for i in range(N)],
    "vendor_name": np.random.choice(vendors, N),
    "amount": np.random.lognormal(mean=11, sigma=1, size=N).round(2),
    "po_rate": np.random.lognormal(mean=11, sigma=0.9, size=N).round(2),
    "invoice_date": pd.date_range("2024-01-01", periods=N, freq="D").strftime("%Y-%m-%d"),
})
# Duplicates and variance
inv.loc[100:104, ["vendor_name", "amount"]] = inv.loc[105:109, ["vendor_name", "amount"]].values
inv.loc[np.random.choice(inv.index, 15, replace=False), "amount"] = inv.loc[np.random.choice(inv.index, 15, replace=False), "amount"].values * 1.08
inv.to_csv(OUT / "P10_invoice_register.csv", index=False)

# ── P11: Inventory Extract ───────────────────────────────────────
inv_items = [f"MAT{i:05d}" for i in range(1, 201)]
inv_df = pd.DataFrame({
    "material_code": np.random.choice(inv_items, N),
    "unrestricted_qty": np.random.randint(0, 1000, N),
    "value": np.random.lognormal(mean=10, sigma=1, size=N).round(2),
    "last_movement_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 400, N)],
    "shelf_life_expiry": [(datetime(2025,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(-100, 365, N)],
    "abc_class": np.random.choice(["A", "B", "C"], N, p=[0.2, 0.3, 0.5]),
    "material_type": np.random.choice(["RM", "PM", "FG", "SFG", "Spares"], N),
    "plant": np.random.choice(["P01", "P02", "P03"], N),
})
inv_df.to_csv(OUT / "P11_inventory_extract.csv", index=False)

# ── P12: Asset Register ──────────────────────────────────────────
assets = pd.DataFrame({
    "asset_description": np.random.choice(["Plant Machinery", "Computer", "Furniture", "Vehicle", "Building", "Server Rack", "AC Unit", "Whitewash"], N),
    "cost": np.random.lognormal(mean=12, sigma=1.5, size=N).round(2),
    "accumulated_depreciation": np.random.lognormal(mean=10, sigma=1.2, size=N).round(2),
    "applied_rate_pct": np.random.choice([3.34, 6.67, 10.0, 33.33, 9.5], N),
    "asset_class": np.random.choice(["Plant & Machinery", "Buildings (Factory)", "Furniture & Fixtures", "Computers", "Vehicles"], N),
    "acquisition_date": [(datetime(2020,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 1500, N)],
    "capex_approved": np.random.choice([0, 1], N, p=[0.05, 0.95]),
})
assets.to_csv(OUT / "P12_asset_register.csv", index=False)

# ── P13: Expense Claims ──────────────────────────────────────────
grades = ["Grade A", "Grade B", "Grade C"]
expense = pd.DataFrame({
    "employee_id": [f"EMP{i:04d}" for i in range(1, N+1)],
    "grade": np.random.choice(grades, N),
    "claim_amount": np.random.lognormal(mean=7, sigma=0.8, size=N).round(2),
    "claim_type": np.random.choice(["Travel", "Hotel", "Meals", "Conveyance", "Training"], N),
    "approver_id": [f"EMP{i:04d}" for i in np.random.randint(1, N, N)],
    "docs_attached": np.random.choice([0, 1], N, p=[0.15, 0.85]),
})
# Self-approved
expense.loc[10:14, "approver_id"] = expense.loc[10:14, "employee_id"].values
expense.to_csv(OUT / "P13_expense_register.csv", index=False)

# ── P18: Payroll Register ────────────────────────────────────────
payroll = pd.DataFrame({
    "employee_id": [f"EMP{i:04d}" for i in range(1, N+1)],
    "pan": [f"ABCDE{i:04d}F" for i in range(1, N+1)],
    "bank_account": [f"{np.random.randint(10000000, 99999999):08d}" for _ in range(N)],
    "basic_da": np.random.lognormal(mean=10, sigma=0.5, size=N).round(2),
    "pf_deducted": np.random.lognormal(mean=8, sigma=0.4, size=N).round(2),
    "esi_deducted": np.random.lognormal(mean=7, sigma=0.3, size=N).round(2),
    "gross_wages": np.random.lognormal(mean=10.5, sigma=0.6, size=N).round(2),
    "status": np.random.choice(["Active", "Resigned", "On Leave"], N, p=[0.88, 0.08, 0.04]),
    "last_attendance_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 200, N)],
})
# Ghost employees
dup_indices = np.random.choice(payroll.index, 10, replace=False)
payroll.loc[dup_indices[:5], "pan"] = payroll.loc[dup_indices[:5], "pan"].values  # duplicate PANs
payroll.loc[dup_indices[5:], "bank_account"] = payroll.loc[dup_indices[5:], "bank_account"].values
payroll.to_csv(OUT / "P18_payroll_register.csv", index=False)

# ── P19: Sales Register ──────────────────────────────────────────
sales = pd.DataFrame({
    "invoice_no": [f"SINV{20240000+i}" for i in range(N)],
    "amount": np.random.lognormal(mean=11.5, sigma=1, size=N).round(2),
    "invoice_date": pd.date_range("2024-01-01", periods=N, freq="D").strftime("%Y-%m-%d"),
    "dispatch_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(-2, 5, N)],
    "credit_note_no": np.random.choice([""] * 450 + [f"CN{20240000+i}" for i in range(50)], N),
    "credit_note_date": np.random.choice([""] * 450 + pd.date_range("2024-01-01", periods=50, freq="D").strftime("%Y-%m-%d").tolist(), N),
    "customer_name": np.random.choice(customers, N),
})
sales.to_csv(OUT / "P19_sales_register.csv", index=False)

# ── P20: SUIM Access Dump ────────────────────────────────────────
tcodes = ["FK01", "F110", "ME21N", "MIGO", "PC00", "PA30", "FD01", "VF11", "FB50", "FBV0", "FS00", "FBL1N", "MB52"]
users = [f"USER{i:03d}" for i in range(1, 51)]
access = pd.DataFrame({
    "user_id": np.random.choice(users, N*2),
    "tcode": np.random.choice(tcodes, N*2),
    "role": np.random.choice(["FI_USER", "MM_USER", "HR_USER", "SAP_ALL", "SAP_NEW", "SD_USER"], N*2),
    "last_login": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 200, N*2)],
    "status": np.random.choice(["Active", "Locked", "Inactive"], N*2, p=[0.85, 0.1, 0.05]),
})
# SoD conflicts
access.loc[0, ["user_id", "tcode", "role"]] = ["USER001", "FK01", "FI_USER"]
access.loc[1, ["user_id", "tcode", "role"]] = ["USER001", "F110", "FI_USER"]
access.loc[2, ["user_id", "tcode", "role"]] = ["USER002", "ME21N", "MM_USER"]
access.loc[3, ["user_id", "tcode", "role"]] = ["USER002", "MIGO", "MM_USER"]
access.loc[4, ["user_id", "tcode", "role"]] = ["USER003", "PC00", "HR_USER"]
access.loc[5, ["user_id", "tcode", "role"]] = ["USER003", "PA30", "HR_USER"]
# Generic IDs
access.loc[6, "user_id"] = "ADMIN"
access.loc[7, "user_id"] = "TEST"
access.to_csv(OUT / "P20_suim_access_dump.csv", index=False)

# ── P21: Contract Register ───────────────────────────────────────
contracts = pd.DataFrame({
    "contract_no": [f"CTR{20240000+i}" for i in range(200)],
    "vendor_name": np.random.choice(vendors, 200),
    "start_date": [(datetime(2023,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 400, 200)],
    "end_date": [(datetime(2024,6,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 300, 200)],
    "contract_value": np.random.lognormal(mean=12, sigma=1.5, size=200).round(2),
    "last_payment_date": [(datetime(2024,1,1) + timedelta(days=int(i))).strftime("%Y-%m-%d") for i in np.random.randint(0, 400, 200)],
    "ld_rate_pct": np.random.choice([0.5, 1.0, 2.0, 5.0], 200),
    "ld_recovered": np.random.lognormal(mean=9, sigma=1, size=200).round(2),
})
contracts.to_csv(OUT / "P21_contract_register.csv", index=False)

# ── P25: Population Data (for sampling) ──────────────────────────
pop = pd.DataFrame({
    "transaction_id": [f"TXN{20240000+i}" for i in range(1000)],
    "amount": np.random.lognormal(mean=11, sigma=1.2, size=1000).round(2),
    "department": np.random.choice(["Finance", "HR", "Operations", "Sales", "Procurement"], 1000),
    "vendor_name": np.random.choice(vendors, 1000),
})
pop.to_csv(OUT / "P25_population_data.csv", index=False)

print("Synthetic data generated successfully!")
print(f"Location: {OUT.resolve()}")
for f in sorted(OUT.glob("*.csv")):
    print(f"   - {f.name}")
