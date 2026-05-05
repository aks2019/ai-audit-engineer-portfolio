"""Shared SQLite audit trail — all detection pages write findings here.
Integrated Engagement & Standards Management System."""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime

def init_audit_db():
    """Create data dir and all audit tables if missing."""
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()

    # 0. Draft Findings (Maker-Checker Staging)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draft_audit_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            module_name TEXT,
            engagement_id INTEGER,
            entity_id INTEGER,
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
            draft_status TEXT DEFAULT 'Draft',
            ai_explanation TEXT,
            ai_citations TEXT,
            source_row_ref TEXT,
            source_file_hash TEXT,
            source_file_name TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            generated_by TEXT DEFAULT 'system',
            confirmed_at TEXT,
            confirmed_by TEXT,
            discarded_at TEXT,
            discarded_by TEXT,
            discard_reason TEXT,
            finding_hash TEXT,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(entity_id) REFERENCES audit_entities(id)
        )
    """)

    # 1. Audit Engagements (The Heart of the OS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_engagements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'Planned', -- Planned, Ongoing, Completed, Archived
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Audit Entities (Companies/Locations within an engagement)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            entity_name TEXT NOT NULL,
            location TEXT,
            code TEXT,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id) ON DELETE CASCADE
        )
    """)

    # 3. Standards Registry (The Knowledge Base)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family TEXT NOT NULL, -- e.g., 'Ind AS', 'Companies Act'
            reference TEXT NOT NULL, -- e.g., 'Section 135'
            description TEXT,
            applicability TEXT
        )
    """)

    # 4. Control Library (Mapping standards to processes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_controls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            standard_id INTEGER,
            process TEXT,
            control_objective TEXT,
            control_activity TEXT,
            control_type TEXT,
            frequency TEXT,
            owner TEXT,
            sap_module TEXT,
            sap_tcode TEXT,
            evidence_required TEXT,
            assertion TEXT,
            standard_ref TEXT,
            is_automated INTEGER DEFAULT 0,
            test_procedure TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(standard_id) REFERENCES audit_standards(id) ON DELETE SET NULL
        )
    """)

    # 5. Core Findings Table (Updated with Engagement & Entity links)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            entity_id INTEGER,
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
            days_to_close INTEGER,
            evidence_hash TEXT,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(entity_id) REFERENCES audit_entities(id)
        )
    """)

    # 6. Workflow history log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER,
            old_status TEXT,
            new_status TEXT,
            changed_by TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            comment TEXT,
            FOREIGN KEY(finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE
        )
    """)

    # 7. Management responses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS management_responses (
            finding_id INTEGER PRIMARY KEY,
            response TEXT,
            action_owner TEXT,
            due_date TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE
        )
    """)

    # 8. KPI tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_kpi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            period TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # 9. Sampling runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sampling_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            run_name TEXT,
            population_size INTEGER,
            sample_size INTEGER,
            method TEXT,
            confidence_level REAL,
            materiality_threshold REAL,
            executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # 10. Evidence Files (Audit-grade trail)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER,
            file_path TEXT,
            file_hash TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def load_findings(engagement_id: int = None, entity_id: int = None, period: str = None, 
                  risk_bands: list = None, area: str = None, company_code: str = None, 
                  status: str = None) -> pd.DataFrame:
    """Load findings from SQLite with enhanced engagement/entity filters."""
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM audit_findings WHERE 1=1"
    params = []
    if engagement_id:
        q += " AND engagement_id=?"
        params.append(engagement_id)
    if entity_id:
        q += " AND entity_id=?"
        params.append(entity_id)
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
    cursor = conn.cursor()

    # Get old status
    old = cursor.execute("SELECT status FROM audit_findings WHERE id=?", (finding_id,)).fetchone()
    old_status = old[0] if old else "Open"

    # Update finding
    cursor.execute(
        "UPDATE audit_findings SET status=? WHERE id=?",
        (new_status, finding_id),
    )

    # If closing, record closed_at and days_to_close
    if new_status in ["Closed", "Verified"]:
        cursor.execute(
            """UPDATE audit_findings
               SET closed_at = CURRENT_TIMESTAMP,
                   days_to_close = CAST((julianday('now') - julianday(opened_at)) AS INTEGER)
               WHERE id=?""",
            (finding_id,)
        )

    # Log workflow history
    cursor.execute(
        """INSERT INTO workflow_history (finding_id, old_status, new_status, changed_by, comment)
           VALUES (?,?,?,?,?)""",
        (finding_id, old_status, new_status, changed_by, comment),
    )

    # Save management response
    if management_response or action_owner or due_date:
        cursor.execute("""
            INSERT OR REPLACE INTO management_responses 
            (finding_id, response, action_owner, due_date, updated_at)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)
        """, (finding_id, management_response, action_owner, due_date))

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


def get_kpis(engagement_id: int = None, metric_name: str = None, period: str = None) -> pd.DataFrame:
    """Load KPI records."""
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM audit_kpi WHERE 1=1"
    params = []
    if engagement_id:
        q += " AND engagement_id=?"
        params.append(engagement_id)
    if metric_name:
        q += " AND metric_name=?"
        params.append(metric_name)
    if period:
        q += " AND period=?"
        params.append(period)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_sla_breaches(engagement_id: int = None) -> pd.DataFrame:
    """Get findings that have breached their SLA deadline."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("data/audit.db")
    q = """
        SELECT f.*, e.entity_name,
               CAST(julianday(?) - julianday(f.sla_deadline) AS INTEGER) as days_overdue
        FROM audit_findings f
        LEFT JOIN audit_entities e ON f.entity_id = e.id
        WHERE f.status IN ('Open', 'In Progress')
          AND f.sla_deadline IS NOT NULL
          AND f.sla_deadline < ?
    """
    params = [today, today]

    if engagement_id:
        q += " AND f.engagement_id = ?"
        params.append(engagement_id)

    q += " ORDER BY days_overdue DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def get_active_engagements():
    """Return list of ongoing or planned engagements."""
    conn = sqlite3.connect("data/audit.db")
    df = pd.read_sql_query("SELECT id, name FROM audit_engagements WHERE status != 'Archived' ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_engagement(name: str, description: str = None, start_date: str = None, end_date: str = None, status: str = "Planned"):
    """Helper to create a new engagement."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_engagements (name, description, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (name, description, start_date, end_date, status))
    engagement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return engagement_id
    cursor.execute("INSERT INTO audit_engagements (name, description) VALUES (?, ?)", (name, description))
    engagement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return engagement_id

def add_entity(engagement_id: int, entity_name: str, location: str = None, code: str = None):
    """Helper to create an entity within an engagement."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO audit_entities (engagement_id, entity_name, location, code) VALUES (?, ?, ?, ?)",
                   (engagement_id, entity_name, location, code))
    entity_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entity_id


def save_sampling_run(run_name: str, population_size: int, sample_size: int,
                     method: str, confidence_level: float = 0.95,
                     materiality_threshold: float = None, engagement_id: int = None):
    """Save a statistical sampling run to the database."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sampling_runs (run_name, population_size, sample_size, method, confidence_level, materiality_threshold, engagement_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_name, population_size, sample_size, method, confidence_level, materiality_threshold, engagement_id))
    conn.commit()
    conn.close()


def add_standard(family: str, reference: str, description: str = None, applicability: str = None):
    """Helper to register a standard."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO audit_standards (family, reference, description, applicability) VALUES (?, ?, ?, ?)",
                   (family, reference, description, applicability))
    standard_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return standard_id

def record_kpi(metric_name: str, metric_value: float, period: str = None, engagement_id: int = None):
    """Record a KPI metric (optionally for an engagement)."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_kpi (metric_name, metric_value, period, engagement_id)
        VALUES (?, ?, ?, ?)
    """, (metric_name, metric_value, period, engagement_id))
    conn.commit()
    conn.close()

# ====================== DRAFT FINDINGS WORKFLOW (MAKER-CHECKER) ======================
import hashlib
import json

def init_draft_findings_table():
    """Create draft_audit_findings table for staging proposed findings."""
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draft_audit_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            module_name TEXT,
            engagement_id INTEGER,
            entity_id INTEGER,
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
            draft_status TEXT DEFAULT 'Draft',
            ai_explanation TEXT,
            ai_citations TEXT,
            source_row_ref TEXT,
            source_file_hash TEXT,
            source_file_name TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            generated_by TEXT DEFAULT 'system',
            confirmed_at TEXT,
            confirmed_by TEXT,
            discarded_at TEXT,
            discarded_by TEXT,
            discard_reason TEXT,
            finding_hash TEXT,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(entity_id) REFERENCES audit_entities(id)
        )
    """)

    conn.commit()
    conn.close()


def compute_finding_hash(data: dict) -> str:
    """Compute deterministic hash to detect duplicate findings."""
    content = json.dumps({
        "area": data.get("area"),
        "finding": data.get("finding"),
        "vendor": data.get("vendor_name"),
        "amount": data.get("amount_at_risk"),
        "period": data.get("period")
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def stage_findings(findings_df: pd.DataFrame, module_name: str, run_id: str = None,
                   engagement_id: int = None, entity_id: int = None, period: str = None,
                   generated_by: str = "system", ai_explanation: str = None,
                   ai_citations: str = None, source_file_name: str = None,
                   source_file_hash: str = None) -> int:
    """Save proposed findings to draft stage, not to official audit_findings."""
    if findings_df is None or len(findings_df) == 0:
        return 0

    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    staged_count = 0

    for _, row in findings_df.iterrows():
        finding_data = {
            "area": row.get("area", ""),
            "finding": row.get("finding", ""),
            "vendor_name": row.get("vendor_name", ""),
            "amount_at_risk": row.get("amount_at_risk", 0),
            "period": row.get("period", period)
        }
        finding_hash = compute_finding_hash(finding_data)

        cursor.execute("""
            INSERT INTO draft_audit_findings (
                run_id, module_name, engagement_id, entity_id, company_code, plant_code,
                area, checklist_ref, finding, amount_at_risk, vendor_name, finding_date,
                period, risk_band, draft_status, ai_explanation, ai_citations,
                source_row_ref, source_file_name, source_file_hash, generated_by, finding_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, module_name, engagement_id, entity_id,
            row.get("company_code", "HQ"), row.get("plant_code", ""),
            row.get("area", ""), row.get("checklist_ref", ""), row.get("finding", ""),
            row.get("amount_at_risk", 0), row.get("vendor_name", ""), row.get("finding_date", ""),
            row.get("period", period), row.get("risk_band", "MEDIUM"), "Draft",
            ai_explanation, ai_citations, row.get("source_row_ref", ""),
            source_file_name, source_file_hash, generated_by, finding_hash
        ))
        staged_count += 1

    conn.commit()
    conn.close()
    return staged_count


def load_draft_findings(run_id: str = None, module_name: str = None,
                       status: str = "Draft", engagement_id: int = None) -> pd.DataFrame:
    """Load pending draft findings for auditor review."""
    conn = sqlite3.connect("data/audit.db")
    q = "SELECT * FROM draft_audit_findings WHERE 1=1"
    params = []

    if run_id:
        q += " AND run_id = ?"
        params.append(run_id)
    if module_name:
        q += " AND module_name = ?"
        params.append(module_name)
    if status:
        q += " AND draft_status = ?"
        params.append(status)
    if engagement_id:
        q += " AND engagement_id = ?"
        params.append(engagement_id)

    q += " ORDER BY generated_at DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def confirm_draft_findings(draft_ids: list, confirmed_by: str = "auditor",
                          edited_values: dict = None) -> int:
    """Move selected draft findings into official audit_findings."""
    if not draft_ids:
        return 0

    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()
    confirmed_count = 0

    for draft_id in draft_ids:
        # Load draft record
        draft = cursor.execute(
            "SELECT * FROM draft_audit_findings WHERE id = ?", (draft_id,)
        ).fetchone()

        if not draft:
            continue

        # Apply any edits if provided
        if edited_values and draft_id in edited_values:
            edits = edited_values[draft_id]
        else:
            edits = {}

        # Insert into official audit_findings
        cursor.execute("""
            INSERT INTO audit_findings (
                engagement_id, entity_id, run_id, company_code, plant_code,
                area, checklist_ref, finding, amount_at_risk, vendor_name,
                finding_date, period, risk_band, status, opened_by, opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            draft[3], draft[4], draft[1], draft[5], draft[6],
            draft[7], draft[8], edits.get("finding", draft[9]),
            edits.get("amount_at_risk", draft[10]), edits.get("vendor_name", draft[11]),
            draft[12], edits.get("period", draft[13]),
            edits.get("risk_band", draft[14]), "Open", confirmed_by
        ))

        # Update draft status
        cursor.execute("""
            UPDATE draft_audit_findings
            SET draft_status = 'Confirmed', confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
            WHERE id = ?
        """, (confirmed_by, draft_id))

        confirmed_count += 1

    conn.commit()
    conn.close()
    return confirmed_count


def discard_draft_findings(draft_ids: list, discarded_by: str = "auditor",
                          reason: str = None) -> int:
    """Mark draft exceptions as discarded."""
    if not draft_ids:
        return 0

    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()

    placeholders = ",".join(["?"] * len(draft_ids))
    cursor.execute(f"""
        UPDATE draft_audit_findings
        SET draft_status = 'Discarded', discarded_at = CURRENT_TIMESTAMP, discarded_by = ?, discard_reason = ?
        WHERE id IN ({placeholders})
    """, (discarded_by, reason, *draft_ids))

    discarded_count = len(draft_ids)
    conn.commit()
    conn.close()
    return discarded_count


def is_duplicate_finding(finding_hash: str, engagement_id: int = None) -> bool:
    """Check if a finding with same hash already exists in audit_findings."""
    conn = sqlite3.connect("data/audit.db")
    cursor = conn.cursor()

    q = "SELECT COUNT(*) FROM draft_audit_findings WHERE finding_hash = ? AND draft_status = 'Confirmed'"
    params = [finding_hash]

    if engagement_id:
        q += " AND engagement_id = ?"
        params.append(engagement_id)

    count = cursor.execute(q, params).fetchone()[0]
    conn.close()
    return count > 0


def get_confirmed_findings_count(engagement_id: int = None) -> dict:
    """Get count of confirmed findings for reporting."""
    conn = sqlite3.connect("data/audit.db")

    q = "SELECT status, COUNT(*) as cnt FROM audit_findings"
    params = []
    if engagement_id:
        q += " WHERE engagement_id = ?"
        params.append(engagement_id)
    q += " GROUP BY status"

    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()

    return {
        "total": df["cnt"].sum() if len(df) > 0 else 0,
        "open": df[df["status"] == "Open"]["cnt"].sum() if "Open" in df["status"].values else 0,
        "closed": df[df["status"] == "Closed"]["cnt"].sum() if "Closed" in df["status"].values else 0,
        "verified": df[df["status"] == "Verified"]["cnt"].sum() if "Verified" in df["status"].values else 0
    }