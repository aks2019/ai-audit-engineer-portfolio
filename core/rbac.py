"""RBAC and Governance - User Roles, Maker-Checker, Audit Logs."""
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any
import hashlib


def get_db_path() -> str:
    Path("data").mkdir(exist_ok=True)
    return "data/audit.db"


def init_rbac_tables():
    """Initialize RBAC and governance tables."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'viewer',
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    """)

    # Role permissions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            description TEXT,
            UNIQUE(role, permission)
        )
    """)

    # Immutable audit log (separate from entity-specific logs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS governance_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            user TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            session_id TEXT
        )
    """)

    # Maker-Checker approvals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maker_checker_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            maker TEXT NOT NULL,
            maker_comments TEXT,
            maker_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewer TEXT,
            reviewer_comments TEXT,
            status TEXT DEFAULT 'Pending',
            reviewer_timestamp TEXT,
            due_date TEXT
        )
    """)

    # AI Response audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_response_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            request_hash TEXT,
            prompt_hash TEXT,
            response_hash TEXT,
            provider TEXT,
            model TEXT,
            tokens_used INTEGER,
            user TEXT,
            engagement_id INTEGER,
            module_name TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


# ====================== USER MANAGEMENT ======================

def create_user(username: str, display_name: str = None, email: str = None,
               role: str = "viewer") -> int:
    """Create a new audit user."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_users (username, display_name, email, role)
        VALUES (?, ?, ?, ?)
    """, (username, display_name, email, role))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get user details."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM audit_users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_role(username: str, role: str) -> bool:
    """Update user role."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("UPDATE audit_users SET role = ? WHERE username = ?", (role, username))
    conn.commit()
    conn.close()
    return True


def list_users(status: str = None) -> pd.DataFrame:
    """List all users."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM audit_users"
    if status:
        q += f" WHERE status = '{status}'"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


# ====================== PERMISSIONS ======================

ROLE_PERMISSIONS = {
    "admin": [
        "create_engagement", "edit_engagement", "delete_engagement", "view_engagement",
        "create_finding", "edit_finding", "delete_finding", "confirm_finding", "discard_finding",
        "view_all_reports", "export_reports",
        "manage_users", "manage_roles",
        "approve_maker_checker", "reject_maker_checker",
        "manage_policies", "edit_policies",
        "view_ai_logs"
    ],
    "auditor": [
        "create_engagement", "edit_engagement", "view_engagement",
        "create_finding", "edit_finding", "view_finding",
        "view_reports", "export_reports",
        "confirm_finding", "discard_finding",
        "manage_policies"
    ],
    "reviewer": [
        "view_engagement", "view_finding",
        "view_reports", "export_reports",
        "approve_maker_checker", "reject_maker_checker"
    ],
    "viewer": [
        "view_engagement", "view_finding",
        "view_reports"
    ]
}


def seed_role_permissions():
    """Seed default role permissions."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if already seeded
    existing = cursor.execute("SELECT COUNT(*) FROM role_permissions").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    for role, permissions in ROLE_PERMISSIONS.items():
        for perm in permissions:
            cursor.execute("""
                INSERT OR IGNORE INTO role_permissions (role, permission, description)
                VALUES (?, ?, ?)
            """, (role, perm, f"Permission for {role}"))

    conn.commit()
    conn.close()


def has_permission(username: str, permission: str) -> bool:
    """Check if user has a specific permission."""
    user = get_user(username)
    if not user or user.get("status") != "Active":
        return False

    role = user.get("role", "viewer")
    user_perms = ROLE_PERMISSIONS.get(role, [])
    return permission in user_perms


def get_user_permissions(username: str) -> List[str]:
    """Get all permissions for a user."""
    user = get_user(username)
    if not user:
        return []
    return ROLE_PERMISSIONS.get(user.get("role", "viewer"), [])


# ====================== GOVERNANCE AUDIT LOG ======================

def log_governance_action(user: str, action: str, entity_type: str = None,
                         entity_id: int = None, old_value: str = None,
                         new_value: str = None) -> int:
    """Log an immutable governance action."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO governance_audit_log (user, action, entity_type, entity_id, old_value, new_value)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user, action, entity_type, entity_id, old_value, new_value))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_governance_log(entity_type: str = None, entity_id: int = None,
                      user: str = None, limit: int = 100) -> pd.DataFrame:
    """Get governance audit log."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM governance_audit_log WHERE 1=1"
    params = []

    if entity_type:
        q += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        q += " AND entity_id = ?"
        params.append(entity_id)
    if user:
        q += " AND user = ?"
        params.append(user)

    q += f" ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


# ====================== MAKER-CHECKER ======================

def submit_for_approval(entity_type: str, entity_id: int, action: str,
                       maker: str, maker_comments: str = None,
                       due_date: str = None) -> int:
    """Submit an action for maker-checker approval."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO maker_checker_approvals (entity_type, entity_id, action, maker, maker_comments, due_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entity_type, entity_id, action, maker, maker_comments, due_date))
    approval_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Log governance action
    log_governance_action(maker, f"SUBMIT_{action}", entity_type, entity_id)

    return approval_id


def approve_request(approval_id: int, reviewer: str, reviewer_comments: str = None) -> bool:
    """Approve a maker-checker request."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Get the request
    row = cursor.execute(
        "SELECT * FROM maker_checker_approvals WHERE id = ?", (approval_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    # Update approval
    cursor.execute("""
        UPDATE maker_checker_approvals
        SET status = 'Approved', reviewer = ?, reviewer_comments = ?, reviewer_timestamp = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (reviewer, reviewer_comments, approval_id))

    conn.commit()
    conn.close()

    # Log governance action
    log_governance_action(reviewer, f"APPROVE_{row[3]}", row[2], row[3])

    return True


def reject_request(approval_id: int, reviewer: str, reviewer_comments: str = None) -> bool:
    """Reject a maker-checker request."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    row = cursor.execute(
        "SELECT * FROM maker_checker_approvals WHERE id = ?", (approval_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    cursor.execute("""
        UPDATE maker_checker_approvals
        SET status = 'Rejected', reviewer = ?, reviewer_comments = ?, reviewer_timestamp = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (reviewer, reviewer_comments, approval_id))

    conn.commit()
    conn.close()

    log_governance_action(reviewer, f"REJECT_{row[3]}", row[2], row[3])

    return True


def get_pending_approvals(reviewer: str = None) -> pd.DataFrame:
    """Get pending maker-checker approvals."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM maker_checker_approvals WHERE status = 'Pending'"
    if reviewer:
        q += f" AND reviewer = '{reviewer}'"
    q += " ORDER BY maker_timestamp DESC"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


# ====================== AI RESPONSE AUDIT ======================

def log_ai_response(request_hash: str, prompt_hash: str, response_hash: str,
                   provider: str, model: str, user: str = "system",
                   engagement_id: int = None, module_name: str = None,
                   status: str = "success", tokens_used: int = 0) -> int:
    """Log AI response for audit trail."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ai_response_audit (
            request_hash, prompt_hash, response_hash, provider, model,
            user, engagement_id, module_name, status, tokens_used
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (request_hash, prompt_hash, response_hash, provider, model,
          user, engagement_id, module_name, status, tokens_used))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_ai_audit_log(engagement_id: int = None, module_name: str = None,
                     user: str = None, limit: int = 100) -> pd.DataFrame:
    """Get AI response audit log."""
    conn = sqlite3.connect(get_db_path())
    q = "SELECT * FROM ai_response_audit WHERE 1=1"
    params = []

    if engagement_id:
        q += " AND engagement_id = ?"
        params.append(engagement_id)
    if module_name:
        q += " AND module_name = ?"
        params.append(module_name)
    if user:
        q += " AND user = ?"
        params.append(user)

    q += f" ORDER BY timestamp DESC LIMIT {limit}"
    df = pd.read_sql_query(q, conn, params=params if params else None)
    conn.close()
    return df


# ====================== DEFAULT SETUP ======================

def setup_default_users():
    """Create default audit users."""
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Check if users exist
    existing = cursor.execute("SELECT COUNT(*) FROM audit_users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    # Create default users
    default_users = [
        ("admin", "System Administrator", "admin@audit.local", "admin"),
        ("auditor", "Lead Auditor", "auditor@audit.local", "auditor"),
        ("reviewer", "Audit Reviewer", "reviewer@audit.local", "reviewer"),
        ("viewer", "Read Only User", "viewer@audit.local", "viewer")
    ]

    for username, display_name, email, role in default_users:
        cursor.execute("""
            INSERT INTO audit_users (username, display_name, email, role)
            VALUES (?, ?, ?, ?)
        """, (username, display_name, email, role))

    conn.commit()
    conn.close()


def init_rbac():
    """Initialize complete RBAC system."""
    init_rbac_tables()
    seed_role_permissions()
    setup_default_users()