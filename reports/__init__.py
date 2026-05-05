"""SARVAGYA Reporting Engine - Audience-specific Audit Reports."""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def get_connection():
    """Get database connection."""
    return sqlite3.connect(get_db_path())


# ====================== ENGAGEMENT SUMMARY ======================

def get_engagement_summary(engagement_id: int) -> Dict[str, Any]:
    """Get comprehensive engagement summary."""
    conn = get_connection()

    # Basic info
    eng = pd.read_sql_query(
        "SELECT * FROM audit_engagements WHERE id = ?", conn, params=(engagement_id,)
    ).iloc[0].to_dict() if engagement_id else {}

    # Entities
    entities = pd.read_sql_query(
        "SELECT * FROM audit_entities WHERE engagement_id = ?", conn, params=(engagement_id,)
    )

    # Findings summary (only confirmed ones)
    findings = pd.read_sql_query(
        "SELECT status, COUNT(*) as count FROM audit_findings WHERE engagement_id = ? GROUP BY status",
        conn, params=(engagement_id,)
    )

    # KPIs
    kpis = pd.read_sql_query(
        "SELECT metric_name, metric_value FROM audit_kpi WHERE engagement_id = ?",
        conn, params=(engagement_id,)
    )

    conn.close()

    total_findings = findings['count'].sum() if len(findings) > 0 else 0
    open_findings = findings[findings['status'] == 'Open']['count'].sum() if 'Open' in findings['status'].values else 0
    closed_findings = findings[findings['status'] == 'Closed']['count'].sum() if 'Closed' in findings['status'].values else 0

    return {
        "engagement": eng,
        "entity_count": len(entities),
        "entities": entities.to_dict('records') if len(entities) > 0 else [],
        "total_findings": total_findings,
        "open_findings": open_findings,
        "closed_findings": closed_findings,
        "closure_rate": round(closed_findings / total_findings * 100, 1) if total_findings > 0 else 0,
        "kpis": kpis.to_dict('records') if len(kpis) > 0 else []
    }


# ====================== FINDINGS REPORT ======================

def get_findings_report(engagement_id: int = None, entity_id: int = None,
                       status: str = None, risk_band: str = None) -> pd.DataFrame:
    """Get filtered findings for reporting."""
    conn = get_connection()
    q = """
        SELECT f.id, f.area, f.finding, f.amount_at_risk, f.risk_band, f.status,
               f.opened_at, f.closed_at, f.days_to_close, e.entity_name,
               mr.response as management_response, mr.action_owner
        FROM audit_findings f
        LEFT JOIN audit_entities e ON f.entity_id = e.id
        LEFT JOIN management_responses mr ON f.id = mr.finding_id
        WHERE 1=1
    """
    params = []

    if engagement_id:
        q += " AND f.engagement_id = ?"
        params.append(engagement_id)
    if entity_id:
        q += " AND f.entity_id = ?"
        params.append(entity_id)
    if status:
        q += " AND f.status = ?"
        params.append(status)
    if risk_band:
        q += " AND f.risk_band = ?"
        params.append(risk_band)

    q += " ORDER BY f.risk_band DESC, f.opened_at DESC"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


# ====================== WORKING PAPER REPORT ======================

def generate_working_paper_report(engagement_id: int) -> Dict[str, Any]:
    """Generate audit working paper report."""
    conn = get_connection()

    # Get all workpapers
    workpapers = pd.read_sql_query("""
        SELECT w.*, e.entity_name
        FROM workpapers w
        LEFT JOIN audit_entities e ON w.entity_id = e.id
        WHERE w.engagement_id = ?
        ORDER BY w.created_at DESC
    """, conn, params=(engagement_id,))

    # Get all findings
    findings = get_findings_report(engagement_id)

    # Get evidence count
    evidence_count = pd.read_sql_query("""
        SELECT COUNT(*) as cnt FROM evidence_files ef
        JOIN audit_findings f ON ef.finding_id = f.id
        WHERE f.engagement_id = ?
    """, conn, params=(engagement_id,)).iloc[0]['cnt']

    conn.close()

    return {
        "report_type": "Working Paper",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "workpapers": workpapers.to_dict('records') if len(workpapers) > 0 else [],
        "workpaper_count": len(workpapers),
        "findings": findings.to_dict('records') if len(findings) > 0 else [],
        "finding_count": len(findings),
        "evidence_count": evidence_count,
        "summary": {
            "total_procedures": len(workpapers),
            "total_findings": len(findings),
            "evidence_items": evidence_count
        }
    }


# ====================== MANAGEMENT EXCEPTION REPORT ======================

def generate_management_exception_report(engagement_id: int) -> Dict[str, Any]:
    """Generate management exception report (open findings)."""
    findings = get_findings_report(engagement_id, status="Open")

    # Group by area
    by_area = findings.groupby('area').agg({
        'id': 'count',
        'amount_at_risk': 'sum'
    }).reset_index()
    by_area.columns = ['area', 'finding_count', 'total_amount']

    # Group by risk band
    by_risk = findings.groupby('risk_band').agg({
        'id': 'count',
        'amount_at_risk': 'sum'
    }).reset_index()

    return {
        "report_type": "Management Exception Report",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "open_findings": findings.to_dict('records') if len(findings) > 0 else [],
        "summary": {
            "total_open": len(findings),
            "total_amount_at_risk": findings['amount_at_risk'].sum() if len(findings) > 0 else 0,
            "by_area": by_area.to_dict('records') if len(by_area) > 0 else [],
            "by_risk": by_risk.to_dict('records') if len(by_risk) > 0 else []
        }
    }


# ====================== AUDIT COMMITTEE PACK ======================

def generate_audit_committee_pack(engagement_id: int) -> Dict[str, Any]:
    """Generate comprehensive audit committee pack."""
    summary = get_engagement_summary(engagement_id)
    findings = get_findings_report(engagement_id)

    # Status summary
    status_summary = findings.groupby('status').size().to_dict()

    # Risk summary
    risk_summary = findings.groupby('risk_band').agg({
        'id': 'count',
        'amount_at_risk': 'sum'
    }).to_dict('records')

    # Recent workflow
    conn = get_connection()
    recent_changes = pd.read_sql_query("""
        SELECT wh.changed_at, wh.old_status, wh.new_status, wh.changed_by, f.area
        FROM workflow_history wh
        JOIN audit_findings f ON wh.finding_id = f.id
        WHERE f.engagement_id = ?
        ORDER BY wh.changed_at DESC
        LIMIT 20
    """, conn, params=(engagement_id,))
    conn.close()

    return {
        "report_type": "Audit Committee Pack",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engagement_summary": summary,
        "findings_summary": {
            "total": len(findings),
            "status": status_summary,
            "by_risk": risk_summary
        },
        "recent_changes": recent_changes.to_dict('records') if len(recent_changes) > 0 else [],
        "recommendations": [
            f"Close {summary.get('open_findings', 0)} open findings" if summary.get('open_findings', 0) > 0 else "No open findings",
            "Review high-risk findings first",
            "Track management response timelines"
        ]
    }


# ====================== CARO READINESS REPORT ======================

def generate_caro_readiness_report(engagement_id: int) -> Dict[str, Any]:
    """Generate CARO 2020 readiness report."""
    conn = get_connection()

    # Get CARO checklist
    caro = pd.read_sql_query("""
        SELECT ci.item_text, ci.standard_ref, ci.response, ci.remarks, ci.responded_at
        FROM checklist_items ci
        JOIN audit_checklists ac ON ci.checklist_id = ac.id
        WHERE ac.checklist_type = 'CARO'
    """, conn)

    # Map to findings
    caro_responses = caro.groupby('response').size().to_dict()

    conn.close()

    return {
        "report_type": "CARO Readiness Report",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "caro_clauses": caro.to_dict('records') if len(caro) > 0 else [],
        "summary": {
            "total_clauses": len(caro),
            "yes": caro_responses.get('Yes', 0),
            "no": caro_responses.get('No', 0),
            "na": caro_responses.get('NA', 0),
            "pending": caro_responses.get(None, 0)
        },
        "readiness_score": round(caro_responses.get('Yes', 0) / len(caro) * 100, 1) if len(caro) > 0 else 0
    }


# ====================== FINANCIAL STATEMENT REVIEW MEMO ======================

def generate_fs_review_memo(engagement_id: int, fs_checks: Dict = None) -> Dict[str, Any]:
    """Generate financial statement review memo."""
    # Get findings related to financial areas
    conn = get_connection()
    fs_findings = pd.read_sql_query("""
        SELECT * FROM audit_findings
        WHERE engagement_id = ? AND area IN ('Financial', 'Inventory', 'Fixed Assets', 'Revenue', 'Borrowings')
        ORDER BY risk_band DESC, amount_at_risk DESC
    """, conn, params=(engagement_id,))
    conn.close()

    return {
        "report_type": "Financial Statement Review Memo",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fs_findings": fs_findings.to_dict('records') if len(fs_findings) > 0 else [],
        "deterministic_checks": fs_checks if fs_checks else {},
        "summary": {
            "total_fs_issues": len(fs_findings),
            "total_amount": fs_findings['amount_at_risk'].sum() if len(fs_findings) > 0 else 0
        }
    }


# ====================== POLICY GAP REPORT ======================

def generate_policy_gap_report(engagement_id: int = None) -> Dict[str, Any]:
    """Generate policy gap report."""
    conn = get_connection()

    # Get policy exceptions
    from core.policy_manager import get_policy_exceptions
    exceptions = get_policy_exceptions()

    # Get policies
    policies = pd.read_sql_query("""
        SELECT * FROM policy_documents
        WHERE superseded_status = 'Active'
        ORDER BY updated_at DESC
    """, conn)

    conn.close()

    return {
        "report_type": "Policy Gap Report",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "policies": policies.to_dict('records') if len(policies) > 0 else [],
        "exceptions": exceptions.to_dict('records') if len(exceptions) > 0 else [],
        "summary": {
            "total_policies": len(policies),
            "open_exceptions": len(exceptions[exceptions['status'] == 'Open']) if len(exceptions) > 0 else 0
        }
    }


# ====================== OPEN FINDING TRACKER ======================

def generate_open_finding_tracker(engagement_id: int = None) -> Dict[str, Any]:
    """Generate open finding tracker with SLA tracking."""
    findings = get_findings_report(engagement_id, status="Open")

    # Calculate SLA breach
    today = datetime.now().strftime("%Y-%m-%d")
    overdue = []

    for _, f in findings.iterrows():
        if f.get('sla_deadline') and f.get('sla_deadline') < today:
            overdue.append(f)

    return {
        "report_type": "Open Finding Tracker",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "open_findings": findings.to_dict('records') if len(findings) > 0 else [],
        "overdue_findings": overdue,
        "summary": {
            "total_open": len(findings),
            "overdue": len(overdue),
            "on_time": len(findings) - len(overdue)
        }
    }


# ====================== ENTITY/LOCATION RISK DASHBOARD ======================

def generate_risk_dashboard(engagement_id: int = None) -> Dict[str, Any]:
    """Generate entity/location risk dashboard."""
    conn = get_connection()

    # Get entities with their findings
    entities = pd.read_sql_query("""
        SELECT e.id, e.entity_name, e.location, e.code,
               COUNT(f.id) as total_findings,
               SUM(CASE WHEN f.status = 'Open' THEN 1 ELSE 0 END) as open_findings,
               SUM(CASE WHEN f.risk_band = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN f.risk_band = 'HIGH' THEN 1 ELSE 0 END) as high,
               SUM(COALESCE(f.amount_at_risk, 0)) as amount_at_risk
        FROM audit_entities e
        LEFT JOIN audit_findings f ON e.id = f.entity_id
        WHERE e.engagement_id = ?
        GROUP BY e.id
    """, conn, params=(engagement_id,))

    # Risk distribution
    risk_dist = entities.groupby(pd.cut(entities['amount_at_risk'], bins=[0, 100000, 1000000, 10000000, float('inf')],
                                        labels=['Low', 'Medium', 'High', 'Critical'])).size().to_dict()

    conn.close()

    return {
        "report_type": "Entity Risk Dashboard",
        "engagement_id": engagement_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entities": entities.to_dict('records') if len(entities) > 0 else [],
        "risk_distribution": risk_dist,
        "summary": {
            "total_entities": len(entities),
            "total_open_findings": entities['open_findings'].sum() if len(entities) > 0 else 0,
            "total_amount_at_risk": entities['amount_at_risk'].sum() if len(entities) > 0 else 0
        }
    }


# ====================== MASTER REPORT FUNCTION ======================

def generate_report(report_type: str, engagement_id: int = None, **kwargs) -> Dict[str, Any]:
    """Generate any report by type."""
    report_generators = {
        "working_paper": generate_working_paper_report,
        "management_exception": generate_management_exception_report,
        "audit_committee": generate_audit_committee_pack,
        "caro_readiness": generate_caro_readiness_report,
        "fs_review": generate_fs_review_memo,
        "policy_gap": generate_policy_gap_report,
        "open_finding_tracker": generate_open_finding_tracker,
        "risk_dashboard": generate_risk_dashboard
    }

    generator = report_generators.get(report_type)
    if generator:
        return generator(engagement_id, **kwargs)
    else:
        return {"error": f"Unknown report type: {report_type}"}