import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engagements import create_engagement, list_engagements, update_engagement
from utils.audit_db import init_audit_db
from utils.audit_page_helpers import ACTIVE_ENGAGEMENT_ID_KEY, ACTIVE_ENGAGEMENT_NAME_KEY

st.set_page_config(page_title="Audit Session Manager", layout="wide")
st.title("📅 Audit Session Manager")
st.caption("Full Database Maintenance • Archive • Restore • Switch Engagements • Per Section 14 of master plan")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "audit.db"
init_audit_db()
SNAPSHOT_PATTERNS = ("audit_backup_*.db", "audit_pre_restore_*.db")

# ====================== HELPER FUNCTIONS ======================
def get_current_engagements():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT e.id, e.name, e.status, e.start_date, e.end_date, e.created_at,
               COUNT(f.id) as findings_count,
               SUM(CASE WHEN f.status = 'Open' THEN 1 ELSE 0 END) as open_findings,
               MAX(f.opened_at) as last_activity
        FROM audit_engagements e
        LEFT JOIN audit_findings f ON f.engagement_id = e.id
        GROUP BY e.id, e.name, e.status, e.start_date, e.end_date, e.created_at
        ORDER BY e.created_at DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["findings_count"] = df["findings_count"].fillna(0).astype(int)
        df["open_findings"] = df["open_findings"].fillna(0).astype(int)
    archive_counts = get_archive_counts_by_name()
    if not df.empty:
        df["archive_findings_count"] = df["name"].map(lambda name: archive_counts.get(name, {}).get("findings_count", 0))
        df["archive_open_findings"] = df["name"].map(lambda name: archive_counts.get(name, {}).get("open_findings", 0))
        df["findings_count"] = df.apply(
            lambda row: row["archive_findings_count"] if row["findings_count"] == 0 and row["archive_findings_count"] else row["findings_count"],
            axis=1,
        )
        df["open_findings"] = df.apply(
            lambda row: row["archive_open_findings"] if row["open_findings"] == 0 and row["archive_open_findings"] else row["open_findings"],
            axis=1,
        )
        existing_names = set(df["name"].tolist())
    else:
        existing_names = set()

    missing_archive_rows = []
    for name, archive in archive_counts.items():
        if name in existing_names:
            continue
        missing_archive_rows.append({
            "id": None,
            "name": name,
            "status": "Snapshot only",
            "start_date": archive.get("start_date"),
            "end_date": archive.get("end_date"),
            "created_at": archive.get("created_at"),
            "findings_count": archive.get("findings_count", 0),
            "open_findings": archive.get("open_findings", 0),
            "last_activity": archive.get("last_activity"),
            "archive_findings_count": archive.get("findings_count", 0),
            "archive_open_findings": archive.get("open_findings", 0),
        })
    if missing_archive_rows:
        df = pd.concat([df, pd.DataFrame(missing_archive_rows)], ignore_index=True)
    return df

def set_active_engagement(engagement_id: int, engagement_name: str):
    st.session_state[ACTIVE_ENGAGEMENT_ID_KEY] = int(engagement_id)
    st.session_state[ACTIVE_ENGAGEMENT_NAME_KEY] = engagement_name

def get_latest_engagement():
    engs = list_engagements()
    if not engs.empty and "status" in engs.columns:
        open_engs = engs[engs["status"].fillna("") != "Archived"]
        if not open_engs.empty:
            engs = open_engs
    if engs.empty:
        return None
    return engs.iloc[0]

def iter_snapshot_files():
    files = []
    for pattern in SNAPSHOT_PATTERNS:
        files.extend(DATA_DIR.glob(pattern))
    return sorted(set(files), reverse=True)

def get_table_columns(conn, table_name: str) -> list:
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    except Exception:
        return []

def snapshot_engagement_rows(snapshot_path: Path) -> list:
    rows = []
    try:
        conn = sqlite3.connect(snapshot_path)
        conn.row_factory = sqlite3.Row
        eng_cols = get_table_columns(conn, "audit_engagements")
        if not eng_cols:
            conn.close()
            return rows

        findings_cols = get_table_columns(conn, "audit_findings")
        count_by_eng = {}
        if "engagement_id" in findings_cols:
            for row in conn.execute("""
                SELECT engagement_id, COUNT(*) as findings_count,
                       SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_findings,
                       MAX(opened_at) as last_activity
                FROM audit_findings
                GROUP BY engagement_id
            """):
                count_by_eng[row["engagement_id"]] = {
                    "findings_count": row["findings_count"] or 0,
                    "open_findings": row["open_findings"] or 0,
                    "last_activity": row["last_activity"],
                }
        else:
            total = conn.execute("SELECT COUNT(*) FROM audit_findings").fetchone()[0] if findings_cols else 0
            count_by_eng[None] = {"findings_count": total, "open_findings": total, "last_activity": None}

        engagements = conn.execute("""
            SELECT id, name, status, start_date, end_date, created_at
            FROM audit_engagements
            ORDER BY created_at DESC
        """).fetchall()
        conn.close()

        for eng in engagements:
            counts = count_by_eng.get(eng["id"], {"findings_count": 0, "open_findings": 0, "last_activity": None})
            if counts["findings_count"] == 0 and eng["status"] == "Archived":
                continue
            rows.append({
                "snapshot_key": f"{snapshot_path.name}|{eng['id']}",
                "filename": snapshot_path.name,
                "snapshot_type": "Pre-restore" if snapshot_path.name.startswith("audit_pre_restore_") else "Backup",
                "timestamp": snapshot_path.stem.replace("audit_backup_", "").replace("audit_pre_restore_", ""),
                "source_engagement_id": eng["id"],
                "engagement_name": eng["name"],
                "status": eng["status"],
                "start_date": eng["start_date"],
                "end_date": eng["end_date"],
                "created_at": eng["created_at"],
                "findings_count": counts["findings_count"],
                "open_findings": counts["open_findings"],
                "last_activity": counts["last_activity"],
                "size_mb": round(snapshot_path.stat().st_size / (1024 * 1024), 2),
            })
    except Exception:
        return rows
    return rows

def get_archive_counts_by_name() -> dict:
    archive_counts = {}
    for snapshot in iter_snapshot_files():
        for row in snapshot_engagement_rows(snapshot):
            if row["findings_count"] <= 0:
                continue
            name = row["engagement_name"]
            existing = archive_counts.get(name)
            if not existing or row["timestamp"] > existing["timestamp"]:
                archive_counts[name] = row
    return archive_counts

def list_backups():
    data = []
    for snapshot in iter_snapshot_files():
        data.extend(snapshot_engagement_rows(snapshot))
    return pd.DataFrame(data)

def copy_table_from_snapshot(source_conn, target_conn, table_name: str, target_engagement_id: int,
                             source_engagement_id: int = None):
    source_cols = get_table_columns(source_conn, table_name)
    target_cols = get_table_columns(target_conn, table_name)
    cols = [col for col in source_cols if col in target_cols]
    if not cols:
        return

    target_conn.execute(f"DELETE FROM {table_name}")
    q = f"SELECT {', '.join(cols)} FROM {table_name}"
    params = []
    if "engagement_id" in cols and source_engagement_id is not None:
        q += " WHERE engagement_id = ?"
        params.append(source_engagement_id)

    rows = source_conn.execute(q, params).fetchall()
    if not rows:
        return

    placeholders = ",".join(["?"] * len(cols))
    insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
    for row in rows:
        values = list(row)
        if "engagement_id" in cols:
            values[cols.index("engagement_id")] = target_engagement_id
        target_conn.execute(insert_sql, values)

def ensure_engagement_from_snapshot(source_conn, target_conn, source_engagement_id: int) -> tuple:
    source_conn.row_factory = sqlite3.Row
    source = source_conn.execute("""
        SELECT name, description, start_date, end_date, created_at
        FROM audit_engagements
        WHERE id = ?
    """, (source_engagement_id,)).fetchone()
    if not source:
        raise ValueError("Selected engagement was not found inside the snapshot.")

    existing = target_conn.execute(
        "SELECT id FROM audit_engagements WHERE name = ? ORDER BY created_at DESC LIMIT 1",
        (source["name"],),
    ).fetchone()
    if existing:
        target_id = existing[0]
        target_conn.execute("""
            UPDATE audit_engagements
            SET description = ?, start_date = ?, end_date = ?, status = 'Ongoing'
            WHERE id = ?
        """, (source["description"], source["start_date"], source["end_date"], target_id))
    else:
        target_conn.execute("""
            INSERT INTO audit_engagements (name, description, start_date, end_date, status, created_at)
            VALUES (?, ?, ?, ?, 'Ongoing', ?)
        """, (source["name"], source["description"], source["start_date"], source["end_date"], source["created_at"]))
        target_id = target_conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return target_id, source["name"]

def restore_backup(snapshot_key: str):
    backup_name, source_id_text = snapshot_key.split("|", 1)
    backup_file = DATA_DIR / backup_name
    source_engagement_id = int(source_id_text)
    if not backup_file.exists():
        st.error("Snapshot not found")
        return False

    pre_restore = DATA_DIR / f"audit_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy(DB_PATH, pre_restore)

    source_conn = sqlite3.connect(backup_file)
    target_conn = sqlite3.connect(DB_PATH)
    try:
        target_conn.execute("BEGIN")
        target_id, target_name = ensure_engagement_from_snapshot(source_conn, target_conn, source_engagement_id)
        target_conn.execute("UPDATE audit_engagements SET status = 'Archived' WHERE id != ?", (target_id,))

        copy_table_from_snapshot(source_conn, target_conn, "audit_findings", target_id, source_engagement_id)
        copy_table_from_snapshot(source_conn, target_conn, "draft_audit_findings", target_id, source_engagement_id)
        copy_table_from_snapshot(source_conn, target_conn, "workflow_history", target_id)
        copy_table_from_snapshot(source_conn, target_conn, "management_responses", target_id)
        copy_table_from_snapshot(source_conn, target_conn, "audit_kpi", target_id, source_engagement_id)
        copy_table_from_snapshot(source_conn, target_conn, "sampling_runs", target_id, source_engagement_id)

        target_conn.commit()
        set_active_engagement(target_id, target_name)
    except Exception as exc:
        target_conn.rollback()
        st.error(f"Restore failed: {exc}")
        return False
    finally:
        source_conn.close()
        target_conn.close()

    return True

# ====================== MAIN UI ======================
tab1, tab2, tab3, tab4 = st.tabs(["Current Engagements", "Backup & Restore", "Maintenance", "System Setup"])

with tab1:
    st.subheader("Engagement Management")
    df_current = get_current_engagements()
    if not df_current.empty:
        active_id = st.session_state.get(ACTIVE_ENGAGEMENT_ID_KEY)
        selectable = df_current[df_current["id"].notna()].copy()
        ids = selectable["id"].astype(int).tolist()
        default_index = ids.index(active_id) if active_id in ids else 0
        if ids:
            selected_id = st.selectbox(
                "Active Engagement for Detection Pages",
                ids,
                index=default_index,
                format_func=lambda i: selectable.loc[selectable["id"] == i, "name"].iloc[0],
            )
            selected_name = selectable.loc[selectable["id"] == selected_id, "name"].iloc[0]
            set_active_engagement(selected_id, selected_name)
            st.success(f"Active engagement: {selected_name} (ID {selected_id})")
        else:
            st.info("Only archived snapshots are available. Restore one before selecting an active engagement.")
        st.dataframe(df_current, use_container_width=True, hide_index=True)
    else:
        st.info("No audit engagements yet. Start one from Backup & Restore.")

with tab2:
    st.subheader("Saved Audit Engagement Snapshots")
    df_backups = list_backups()
    
    if not df_backups.empty:
        st.dataframe(df_backups, use_container_width=True, column_config={
            "snapshot_key": None,
            "filename": st.column_config.TextColumn("Snapshot File"),
            "snapshot_type": st.column_config.TextColumn("Type"),
            "engagement_name": st.column_config.TextColumn("Engagement Name"),
            "timestamp": st.column_config.TextColumn("Timestamp"),
            "findings_count": st.column_config.NumberColumn("Findings"),
            "open_findings": st.column_config.NumberColumn("Open"),
            "size_mb": st.column_config.NumberColumn("Size (MB)", format="%.2f")
        })
        
        col1, col2 = st.columns([3,1])
        with col1:
            backup_options = df_backups["snapshot_key"].tolist()
            backup_display = {
                row["snapshot_key"]: (
                    f"{row['engagement_name']} | {row['snapshot_type']} | "
                    f"{row['timestamp']} | {row['findings_count']} finding(s)"
                )
                for _, row in df_backups.iterrows()
            }
            selected_backup = st.selectbox(
                "Select snapshot to restore",
                backup_options,
                format_func=lambda x: backup_display.get(x, x)
            )
        with col2:
            if st.button("Restore this Engagement", type="primary", use_container_width=True):
                if restore_backup(selected_backup):
                    st.success("Snapshot restored as active engagement")
                    st.rerun()
    else:
        st.info("No snapshots yet. Start a new engagement or restore an older pre-restore snapshot.")

    # Start New Engagement
    st.divider()
    st.subheader("🚀 Start New Audit Engagement")
    engagement_name = st.text_input("Engagement Name", value=f"FY{datetime.now().year}_Q{((datetime.now().month-1)//3)+1}_Sarvagya")
    company_code = st.text_input("Company Code", value="Sarvagya")
    period = st.text_input("Period (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))

    if st.button("Start New Engagement & Archive Current", type="primary", use_container_width=True):
        # Archive current
        backup_name = f"audit_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(DB_PATH, DATA_DIR / backup_name)
        st.success(f"✅ Current data archived as {backup_name}")
        
        # Clear current findings (keep schema)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM audit_findings")
        conn.execute("DELETE FROM workflow_history")
        conn.execute("DELETE FROM management_responses")
        conn.execute("DELETE FROM audit_kpi")
        conn.execute("DELETE FROM sampling_runs")
        conn.commit()
        conn.close()

        current_active_id = st.session_state.get(ACTIVE_ENGAGEMENT_ID_KEY)
        if current_active_id:
            update_engagement(current_active_id, status="Archived")

        start_date = period + "-01" if len(period) == 7 else None
        description = f"Company Code: {company_code} | Period: {period}"
        new_engagement_id = create_engagement(
            engagement_name,
            description=description,
            start_date=start_date,
            status="Ongoing",
        )
        set_active_engagement(new_engagement_id, engagement_name)
        
        st.success(f"Engagement **{engagement_name}** started for {company_code} / {period} and set as active engagement ID {new_engagement_id}")
        st.rerun()

with tab3:
    st.subheader("Database Maintenance")
    colA, colB, colC = st.columns(3)
    with colA:
        if st.button("🧹 Vacuum Database"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("VACUUM")
            conn.close()
            st.success("Database vacuumed")
    with colB:
        if st.button("📤 Export All Findings (CSV)"):
            conn = sqlite3.connect(DB_PATH)
            df_all = pd.read_sql("SELECT * FROM audit_findings", conn)
            conn.close()
            csv = df_all.to_csv(index=False).encode()
            st.download_button("Download full_audit_findings.csv", csv, "full_audit_findings.csv", "text/csv")
    with colC:
        if st.button("🗑️ Delete All Backups"):
            for f in DATA_DIR.glob("audit_backup_*.db"):
                f.unlink()
            st.success("All backups deleted")

with tab4:
    st.subheader("System Setup & Sample Data")

    # ── DB Status ──────────────────────────────────────────────────
    st.markdown("#### Database Status")
    eng_count = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        table_count  = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        eng_count    = conn.execute("SELECT COUNT(*) FROM audit_engagements").fetchone()[0]
        std_count    = conn.execute("SELECT COUNT(*) FROM audit_standards").fetchone()[0]
        entity_count = conn.execute("SELECT COUNT(*) FROM audit_entities").fetchone()[0]
        conn.close()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tables in DB", table_count)
        c2.metric("Engagements", eng_count)
        c3.metric("Standards", std_count)
        c4.metric("Entities", entity_count)
    except Exception as e:
        st.error(f"Cannot read database: {e}")

    st.divider()

    # ── Seed Sample Data ───────────────────────────────────────────
    st.markdown("#### Seed Sample Data")
    st.info(
        "Creates a default engagement (**Annual Statutory Audit 2024-25**), "
        "two entities (HQ Kolkata + Guwahati Plant), and baseline standards. "
        "Run once on a fresh install or after archiving a prior engagement."
    )

    if eng_count > 0:
        st.warning(
            f"**{eng_count} engagement(s) already exist.** "
            "Running seed again will add duplicate records. "
            "Archive the current engagement first, or check the box below to proceed anyway."
        )
        allow_seed = st.checkbox("I understand — seed sample data anyway")
    else:
        allow_seed = True

    if st.button("Seed Sample Data", type="primary", disabled=not allow_seed, use_container_width=True):
        try:
            from scripts.seed_audit_data import seed_database
            seed_database()
            st.success(
                "Sample data seeded successfully. "
                "Go to **P14: Audit Planning Engine** to view the default engagement."
            )
            st.rerun()
        except Exception as e:
            st.error(f"Seeding failed: {e}")

    st.divider()

    # ── Standards Registry Browser ─────────────────────────────────
    st.markdown("#### Standards Registry Browser")
    st.caption("Browse all audit standards loaded in the database — no code access needed.")

    try:
        conn = sqlite3.connect(DB_PATH)
        df_std = pd.read_sql_query(
            "SELECT id, family, reference, description, applicability, source_url "
            "FROM audit_standards ORDER BY family, reference",
            conn
        )
        conn.close()

        if df_std.empty:
            st.info("No standards in database yet. Click 'Sync Standards' below to load all standards.")
        else:
            families = ["All Families"] + sorted(df_std["family"].unique().tolist())
            col_f, col_s = st.columns([2, 3])
            with col_f:
                sel_family = st.selectbox("Filter by Family", families, key="std_family_filter")
            with col_s:
                search_txt = st.text_input("Search description / reference", placeholder="e.g. related party, revenue, fraud", key="std_search")

            view = df_std.copy()
            if sel_family != "All Families":
                view = view[view["family"] == sel_family]
            if search_txt.strip():
                mask = (
                    view["description"].str.contains(search_txt, case=False, na=False) |
                    view["reference"].str.contains(search_txt, case=False, na=False) |
                    view["applicability"].str.contains(search_txt, case=False, na=False)
                )
                view = view[mask]

            st.caption(f"Showing {len(view)} of {len(df_std)} standards")
            st.dataframe(
                view[["family", "reference", "description", "applicability", "source_url"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "source_url": st.column_config.LinkColumn("Source", display_text="Open")
                }
            )
    except Exception as e:
        st.error(f"Cannot load standards: {e}")

    st.divider()

    # ── Sync / Add Missing Standards ──────────────────────────────
    st.markdown("#### Sync Standards Registry")
    st.info("Adds any new standards from the master list that are not yet in the database. Safe to run at any time — existing standards are never duplicated or overwritten.")

    if st.button("Sync All Standards", use_container_width=True):
        try:
            from core.standards_registry import seed_official_standards
            added = seed_official_standards()
            if added == 0:
                st.success("Registry is already up to date — no new standards to add.")
            else:
                st.success(f"Sync complete: **{added} new standard(s)** added to the registry.")
            st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {e}")

    st.divider()

    # ── Add / Update Standard (Option A) ──────────────────────────
    st.markdown("#### Add or Update a Standard")
    st.caption("Add a new standard not yet in the registry, or correct an existing entry.")

    with st.form("add_standard_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)
        with fc1:
            new_family = st.selectbox(
                "Standard Family *",
                ["Companies Act", "CARO", "Ind AS", "AS", "CAS", "SIA", "SA",
                 "GST", "TDS", "SEBI", "FEMA", "Labour Law", "Other"],
                key="new_std_family"
            )
        with fc2:
            new_ref = st.text_input("Reference (e.g. Section 148, Ind AS 116) *", key="new_std_ref")

        new_desc = st.text_input("Description / Title *", key="new_std_desc")
        new_appl = st.text_input("Applicability (who this applies to)", key="new_std_appl")
        new_clause = st.text_area("Clause Text / Key Requirements", height=100, key="new_std_clause")
        new_url = st.text_input("Source URL (official government / ICAI / ICMAI link)", key="new_std_url")

        update_if_exists = st.checkbox(
            "Update existing record if this family + reference already exists",
            key="new_std_overwrite"
        )
        submitted = st.form_submit_button("Save Standard", type="primary", use_container_width=True)

    if submitted:
        if not new_family or not new_ref.strip() or not new_desc.strip():
            st.error("Family, Reference, and Description are required.")
        else:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                exists = cursor.execute(
                    "SELECT id FROM audit_standards WHERE family = ? AND reference = ?",
                    (new_family, new_ref.strip())
                ).fetchone()

                if exists and not update_if_exists:
                    st.warning(
                        f"**{new_family} — {new_ref}** already exists (ID {exists[0]}). "
                        "Tick 'Update existing record' to overwrite it."
                    )
                elif exists and update_if_exists:
                    cursor.execute("""
                        UPDATE audit_standards
                        SET description=?, applicability=?, clause_text=?, source_url=?
                        WHERE family=? AND reference=?
                    """, (new_desc.strip(), new_appl.strip(), new_clause.strip(),
                          new_url.strip(), new_family, new_ref.strip()))
                    conn.commit()
                    st.success(f"Updated: **{new_family} — {new_ref}**")
                else:
                    cursor.execute("""
                        INSERT INTO audit_standards (family, reference, description, applicability, clause_text, source_url)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (new_family, new_ref.strip(), new_desc.strip(), new_appl.strip(),
                          new_clause.strip(), new_url.strip()))
                    conn.commit()
                    st.success(f"Added: **{new_family} — {new_ref}**")
                conn.close()
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

st.caption("All actions are logged in rag_usage_log. Restore creates pre-restore backup automatically.")
