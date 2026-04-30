"""Column Mapper — Auto-detect SAP field synonyms and persist company profiles.

Principle: ZERO hardcoded column names in ML/rule logic. All logic uses internal
standard names only. SAP exports WRBTR, DMBTR, NETWR → mapped to `amount` before
any detection runs.
"""
from pathlib import Path
import json
from typing import List, Dict

# Standard internal concept names — NEVER change in logic code
STANDARD_CONCEPTS = {
    "payment_anomaly": ["amount", "vendor_name", "posting_date", "document_date",
                        "days_overdue", "related_party", "invoice_number",
                        "credit_terms_days", "tolerance_override_flag", "plant_code"],
    "inventory": ["material_code", "material_desc", "plant", "unrestricted_qty",
                  "value", "last_movement_date", "material_type", "shelf_life_expiry",
                  "abc_class", "standard_price"],
    "payroll": ["employee_id", "employee_name", "pan", "bank_account", "department",
                "grade", "basic_da", "gross_salary", "pf_deducted", "esi_deducted",
                "overtime_hours", "last_attendance_date", "status"],
    "sales": ["invoice_no", "customer_name", "invoice_date", "dispatch_date",
              "amount", "discount_pct", "credit_note_no", "return_qty"],
    "contract": ["contract_no", "vendor_name", "start_date", "end_date", "value",
                 "last_payment_date", "ld_rate_pct", "renewal_status"],
    "access": ["user_id", "role", "tcode", "last_login", "status", "department"],
    "bank_reconciliation": ["bank_date", "bank_amount", "bank_narration", "bank_chq_no",
                            "gl_date", "gl_amount", "gl_narration", "gl_chq_no"],
    "fixed_assets": ["asset_id", "asset_description", "acquisition_date", "cost",
                     "accumulated_depreciation", "net_block", "depreciation_rate",
                     "asset_class", "location", "capex_approved", "capex_approver"],
}

# SAP field synonym map — auto-detect column mapping
SYNONYMS = {
    "amount": ["amount", "net_amount", "wrbtr", "gross_amount", "payment_amount",
               "inv_amount", "bill_amount", "total", "value", "dmbtr", "netwr",
               "bank_amount", "gl_amount", "po_value", "contract_value"],
    "vendor_name": ["vendor_name", "vendor", "lifnr", "supplier", "party_name",
                    "creditor", "name_1", "vendor_description", "kred", "customer_name",
                    "dealer_name", "distributor"],
    "posting_date": ["posting_date", "budat", "post_date", "value_date", "date",
                     "document_date", "bank_date", "gl_date", "invoice_date",
                     "dispatch_date", "acquisition_date"],
    "days_overdue": ["days_overdue", "overdue_days", "aging_days", "days_outstanding",
                     "delay_days"],
    "material_code": ["material_code", "matnr", "material", "mat_no", "item_code",
                      "product_code", "sku"],
    "employee_id": ["employee_id", "emp_id", "pernr", "staff_id", "personnel_no"],
    "pan": ["pan", "pan_no", "pan_number", "tax_id"],
    "invoice_no": ["invoice_no", "invoice_number", "vbeln", "belnr", "bill_no",
                   "credit_note_no", "document_no"],
    "bank_account": ["bank_account", "bank_acc", "account_no", "iban"],
    "user_id": ["user_id", "userid", "user_name", "uname", "bname"],
    "tcode": ["tcode", "transaction_code", "t_code", "tcod"],
    "contract_no": ["contract_no", "contract_number", "po_number", "purchase_order",
                    "outline_agreement", "agreement_no"],
}


def auto_suggest_mapping(df_columns: list, module: str) -> dict:
    """Suggest internal→actual column mapping for a given module."""
    suggestions = {}
    for concept in STANDARD_CONCEPTS.get(module, []):
        for col in df_columns:
            if col.lower().strip() in [s.lower() for s in SYNONYMS.get(concept, [])]:
                suggestions[concept] = col
                break
    return suggestions


def save_profile(profile_name: str, module: str, mapping: dict, company: str = ""):
    """Persist a confirmed column mapping profile to disk."""
    d = Path("data/column_profiles")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{profile_name}.json").write_text(
        json.dumps({"profile_name": profile_name, "company": company,
                    "module": module, "mapping": mapping}, indent=2))


def load_profile(profile_name: str) -> dict:
    """Load a saved column mapping profile."""
    d = Path("data/column_profiles")
    return json.loads((d / f"{profile_name}.json").read_text())


def list_profiles(module: str = None) -> List[str]:
    """List all saved profiles, optionally filtered by module."""
    d = Path("data/column_profiles")
    if not d.exists():
        return []
    profiles = []
    for f in d.glob("*.json"):
        data = json.loads(f.read_text())
        if module is None or data.get("module") == module:
            profiles.append(data["profile_name"])
    return profiles


def apply_mapping(df, mapping: dict):
    """Rename DataFrame columns according to a mapping dict {internal: actual}."""
    rename = {v: k for k, v in mapping.items() if v in df.columns}
    return df.rename(columns=rename)
