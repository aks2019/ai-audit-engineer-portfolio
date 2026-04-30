"""Shared SQLite audit trail — all detection pages write findings here.

Principle 6: Shared Audit Trail. Projects 15–17 read from this single source.
No page is a silo.
"""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta


def init_audit_db():
    """Create data dir and all audit tables if missing."""
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/audit.db")

    # Core findings table (extended for multi-company + workflow)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        company_code TEXT DEFAULT 'HQ',
        plant_code TEXT DEFAULT '',
        area TEXT,
        checklist_ref TEXT,
        finding TEXT,
        amount_at_risk REAL,
        vendor_name TEXT,
        finding_date TEXT,
        period TEXT,
        risk_band TEXT,
        status TEXT DEFAULT 'Open',
        sla_deadline TEXT,
        assigned_to TEXT,
        opened_by TEXT,
        opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT,
        days_to_close INTEGER
    )"""
    )

    # Workflow history log
    conn.execute(
        """CREATE TABLE IF NOT EXISTS workflow_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        finding_id INTEGER,
        old_status TEXT,
        new_status TEXT,
        changed_by TEXT,
        changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        comment TEXT
    )"""
    )

    # Management responses
    conn.execute(
        """CREATE TABLE IF NOT EXISTS management_responses (
            finding_id INTEGER PRIMARY KEY,
            response TEXT,
            action_owner TEXT,
            due_date TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # KPI tracking
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_kpi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            period TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # Sampling runs
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sampling_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_name TEXT,
            population_size INTEGER,
            sample_size INTEGER,
            method TEXT,
            confidence_level REAL,
            materiality_threshold REAL,
            executed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    conn.commit()
    conn.close()


def load_findings(period: str = None, risk_bands: list = None, area: str = None,
                  company_code: str = None, status: str = None) -> pd.DataFrame:
    """Load findings from SQLite with optional filters."""
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM audit_findings WHERE 1=1"
    params = []
    if period:
        q += " AND period=?"
        params.append(period)
    if risk_bands:
        placeholders = ",".join(["?"] * len(risk_bands))
        q += f" AND risk_band IN ({placeholders})"
        params.extend(risk_bands)
    if area:
        q += " AND area=?"
        params.append(area)
    if company_code:
        q += " AND company_code=?"
        params.append(company_code)
    if status:
        q += " AND status=?"
        params.append(status)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def compute_risk_score(amount_at_risk: float, recurrence_count: int) -> tuple:
    """Return (score, band) based on amount and recurrence."""
    impact = (
        1
        + (amount_at_risk > 100000)
        + (amount_at_risk > 1000000)
        + (amount_at_risk > 5000000)
        + (amount_at_risk > 10000000)
    )
    likelihood = 1 if recurrence_count == 1 else (3 if recurrence_count == 2 else 5)
    score = impact * likelihood
    band = (
        "CRITICAL"
        if score >= 20
        else "HIGH"
        if score >= 12
        else "MEDIUM"
        if score >= 6
        else "LOW"
    )
    return score, band


def update_status(finding_id: int, new_status: str, changed_by: str = "system", comment: str = "",
                  management_response: str = "", action_owner: str = "", due_date: str = ""):
    """Update finding status with full workflow history."""
    conn = sqlite3.connect("data/audit.db")

    # Get old status
    old = conn.execute("SELECT status FROM audit_findings WHERE id=?", (finding_id,)).fetchone()
    old_status = old[0] if old else "Open"

    # Update finding
    conn.execute(
        "UPDATE audit_findings SET status=? WHERE id=?",
        (new_status, finding_id),
    )

    # If closing, record closed_at and days_to_close
    if new_status in ["Closed", "Verified"]:
        conn.execute(
            """UPDATE audit_findings
               SET closed_at = CURRENT_TIMESTAMP,
                   days_to_close = CAST((julianday('now') - julianday(opened_at)) AS INTEGER)
               WHERE id=?""",
            (finding_id,)
        )

    # Log workflow history
    conn.execute(
        """INSERT INTO workflow_history (finding_id, old_status, new_status, changed_by, comment)
           VALUES (?,?,?,?,?)""",
        (finding_id, old_status, new_status, changed_by, comment),
    )

    # Save management response
    if management_response or action_owner or due_date:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS management_responses (
                finding_id INTEGER PRIMARY KEY,
                response TEXT,
                action_owner TEXT,
                due_date TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO management_responses
               (finding_id, response, action_owner, due_date, updated_at)
               VALUES (?,?,?,?,CURRENT_TIMESTAMP)""",
            (finding_id, management_response, action_owner, due_date),
        )

    conn.commit()
    conn.close()


def get_workflow_history(finding_id: int) -> pd.DataFrame:
    """Get status change history for a finding."""
    conn = sqlite3.connect("data/audit.db")
    df = pd.read_sql_query(
        "SELECT * FROM workflow_history WHERE finding_id=? ORDER BY changed_at DESC",
        conn, params=(finding_id,)
    )
    conn.close()
    return df


def get_sla_breaches() -> pd.DataFrame:
    """Return findings where SLA deadline has passed and status is not Closed/Verified."""
    conn = sqlite3.connect("data/audit.db")
    df = pd.read_sql_query(
        """SELECT * FROM audit_findings
           WHERE sla_deadline < date('now')
           AND status NOT IN ('Closed','Verified')
           ORDER BY sla_deadline ASC""",
        conn
    )
    conn.close()
    return df


def record_kpi(metric_name: str, metric_value: float, period: str):
    """Record a KPI metric."""
    conn = sqlite3.connect("data/audit.db")
    conn.execute(
        "INSERT INTO audit_kpi (metric_name, metric_value, period) VALUES (?,?,?)",
        (metric_name, metric_value, period),
    )
    conn.commit()
    conn.close()


def get_kpis(metric_name: str = None, period: str = None) -> pd.DataFrame:
    """Load KPI records."""
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM audit_kpi WHERE 1=1"
    params = []
    if metric_name:
        q += " AND metric_name=?"
        params.append(metric_name)
    if period:
        q += " AND period=?"
        params.append(period)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def save_sampling_run(run_name: str, population_size: int, sample_size: int,
                      method: str, confidence_level: float, materiality_threshold: float):
    """Record a statistical sampling run."""
    conn = sqlite3.connect("data/audit.db")
    conn.execute(
        """INSERT INTO sampling_runs
           (run_name, population_size, sample_size, method, confidence_level, materiality_threshold)
           VALUES (?,?,?,?,?,?)""",
        (run_name, population_size, sample_size, method, confidence_level, materiality_threshold),
    )
    conn.commit()
    conn.close()
