"""Policy Review Engine - AI-powered Policy Compliance Analysis.

Features:
- Classify policy type
- Extract clauses
- Map clauses to process/control/risk
- Detect missing clauses
- Compare policy vs SAP behavior
- Generate policy compliance exceptions
"""
import re
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime


# Standard control requirements per policy type
POLICY_CONTROL_MAPPING = {
    "Finance Policy": [
        "Authorization limits", "Approval hierarchy", "Payment terms",
        "Bank reconciliation", "Journal entry approval", "Petty cash limits"
    ],
    "Procurement Policy": [
        "Vendor selection", "Purchase order limits", "Bidding process",
        "Vendor master approval", "Purchase terms", "Receipt of goods"
    ],
    "HR Policy": [
        "Leave policy", "Travel policy", "Expense reimbursement",
        "Salary revision", "Performance appraisal", "Separation process"
    ],
    "IT Policy": [
        "Password policy", "Access control", "Data backup", "Software installation",
        "Network security", "Incident reporting"
    ],
    "Sales Policy": [
        "Credit policy", "Discount approval", "Return policy", "Revenue recognition",
        "Debtor follow-up", "Sales target"
    ],
    "Inventory Policy": [
        "Stock valuation", "Slow-moving stock", "Physical verification",
        "Inventory reorder levels", "Stock shortage handling"
    ]
}


# Expected clauses for each policy type
EXPECTED_CLAUSES = {
    "Finance Policy": [
        "objective", "scope", "definitions", "authorization", "approval",
        "limits", "bank", "reconciliation", "journal", "petty cash",
        "reporting", "review", "amendment"
    ],
    "Procurement Policy": [
        "objective", "scope", "definitions", "vendor selection", "bidding",
        "purchase order", "approval", "limits", "receipt", "payment",
        "vendor master", "reporting", "review"
    ],
    "HR Policy": [
        "objective", "scope", "definitions", "eligibility", "leave",
        "travel", "expense", "perquisite", "separation", "reporting"
    ],
    "IT Policy": [
        "objective", "scope", "definitions", "access", "password", "security",
        "backup", "network", "software", "incident", "reporting"
    ]
}


def classify_policy_type(policy_text: str) -> Dict[str, Any]:
    """Classify policy type based on content."""
    text_lower = policy_text.lower()

    policy_type_scores = {
        "Finance Policy": 0,
        "Procurement Policy": 0,
        "HR Policy": 0,
        "IT Policy": 0,
        "Sales Policy": 0,
        "Inventory Policy": 0
    }

    keywords = {
        "Finance Policy": ["finance", "payment", "bank", "journal", "reconciliation", "budget", "expense", "petty cash"],
        "Procurement Policy": ["procurement", "purchase", "vendor", "supplier", "bidding", "po", "procure"],
        "HR Policy": ["leave", "travel", "expense", "salary", "payroll", "perquisite", "increment", "appraisal"],
        "IT Policy": ["password", "access", "security", "backup", "network", "software", "system", "data"],
        "Sales Policy": ["sales", "customer", "credit", "discount", "revenue", "debtor", "collection"],
        "Inventory Policy": ["inventory", "stock", "warehouse", "material", "valuation", "reorder"]
    }

    for ptype, kws in keywords.items():
        for kw in kws:
            if kw in text_lower:
                policy_type_scores[ptype] += 1

    # Get best match
    best_type = max(policy_type_scores, key=policy_type_scores.get)
    confidence = policy_type_scores[best_type] / max(sum(policy_type_scores.values()), 1)

    return {
        "policy_type": best_type if policy_type_scores[best_type] > 0 else "Unknown",
        "confidence": round(confidence, 2),
        "scores": policy_type_scores
    }


def extract_clauses(policy_text: str) -> List[Dict[str, Any]]:
    """Extract clauses/sections from policy document."""
    clauses = []

    # Split by common clause patterns
    patterns = [
        r'^\d+\.\s+([A-Z][^\n]+)',  # 1. Section Title
        r'^([A-Z][A-Z\s]+):\s*',      # SECTION TITLE:
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+):\s*',  # Section Name:
    ]

    lines = policy_text.split('\n')
    current_section = None

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Check for section headers
        for pattern in patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                current_section = match.group(1).strip()
                clauses.append({
                    "section": current_section,
                    "text": line,
                    "line_number": i + 1,
                    "type": "header"
                })
                break
        else:
            # Add as content under current section
            if current_section and len(line) > 20:
                clauses.append({
                    "section": current_section,
                    "text": line[:200],
                    "line_number": i + 1,
                    "type": "content"
                })

    return clauses


def detect_missing_clauses(policy_text: str, policy_type: str) -> List[Dict[str, Any]]:
    """Detect missing clauses based on expected policy structure."""
    if policy_type not in EXPECTED_CLAUSES:
        return []

    text_lower = policy_text.lower()
    missing = []

    for expected in EXPECTED_CLAUSES[policy_type]:
        found = False
        for keyword in [expected, expected.replace(" ", ""), expected.replace(" ", "_")]:
            if keyword in text_lower or keyword.replace("_", "") in text_lower:
                found = True
                break

        if not found:
            missing.append({
                "clause": expected,
                "importance": "High" if expected in ["objective", "scope", "authorization", "approval", "limits"] else "Medium",
                "recommendation": f"Add {expected} clause to policy"
            })

    return missing


def map_clauses_to_controls(clauses: List[Dict], policy_type: str) -> List[Dict[str, Any]]:
    """Map extracted clauses to standard controls."""
    if policy_type not in POLICY_CONTROL_MAPPING:
        return []

    mappings = []
    expected_controls = POLICY_CONTROL_MAPPING[policy_type]

    # Simple keyword matching for mapping
    for clause in clauses:
        if clause.get("type") != "header":
            continue

        section = clause.get("section", "").lower()

        for control in expected_controls:
            control_lower = control.lower()
            if any(kw in section for kw in control_lower.split()):
                mappings.append({
                    "clause": clause.get("section"),
                    "control": control,
                    "mapped": True
                })
                break

    return mappings


def compare_with_sap_behavior(policy_text: str, sap_extract_df: pd.DataFrame = None) -> List[Dict[str, Any]]:
    """Compare policy requirements with actual SAP behavior."""
    exceptions = []

    # Extract policy limits/rules
    limit_patterns = [
        (r'approval\s+limit.*?(\d+)', 'approval_limit'),
        (r'credit\s+limit.*?(\d+)', 'credit_limit'),
        (r'maximum.*?(\d+)', 'maximum'),
    ]

    policy_limits = {}
    for pattern, limit_type in limit_patterns:
        match = re.search(pattern, policy_text, re.IGNORECASE)
        if match:
            policy_limits[limit_type] = int(match.group(1))

    # If SAP data provided, compare
    if sap_extract_df is not None and not sap_extract_df.empty:
        # Check for transactions exceeding policy limits
        for _, row in sap_extract_df.iterrows():
            amount = row.get('Amount', row.get('amount', 0))
            if amount and policy_limits.get('approval_limit'):
                if amount > policy_limits['approval_limit']:
                    exceptions.append({
                        "type": "POLICY_VIOLATION",
                        "severity": "HIGH",
                        "description": f"Transaction amount {amount} exceeds policy approval limit {policy_limits['approval_limit']}",
                        "doc_no": row.get('Doc.No', row.get('doc_no', 'N/A')),
                        "amount": amount
                    })

    return exceptions


def analyze_policy_gaps(policy_text: str, policy_type: str = None,
                       sap_extract_df: pd.DataFrame = None) -> Dict[str, Any]:
    """Comprehensive policy gap analysis."""
    # Auto-classify if type not provided
    if policy_type is None:
        classification = classify_policy_type(policy_text)
        policy_type = classification["policy_type"]

    # Extract clauses
    clauses = extract_clauses(policy_text)

    # Detect missing clauses
    missing_clauses = detect_missing_clauses(policy_text, policy_type)

    # Map to controls
    control_mappings = map_clauses_to_controls(clauses, policy_type)

    # Compare with SAP
    sap_exceptions = compare_with_sap_behavior(policy_text, sap_extract_df)

    # Overall assessment
    gap_score = len(missing_clauses) * 10 + len(sap_exceptions) * 20
    if gap_score > 50:
        status = "CRITICAL"
    elif gap_score > 20:
        status = "REVIEW"
    else:
        status = "OK"

    return {
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "policy_type": policy_type,
        "classification_confidence": classify_policy_type(policy_text).get("confidence", 0),
        "clauses_extracted": len(clauses),
        "missing_clauses": missing_clauses,
        "control_mappings": control_mappings,
        "sap_exceptions": sap_exceptions,
        "gap_score": gap_score,
        "status": status,
        "recommendations": [
            f"Add missing {len(missing_clauses)} clauses" if missing_clauses else "No clause gaps",
            f"Review {len(sap_exceptions)} SAP exceptions" if sap_exceptions else "No SAP policy violations"
        ]
    }


# AI-enhanced policy review (uses AI service if available)
def ai_review_policy(policy_text: str, controls_list: str = "",
                     sap_summary: str = "") -> Dict[str, Any]:
    """AI-enhanced policy review using the AI service."""
    try:
        from services.ai_service import review_policy
        return review_policy(policy_text[:5000], controls_list)
    except Exception as e:
        return {
            "error": str(e),
            "fallback": "Using deterministic review instead"
        }