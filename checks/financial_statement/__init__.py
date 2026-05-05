"""Financial Statement Deterministic Checks - Ind AS/AS/CARO/Schedule III."""
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime


def map_tb_to_schedule_iii(tb_df: pd.DataFrame, entity_type: str = "Manufacturing") -> Dict[str, Any]:
    """
    Map Trial Balance to Schedule III format for Indian companies.
    Returns mapped financial statements and exceptions.
    """
    # Common mappings for manufacturing companies (Schedule III Part I)
    bs_mapping = {
        # Share Capital & Reserves
        "share capital": ["share capital", "equity share capital", "paid up capital"],
        "reserves": ["reserves", "surplus", "profit loss", "securities premium"],
        # Non-Current Liabilities
        "long term borrowings": ["long term loans", "term loans", "borrowing long"],
        "deferred tax liabilities": ["deferred tax", "dtl"],
        "other long term liabilities": ["other long term"],
        # Current Liabilities
        "short term borrowings": ["short term loans", "cash credit", "overdraft"],
        "trade payables": ["creditors", "sundry creditors", "trade payables", "accounts payable"],
        "other current liabilities": ["other current liabilities", "advance from customer"],
        "provision": ["provision", "expense provision"],
        # Non-Current Assets
        "fixed assets": ["fixed assets", "plant machinery", "building", "furniture", "vehicle"],
        "intangible assets": ["intangible", "goodwill", "patent", "software"],
        "investments": ["investments", "mutual funds", "shares"],
        "deferred tax assets": ["deferred tax assets", "dta"],
        "long term loans": ["loans long term", "advances long"],
        # Current Assets
        "inventory": ["inventory", "stock", "raw material", "finished goods", "wip"],
        "trade receivables": ["debtors", "receivables", "sundry debtors", "trade receivables"],
        "cash": ["cash", "bank", "cash in hand"],
        "short term loans": ["loans short", "advances short"],
        "other current assets": ["prepaid", "advance tax", "other current"],
    }

    # Try to match accounts to BS heads
    mapped = {}
    unmatched = []

    for _, row in tb_df.iterrows():
        account_name = str(row.get('account_name', '')).lower()
        closing_debit = row.get('closing_debit', 0) or 0
        closing_credit = row.get('closing_credit', 0) or 0
        net = closing_debit - closing_credit

        matched = False
        for head, keywords in bs_mapping.items():
            if any(kw in account_name for kw in keywords):
                if head not in mapped:
                    mapped[head] = 0
                mapped[head] += net
                matched = True
                break

        if not matched:
            unmatched.append({"account": row.get('account_name'), "amount": net})

    return {
        "balance_sheet": mapped,
        "unmatched_accounts": unmatched,
        "mapping_confidence": round((len(mapped) / (len(mapped) + len(unmatched))) * 100, 1) if len(mapped) + len(unmatched) > 0 else 0
    }


def check_ind_as_applicability(turnover: float, listed: bool, net_worth: float) -> Dict[str, Any]:
    """
    Determine Ind AS applicability per Companies (Indian Accounting Standards) Rules 2015.
    """
    rules = []

    # Level 1: Listed/soon to be listed + net worth > 250 Cr
    if listed:
        rules.append({"rule": "Level 1 - Listed Companies", "applies": True, "note": "Mandatory Ind AS"})
    elif net_worth > 25000000000:  # 250 Cr
        rules.append({"rule": "Level 1 - Net worth > 250 Cr", "applies": True, "note": "Mandatory Ind AS"})
    elif turnover > 5000000000 and net_worth > 500000000:  # 500 Cr turnover, 50 Cr net worth
        rules.append({"rule": "Level 2 - High turnover", "applies": True, "note": "Mandatory Ind AS if net worth > 50 Cr"})
    else:
        rules.append({"rule": "Optional transition", "applies": False, "note": "May opt for Ind AS voluntarily"})

    # Apply simplified for non-listed
    uses_ind_as = listed or net_worth > 25000000000 or (turnover > 5000000000 and net_worth > 500000000)

    return {
        "applies_ind_as": uses_ind_as,
        "applicable_from": "FY 2016-17" if uses_ind_as else "N/A",
        "rules_applied": rules,
        "framework": "Ind AS" if uses_ind_as else "AS (Indian GAAP)"
    }


def check_related_party_disclosures(tb_df: pd.DataFrame, rp_list: List[Dict] = None) -> Dict[str, Any]:
    """
    Check related party transaction disclosures per Ind AS 24 / AS 18.
    """
    if rp_list is None:
        rp_list = []

    # Find potential RP transactions in TB
    rp_accounts = []
    for _, row in tb_df.iterrows():
        account_name = str(row.get('account_name', '')).lower()
        for rp in rp_list:
            if 'name' in rp and rp['name'].lower() in account_name:
                rp_accounts.append({
                    "account": row.get('account_name'),
                    "amount": abs(row.get('closing_debit', 0) or 0) + abs(row.get('closing_credit', 0) or 0),
                    "related_party": rp['name']
                })

    # Check for missing RP disclosures
    issues = []
    if len(rp_accounts) > 0:
        issues.append({
            "type": "RP_TRANSACTIONS_FOUND",
            "severity": "HIGH",
            "description": f"Found {len(rp_accounts)} related party accounts requiring disclosure",
            "accounts": rp_accounts
        })
    else:
        issues.append({
            "type": "NO_RP_CHECK",
            "severity": "MEDIUM",
            "description": "No RP transactions detected - verify RP register is complete"
        })

    return {
        "rp_transactions": rp_accounts,
        "disclosure_required": len(rp_accounts) > 0,
        "issues": issues
    }


def check_ppe_ageing(ppe_df: pd.DataFrame, useful_life_override: Dict[str, int] = None) -> Dict[str, Any]:
    """
    Check PPE/CWIP ageing and capitalization per Schedule II / Ind AS 16.
    """
    if useful_life_override is None:
        useful_life_override = {}

    if ppe_df.empty:
        return {"status": "NO_PPE_DATA", "issues": []}

    current_date = datetime.now()
    issues = []

    for _, row in ppe_df.iterrows():
        asset_name = row.get('asset_name', 'Unknown')
        put_to_use = row.get('date_put_to_use')
        cost = row.get('cost', 0) or 0
        depreciation = row.get('depreciation', 0) or 0
        useful_life = useful_life_override.get(asset_name.lower(), row.get('useful_life', 10))

        if put_to_use:
            try:
                if isinstance(put_to_use, str):
                    use_date = datetime.strptime(str(put_to_use), "%Y-%m-%d")
                else:
                    use_date = put_to_use

                age_years = (current_date - use_date).days / 365.25

                if age_years > useful_life and cost - depreciation > 0:
                    issues.append({
                        "type": "FULLY_DEPRECIATED_IN_USE",
                        "severity": "HIGH",
                        "asset": asset_name,
                        "age_years": round(age_years, 1),
                        "useful_life": useful_life,
                        "residual_value": round(cost - depreciation, 2),
                        "standard_ref": "Ind AS 16 / Schedule II"
                    })
            except:
                pass

        # Check CWIP stagnation
        if 'cwip' in str(asset_name).lower() and cost > 1000000:
            issues.append({
                "type": "CWIP_STAGNATION",
                "severity": "MEDIUM",
                "asset": asset_name,
                "amount": cost,
                "note": "Review CWIP capitalization timeline"
            })

    return {
        "total_assets": len(ppe_df),
        "issues": issues,
        "critical_count": len([i for i in issues if i['severity'] == 'HIGH'])
    }


def check_revenue_recognition(tb_df: pd.DataFrame, inventory_df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Check revenue recognition red flags per Ind AS 115.
    """
    issues = []

    # Get revenue account
    revenue = 0
    for _, row in tb_df.iterrows():
        account = str(row.get('account_name', '')).lower()
        if 'revenue' in account or 'sales' in account or 'income' in account:
            if row.get('closing_credit'):
                revenue += row.get('closing_credit', 0)

    # Check for unusual credit balances in receivables
    for _, row in tb_df.iterrows():
        account = str(row.get('account_name', '')).lower()
        if 'debtor' in account or 'receivable' in account:
            if row.get('closing_credit') and row.get('closing_credit') > 0:
                issues.append({
                    "type": "CREDIT_BALANCE_RECEIVABLE",
                    "severity": "HIGH",
                    "account": row.get('account_name'),
                    "amount": row.get('closing_credit'),
                    "note": "Verify if this is credit note or anomaly"
                })

    # Check inventory to revenue ratio for FMCG
    if inventory_df is not None and revenue > 0:
        total_inventory = inventory_df['amount'].sum() if 'amount' in inventory_df.columns else 0
        inv_rev_ratio = total_inventory / revenue if revenue > 0 else 0
        if inv_rev_ratio > 1.5:
            issues.append({
                "type": "HIGH_INVENTORY_RATIO",
                "severity": "MEDIUM",
                "ratio": round(inv_rev_ratio, 2),
                "note": "Review slow-moving inventory (FMCG normal: 0.5-1.0)"
            })

    # Check for advance from customers (unearned revenue)
    for _, row in tb_df.iterrows():
        account = str(row.get('account_name', '')).lower()
        if 'advance' in account and 'customer' in account:
            if row.get('closing_credit'):
                issues.append({
                    "type": "UNEARNED_REVENUE",
                    "severity": "LOW",
                    "account": row.get('account_name'),
                    "amount": row.get('closing_credit'),
                    "note": "Verify performance obligations per Ind AS 115"
                })

    return {
        "total_revenue": revenue,
        "issues": issues,
        "compliance_status": "REVIEW" if issues else "OK"
    }


def check_inventory_nrv(inventory_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Check Inventory NRV and slow-moving items per AS 2 / Ind AS 2.
    """
    if inventory_df.empty:
        return {"status": "NO_INVENTORY_DATA", "issues": []}

    issues = []

    for _, row in inventory_df.iterrows():
        item = row.get('item_name', 'Unknown')
        qty = row.get('quantity', 0) or 0
        rate = row.get('rate', 0) or 0
        cost = row.get('cost', 0) or 0
        age_days = row.get('age_days', 0) or 0

        # NRV check: if cost > net realisable value
        if rate > 0 and cost > rate:
            issues.append({
                "type": "NRV_LOSS",
                "severity": "HIGH",
                "item": item,
                "cost": cost,
                "nrv": rate,
                "loss": cost - rate,
                "standard_ref": "AS 2 / Ind AS 2"
            })

        # Slow-moving check (>180 days)
        if age_days > 180 and qty > 0:
            issues.append({
                "type": "SLOW_MOVING",
                "severity": "MEDIUM",
                "item": item,
                "age_days": age_days,
                "quantity": qty,
                "value": qty * cost
            })

    # Summary
    slow_moving_count = len([i for i in issues if i['type'] == 'SLOW_MOVING'])
    nrv_loss_count = len([i for i in issues if i['type'] == 'NRV_LOSS'])

    return {
        "total_items": len(inventory_df),
        "issues": issues,
        "slow_moving_count": slow_moving_count,
        "nrv_loss_count": nrv_loss_count,
        "provision_required": nrv_loss_count > 0
    }


def check_borrowings_msme_statutory(tb_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Check borrowings, MSME dues, and statutory dues per CARO/Schedule III.
    """
    issues = []

    # Map common accounts
    account_map = {
        "borrowings_short": ["cash credit", "overdraft", "short term loan", "working capital"],
        "borrowings_long": ["term loan", "long term loan", "debentures"],
        "msme": ["msme", "micro small medium", "sbi msme"],
        "statutory": ["pf", "esi", "gst", "tds", "tax", "duty"]
    }

    for _, row in tb_df.iterrows():
        account = str(row.get('account_name', '')).lower()
        debit = row.get('closing_debit', 0) or 0
        credit = row.get('closing_credit', 0) or 0
        net = credit - debit  # Credit balance is liability

        # Check MSME dues (payable)
        if any(kw in account for kw in account_map["msme"]) and credit > 0:
            if credit > 100000:  # Material threshold
                issues.append({
                    "type": "MSME_DUES",
                    "severity": "HIGH",
                    "account": row.get('account_name'),
                    "amount": credit,
                    "note": "Verify payment within 45/90 days as per MSME Act"
                })

        # Check statutory dues
        if any(kw in account for kw in account_map["statutory"]):
            if debit > 0 or credit > 0:
                issues.append({
                    "type": "STATUTORY_DUES",
                    "severity": "MEDIUM",
                    "account": row.get('account_name'),
                    "balance": max(debit, credit),
                    "note": "Verify timely deposit"
                })

        # Check borrowings (materiality)
        if any(kw in account for kw in account_map["borrowings_short"] + account_map["borrowings_long"]):
            if credit > 1000000:
                issues.append({
                    "type": "MATERIAL_BORROWING",
                    "severity": "LOW",
                    "account": row.get('account_name'),
                    "amount": credit,
                    "note": "Verify terms and covenants"
                })

    msme_issues = [i for i in issues if i.get("type") == "MSME_DUES"]
    statutory_issues = [i for i in issues if i.get("type") == "STATUTORY_DUES"]
    return {
        "issues": issues,
        "msme_issues": msme_issues,
        "statutory_issues": statutory_issues
    }


def check_contingent_liabilities(cl_df: pd.DataFrame, tb_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Check contingent liabilities per AS 29 / Ind AS 37.
    """
    issues = []

    # Get total contingent liabilities
    total_cl = 0
    if not cl_df.empty:
        for _, row in cl_df.iterrows():
            amount = row.get('amount', 0) or 0
            classification = str(row.get('classification', '')).lower()

            total_cl += amount

            # Check unprovided
            if 'probable' in classification and amount > 0:
                issues.append({
                    "type": "UNPROVIDED_CONTINGENT",
                    "severity": "HIGH",
                    "description": row.get('description'),
                    "amount": amount,
                    "note": "Should be provided as provision"
                })
            elif 'possible' in classification and amount > 10000000:  # 1 Cr material
                issues.append({
                    "type": "DISCLOSURE_REQUIRED",
                    "severity": "MEDIUM",
                    "description": row.get('description'),
                    "amount": amount
                })

    # Check against borrowings for going concern
    borrowings = 0
    for _, row in tb_df.iterrows():
        account = str(row.get('account_name', '')).lower()
        if 'borrow' in account:
            borrowings += row.get('closing_credit', 0) or 0

    if total_cl > borrowings * 0.5:  # CL > 50% of borrowings
        issues.append({
            "type": "GOING_CONCERN_CONCERN",
            "severity": "HIGH",
            "note": f"Contingent liabilities ({total_cl}) > 50% of borrowings ({borrowings})"
        })

    return {
        "total_contingent_liabilities": total_cl,
        "issues": issues,
        "provision_required": len([i for i in issues if i['severity'] == 'HIGH'])
    }


def generate_fs_review_report(tb_df: pd.DataFrame, entity_info: Dict = None,
                              inventory_df: pd.DataFrame = None,
                              ppe_df: pd.DataFrame = None,
                              cl_df: pd.DataFrame = None,
                              rp_list: List[Dict] = None) -> Dict[str, Any]:
    """
    Generate comprehensive financial statement review report.
    """
    if entity_info is None:
        entity_info = {"turnover": 0, "listed": False, "net_worth": 0}

    report = {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "entity": entity_info,
        "checks": {}
    }

    # 1. Schedule III Mapping
    report["checks"]["schedule_iii_mapping"] = map_tb_to_schedule_iii(tb_df)

    # 2. Ind AS Applicability
    report["checks"]["ind_as_applicability"] = check_ind_as_applicability(
        entity_info.get("turnover", 0),
        entity_info.get("listed", False),
        entity_info.get("net_worth", 0)
    )

    # 3. Related Party
    report["checks"]["related_party"] = check_related_party_disclosures(tb_df, rp_list)

    # 4. PPE Ageing
    report["checks"]["ppe_ageing"] = check_ppe_ageing(ppe_df if ppe_df is not None else pd.DataFrame())

    # 5. Revenue Recognition
    report["checks"]["revenue_recognition"] = check_revenue_recognition(
        tb_df,
        inventory_df if inventory_df is not None else pd.DataFrame()
    )

    # 6. Inventory NRV
    report["checks"]["inventory_nrv"] = check_inventory_nrv(
        inventory_df if inventory_df is not None else pd.DataFrame()
    )

    # 7. Borrowings/MSME/Statutory
    report["checks"]["borrowings_msme_statutory"] = check_borrowings_msme_statutory(tb_df)

    # 8. Contingent Liabilities
    report["checks"]["contingent_liabilities"] = check_contingent_liabilities(
        cl_df if cl_df is not None else pd.DataFrame(),
        tb_df
    )

    # Summary
    all_issues = []
    for check_name, result in report["checks"].items():
        if "issues" in result:
            all_issues.extend(result["issues"])

    report["summary"] = {
        "total_issues": len(all_issues),
        "critical_issues": len([i for i in all_issues if i.get("severity") == "HIGH"]),
        "medium_issues": len([i for i in all_issues if i.get("severity") == "MEDIUM"]),
        "low_issues": len([i for i in all_issues if i.get("severity") == "LOW"]),
        "recommendation": "REVIEW_REQUIRED" if len(all_issues) > 0 else "NO_MATERIAL_ISSUES"
    }

    return report