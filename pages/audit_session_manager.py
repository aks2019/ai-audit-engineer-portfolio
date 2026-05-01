import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.audit_db import (
    confirm_draft_findings,
    discard_draft_findings,
    init_audit_db,
    load_draft_findings,
)

st.set_page_config(page_title="Audit Session Manager", layout="wide")
st.title("Audit Session Manager")
st.caption("Engagement maintenance, draft finding review, confirmation, archive, and restore")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "audit.db"
init_audit_db()


def get_current_engagements():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """
        SELECT period, run_id, COUNT(*) as confirmed_findings_count,
               MAX(finding_date) as last_activity,
               GROUP_CONCAT(DISTINCT area) as areas
        FROM audit_findings
        GROUP BY period, run_id
        ORDER BY period DESC, run_id DESC
        """,
        conn,
    )
    conn.close()
    return df


def list_backups():
    backups = list(DATA_DIR.glob("audit_backup_*.db"))
    data = []
    for backup in sorted(backups, reverse=True):
        size = backup.stat().st_size / (1024 * 1024)
        timestamp = backup.stem.replace("audit_backup_", "")
        data.append({"filename": backup.name, "timestamp": timestamp, "size_mb": round(size, 2)})
    return pd.DataFrame(data)


def restore_backup(backup_path: str):
    backup_file = DATA_DIR / backup_path
    if not backup_file.exists():
        st.error("Backup not found")
        return False
    if DB_PATH.exists():
        shutil.copy(DB_PATH, DATA_DIR / f"audit_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy(backup_file, DB_PATH)
    return True


def _selected_ids(edited_df: pd.DataFrame) -> list[int]:
    if edited_df.empty or "select" not in edited_df.columns:
        return []
    return edited_df.loc[edited_df["select"] == True, "id"].astype(int).tolist()


tab1, tab2, tab3, tab4 = st.tabs([
    "Draft Finding Review",
    "Current Engagements",
    "Backup & Restore",
    "Maintenance",
])

with tab1:
    st.subheader("Draft Findings Awaiting Auditor Confirmation")
    st.info("Generated exceptions are draft records only. Formal reports use confirmed audit_findings after you confirm selected drafts.")

    drafts = load_draft_findings(status="Draft")
    if drafts.empty:
        st.success("No draft findings are pending review.")
    else:
        modules = ["All"] + sorted(drafts["module"].dropna().unique().tolist())
        selected_module = st.selectbox("Filter by module", modules)
        review_df = drafts.copy()
        if selected_module != "All":
            review_df = review_df[review_df["module"] == selected_module]

        display_cols = [
            "id", "module", "area", "risk_band", "proposed_finding",
            "amount_at_risk", "reference_name", "checklist_ref", "period",
            "assigned_to", "sla_deadline", "ai_explanation", "policy_citations",
            "source_file_name", "source_row_ref", "generated_at",
        ]
        review_df = review_df[[c for c in display_cols if c in review_df.columns]].copy()
        review_df.insert(0, "select", False)

        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "id": st.column_config.NumberColumn("Draft ID", disabled=True),
                "proposed_finding": st.column_config.TextColumn("Finding text"),
                "risk_band": st.column_config.SelectboxColumn(
                    "Risk band", options=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                ),
            },
        )

        selected_ids = _selected_ids(edited)
        c1, c2, c3 = st.columns(3)
        reviewer = st.text_input("Confirmed / discarded by", value="audit_admin")

        with c1:
            if st.button("Confirm Selected Findings", type="primary", use_container_width=True, disabled=not selected_ids):
                editable_cols = ["proposed_finding", "risk_band", "amount_at_risk", "checklist_ref", "assigned_to", "sla_deadline"]
                edits = {}
                for _, row in edited[edited["id"].isin(selected_ids)].iterrows():
                    edits[int(row["id"])] = {col: row[col] for col in editable_cols if col in edited.columns}
                result = confirm_draft_findings(selected_ids, confirmed_by=reviewer, edited_values=edits)
                st.success(
                    f"Confirmed {result['confirmed']} finding(s). "
                    f"Skipped duplicates: {result['skipped_duplicates']}."
                )
                st.rerun()

        with c2:
            reason = st.text_input("Discard reason", value="Not an audit finding")
            if st.button("Discard Selected Drafts", use_container_width=True, disabled=not selected_ids):
                count = discard_draft_findings(selected_ids, discarded_by=reviewer, reason=reason)
                st.warning(f"Discarded {count} draft finding(s).")
                st.rerun()

        with c3:
            csv = review_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export Draft Exceptions",
                csv,
                f"draft_findings_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv",
                use_container_width=True,
            )

with tab2:
    st.subheader("Confirmed Engagement Activity in audit.db")
    current = get_current_engagements()
    if current.empty:
        st.info("No confirmed findings yet in the current database.")
    else:
        st.dataframe(current, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Saved Audit Engagements")
    backups = list_backups()

    if not backups.empty:
        st.dataframe(backups, use_container_width=True, hide_index=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_backup = st.selectbox(
                "Select backup to restore",
                backups["filename"].tolist(),
                format_func=lambda x: x.replace("audit_backup_", ""),
            )
        with col2:
            if st.button("Restore this Engagement", type="primary", use_container_width=True):
                if restore_backup(selected_backup):
                    st.success(f"Restored {selected_backup} as active database")
                    st.rerun()
    else:
        st.info("No backups yet. Start a new engagement to create one.")

    st.divider()
    st.subheader("Start New Audit Engagement")
    engagement_name = st.text_input("Engagement Name", value=f"FY{datetime.now().year}_Q{((datetime.now().month-1)//3)+1}_Audit")
    company_code = st.text_input("Company Code", value="HQ")
    period = st.text_input("Period (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))

    if st.button("Start New Engagement & Archive Current", type="primary", use_container_width=True):
        backup_name = f"audit_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if DB_PATH.exists():
            shutil.copy(DB_PATH, DATA_DIR / backup_name)
            st.success(f"Current data archived as {backup_name}")

        conn = sqlite3.connect(DB_PATH)
        for table in ["audit_findings", "draft_audit_findings", "workflow_history", "management_responses", "audit_kpi", "sampling_runs"]:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()

        st.success(f"{engagement_name} started for {company_code} / {period}")
        st.rerun()

with tab4:
    st.subheader("Database Maintenance")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Vacuum Database", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("VACUUM")
            conn.close()
            st.success("Database vacuumed")
    with col_b:
        conn = sqlite3.connect(DB_PATH)
        confirmed = pd.read_sql("SELECT * FROM audit_findings", conn)
        conn.close()
        csv = confirmed.to_csv(index=False).encode("utf-8")
        st.download_button("Export Confirmed Findings", csv, "confirmed_audit_findings.csv", "text/csv", use_container_width=True)
    with col_c:
        if st.button("Delete All Backups", use_container_width=True):
            for backup in DATA_DIR.glob("audit_backup_*.db"):
                backup.unlink()
            st.warning("All backups deleted")

st.caption("Formal reports read confirmed audit_findings only. Draft exceptions require auditor confirmation first.")
