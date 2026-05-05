"""Audit Program Management - Structured Audit Procedures."""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def create_audit_program(engagement_id: int, program_name: str, description: str = None,
                        program_type: str = "Internal Audit") -> int:
    """Create an audit program."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_programs (engagement_id, program_name, description, program_type)
        VALUES (?, ?, ?, ?)
    """, (engagement_id, program_name, description, program_type))
    program_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return program_id


def get_audit_program(program_id: int) -> Optional[Dict[str, Any]]:
    """Get audit program details."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM audit_programs WHERE id = ?", (program_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_programs_for_engagement(engagement_id: int) -> pd.DataFrame:
    """Get all audit programs for an engagement."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT * FROM audit_programs WHERE engagement_id = ? ORDER BY created_at DESC
    """, conn, params=(engagement_id,))
    conn.close()
    return df


def add_procedure(program_id: int, procedure_name: str, procedure_desc: str = None,
                standard_ref: str = None, evidence_required: str = None,
                procedure_order: int = None) -> int:
    """Add a procedure to an audit program."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get next order if not specified
    if procedure_order is None:
        max_order = cursor.execute(
            "SELECT MAX(procedure_order) FROM program_procedures WHERE program_id = ?",
            (program_id,)
        ).fetchone()[0]
        procedure_order = (max_order or 0) + 1

    cursor.execute("""
        INSERT INTO program_procedures (program_id, procedure_name, procedure_desc, standard_ref, evidence_required, procedure_order)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (program_id, procedure_name, procedure_desc, standard_ref, evidence_required, procedure_order))
    procedure_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return procedure_id


def get_procedures(program_id: int) -> pd.DataFrame:
    """Get all procedures for a program."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT * FROM program_procedures WHERE program_id = ? ORDER BY procedure_order
    """, conn, params=(program_id,))
    conn.close()
    return df


def update_procedure_status(procedure_id: int, status: str, findings: str = None,
                           conclusion: str = None, worked_by: str = "system") -> bool:
    """Update procedure execution status."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE program_procedures
        SET status = ?, findings = ?, conclusion = ?, worked_by = ?, executed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, findings, conclusion, worked_by, procedure_id))
    conn.commit()
    conn.close()
    return True


def create_checklist(checklist_name: str, checklist_type: str, engagement_id: int = None) -> int:
    """Create a checklist (e.g., CARO checklist, Ind AS checklist)."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_checklists (checklist_name, checklist_type, engagement_id)
        VALUES (?, ?, ?)
    """, (checklist_name, checklist_type, engagement_id))
    checklist_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return checklist_id


def add_checklist_item(checklist_id: int, item_text: str, standard_ref: str = None,
                      response_required: str = "Yes/No/NA", order: int = None) -> int:
    """Add item to checklist."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    if order is None:
        max_order = cursor.execute(
            "SELECT MAX(item_order) FROM checklist_items WHERE checklist_id = ?",
            (checklist_id,)
        ).fetchone()[0]
        order = (max_order or 0) + 1

    cursor.execute("""
        INSERT INTO checklist_items (checklist_id, item_text, standard_ref, response_required, item_order)
        VALUES (?, ?, ?, ?, ?)
    """, (checklist_id, item_text, standard_ref, response_required, order))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def get_checklist(checklist_id: int) -> pd.DataFrame:
    """Get checklist with all items."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT * FROM checklist_items WHERE checklist_id = ? ORDER BY item_order
    """, conn, params=(checklist_id,))
    conn.close()
    return df


def update_checklist_response(item_id: int, response: str, finding_id: int = None,
                              remarks: str = None, responded_by: str = "system") -> bool:
    """Update checklist item response."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE checklist_items
        SET response = ?, finding_id = ?, remarks = ?, responded_by = ?, responded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (response, finding_id, remarks, responded_by, item_id))
    conn.commit()
    conn.close()
    return True


def get_checklist_summary(checklist_id: int) -> Dict[str, Any]:
    """Get checklist completion summary."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("SELECT response, COUNT(*) as cnt FROM checklist_items WHERE checklist_id = ? GROUP BY response", conn, params=(checklist_id,))
    conn.close()

    total = df['cnt'].sum()
    answered = df[~df['response'].isin([None, 'NA', ''])]['cnt'].sum()
    yes_count = df[df['response'] == 'Yes']['cnt'].sum() if 'Yes' in df['response'].values else 0
    no_count = df[df['response'] == 'No']['cnt'].sum() if 'No' in df['response'].values else 0
    na_count = df[df['response'] == 'NA']['cnt'].sum() if 'NA' in df['response'].values else 0

    return {
        "total_items": total,
        "answered": answered,
        "pending": total - answered,
        "yes": yes_count,
        "no": no_count,
        "na": na_count,
        "completion_pct": round(answered / total * 100, 1) if total > 0 else 0
    }


def init_audit_program_tables():
    """Initialize audit program tables."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Audit programs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            program_name TEXT NOT NULL,
            description TEXT,
            program_type TEXT,
            status TEXT DEFAULT 'Draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Program procedures
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS program_procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER,
            procedure_name TEXT NOT NULL,
            procedure_desc TEXT,
            standard_ref TEXT,
            evidence_required TEXT,
            procedure_order INTEGER,
            status TEXT DEFAULT 'Pending',
            findings TEXT,
            conclusion TEXT,
            worked_by TEXT,
            executed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(program_id) REFERENCES audit_programs(id) ON DELETE CASCADE
        )
    """)

    # Checklists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_name TEXT NOT NULL,
            checklist_type TEXT,
            engagement_id INTEGER,
            status TEXT DEFAULT 'Draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    # Checklist items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_id INTEGER,
            item_text TEXT NOT NULL,
            standard_ref TEXT,
            response_required TEXT DEFAULT 'Yes/No/NA',
            response TEXT,
            finding_id INTEGER,
            remarks TEXT,
            responded_by TEXT,
            responded_at TEXT,
            item_order INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(checklist_id) REFERENCES audit_checklists(id) ON DELETE CASCADE,
            FOREIGN KEY(finding_id) REFERENCES audit_findings(id)
        )
    """)

    conn.commit()
    conn.close()


def seed_standard_checklists():
    """Seed standard CARO/Ind AS checklists."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if already seeded
    existing = cursor.execute("SELECT COUNT(*) FROM audit_checklists").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    # CARO 2020 Checklist
    cursor.execute("INSERT INTO audit_checklists (checklist_name, checklist_type) VALUES (?, ?)",
                  ("CARO 2020 Checklist", "CARO"))
    caro_id = cursor.lastrowid

    caro_items = [
        ("Clause 1: Whether books of accounts maintained as required by law?", "CARO Clause 1", "Books of accounts maintained as per Section 128"),
        ("Clause 2: Whether fixed assets properly verified?", "CARO Clause 2", "Physical verification done, no material discrepancies"),
        ("Clause 3: Whether inventory physically verified?", "CARO Clause 3", "Physical verification at reasonable intervals"),
        ("Clause 4: Whether loans granted have proper terms?", "CARO Clause 4", "Prima facie not prejudicial to company"),
        ("Clause 5: Compliance with Section 185/186?", "CARO Clause 5", "No violation of loan/investment limits"),
        ("Clause 6: Whether deposits accepted comply with RBI?", "CARO Clause 6", "Terms and conditions not prejudicial"),
        ("Clause 7: Whether cost records maintained under Section 148?", "CARO Clause 7", "Cost records as per Cost Accounting Standards"),
        ("Clause 8: Whether statutory dues deposited on time?", "CARO Clause 8", "Provident Fund, ESI, GST, TDS, etc."),
        ("Clause 9: Whether undisclosed income dealt with?", "CARO Clause 9", "No concealment of income"),
        ("Clause 10: Whether SARS defaults exist?", "CARO Clause 10", "No default in repayment to SARS"),
        ("Clause 11: Whether managerial remuneration compliant?", "CARO Clause 11", "As per Section 197"),
        ("Clause 12: Whether related party transactions compliant?", "CARO Clause 12", "As per Section 188"),
        ("Clause 13: Whether internal audit system in place?", "CARO Clause 13", "Internal audit for prescribed class"),
    ]

    for item_text, standard_ref, response_required in caro_items:
        cursor.execute("""
            INSERT INTO checklist_items (checklist_id, item_text, standard_ref, response_required, item_order)
            VALUES (?, ?, ?, ?, ?)
        """, (caro_id, item_text, standard_ref, "Yes/No/NA", caro_items.index((item_text, standard_ref, response_required)) + 1))

    # Ind AS Checklist
    cursor.execute("INSERT INTO audit_checklists (checklist_name, checklist_type) VALUES (?, ?)",
                  ("Ind AS Compliance Checklist", "Ind AS"))
    ind_as_id = cursor.lastrowid

    ind_as_items = [
        ("Ind AS 1: Financial statements fairly presented?", "Ind AS 1", "True and fair view, Going concern"),
        ("Ind AS 16: PPE measured at cost?", "Ind AS 16", "Initial recognition, Subsequent measurement"),
        ("Ind AS 19: Employee benefits properly accounted?", "Ind AS 19", "Short-term, Long-term, Post-employment"),
        ("Ind AS 24: Related party disclosures complete?", "Ind AS 24", "All related parties identified"),
        ("Ind AS 37: Provisions and contingencies recognized?", "Ind AS 37", "Recognition criteria met"),
        ("Ind AS 115: Revenue recognized as per 5-step model?", "Ind AS 115", "Contract identification, Performance obligation"),
    ]

    for item_text, standard_ref, response_required in ind_as_items:
        cursor.execute("""
            INSERT INTO checklist_items (checklist_id, item_text, standard_ref, response_required, item_order)
            VALUES (?, ?, ?, ?, ?)
        """, (ind_as_id, item_text, standard_ref, "Yes/No/NA", ind_as_items.index((item_text, standard_ref, response_required)) + 1))

    conn.commit()
    conn.close()