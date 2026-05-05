"""SAP Data Pack Review Engine - Standard SAP Extract Templates."""
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime


# Standard SAP data pack definitions with expected columns and validations
SAP_DATA_PACKS = {
    "FBL1N": {
        "name": "Vendor Line Item Display",
        "description": "Accounts Payable aging and transactions",
        "expected_columns": ["Vendor", "Doc.No", "Type", "BusArea", "PstngDate", "DueDate",
                           "Amount", "Currency", "Text", "Ref", "Year"],
        "required_columns": ["Vendor", "PstngDate", "Amount", "DueDate"],
        "sap_tcode": "FBL1N",
        "audit_procedures": [
            "Vendor aging analysis >90 days",
            "Duplicate invoice detection",
            "Payment terms compliance",
            "Inter-company/vendor transactions"
        ]
    },
    "FBL5N": {
        "name": "Customer Line Item Display",
        "description": "Accounts Receivable aging and collections",
        "expected_columns": ["Customer", "Doc.No", "Type", "BusArea", "PstngDate", "DueDate",
                           "Amount", "Currency", "Text", "Ref", "Year"],
        "required_columns": ["Customer", "PstngDate", "Amount", "DueDate"],
        "sap_tcode": "FBL5N",
        "audit_procedures": [
            "Customer aging analysis >90 days",
            "Credit note validity",
            "Sales returns authorization",
            "Related party receivables"
        ]
    },
    "FBL3N": {
        "name": "G/L Account Line Item Display",
        "description": "General Ledger transaction listing",
        "expected_columns": ["Account", "Doc.No", "BusArea", "PstngDate", "ValueDate",
                           "Amount", "Currency", "Text", "Ref", "Year"],
        "required_columns": ["Account", "PstngDate", "Amount"],
        "sap_tcode": "FBL3N",
        "audit_procedures": [
            "Journal entry audit trail",
            "Manual posting review",
            "Period end adjustments",
            "Posting to P&L vs BS accounts"
        ]
    },
    "MB51": {
        "name": "Material Movement History",
        "description": "Inventory movement transactions",
        "expected_columns": ["Material", "Doc.Date", "MoveType", "Plant", "StorageLoc",
                           "Qty", "Amount", "Vendor", "PoNum", "Doc.Num"],
        "required_columns": ["Material", "Doc.Date", "MoveType", "Qty"],
        "sap_tcode": "MB51",
        "audit_procedures": [
            "Inventory movement anomalies",
            "Goods receipt without PO",
            "Negative inventory check",
            "Fast/slow moving items"
        ]
    },
    "MB52": {
        "name": "Warehouse Stocks by Plant",
        "description": "Current inventory valuation",
        "expected_columns": ["Material", "Plant", "StorageLoc", "Unrestricted", "Blocked",
                           "InTransit", "Value", "ValType"],
        "required_columns": ["Material", "Plant", "Unrestricted", "Value"],
        "sap_tcode": "MB52",
        "audit_procedures": [
            "Inventory valuation methods",
            "Blocked stock aging",
            "Stock reconciliation with G/L"
        ]
    },
    "AS03": {
        "name": "Asset Register",
        "description": "Fixed asset master and depreciation",
        "expected_columns": ["Asset", "Description", "AcquisitionDate", "Cost", "AccumDepr",
                           "NetValue", "UsefulLife", "DepreciationType", "Location"],
        "required_columns": ["Asset", "AcquisitionDate", "Cost", "NetValue"],
        "sap_tcode": "AS03",
        "audit_procedures": [
            "Asset capitalization review",
            "Depreciation calculation accuracy",
            "Asset disposal authorization",
            "Impairment review"
        ]
    },
    "SUIM": {
        "name": "User Information System",
        "description": "User and role assignments",
        "expected_columns": ["User", "Role", "Profile", "ValidFrom", "ValidTo", "UserType"],
        "required_columns": ["User", "Role"],
        "sap_tcode": "SUIM",
        "audit_procedures": [
            "Segregation of duties conflicts",
            "Privileged access review",
            "Inactive user cleanup",
            "Critical role assignments"
        ]
    }
}


def validate_sap_pack(df: pd.DataFrame, pack_type: str) -> Dict[str, Any]:
    """
    Validate SAP data pack against expected schema.
    Returns validation results and missing column warnings.
    """
    if pack_type not in SAP_DATA_PACKS:
        return {"status": "UNKNOWN_PACK", "pack_type": pack_type}

    pack = SAP_DATA_PACKS[pack_type]
    expected = pack["expected_columns"]
    required = pack["required_columns"]

    actual_cols = [c.strip() for c in df.columns]
    missing_required = [c for c in required if c not in actual_cols]
    missing_expected = [c for c in expected if c not in actual_cols]
    extra_columns = [c for c in actual_cols if c not in expected]

    return {
        "pack_type": pack_type,
        "tcode": pack["sap_tcode"],
        "status": "VALID" if not missing_required else "INVALID",
        "missing_required": missing_required,
        "missing_expected": missing_expected,
        "extra_columns": extra_columns,
        "row_count": len(df),
        "column_count": len(actual_cols)
    }


def analyze_vendor_aging(vendor_df: pd.DataFrame, reference_date: str = None) -> Dict[str, Any]:
    """
    Analyze FBL1N vendor aging and detect issues.
    """
    if vendor_df.empty:
        return {"status": "NO_DATA", "issues": []}

    if reference_date is None:
        reference_date = datetime.now().strftime("%Y-%m-%d")

    try:
        ref_date = pd.to_datetime(reference_date)
    except:
        ref_date = datetime.now()

    issues = []

    # Calculate aging
    for _, row in vendor_df.iterrows():
        try:
            pstng_date = pd.to_datetime(row.get('PstngDate', row.get('PostingDate')))
            due_date = pd.to_datetime(row.get('DueDate'))

            if pd.notna(due_date):
                days_overdue = (ref_date - due_date).days

                if days_overdue > 90:
                    issues.append({
                        "type": "OVERDUE_90",
                        "vendor": row.get('Vendor'),
                        "doc_no": row.get('Doc.No'),
                        "amount": abs(row.get('Amount', 0)),
                        "days_overdue": days_overdue,
                        "severity": "HIGH"
                    })
                elif days_overdue > 0:
                    issues.append({
                        "type": "OVERDUE_LESS_90",
                        "vendor": row.get('Vendor'),
                        "doc_no": row.get('Doc.No'),
                        "amount": abs(row.get('Amount', 0)),
                        "days_overdue": days_overdue,
                        "severity": "MEDIUM"
                    })
        except:
            pass

    # Summary by vendor
    vendor_summary = vendor_df.groupby('Vendor').agg({
        'Amount': lambda x: x.abs().sum()
    }).reset_index()
    vendor_summary.columns = ['Vendor', 'Total_Outstanding']

    return {
        "status": "ANALYZED",
        "total_vendors": vendor_df['Vendor'].nunique(),
        "total_records": len(vendor_df),
        "issues": issues,
        "overdue_90_count": len([i for i in issues if i['type'] == 'OVERDUE_90']),
        "vendor_summary": vendor_summary.to_dict('records')
    }


def analyze_customer_aging(customer_df: pd.DataFrame, reference_date: str = None) -> Dict[str, Any]:
    """
    Analyze FBL5N customer aging and detect issues.
    """
    if customer_df.empty:
        return {"status": "NO_DATA", "issues": []}

    if reference_date is None:
        reference_date = datetime.now().strftime("%Y-%m-%d")

    try:
        ref_date = pd.to_datetime(reference_date)
    except:
        ref_date = datetime.now()

    issues = []

    for _, row in customer_df.iterrows():
        try:
            due_date = pd.to_datetime(row.get('DueDate'))

            if pd.notna(due_date):
                days_overdue = (ref_date - due_date).days

                if days_overdue > 90:
                    issues.append({
                        "type": "OVERDUE_90",
                        "customer": row.get('Customer'),
                        "doc_no": row.get('Doc.No'),
                        "amount": abs(row.get('Amount', 0)),
                        "days_overdue": days_overdue,
                        "severity": "HIGH"
                    })
        except:
            pass

    # Calculate total receivables
    total_receivables = customer_df['Amount'].abs().sum()

    return {
        "status": "ANALYZED",
        "total_customers": customer_df['Customer'].nunique(),
        "total_receivables": total_receivables,
        "issues": issues,
        "overdue_90_count": len([i for i in issues if i['type'] == 'OVERDUE_90"])
    }


def analyze_gl_postings(gl_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze FBL3N G/L postings for audit red flags.
    """
    if gl_df.empty:
        return {"status": "NO_DATA", "issues": []}

    issues = []

    # Check for manual postings
    for _, row in gl_df.iterrows():
        doc_no = str(row.get('Doc.No', ''))

        # Manual posting indicators (typically start with 1 or 5)
        if doc_no.startswith('1') or doc_no.startswith('5'):
            issues.append({
                "type": "MANUAL_POSTING",
                "account": row.get('Account'),
                "doc_no": doc_no,
                "amount": abs(row.get('Amount', 0)),
                "text": row.get('Text'),
                "severity": "MEDIUM"
            })

    # Check for weekend/posting period entries
    for _, row in gl_df.iterrows():
        try:
            pstng_date = pd.to_datetime(row.get('PstngDate', row.get('PostingDate')))
            if pstng_date.dayofweek >= 5:  # Saturday/Sunday
                issues.append({
                    "type": "WEEKEND_POSTING",
                    "account": row.get('Account'),
                    "doc_no": row.get('Doc.No'),
                    "date": str(pstng_date.date()),
                    "severity": "LOW"
                })
        except:
            pass

    return {
        "status": "ANALYZED",
        "total_records": len(gl_df),
        "manual_postings": len([i for i in issues if i['type'] == "MANUAL_POSTING"]),
        "issues": issues
    }


def analyze_inventory_movements(movement_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze MB51/MB52 inventory movements for anomalies.
    """
    if movement_df.empty:
        return {"status": "NO_DATA", "issues": []}

    issues = []

    # Common movement types
    move_types = {
        "101": "Goods Receipt",
        "102": "Goods Receipt Reversal",
        "201": "Goods Issue",
        "202": "Goods Issue Reversal",
        "301": "Transfer Posting",
        "601": "Good Issue (Delivery)",
        "701": "Inventory Initialization"
    }

    # Check for negative quantities
    for _, row in movement_df.iterrows():
        qty = row.get('Qty', 0)
        if qty and qty < 0:
            issues.append({
                "type": "NEGATIVE_QUANTITY",
                "material": row.get('Material'),
                "move_type": row.get('MoveType'),
                "qty": qty,
                "doc_date": row.get('Doc.Date'),
                "severity": "HIGH"
            })

    # Check for goods receipt without PO
    for _, row in movement_df.iterrows():
        move_type = str(row.get('MoveType', ''))
        po_num = row.get('PoNum', '')

        if move_type == '101' and (po_num is None or po_num == ''):
            issues.append({
                "type": "GR_WITHOUT_PO",
                "material": row.get('Material'),
                "doc_no": row.get('Doc.Num'),
                "qty": row.get('Qty'),
                "vendor": row.get('Vendor'),
                "severity": "HIGH"
            })

    # Summary by movement type
    movement_summary = movement_df.groupby('MoveType').agg({
        'Qty': 'sum',
        'Amount': 'sum' if 'Amount' in movement_df.columns else 'count'
    }).reset_index()

    return {
        "status": "ANALYZED",
        "total_movements": len(movement_df),
        "issues": issues,
        "movement_summary": movement_summary.to_dict('records'),
        "negative_qty_count": len([i for i in issues if i['type'] == "NEGATIVE_QUANTITY"])
    }


def analyze_asset_register(asset_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze AS03 asset register for depreciation and capitalization issues.
    """
    if asset_df.empty:
        return {"status": "NO_DATA", "issues": []}

    issues = []

    for _, row in asset_df.iterrows():
        cost = row.get('Cost', 0) or 0
        accum_depr = row.get('AccumDepr', 0) or 0
        net_value = row.get('NetValue', 0) or 0

        # Check fully depreciated still in use
        if cost > 0 and net_value <= 0:
            issues.append({
                "type": "FULLY_DEPRECIATED",
                "asset": row.get('Asset'),
                "description": row.get('Description'),
                "cost": cost,
                "net_value": net_value,
                "severity": "MEDIUM"
            })

        # Check impairment indicators (Net Value very low vs Cost)
        if cost > 100000 and net_value < cost * 0.1:
            issues.append({
                "type": "POTENTIAL_IMPAIRMENT",
                "asset": row.get('Asset'),
                "cost": cost,
                "net_value": net_value,
                "severity": "HIGH"
            })

        # Check capitalization (should have useful life)
        useful_life = row.get('UsefulLife', 0)
        if cost > 0 and (useful_life is None or useful_life == 0):
            issues.append({
                "type": "NO_USEFUL_LIFE",
                "asset": row.get('Asset'),
                "cost": cost,
                "severity": "MEDIUM"
            })

    return {
        "status": "ANALYZED",
        "total_assets": len(asset_df),
        "issues": issues,
        "fully_depreciated_count": len([i for i in issues if i['type'] == "FULLY_DEPRECIATED"]),
        "potential_impairment_count": len([i for i in issues if i['type'] == "POTENTIAL_IMPAIRMENT"])
    }


def analyze_user_access(access_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze SUIM user access for segregation of duties.
    """
    if access_df.empty:
        return {"status": "NO_DATA", "issues": []}

    issues = []

    # Critical role combinations that violate SoD
    sod_conflicts = [
        {"roles": ["SAP_USER_ADMIN", "SAP_ALL"], "description": "User admin with full access"},
        {"roles": ["SAP_FI_POST", "SAP_FI_REVERSE"], "description": "Posting and reversal"},
        {"roles": ["SAP_MM_PO_CREATE", "SAP_MM_VENDOR_CREATE"], "description": "PO and vendor creation"},
        {"roles": ["SAP_FI_PAYMENT", "SAP_FI_MANUAL_POST"], "description": "Payment and manual posting"}
    ]

    user_roles = access_df.groupby('User')['Role'].apply(list).to_dict()

    for user, roles in user_roles.items():
        for conflict in sod_conflicts:
            if all(r in roles for r in conflict["roles"]):
                issues.append({
                    "type": "SOD_CONFLICT",
                    "user": user,
                    "roles": roles,
                    "conflict": conflict["description"],
                    "severity": "HIGH"
                })

    # Check for inactive users
    for _, row in access_df.iterrows():
        valid_to = row.get('ValidTo')
        if valid_to:
            try:
                if pd.to_datetime(valid_to) < datetime.now():
                    issues.append({
                        "type": "INACTIVE_USER",
                        "user": row.get('User'),
                        "valid_to": valid_to,
                        "severity": "MEDIUM"
                    })
            except:
                pass

    return {
        "status": "ANALYZED",
        "total_users": access_df['User'].nunique(),
        "total_role_assignments": len(access_df),
        "issues": issues,
        "sod_conflicts": len([i for i in issues if i['type'] == "SOD_CONFLICT"]),
        "inactive_users": len([i for i in issues if i['type'] == "INACTIVE_USER"])
    }


def generate_sap_audit_report(packs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Generate comprehensive SAP audit report from all data packs.
    """
    report = {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "packs_processed": [],
        "summary": {}
    }

    all_issues = []

    for pack_type, df in packs.items():
        validation = validate_sap_pack(df, pack_type)

        if pack_type == "FBL1N":
            result = analyze_vendor_aging(df)
        elif pack_type == "FBL5N":
            result = analyze_customer_aging(df)
        elif pack_type == "FBL3N":
            result = analyze_gl_postings(df)
        elif pack_type in ["MB51", "MB52"]:
            result = analyze_inventory_movements(df)
        elif pack_type == "AS03":
            result = analyze_asset_register(df)
        elif pack_type == "SUIM":
            result = analyze_user_access(df)
        else:
            result = {"status": "NOT_IMPLEMENTED"}

        report["packs_processed"].append({
            "pack_type": pack_type,
            "validation": validation,
            "analysis": result
        })

        if "issues" in result:
            all_issues.extend(result["issues"])

    # Summary
    report["summary"] = {
        "total_issues": len(all_issues),
        "critical_issues": len([i for i in all_issues if i.get("severity") == "HIGH"]),
        "medium_issues": len([i for i in all_issues if i.get("severity") == "MEDIUM"]),
        "low_issues": len([i for i in all_issues if i.get("severity") == "LOW"])
    }

    return report