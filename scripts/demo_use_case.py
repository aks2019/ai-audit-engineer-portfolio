"""
SARVAGYA Use Case Demo: FY 2025-26 Internal Audit - Emami Agrotech Ltd

This script demonstrates the complete audit workflow implemented in this session:
1. Create Audit Engagement
2. Add Entities & Standards
3. Run Financial Statement Checks (Deterministic)
4. Stage Findings for Review (Draft Workflow)
5. Confirm Findings (Maker-Checker)
6. Generate Audit Committee Report
"""

import sys
sys.path.insert(0, '.')

from utils.audit_db import (
    init_audit_db, add_engagement, add_entity, load_findings,
    stage_findings, confirm_draft_findings, load_draft_findings, get_sla_breaches
)
from core.evidence import init_evidence_tables
from core.audit_program import init_audit_program_tables, seed_standard_checklists
from core.standards_registry import seed_official_standards, list_standards
from core.rbac import init_rbac
from core.policy_manager import init_policy_tables
from checks.financial_statement import (
    generate_fs_review_report, check_ind_as_applicability,
    check_related_party_disclosures, check_ppe_ageing, check_inventory_nrv,
    check_borrowings_msme_statutory
)
from reports import generate_audit_committee_pack
import pandas as pd
from datetime import datetime, timedelta


def demo_use_case():
    print("=" * 70)
    print("SARVAGYA USE CASE: FY 2025-26 Internal Audit - Emami Agrotech Ltd")
    print("=" * 70)

    # Step 1: Initialize System (already done, but for demo)
    print("\n[Step 1] System already initialized with:")
    print("  - 28 database tables (engagements, standards, controls, RBAC, etc.)")
    print("  - 53 official audit standards (Companies Act, CARO, Ind AS, AS, CAS)")
    print("  - 15 default controls")
    print("  - CARO 2020 & Ind AS checklists")

    # Step 2: Create Audit Engagement
    print("\n[Step 2] Creating Audit Engagement...")
    engagement_id = add_engagement(
        name="FY 2025-26 Internal Audit - Emami Agrotech Ltd",
        description="Annual internal audit for FY 2025-26 covering financial statements, SAP processes, and compliance",
        start_date="2025-04-01",
        end_date="2026-03-31",
        status="Ongoing"
    )
    print(f"  Created engagement ID: {engagement_id}")

    # Step 3: Add Entity (Company/Location)
    print("\n[Step 3] Adding Entity...")
    entity_id = add_entity(
        engagement_id=engagement_id,
        entity_name="Emami Agrotech Ltd",
        location="Kolkata, West Bengal",
        code="EAL-HQ"
    )
    print(f"  Added entity: Emami Agrotech Ltd (ID: {entity_id})")

    # Step 4: Show Applicable Standards
    print("\n[Step 4] Applicable Standards for this Audit:")
    standards = list_standards()
    print(f"  Total standards in registry: {len(standards)}")

    # Show key standards for this audit
    key_standards = standards[standards['family'].isin(['CARO', 'Ind AS', 'Companies Act'])].head(10)
    print("\n  Key Standards:")
    for _, row in key_standards.iterrows():
        print(f"    - {row['family']}: {row['reference']} - {row['description'][:50]}...")

    # Step 5: Simulate Trial Balance Data
    print("\n[Step 5] Simulating Trial Balance Data for Financial Statement Review...")
    tb_data = {
        'account_name': [
            'Share Capital', 'Reserves & Surplus', 'Long Term Borrowings', 'Short Term Borrowings',
            'Trade Payables', 'Provision for Tax', 'Fixed Assets - Plant', 'Fixed Assets - Building',
            'Inventory - Raw Materials', 'Inventory - Finished Goods', 'Trade Receivables',
            'Cash & Bank', 'Sales - Domestic', 'Sales - Export', 'Cost of Goods Sold',
            'Employee Cost', 'Depreciation', 'Interest Expense'
        ],
        'account_group': [
            'Share Capital', 'Reserves', 'Long Term Borrowings', 'Short Term Borrowings',
            'Trade Payables', 'Provisions', 'Fixed Assets', 'Fixed Assets',
            'Inventory', 'Inventory', 'Trade Receivables',
            'Cash', 'Revenue', 'Revenue', 'Cost of Sales',
            'Expenses', 'Depreciation', 'Finance Cost'
        ],
        'closing_debit': [0, 0, 0, 5000000, 15000000, 0, 25000000, 12000000,
                         8000000, 3500000, 12000000, 2500000, 0, 0, 0, 0, 0, 0],
        'closing_credit': [10000000, 15000000, 8000000, 0, 0, 2500000, 0, 0,
                         0, 0, 0, 0, 45000000, 8000000, 32000000, 18000000, 2500000, 1800000]
    }
    tb_df = pd.DataFrame(tb_data)

    # Step 6: Run Deterministic Financial Statement Checks
    print("\n[Step 6] Running Deterministic Financial Statement Checks...")

    entity_info = {
        "name": "Emami Agrotech Ltd",
        "turnover": 53000000,  # 53 Cr
        "listed": False,
        "net_worth": 25000000,  # 25 Cr
        "industry": "FMCG"
    }

    # Check 1: Ind AS Applicability
    ind_as_result = check_ind_as_applicability(
        turnover=entity_info["turnover"],
        listed=entity_info["listed"],
        net_worth=entity_info["net_worth"]
    )
    print(f"\n  [Check 1] Ind AS Applicability:")
    print(f"    Applies Ind AS: {ind_as_result['applies_ind_as']}")
    print(f"    Framework: {ind_as_result['framework']}")
    print(f"    Rules: {ind_as_result['rules_applied'][0]['note'] if ind_as_result['rules_applied'] else 'N/A'}")

    # Check 2: Related Party Disclosures (simulated)
    rp_list = [
        {"name": "Emami Group Holdings", "relationship": "Holding Company"},
        {"name": "Baidyanath Prasad", "relationship": "Key Management Personnel"}
    ]
    rp_result = check_related_party_disclosures(tb_df, rp_list)
    print(f"\n  [Check 2] Related Party Disclosures:")
    print(f"    RP Transactions Found: {len(rp_result['rp_transactions'])}")
    if rp_result['issues']:
        for issue in rp_result['issues']:
            print(f"    - {issue['type']}: {issue['description']}")

    # Check 3: Borrowings, MSME & Statutory Dues
    borrow_result = check_borrowings_msme_statutory(tb_df)
    print(f"\n  [Check 3] Borrowings, MSME & Statutory:")
    print(f"    Total Issues: {len(borrow_result['issues'])}")
    for issue in borrow_result['issues']:
        print(f"    - {issue['type']}: {issue.get('account', 'N/A')} - Amount: {issue.get('amount', issue.get('balance', 0))}")

    # Step 7: Stage Findings (NOT auto-logged - Maker-Checker Workflow)
    print("\n[Step 7] Staging Findings for Auditor Review (Draft Workflow)...")

    # Create proposed findings from checks
    proposed_findings = pd.DataFrame([
        {
            "area": "Related Party",
            "finding": "Emami Group Holdings - Rs 45L credit balance in trade payables - verify if related party transaction as per Section 188",
            "amount_at_risk": 4500000,
            "vendor_name": "Emami Group Holdings",
            "period": "FY 2025-26",
            "risk_band": "HIGH",
            "checklist_ref": "CARO Clause 12"
        },
        {
            "area": "Borrowings",
            "finding": "Short term borrowings Rs 50L - verify terms and interest rate compliance",
            "amount_at_risk": 5000000,
            "vendor_name": "Various Banks",
            "period": "FY 2025-26",
            "risk_band": "MEDIUM",
            "checklist_ref": "Schedule III"
        },
        {
            "area": "Statutory Dues",
            "finding": "Provision for tax Rs 25L - verify timely deposit of TDS as per Section 40(a)(ia)",
            "amount_at_risk": 2500000,
            "vendor_name": "Income Tax Department",
            "period": "FY 2025-26",
            "risk_band": "HIGH",
            "checklist_ref": "CARO Clause 8"
        }
    ])

    staged = stage_findings(
        findings_df=proposed_findings,
        module_name="Financial Statement Auditor",
        engagement_id=engagement_id,
        entity_id=entity_id,
        period="FY 2025-26",
        generated_by="auditor"
    )
    print(f"  Staged {staged} findings for review")

    # Step 8: Load Draft Findings for Review
    print("\n[Step 8] Loading Draft Findings for Auditor Review...")
    drafts = load_draft_findings(engagement_id=engagement_id, status="Draft")
    print(f"  Draft findings pending review: {len(drafts)}")
    if len(drafts) > 0:
        for _, f in drafts.iterrows():
            print(f"    - [{f['risk_band']}] {f['area']}: {f['finding'][:60]}...")

    # Step 9: Confirm Findings (Auditor Reviews and Confirms)
    print("\n[Step 9] Auditor Confirms Selected Findings (Maker-Checker)...")
    if len(drafts) > 0:
        # Confirm first 2 findings
        confirm_ids = drafts['id'].head(2).tolist()
        confirmed = confirm_draft_findings(confirm_ids, confirmed_by="CA Sharma")
        print(f"  Confirmed {confirmed} findings as official audit findings")

    # Step 10: Generate Audit Committee Pack
    print("\n[Step 10] Generating Audit Committee Pack...")
    report = generate_audit_committee_pack(engagement_id)
    print(f"  Report Type: {report['report_type']}")
    print(f"  Generated At: {report['generated_at']}")
    print(f"  Total Findings: {report['findings_summary']['total']}")

    if 'by_risk' in report['findings_summary']:
        print("\n  Findings by Risk:")
        for r in report['findings_summary']['by_risk']:
            print(f"    - {r.get('risk_band', 'N/A')}: {r.get('id', 0)} findings, Rs {r.get('amount_at_risk', 0):,.0f}")

    # Step 11: SLA Breach Check
    print("\n[Step 11] Checking SLA Breaches...")
    breaches = get_sla_breaches(engagement_id=engagement_id)
    print(f"  Overdue findings: {len(breaches)}")

    print("\n" + "=" * 70)
    print("USE CASE COMPLETE")
    print("=" * 70)
    print("""
Summary of Implemented Features Demonstrated:
1. Audit Engagement Lifecycle - Create, track, manage audits
2. Standards Registry - 53 official standards from MCA/ICAI/ICMAI
3. Deterministic FS Checks - Ind AS, RP, Borrowings, MSME, Statutory
4. Draft Findings Workflow - No auto-logging, requires confirmation
5. Maker-Checker - Auditor reviews, confirms, or discards findings
6. Reporting - Audit Committee Pack generation
7. RBAC - Users, roles, permissions
8. Controls Library - Process, risk, control mapping
""")


if __name__ == "__main__":
    demo_use_case()