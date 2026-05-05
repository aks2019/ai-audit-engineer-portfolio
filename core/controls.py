"""Control Library Management - Formal Controls with Standards Mapping."""
import sqlite3
from pathlib import Path
import pandas as pd
from typing import Optional, Dict, List, Any


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db()


def register_control(process: str, control_objective: str, control_activity: str,
                   control_type: str = None, frequency: str = None, owner: str = None,
                   sap_module: str = None, sap_tcode: str = None, evidence_required: str = None,
                   assertion: str = None, standard_ref: str = None, standard_id: int = None,
                   engagement_id: int = None, is_automated: bool = False,
                   test_procedure: str = None) -> int:
    """Register a formal control."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_controls (
            process, control_objective, control_activity, control_type, frequency, owner,
            sap_module, sap_tcode, evidence_required, assertion, standard_ref, standard_id,
            engagement_id, is_automated, test_procedure
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (process, control_objective, control_activity, control_type, frequency, owner,
          sap_module, sap_tcode, evidence_required, assertion, standard_ref, standard_id,
          engagement_id, 1 if is_automated else 0, test_procedure))
    control_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return control_id


def get_control(control_id: int) -> Optional[Dict[str, Any]]:
    """Get control details."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM audit_controls WHERE id = ?", (control_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_controls(engagement_id: int = None, process: str = None,
                 owner: str = None, status: str = "Active") -> pd.DataFrame:
    """List controls with filters."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT c.*, s.family as standard_family, s.reference as standard_reference FROM audit_controls c LEFT JOIN audit_standards s ON c.standard_id = s.id WHERE 1=1"
    params = []

    if engagement_id:
        q += " AND c.engagement_id = ?"
        params.append(engagement_id)
    if process:
        q += " AND c.process = ?"
        params.append(process)
    if owner:
        q += " AND c.owner = ?"
        params.append(owner)
    if status:
        q += " AND c.status = ?"
        params.append(status)

    q += " ORDER BY c.process, c.control_objective"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def map_control_to_standard(control_id: int, standard_id: int,
                            standard_ref: str = None) -> bool:
    """Map a control to a standard."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE audit_controls SET standard_id = ?, standard_ref = ? WHERE id = ?
    """, (standard_id, standard_ref, control_id))
    conn.commit()
    conn.close()
    return True


def get_controls_for_checklist(checklist_id: int) -> pd.DataFrame:
    """Get controls mapped to a checklist."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT c.*, ci.item_text as checklist_item, ci.response
        FROM audit_controls c
        LEFT JOIN checklist_items ci ON c.standard_ref = ci.standard_ref
        WHERE ci.checklist_id = ?
        ORDER BY c.process
    """, conn, params=(checklist_id,))
    conn.close()
    return df


def seed_default_controls():
    """Seed default controls for common processes."""
    controls = [
        # Procurement Controls
        ("Procurement", "Purchase orders properly authorized", "PO approval within limits", "Preventive", "Per transaction", "Procurement Head", "SAP", "ME51N", "Signed PO", "Completeness", "Section 188 Companies Act"),
        ("Procurement", "Vendor selection per policy", "Vendor master verification", "Corrective", "Quarterly", "Procurement Head", "SAP", "XK01", "Vendor master form", "Validity", "Companies Act"),
        ("Procurement", "No splitting of PO to bypass approval", "PO value checks", "Detective", "Real-time", "Procurement Head", "SAP", "ME21N", "PO value report", "Accuracy", "Internal Control"),

        # Finance Controls
        ("Finance", "Journal entries authorized", "Manual JV approval", "Preventive", "Per transaction", "Finance Head", "SAP", "FBV1", "Approval email", "Completeness", "SA 300"),
        ("Finance", "Bank reconciliation timely", "Monthly BRS", "Detective", "Monthly", "Finance Head", "SAP", "FF67", "Reconciliation statement", "Completeness", "AS 14"),
        ("Finance", "Fixed asset capitalization", "Asset capitalization review", "Preventive", "Per transaction", "Finance Head", "SAP", "AS01", "Asset register", "Completeness", "Ind AS 16"),

        # IT Controls
        ("IT", "User access review", " Quarterly access review", "Detective", "Quarterly", "IT Head", "SAP", "SUIM", "Access review report", "Compliance", "ITGC"),
        ("IT", "Segregation of duties", "SoD conflict check", "Preventive", "Real-time", "IT Head", "SAP", "GRC", "SoD report", "Compliance", "ITGC"),
        ("IT", "Data backup verification", "Daily backup check", "Detective", "Daily", "IT Head", "SAP", "DB02", "Backup log", "Availability", "ITGC"),

        # Inventory Controls
        ("Inventory", "Physical inventory verification", "Annual/periodic stock take", "Detective", "Annual", "Operations Head", "SAP", "MI21", "Stock count report", "Completeness", "CARO Clause 3"),
        ("Inventory", "Inventory valuation per policy", "Monthly valuation review", "Preventive", "Monthly", "Finance Head", "SAP", "MB52", "Valuation report", "Valuation", "AS 2 / Ind AS 2"),
        ("Inventory", "Slow-moving inventory review", "Monthly slow-moving report", "Detective", "Monthly", "Operations Head", "SAP", "MB52", "Ageing report", "Valuation", "Internal Control"),

        # Payroll Controls
        ("Payroll", "Salary calculation accuracy", "Payroll audit", "Detective", "Monthly", "HR Head", "SAP", "PC00_M99_CALC", "Payroll register", "Accuracy", "ESIC/PF Act"),
        ("Payroll", "Statutory deductions accuracy", "PF/ESI calculation check", "Detective", "Monthly", "HR Head", "SAP", "PC00_M99_CALC", "Statutory report", "Compliance", "PF/ESI Act"),
    ]

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    for control in controls:
        cursor.execute("""
            INSERT OR IGNORE INTO audit_controls (
                process, control_objective, control_activity, control_type, frequency, owner,
                sap_module, sap_tcode, evidence_required, assertion, standard_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, control)

    conn.commit()
    conn.close()
    return len(controls)


# Control types
CONTROL_TYPES = ["Preventive", "Detective", "Corrective"]

# Control frequencies
CONTROL_FREQUENCIES = ["Real-time", "Daily", "Weekly", "Monthly", "Quarterly", "Annual"]

# Assertions
CONTROL_ASSERTIONS = ["Completeness", "Accuracy", "Validity", "Existence", "Rights", "Classification", "Cutoff"]