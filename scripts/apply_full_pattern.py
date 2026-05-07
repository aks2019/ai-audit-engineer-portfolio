#!/usr/bin/env python3
"""Apply RAG + stage_findings + draft review to all Detection pages (correct version)."""

from pathlib import Path

BASE = Path("c:/AKS LENOVO IDEAPAD DRIVE/D Drive - AI/ai-audit-engineer-portfolio")
PAGES_DIR = BASE / "pages"

PAGE_CONFIGS = {
    "brs_reconciliation.py":     ("brs",   "unmatched_bank",       ""),
    "receivables_bad_debt.py":   ("rec",   "critical",             ""),
    "gst_tds_compliance.py":     ("gst",   "type1",                ""),
    "related_party_monitor.py":  ("rpm",   "df",                   ""),
    "duplicate_invoice_detector.py": ("dup", "exact",              ""),
    "inventory_anomaly.py":      ("inv",   "slow",                 ""),
    "fixed_asset_auditor.py":    ("fa",   "anomalies",            ""),
    "expense_claim_auditor.py":  ("exp",   "flagged",              ""),
    "payroll_audit.py":          ("pay",   "anomalies",            ""),
    "sales_revenue_auditor.py":  ("sales", "exceptions",           ""),
    "itgc_sap_access_auditor.py":("itgc",  "log_df",               ""),
    "contract_management_auditor.py": ("cnt", "df",                ""),
    "statistical_sampling.py":   ("sample","flagged",              ""),
    "dynamic_audit_builder.py":  ("dab",   "anomalies",            ""),
}


SNIPPET_RAG = """
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

SNIPPET_DRAFT = """
# --- Draft Review ---
try:
    from utils.audit_page_helpers import render_draft_review_section
    render_draft_review_section("{page_key}", "{module_name}")
except Exception as _e:
    st.caption(f"Draft review unavailable: {{_e}}")
"""


def add_to_page(page_file: str, page_key: str, flagged_expr: str):
    path = PAGES_DIR / page_file
    if not path.exists():
        print(f"⚠️  Not found: {page_file}")
        return False

    content = path.read_text(encoding="utf-8")

    # Skip if already processed
    if "render_rag_report_section" in content:
        print(f"🔒 Already has RAG: {page_file}")
        return False

    # Stage 1: Add stage_findings after checker.log_to_db
    lines = content.splitlines()
    new_lines = []
    found_log = False
    for line in lines:
        new_lines.append(line)
        if not found_log and "checker.log_to_db(" in line:
            found_log = True
            # Determine indentation
            leading_ws = len(line) - len(line.lstrip())
            indent = line[:leading_ws] if leading_ws > 0 else ""
            new_lines.append(indent + "# ── Stage Findings for Draft Review ──")
            new_lines.append(indent + "from utils.audit_db import stage_findings as _stage_findings")
            new_lines.append(indent + "_staged = _stage_findings(")
            new_lines.append(indent + "    log_df,")
            new_lines.append(indent + '    module_name="' + get_module_name(page_file) + '",')
            new_lines.append(indent + "    run_id=run_id,")
            new_lines.append(indent + '    period=datetime.utcnow().strftime("%Y-%m"),')
            new_lines.append(indent + '    source_file_name=getattr(uploaded_file, \"name\", \"manual\") if \'uploaded_file\' in locals() else \"manual\",')
            new_lines.append(indent + ")")
            new_lines.append(indent + 'st.info(f"📋 {_staged} exception(s) staged for your review.")')
            new_lines.append(indent + "st.session_state.draft_run_id = run_id")

    # Add RAG snippet at end
    module_name = get_module_name(page_file)
    new_lines.append("\n" + SNIPPET_RAG.format(page_key=page_key, flagged_expr=flagged_expr, module_name=module_name))

    # Add Draft Review snippet at end
    new_lines.append("\n" + SNIPPET_DRAFT.format(page_key=page_key, module_name=module_name))

    new_content = "\n".join(new_lines)
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ Updated: {page_file}")
    return True


def get_module_name(page_file: str) -> str:
    """Extract a clean module name from filename."""
    name = page_file.replace(".py", "").replace("_", " ").title()
    return name


def main():
    for page_file, (page_key, flagged_expr, _) in PAGE_CONFIGS.items():
        add_to_page(page_file, page_key, flagged_expr)


if __name__ == "__main__":
    main()
