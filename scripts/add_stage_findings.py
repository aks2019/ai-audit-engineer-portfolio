#!/usr/bin/env python3
"""Add stage_findings + draft review to all Detection pages that use checker.log_to_db."""

from pathlib import Path

BASE = Path("c:/AKS LENOVO IDEAPAD DRIVE/D Drive - AI/ai-audit-engineer-portfolio")
PAGES_DIR = BASE / "pages"

# Map: page -> (page_key, module_name, area_name, checklist_ref)
PAGE_CONFIGS = {
    "brs_reconciliation.py": ("brs", "BRS Reconciliation", "Bank Reconciliation", "Treasury A.2/A.3"),
    "receivables_bad_debt.py": ("rec", "Receivables & Bad Debt", "Receivables", "SAP Depot 5 / HO 15"),
    "related_party_monitor.py": ("rpm", "Related-Party Monitor", "Related Party", "Vendor Mgmt B.3–B.8"),
    "duplicate_invoice_detector.py": ("dup", "Duplicate Invoice Detector", "Duplicate Invoices", "Invoice Verification"),
    "inventory_anomaly.py": ("inv", "Inventory Anomaly", "Inventory", "Inventory Mgmt A.6–A.11"),
    "fixed_asset_auditor.py": ("fa", "Fixed Asset Auditor", "Fixed Assets", "Fixed Assets G.1–G.5"),
    "expense_claim_auditor.py": ("exp", "Expense Claim Auditor", "Expense Claims", "Employee Expenses"),
    "payroll_audit.py": ("pay", "Payroll Audit", "Payroll", "Payroll Controls"),
    "sales_revenue_auditor.py": ("sales", "Sales Revenue Auditor", "Sales", "Sales Controls"),
    "itgc_sap_access_auditor.py": ("itgc", "ITGC & SAP Access", "ITGC", "ITGC Controls"),
    "contract_management_auditor.py": ("cnt", "Contract Management", "Contracts", "Contract Management"),
}

def process_page(page_file: str, page_key: str, module_name: str, area_name: str, checklist_ref: str):
    path = PAGES_DIR / page_file
    if not path.exists():
        print(f"  ⚠️  Not found: {page_file}")
        return

    content = path.read_text(encoding="utf-8")
    if "stage_findings" in content and "_stage_findings" in content:
        print(f"  ✅ Already has stage_findings: {page_file}")
        return

    # Only add to files that have checker.log_to_db
    if "checker.log_to_db(" not in content:
        print(f"  ⚠️  No checker.log_to_db: {page_file}")
        return

    lines = content.splitlines()
    new_lines = []
    found_log = False
    for i, line in enumerate(lines):
        new_lines.append(line)
        if not found_log and "checker.log_to_db(" in line:
            found_log = True
            # Add stage_findings after this line with correct lead indentation
            # Determine the base indentation of the current line
            leading_ws = len(line) - len(line.lstrip())
            indent = " " * leading_ws
            new_lines.append(f"\n{indent}        # ── Stage Findings for Draft Review ──")
            new_lines.append(f"{indent}        from utils.audit_db import stage_findings as _stage_findings")
            new_lines.append(f"{indent}        _staged = _stage_findings(")
            new_lines.append(f"{indent}            log_df,")
            new_lines.append(f'"{indent}            module_name="{module_name}",')
            new_lines.append(f"{indent}            run_id=run_id,")
            new_lines.append(f"{indent}            period=datetime.utcnow().strftime(\"%Y-%m\"),")
            new_lines.append(f"{indent}            source_file_name=getattr(uploaded_file, \"name\", \"manual\") if 'uploaded_file' in locals() else \"manual\",")
            new_lines.append(f"{indent}        )")
            new_lines.append(f"{indent}        st.info(f\"📋 {{_staged}} exception(s) staged for your review.\")")
            # Store run_id for draft review
            new_lines.append(f"{indent}        st.session_state.draft_run_id = run_id")

    if not found_log:
        print(f"  ⚠️  ERROR: checker.log_to_db not found: {page_file}")
        return

    # Add render_draft_review_section at the end
    new_lines.append(f"\n")
    new_lines.append(f"# --- Draft Review ---")
    new_lines.append(f"from utils.audit_page_helpers import render_draft_review_section")
    new_lines.append(f"render_draft_review_section('{page_key}', '{module_name}')")

    new_content = "\n".join(new_lines)
    path.write_text(new_content, encoding="utf-8")
    print(f"  ✅ Updated: {page_file}")


def main():
    for page_file, (page_key, module_name, area_name, checklist_ref) in PAGE_CONFIGS.items():
        process_page(page_file, page_key, module_name, area_name, checklist_ref)


if __name__ == "__main__":
    main()
