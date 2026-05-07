#!/usr/bin/env python3
"""Apply RAG Audit Report + Follow-up Chat pattern to all Detection pages."""

import ast
import re
from pathlib import Path

BASE = Path("c:/AKS LENOVO IDEAPAD DRIVE/D Drive - AI/ai-audit-engineer-portfolio")
PAGES_DIR = BASE / "pages"

# Map: page filename -> (page_key, flagged_var_expr, module_name)
# flagged_var_expr is the variable name or expression that holds the flagged DataFrame
PAGE_CONFIGS = {
    "brs_reconciliation.py":     ("brs",     "unmatched_bank",          "BRS Reconciliation"),
    "receivables_bad_debt.py":   ("rec",     "critical",                "Receivables & Bad Debt"),
    "gst_tds_compliance.py":     ("gst",     "type1",                   "GST Compliance"),
    "related_party_monitor.py":  ("rpm",     "related_high",            "Related-Party Monitor"),
    "duplicate_invoice_detector.py": ("dup",   "duplicates",              "Duplicate Invoice Detector"),
    "inventory_anomaly.py":      ("inv",     "anomalies",               "Inventory Anomaly"),
    "fixed_asset_auditor.py":    ("fa",      "anomalies",               "Fixed Asset Auditor"),
    "expense_claim_auditor.py":  ("exp",     "flagged",                 "Expense Claim Auditor"),
    "payroll_audit.py":          ("pay",     "anomalies",               "Payroll Audit"),
    "sales_revenue_auditor.py":  ("sales",   "exceptions",              "Sales Revenue Auditor"),
    "itgc_sap_access_auditor.py":("itgc",    "anomalies",               "ITGC & SAP Access"),
    "contract_management_auditor.py": ("cnt", "anomalies",             "Contract Management"),
    "statistical_sampling.py":   ("sample",  "anomalies",               "Statistical Sampling"),
    "dynamic_audit_builder.py":  ("dab",     "anomalies",               "Dynamic Audit Builder"),
}


APPEND_SNIPPET = '''
# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    render_rag_report_section(
        "{page_key}",
        flagged_df={flagged_expr},
        module_name="{module_name}"
    )
except Exception as _e:
    st.caption(f"RAG report unavailable: {{_e}}")
'''


def add_rag_to_page(page_file: str, page_key: str, flagged_expr: str, module_name: str):
    path = PAGES_DIR / page_file
    if not path.exists():
        print(f"⚠️  Not found: {page_file}")
        return

    content = path.read_text()

    # Check if already has render_rag_report_section
    if "render_rag_report_section" in content:
        print(f"✅ Already has RAG: {page_file}")
        return

    # Find the last line that is a statement (not blank, not a comment)
    lines = content.splitlines()
    last_stmt_idx = len(lines) - 1
    while last_stmt_idx >= 0 and lines[last_stmt_idx].strip() in ("", "\n"):
        last_stmt_idx -= 1

    # Insert after the last statement
    snippet = APPEND_SNIPPET.format(page_key=page_key, flagged_expr=flagged_expr, module_name=module_name)
    new_content = content + "\n" + snippet

    path.write_text(new_content)
    print(f"✅ Updated: {page_file}")


def main():
    for page_file, (page_key, flagged_expr, module_name) in PAGE_CONFIGS.items():
        add_rag_to_page(page_file, page_key, flagged_expr, module_name)


if __name__ == "__main__":
    main()
