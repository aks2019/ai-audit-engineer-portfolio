"""Shared SQLite audit trail for SARVAGYA.

Confirmed audit findings live in audit_findings and feed formal MIS, detailed audit
reports, committee packs, workflow, and KPIs. Detection pages must stage proposed
exceptions in draft_audit_findings first; an auditor confirms selected drafts before
they become official findings.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DB_PATH = Path("data") / "audit.db"


def _connect() -> sqlite3.Connection:
    Path("data").mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_audit_db():
    """Create data dir and all audit tables if missing."""
    conn = _connect()

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

    # Backward-compatible columns for confirmed, evidence-linked findings.
    _ensure_column(conn, "audit_findings", "finding_hash", "TEXT")
    _ensure_column(conn, "audit_findings", "ai_explanation", "TEXT")
    _ensure_column(conn, "audit_findings", "policy_citations", "TEXT")
    _ensure_column(conn, "audit_findings", "source_row_ref", "TEXT")
    _ensure_column(conn, "audit_findings", "source_file_name", "TEXT")
    _ensure_column(conn, "audit_findings", "source_file_hash", "TEXT")
    _ensure_column(conn, "audit_findings", "confirmed_by", "TEXT")
    _ensure_column(conn, "audit_findings", "confirmed_at", "TEXT")

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
        """CREATE TABLE IF NOT EXISTS audit_kpi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            period TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )

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

    conn.execute(
        """CREATE TABLE IF NOT EXISTS draft_audit_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_hash TEXT UNIQUE,
            module TEXT,
            run_id TEXT,
            company_code TEXT DEFAULT 'HQ',
            plant_code TEXT DEFAULT '',
            area TEXT,
            checklist_ref TEXT,
            proposed_finding TEXT,
            amount_at_risk REAL,
            reference_name TEXT,
            risk_band TEXT,
            period TEXT,
            ai_explanation TEXT,
            policy_citations TEXT,
            source_row_ref TEXT,
            source_file_name TEXT,
            source_file_hash TEXT,
            draft_status TEXT DEFAULT 'Draft',
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            generated_by TEXT DEFAULT 'system',
            confirmed_at TEXT,
            confirmed_by TEXT,
            discarded_at TEXT,
            discarded_by TEXT,
            discard_reason TEXT,
            prompt_hash TEXT,
            response_hash TEXT,
            model_provider TEXT,
            assigned_to TEXT,
            sla_deadline TEXT,
            metadata_json TEXT
        )"""
    )

    conn.commit()
    conn.close()


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def compute_finding_hash(payload: dict) -> str:
    """Compute deterministic hash for duplicate prevention."""
    keys = [
        "module", "company_code", "plant_code", "area", "checklist_ref",
        "proposed_finding", "amount_at_risk", "reference_name", "period",
        "source_row_ref", "source_file_name", "source_file_hash",
    ]
    normalized = {key: str(payload.get(key, "")) for key in keys}
    return hashlib.sha256(_stable_json(normalized).encode("utf-8")).hexdigest()


def is_duplicate_finding(finding_hash: str) -> bool:
    """Return True when a finding hash is already confirmed."""
    init_audit_db()
    conn = _connect()
    found = conn.execute(
        "SELECT 1 FROM audit_findings WHERE finding_hash=? LIMIT 1",
        (finding_hash,),
    ).fetchone()
    conn.close()
    return found is not None


def stage_findings(df: pd.DataFrame, module: str, run_id: str, period: str,
                   metadata: dict | None = None) -> dict:
    """Stage proposed findings for auditor review without official logging."""
    init_audit_db()
    metadata = metadata or {}
    company_code = metadata.get("company_code", "HQ")
    plant_code = metadata.get("plant_code", "")
    area = metadata.get("area", module)
    generated_by = metadata.get("generated_by", "system")
    source_file_name = metadata.get("source_file_name", "")
    source_file_hash = metadata.get("source_file_hash", "")
    model_provider = metadata.get("model_provider", "")

    inserted = 0
    skipped_duplicates = 0
    conn = _connect()
    for idx, row in df.iterrows():
        payload = {
            "module": module,
            "run_id": run_id,
            "company_code": row.get("company_code", company_code),
            "plant_code": row.get("plant_code", plant_code),
            "area": row.get("area", area),
            "checklist_ref": row.get("checklist_ref", metadata.get("checklist_ref", "")),
            "proposed_finding": row.get(
                "proposed_finding",
                row.get("finding", row.get("flag_reason", "Exception detected")),
            ),
            "amount_at_risk": float(row.get("amount_at_risk", row.get("amount", 0)) or 0),
            "reference_name": row.get(
                "reference_name",
                row.get("vendor_name", row.get("customer_name", row.get("employee_name", ""))),
            ),
            "risk_band": row.get("risk_band", metadata.get("risk_band", "HIGH")),
            "period": period,
            "source_row_ref": str(row.get("source_row_ref", idx)),
            "source_file_name": source_file_name,
            "source_file_hash": source_file_hash,
        }
        finding_hash = row.get("finding_hash") or compute_finding_hash(payload)
        try:
            conn.execute(
                """INSERT INTO draft_audit_findings
                (finding_hash, module, run_id, company_code, plant_code, area,
                 checklist_ref, proposed_finding, amount_at_risk, reference_name,
                 risk_band, period, ai_explanation, policy_citations, source_row_ref,
                 source_file_name, source_file_hash, generated_by, prompt_hash,
                 response_hash, model_provider, assigned_to, sla_deadline, metadata_json)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    finding_hash,
                    payload["module"],
                    payload["run_id"],
                    payload["company_code"],
                    payload["plant_code"],
                    payload["area"],
                    payload["checklist_ref"],
                    payload["proposed_finding"],
                    payload["amount_at_risk"],
                    payload["reference_name"],
                    payload["risk_band"],
                    payload["period"],
                    row.get("ai_explanation", metadata.get("ai_explanation", "")),
                    row.get("policy_citations", metadata.get("policy_citations", "")),
                    payload["source_row_ref"],
                    payload["source_file_name"],
                    payload["source_file_hash"],
                    generated_by,
                    row.get("prompt_hash", metadata.get("prompt_hash", "")),
                    row.get("response_hash", metadata.get("response_hash", "")),
                    model_provider,
                    row.get("assigned_to", metadata.get("assigned_to", "")),
                    row.get("sla_deadline", metadata.get("sla_deadline", "")),
                    _stable_json(metadata),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped_duplicates += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped_duplicates": skipped_duplicates}


def load_draft_findings(run_id: str | None = None, module: str | None = None,
                        status: str | None = "Draft") -> pd.DataFrame:
    """Load staged findings for review."""
    init_audit_db()
    conn = _connect()
    q = "SELECT * FROM draft_audit_findings WHERE 1=1"
    params = []
    if run_id:
        q += " AND run_id=?"
        params.append(run_id)
    if module:
        q += " AND module=?"
        params.append(module)
    if status:
        q += " AND draft_status=?"
        params.append(status)
    q += " ORDER BY generated_at DESC, id DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def confirm_draft_findings(draft_ids: list[int], confirmed_by: str = "auditor",
                           edited_values: dict[int, dict] | None = None) -> dict:
    """Promote selected draft findings into official audit_findings."""
    init_audit_db()
    edited_values = edited_values or {}
    confirmed = 0
    skipped_duplicates = 0
    missing = 0

    conn = _connect()
    cols = [row[1] for row in conn.execute("PRAGMA table_info(draft_audit_findings)").fetchall()]
    for draft_id in draft_ids:
        row = conn.execute(
            "SELECT * FROM draft_audit_findings WHERE id=? AND draft_status='Draft'",
            (int(draft_id),),
        ).fetchone()
        if row is None:
            missing += 1
            continue
        draft = dict(zip(cols, row))
        draft.update(edited_values.get(int(draft_id), {}))

        if conn.execute(
            "SELECT 1 FROM audit_findings WHERE finding_hash=? LIMIT 1",
            (draft["finding_hash"],),
        ).fetchone():
            skipped_duplicates += 1
            continue

        conn.execute(
            """INSERT INTO audit_findings
            (run_id, finding_hash, company_code, plant_code, area, checklist_ref,
             finding, amount_at_risk, vendor_name, finding_date, period, risk_band,
             status, sla_deadline, assigned_to, opened_by, ai_explanation,
             policy_citations, source_row_ref, source_file_name, source_file_hash,
             confirmed_by, confirmed_at)
             VALUES (?,?,?,?,?,?,?,?,?,date('now'),?,?,'Open',?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (
                draft.get("run_id", ""),
                draft.get("finding_hash", ""),
                draft.get("company_code", "HQ"),
                draft.get("plant_code", ""),
                draft.get("area", ""),
                draft.get("checklist_ref", ""),
                draft.get("proposed_finding", ""),
                float(draft.get("amount_at_risk") or 0),
                draft.get("reference_name", ""),
                draft.get("period", ""),
                draft.get("risk_band", "HIGH"),
                draft.get("sla_deadline", ""),
                draft.get("assigned_to", ""),
                confirmed_by,
                draft.get("ai_explanation", ""),
                draft.get("policy_citations", ""),
                draft.get("source_row_ref", ""),
                draft.get("source_file_name", ""),
                draft.get("source_file_hash", ""),
                confirmed_by,
            ),
        )
        conn.execute(
            """UPDATE draft_audit_findings
               SET draft_status='Confirmed', confirmed_at=CURRENT_TIMESTAMP,
                   confirmed_by=?
               WHERE id=?""",
            (confirmed_by, int(draft_id)),
        )
        confirmed += 1
    conn.commit()
    conn.close()
    return {"confirmed": confirmed, "skipped_duplicates": skipped_duplicates, "missing": missing}


def discard_draft_findings(draft_ids: list[int], discarded_by: str = "auditor",
                           reason: str = "") -> int:
    """Mark selected draft findings as discarded."""
    init_audit_db()
    conn = _connect()
    before = conn.total_changes
    conn.executemany(
        """UPDATE draft_audit_findings
           SET draft_status='Discarded', discarded_at=CURRENT_TIMESTAMP,
               discarded_by=?, discard_reason=?
           WHERE id=? AND draft_status='Draft'""",
        [(discarded_by, reason, int(draft_id)) for draft_id in draft_ids],
    )
    changed = conn.total_changes - before
    conn.commit()
    conn.close()
    return changed


def load_findings(period: str = None, risk_bands: list = None, area: str = None,
                  company_code: str = None, status: str = None) -> pd.DataFrame:
    """Load confirmed findings from SQLite with optional filters."""
    init_audit_db()
    conn = _connect()
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
    """Update confirmed finding status with full workflow history."""
    init_audit_db()
    conn = _connect()

    old = conn.execute("SELECT status FROM audit_findings WHERE id=?", (finding_id,)).fetchone()
    old_status = old[0] if old else "Open"

    conn.execute(
        "UPDATE audit_findings SET status=? WHERE id=?",
        (new_status, finding_id),
    )

    if new_status in ["Closed", "Verified"]:
        conn.execute(
            """UPDATE audit_findings
               SET closed_at = CURRENT_TIMESTAMP,
                   days_to_close = CAST((julianday('now') - julianday(opened_at)) AS INTEGER)
               WHERE id=?""",
            (finding_id,)
        )

    conn.execute(
        """INSERT INTO workflow_history (finding_id, old_status, new_status, changed_by, comment)
           VALUES (?,?,?,?,?)""",
        (finding_id, old_status, new_status, changed_by, comment),
    )

    if management_response or action_owner or due_date:
        conn.execute(
            """INSERT OR REPLACE INTO management_responses
               (finding_id, response, action_owner, due_date, updated_at)
               VALUES (?,?,?,?,CURRENT_TIMESTAMP)""",
            (finding_id, management_response, action_owner, due_date),
        )

    conn.commit()
    conn.close()


def get_workflow_history(finding_id: int) -> pd.DataFrame:
    """Get status change history for a confirmed finding."""
    init_audit_db()
    conn = _connect()
    df = pd.read_sql_query(
        "SELECT * FROM workflow_history WHERE finding_id=? ORDER BY changed_at DESC",
        conn, params=(finding_id,)
    )
    conn.close()
    return df


def get_sla_breaches() -> pd.DataFrame:
    """Return confirmed findings where SLA has passed and status is open."""
    init_audit_db()
    conn = _connect()
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
    init_audit_db()
    conn = _connect()
    conn.execute(
        "INSERT INTO audit_kpi (metric_name, metric_value, period) VALUES (?,?,?)",
        (metric_name, metric_value, period),
    )
    conn.commit()
    conn.close()


def get_kpis(metric_name: str = None, period: str = None) -> pd.DataFrame:
    """Load KPI records."""
    init_audit_db()
    conn = _connect()
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
    init_audit_db()
    conn = _connect()
    conn.execute(
        """INSERT INTO sampling_runs
           (run_name, population_size, sample_size, method, confidence_level, materiality_threshold)
           VALUES (?,?,?,?,?,?)""",
        (run_name, population_size, sample_size, method, confidence_level, materiality_threshold),
    )
    conn.commit()
    conn.close()
