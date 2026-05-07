#!/usr/bin/env python3
"""Apply RAG Audit Report + Follow-up Chat pattern to all Detection pages."""

from pathlib import Path

BASE = Path("c:/AKS LENOVO IDEAPAD DRIVE/D Drive - AI/ai-audit-engineer-portfolio")
PAGES_DIR = BASE / "pages"

# Map: page -> (page_key, flagged_var_expr, module_name)
# flagged_var_expr can be any valid Python expression evaluating to a DataFrame or None
PAGE_CONFIGS = {
    "brs_reconciliation.py":     ("brs",   "unmatched_bank",       "BRS Reconciliation"),
    "receivables_bad_debt.py":   ("rec",   "critical",             "Receivables & Bad Debt"),
    "gst_tds_compliance.py":     ("gst",   "type1",                "GST Compliance"),
    "related_party_monitor.py":  ("rpm",   "df",                   "Related-Party Monitor"),
    "duplicate_invoice_detector.py": ("dup", "exact",              "Duplicate Invoice Detector"),
    "inventory_anomaly.py":      ("inv",   "slow",                 "Inventory Anomaly"),
    "fixed_asset_auditor.py":    ("fa",    "df",                   "Fixed Asset Auditor"),
    "expense_claim_auditor.py":  ("exp",   "flagged",              "Expense Claim Auditor"),
    "payroll_audit.py":          ("pay",   "anomalies",            "Payroll Audit"),
    "sales_revenue_auditor.py":  ("sales", "exceptions",           "Sales Revenue Auditor"),
    "itgc_sap_access_auditor.py":("itgc",  "log_df",               "ITGC & SAP Access"),
    "contract_management_auditor.py": ("cnt", "df",                "Contract Management"),
    "statistical_sampling.py":   ("sample","flagged",              "Statistical Sampling"),
    "dynamic_audit_builder.py":  ("dab",   "anomalies",            "Dynamic Audit Builder"),
}

SNIPPET = """
# --- AI Audit Report (RAG) ---
try:
    from utils.audit_page_helpers import render_rag_report_section
    flagged_rag_df = {flagged_expr} if '{flagged_expr}' in locals() and {flagged_expr} is not None and not {flagged_expr}.empty else None
    if flagged_rag_df is not None:
        render_rag_report_section(
            "{page_key}",
            flagged_df=flagged_rag_df,
            module_name="{module_name}"
        )
    else:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {{_e}}")
"""


def add_rag_to_page(page_file: str, page_key: str, flagged_expr: str, module_name: str):
    path = PAGES_DIR / page_file
    if not path.exists():
        print(f"⚠️  Not found: {page_file}")
        return

    content = path.read_text(encoding="utf-8")
    if "render_rag_report_section" in content:
        print(f"✅ Already has RAG: {page_file}")
        return

    snippet = SNIPPET.format(page_key=page_key, flagged_expr=flagged_expr, module_name=module_name)
    new_content = content + "\n" + snippet
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ Updated: {page_file}")


def main():
    for page_file, (page_key, flagged_expr, module_name) in PAGE_CONFIGS.items():
        add_rag_to_page(page_file, page_key, flagged_expr, module_name)


if __name__ == "__main__":
    main()
