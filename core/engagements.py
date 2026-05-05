"""Core Engagement Management - The Heart of Audit OS."""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any


def get_db_path() -> str:
    """Centralize DB path for consistency."""
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def create_engagement(name: str, description: str = None, start_date: str = None,
                      end_date: str = None, status: str = "Planned") -> int:
    """Create a new audit engagement."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_engagements (name, description, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (name, description, start_date, end_date, status))
    engagement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return engagement_id


def get_engagement(engagement_id: int) -> Optional[Dict[str, Any]]:
    """Get engagement details by ID."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM audit_engagements WHERE id = ?", (engagement_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_engagements(status: str = None) -> pd.DataFrame:
    """List all engagements with optional status filter."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM audit_engagements"
    params = []
    if status:
        q += " WHERE status = ?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def update_engagement(engagement_id: int, **kwargs) -> bool:
    """Update engagement fields."""
    allowed = ['name', 'description', 'start_date', 'end_date', 'status']
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute(f"UPDATE audit_engagements SET {set_clause} WHERE id = ?",
                   list(updates.values()) + [engagement_id])
    conn.commit()
    conn.close()
    return True


def create_entity(engagement_id: int, entity_name: str, location: str = None,
                code: str = None, industry: str = None, pan: str = None,
                cin: str = None) -> int:
    """Create an entity (company/location) within an engagement."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_entities (engagement_id, entity_name, location, code, industry, pan, cin)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (engagement_id, entity_name, location, code, industry, pan, cin))
    entity_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entity_id


def get_entities(engagement_id: int) -> pd.DataFrame:
    """Get all entities for an engagement."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query(
        "SELECT * FROM audit_entities WHERE engagement_id = ? ORDER BY entity_name",
        conn, params=(engagement_id,)
    )
    conn.close()
    return df


def create_process(engagement_id: int, process_name: str, description: str = None,
                  risk_owner: str = None) -> int:
    """Create a process within an engagement."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_processes (engagement_id, process_name, description, risk_owner)
        VALUES (?, ?, ?, ?)
    """, (engagement_id, process_name, description, risk_owner))
    process_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return process_id


def create_risk(engagement_id: int, process_id: int, risk_description: str,
               risk_category: str = None, inherent_risk: str = None) -> int:
    """Create a risk within a process."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_risks (engagement_id, process_id, risk_description, risk_category, inherent_risk)
        VALUES (?, ?, ?, ?, ?)
    """, (engagement_id, process_id, risk_description, risk_category, inherent_risk))
    risk_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return risk_id


def get_engagement_summary(engagement_id: int) -> Dict[str, Any]:
    """Get comprehensive engagement summary."""
    conn = sqlite3.connect(get_db_path())

    # Engagement basic info
    eng = pd.read_sql_query("SELECT * FROM audit_engagements WHERE id = ?", conn, params=(engagement_id,)).iloc[0].to_dict()

    # Entity count
    entity_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM audit_entities WHERE engagement_id = ?", conn, params=(engagement_id,)).iloc[0]['cnt']

    # Open findings count
    open_findings = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM audit_findings WHERE engagement_id = ? AND status = 'Open'",
        conn, params=(engagement_id,)
    ).iloc[0]['cnt']

    # Total findings
    total_findings = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM audit_findings WHERE engagement_id = ?",
        conn, params=(engagement_id,)
    ).iloc[0]['cnt']

    conn.close()

    return {
        **eng,
        "entity_count": entity_count,
        "open_findings": open_findings,
        "total_findings": total_findings,
        "closure_rate": round((total_findings - open_findings) / total_findings * 100, 1) if total_findings > 0 else 0
    }


def link_finding_to_engagement(finding_id: int, engagement_id: int, entity_id: int = None):
    """Link existing finding to an engagement."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE audit_findings SET engagement_id = ?, entity_id = ? WHERE id = ?
    """, (engagement_id, entity_id, finding_id))
    conn.commit()
    conn.close()


def get_engagement_workpaper(engagement_id: int) -> pd.DataFrame:
    """Get all workpapers for an engagement (findings + evidence + workflow)."""
    conn = sqlite3.connect(get_db_path())

    findings = pd.read_sql_query("""
        SELECT f.*, e.entity_name, w.old_status, w.new_status, w.changed_by, w.changed_at
        FROM audit_findings f
        LEFT JOIN audit_entities e ON f.entity_id = e.id
        LEFT JOIN workflow_history w ON f.id = w.finding_id
        WHERE f.engagement_id = ?
        ORDER BY f.id, w.changed_at DESC
    """, conn, params=(engagement_id,))

    conn.close()
    return findings