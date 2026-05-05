"""Evidence Management - Audit-grade Trail with Immutability."""
import sqlite3
import hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import os


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file for integrity verification."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of string content."""
    return hashlib.sha256(content.encode()).hexdigest()


def upload_evidence(finding_id: int, file_path: str, description: str = None,
                   uploaded_by: str = "system", evidence_type: str = "Supporting Document") -> int:
    """Upload evidence file with hash verification."""
    Path("data/evidence").mkdir(exist_ok=True)

    # Compute original file hash
    file_hash = compute_file_hash(file_path)

    # Copy to evidence store with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.basename(file_path)
    new_file_name = f"{timestamp}_{finding_id}_{file_name}"
    dest_path = f"data/evidence/{new_file_name}"

    import shutil
    shutil.copy2(file_path, dest_path)

    # Compute new file hash after copy
    stored_hash = compute_file_hash(dest_path)

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO evidence_files (finding_id, file_path, file_hash, description, uploaded_by, evidence_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (finding_id, dest_path, stored_hash, description, uploaded_by, evidence_type))
    evidence_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return evidence_id


def get_evidence_for_finding(finding_id: int) -> pd.DataFrame:
    """Get all evidence files for a finding."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT id, file_path, file_hash, description, evidence_type, uploaded_by, uploaded_at
        FROM evidence_files WHERE finding_id = ? ORDER BY uploaded_at DESC
    """, conn, params=(finding_id,))
    conn.close()
    return df


def verify_evidence_integrity(evidence_id: int) -> Dict[str, Any]:
    """Verify evidence file integrity by recomputing hash."""
    conn = sqlite3.connect(get_db_path())
    row = pd.read_sql_query("SELECT * FROM evidence_files WHERE id = ?", conn, params=(evidence_id,)).iloc[0]
    conn.close()

    stored_hash = row['file_hash']
    current_hash = compute_file_hash(row['file_path'])

    return {
        "evidence_id": evidence_id,
        "stored_hash": stored_hash,
        "current_hash": current_hash,
        "integrity_verified": stored_hash == current_hash,
        "file_path": row['file_path']
    }


def add_workpaper(engagement_id: int, workpaper_name: str, content: str,
                 entity_id: int = None, workpaper_type: str = "Working Paper",
                 prepared_by: str = "system", reviewed_by: str = None) -> int:
    """Create a workpaper with content hash."""
    content_hash = compute_content_hash(content)

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workpapers (engagement_id, entity_id, workpaper_name, content, content_hash, workpaper_type, prepared_by, reviewed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (engagement_id, entity_id, workpaper_name, content, content_hash, workpaper_type, prepared_by, reviewed_by))
    workpaper_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return workpaper_id


def get_workpapers(engagement_id: int = None, entity_id: int = None) -> pd.DataFrame:
    """Get workpapers with optional filters."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM workpapers WHERE 1=1"
    params = []
    if engagement_id:
        q += " AND engagement_id = ?"
        params.append(engagement_id)
    if entity_id:
        q += " AND entity_id = ?"
        params.append(entity_id)
    q += " ORDER BY created_at DESC"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def add_review_note(finding_id: int, note_text: str, note_type: str = "Observation",
                   noted_by: str = "system", reviewer: str = None) -> int:
    """Add a review note with timestamp."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO review_notes (finding_id, note_text, note_type, noted_by, reviewer)
        VALUES (?, ?, ?, ?, ?)
    """, (finding_id, note_text, note_type, noted_by, reviewer))
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


def get_review_notes(finding_id: int) -> pd.DataFrame:
    """Get all review notes for a finding."""
    conn = sqlite3.connect(get_db_path())
    df = pd.read_sql_query("""
        SELECT * FROM review_notes WHERE finding_id = ? ORDER BY created_at DESC
    """, conn, params=(finding_id,))
    conn.close()
    return df


def create_audit_log(action: str, entity_type: str, entity_id: int,
                   user: str = "system", details: str = None) -> int:
    """Create immutable audit log entry."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (action, entity_type, entity_id, user, details)
        VALUES (?, ?, ?, ?, ?)
    """, (action, entity_type, entity_id, user, details))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_audit_log(entity_type: str = None, entity_id: int = None) -> pd.DataFrame:
    """Get audit log with filters."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if entity_type:
        q += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        q += " AND entity_id = ?"
        params.append(entity_id)
    q += " ORDER BY created_at DESC"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


def init_evidence_tables():
    """Initialize additional evidence-related tables."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Workpapers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workpapers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            entity_id INTEGER,
            workpaper_name TEXT NOT NULL,
            content TEXT,
            content_hash TEXT,
            workpaper_type TEXT,
            prepared_by TEXT,
            reviewed_by TEXT,
            status TEXT DEFAULT 'Draft',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(entity_id) REFERENCES audit_entities(id)
        )
    """)

    # Review notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id INTEGER,
            note_text TEXT NOT NULL,
            note_type TEXT,
            noted_by TEXT,
            reviewer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE
        )
    """)

    # Immutable audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            user TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add columns to audit_entities if not exist
    try:
        cursor.execute("ALTER TABLE audit_entities ADD COLUMN industry TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE audit_entities ADD COLUMN pan TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE audit_entities ADD COLUMN cin TEXT")
    except:
        pass

    # Add columns to audit_standards
    try:
        cursor.execute("ALTER TABLE audit_standards ADD COLUMN clause_text TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE audit_standards ADD COLUMN source_url TEXT")
    except:
        pass

    # Add processes and risks tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            process_name TEXT NOT NULL,
            description TEXT,
            risk_owner TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER,
            process_id INTEGER,
            risk_description TEXT NOT NULL,
            risk_category TEXT,
            inherent_risk TEXT,
            residual_risk TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES audit_engagements(id),
            FOREIGN KEY(process_id) REFERENCES audit_processes(id)
        )
    """)

    conn.commit()
    conn.close()