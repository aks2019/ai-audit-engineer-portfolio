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

def list_backups():
    backups = list(DATA_DIR.glob("audit_backup_*.db"))
    data = []
    for b in sorted(backups, reverse=True):
        size = b.stat().st_size / (1024*1024)  # MB
        ts = b.stem.replace("audit_backup_", "")
        # Extract engagement name from backup database
        engagement_name = "Unknown"
        try:
            conn = sqlite3.connect(b)
            cursor = conn.cursor()
            # Get the most recent active engagement name from this backup
            result = cursor.execute(
                "SELECT name FROM audit_engagements WHERE status != 'Archived' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if result:
                engagement_name = result[0]
            else:
                # Try any engagement if none are active
                result = cursor.execute(
                    "SELECT name FROM audit_engagements ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if result:
                    engagement_name = result[0]
            conn.close()
        except Exception:
            engagement_name = "Unknown"
        data.append({"filename": b.name, "timestamp": ts, "engagement_name": engagement_name, "size_mb": round(size, 2)})
    return pd.DataFrame(data)

def restore_backup(backup_path: str):
    backup_file = DATA_DIR / backup_path
    if not backup_file.exists():
        st.error("Backup not found")
        return False
    # Backup current before restore
    shutil.copy(DB_PATH, DATA_DIR / f"audit_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy(backup_file, DB_PATH)
    latest = get_latest_engagement()
    if latest is not None:
        set_active_engagement(int(latest["id"]), str(latest["name"]))
    return True

# ====================== MAIN UI ======================
tab1, tab2, tab3, tab4 = st.tabs(["Current Engagements", "Backup & Restore", "Maintenance", "System Setup"])

with tab1:
    st.subheader("Engagement Management")
    df_current = get_current_engagements()
    if not df_current.empty:
        active_id = st.session_state.get(ACTIVE_ENGAGEMENT_ID_KEY)
        ids = df_current["id"].tolist()
        default_index = ids.index(active_id) if active_id in ids else 0
        selected_id = st.selectbox(
            "Active Engagement for Detection Pages",
            ids,
            index=default_index,
            format_func=lambda i: df_current.loc[df_current["id"] == i, "name"].iloc[0],
        )
        selected_name = df_current.loc[df_current["id"] == selected_id, "name"].iloc[0]
        set_active_engagement(selected_id, selected_name)
        st.success(f"Active engagement: {selected_name} (ID {selected_id})")
        st.dataframe(df_current, use_container_width=True, hide_index=True)
    else:
        st.info("No audit engagements yet. Start one from Backup & Restore.")

with tab2:
    st.subheader("Saved Audit Engagements (Backups)")
    df_backups = list_backups()
    
    if not df_backups.empty:
        st.dataframe(df_backups, use_container_width=True, column_config={
            "filename": st.column_config.TextColumn("Backup File"),
            "engagement_name": st.column_config.TextColumn("Engagement Name"),
            "timestamp": st.column_config.TextColumn("Timestamp"),
            "size_mb": st.column_config.NumberColumn("Size (MB)", format="%.2f")
        })
        
        col1, col2 = st.columns([3,1])
        with col1:
            # Create a mapping for display - show engagement name + timestamp
            backup_options = df_backups["filename"].tolist()
            backup_display = {row["filename"]: f"{row['engagement_name']} ({row['timestamp']})" for _, row in df_backups.iterrows()}
            selected_backup = st.selectbox(
                "Select backup to restore",
                backup_options,
                format_func=lambda x: backup_display.get(x, x)
            )
        with col2:
            if st.button("🔄 Restore this Engagement", type="primary", use_container_width=True):
                if restore_backup(selected_backup):
                    st.success(f"✅ Restored {selected_backup} as active engagement")
                    st.rerun()
    else:
        st.info("No backups yet. Start a new engagement to create one.")

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
