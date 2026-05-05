"""Enhanced Policy Management - Versioning, Metadata, and Control Mapping."""
import sqlite3
import hashlib
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def init_policy_tables():
    """Initialize policy management tables."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Policy Documents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT NOT NULL,
            doc_type TEXT,
            version TEXT DEFAULT '1.0',
            effective_date TEXT,
            expiry_date TEXT,
            owner TEXT,
            department TEXT,
            approval_status TEXT DEFAULT 'Draft',
            superseded_status TEXT DEFAULT 'Active',
            source_file_hash TEXT,
            file_path TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Policy Versions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            version TEXT NOT NULL,
            file_hash TEXT,
            file_path TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            change_notes TEXT,
            FOREIGN KEY(doc_id) REFERENCES policy_documents(id) ON DELETE CASCADE
        )
    """)

    # Policy-Control Mapping
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_control_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            clause_text TEXT,
            control_id INTEGER,
            process_id INTEGER,
            risk_id INTEGER,
            mapped_by TEXT,
            mapped_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(doc_id) REFERENCES policy_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(control_id) REFERENCES audit_controls(id),
            FOREIGN KEY(process_id) REFERENCES audit_processes(id),
            FOREIGN KEY(risk_id) REFERENCES audit_risks(id)
        )
    """)

    # Policy Exceptions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            exception_type TEXT,
            description TEXT,
            severity TEXT,
            detected_by TEXT,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Open',
            FOREIGN KEY(doc_id) REFERENCES policy_documents(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def register_policy(doc_name: str, doc_type: str, owner: str = None,
                   department: str = None, effective_date: str = None,
                   source_file_hash: str = None, file_path: str = None,
                   description: str = None) -> int:
    """Register a new policy document."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO policy_documents (
            doc_name, doc_type, owner, department, effective_date,
            source_file_hash, file_path, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (doc_name, doc_type, owner, department, effective_date,
          source_file_hash, file_path, description))
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def add_policy_version(doc_id: int, version: str, file_hash: str,
                      file_path: str, uploaded_by: str = "system",
                      change_notes: str = None) -> int:
    """Add a new version of a policy document."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO policy_versions (doc_id, version, file_hash, file_path, uploaded_by, change_notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (doc_id, version, file_hash, file_path, uploaded_by, change_notes))
    version_id = cursor.lastrowid

    # Update main document version
    cursor.execute("""
        UPDATE policy_documents SET version = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (version, doc_id))

    conn.commit()
    conn.close()
    return version_id


def update_policy_status(doc_id: int, approval_status: str = None,
                         superseded_status: str = None) -> bool:
    """Update policy approval or superseded status."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    if approval_status:
        cursor.execute("UPDATE policy_documents SET approval_status = ? WHERE id = ?",
                     (approval_status, doc_id))
    if superseded_status:
        cursor.execute("UPDATE policy_documents SET superseded_status = ? WHERE id = ?",
                     (superseded_status, doc_id))

    conn.commit()
    conn.close()
    return True


def list_policies(status: str = None, doc_type: str = None,
                 department: str = None) -> pd.DataFrame:
    """List policies with filters."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM policy_documents WHERE 1=1"
    params = []

    if status:
        q += " AND superseded_status = ?"
        params.append(status)
    if doc_type:
        q += " AND doc_type = ?"
        params.append(doc_type)
    if department:
        q += " AND department = ?"
        params.append(department)

    q += " ORDER BY updated_at DESC"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def get_policy_versions(doc_id: int) -> pd.DataFrame:
    """Get all versions of a policy document."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT * FROM policy_versions WHERE doc_id = ? ORDER BY uploaded_at DESC
    """, conn, params=(doc_id,))
    conn.close()
    return df


def map_policy_to_control(doc_id: int, clause_text: str,
                          control_id: int = None, process_id: int = None,
                          risk_id: int = None, mapped_by: str = "system") -> int:
    """Map a policy clause to a control/process/risk."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO policy_control_mappings (doc_id, clause_text, control_id, process_id, risk_id, mapped_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (doc_id, clause_text, control_id, process_id, risk_id, mapped_by))
    mapping_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return mapping_id


def get_policy_mappings(doc_id: int = None, control_id: int = None) -> pd.DataFrame:
    """Get policy-control mappings."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM policy_control_mappings WHERE 1=1"
    params = []

    if doc_id:
        q += " AND doc_id = ?"
        params.append(doc_id)
    if control_id:
        q += " AND control_id = ?"
        params.append(control_id)

    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def add_policy_exception(doc_id: int, exception_type: str, description: str,
                        severity: str = "MEDIUM", detected_by: str = "system") -> int:
    """Record a policy compliance exception."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO policy_exceptions (doc_id, exception_type, description, severity, detected_by)
        VALUES (?, ?, ?, ?, ?)
    """, (doc_id, exception_type, description, severity, detected_by))
    exception_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return exception_id


def get_policy_exceptions(doc_id: int = None, status: str = None) -> pd.DataFrame:
    """Get policy compliance exceptions."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM policy_exceptions WHERE 1=1"
    params = []

    if doc_id:
        q += " AND doc_id = ?"
        params.append(doc_id)
    if status:
        q += " AND status = ?"
        params.append(status)

    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


# Policy types for classification
POLICY_TYPES = [
    "Finance Policy",
    "HR Policy",
    "IT Policy",
    "Procurement Policy",
    "Sales Policy",
    "Operations Policy",
    "Compliance Policy",
    "Safety Policy",
    "Quality Policy",
    "Travel Policy",
    "Contract",
    "SOP",
    "Checklist",
    "Other"
]


# Approval statuses
APPROVAL_STATUSES = ["Draft", "Under Review", "Approved", "Rejected"]

# Superseded statuses
SUPERSEDED_STATUSES = ["Active", "Superseded", "Expired", "Retired"]