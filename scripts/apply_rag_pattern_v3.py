#!/usr/bin/env python3
"""Apply RAG Audit Report + Follow-up Chat pattern to all Detection pages."""

from pathlib import Path

BASE = Path("c:/AKS LENOVO IDEAPAD DRIVE/D Drive - AI/ai-audit-engineer-portfolio")
PAGES_DIR = BASE / "pages"

PAGE_CONFIGS = {
    "brs_reconciliation.py":     ("brs",   "unmatched_bank",       "BRS Reconciliation"),
    "receivables_bad_debt.py":   ("rec",   "critical",             "Receivables & Bad Debt"),
    "gst_tds_compliance.py":     ("gst",   "type1",                "GST Compliance"),
    "related_party_monitor.py":  ("rpm",   "df",                   "Related-Party Monitor"),
    "duplicate_invoice_detector.py": ("dup", "exact",              "Duplicate Invoice Detector"),
    "inventory_anomaly.py":      ("inv",   "slow",                 "Inventory Anomaly"),
    "fixed_asset_auditor.py":    ("fa",   "anomalies",            "Fixed Asset Auditor"),
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
    flagged_rag = None
    try:
        flagged_rag = {flagged_expr}
    except (NameError, AttributeError):
        pass
    if flagged_rag is not None and not flagged_rag.empty:
        render_rag_report_section(
            "{page_key}",
            flagged_df=flagged_rag,
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

    # Find last st.button or st.caption and insert BEFORE it
    lines = content.splitlines()
    
    # Find lines that start with 'st.caption' or 'st.button'
    insert_after = len(lines) - 1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line.startswith("st.caption") or line.startswith("st.button"):
            insert_after = i
            break
    
    # Insert the snippet after the found line
    snippet = SNIPPET.format(page_key=page_key, flagged_expr=flagged_expr, module_name=module_name)
    new_lines = lines[:insert_after + 1] + snippet.splitlines() + lines[insert_after + 1:]
    new_content = "\n".join(new_lines)
    
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ Updated: {page_file}")


def main():
    for page_file, (page_key, flagged_expr, module_name) in PAGE_CONFIGS.items():
        add_rag_to_page(page_file, page_key, flagged_expr, module_name)


if __name__ == "__main__":
    main()
