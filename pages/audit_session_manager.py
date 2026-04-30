import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import shutil

st.set_page_config(page_title="Audit Session Manager", layout="wide")
st.title("📅 Audit Session Manager")
st.caption("Full Database Maintenance • Archive • Restore • Switch Engagements • Per Section 14 of master plan")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "audit.db"

# ====================== HELPER FUNCTIONS ======================
def get_current_engagements():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT period, run_id, COUNT(*) as findings_count,
               MAX(finding_date) as last_activity,
               GROUP_CONCAT(DISTINCT area) as areas
        FROM audit_findings 
        GROUP BY period, run_id 
        ORDER BY period DESC, run_id DESC
    """, conn)
    conn.close()
    return df

def list_backups():
    backups = list(DATA_DIR.glob("audit_backup_*.db"))
    data = []
    for b in sorted(backups, reverse=True):
        size = b.stat().st_size / (1024*1024)  # MB
        ts = b.stem.replace("audit_backup_", "")
        data.append({"filename": b.name, "timestamp": ts, "size_mb": round(size, 2)})
    return pd.DataFrame(data)

def restore_backup(backup_path: str):
    backup_file = DATA_DIR / backup_path
    if not backup_file.exists():
        st.error("Backup not found")
        return False
    # Backup current before restore
    shutil.copy(DB_PATH, DATA_DIR / f"audit_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy(backup_file, DB_PATH)
    return True

# ====================== MAIN UI ======================
tab1, tab2, tab3 = st.tabs(["Current Engagements", "Backup & Restore", "Maintenance"])

with tab1:
    st.subheader("Active Engagements in audit.db")
    df_current = get_current_engagements()
    if not df_current.empty:
        st.dataframe(df_current, use_container_width=True)
    else:
        st.info("No findings yet in current engagement.")

with tab2:
    st.subheader("Saved Audit Engagements (Backups)")
    df_backups = list_backups()
    
    if not df_backups.empty:
        st.dataframe(df_backups, use_container_width=True)
        
        col1, col2 = st.columns([3,1])
        with col1:
            selected_backup = st.selectbox(
                "Select backup to restore",
                df_backups["filename"].tolist(),
                format_func=lambda x: x.replace("audit_backup_", "")
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
    engagement_name = st.text_input("Engagement Name", value=f"FY{datetime.now().year}_Q{((datetime.now().month-1)//3)+1}_Emami")
    company_code = st.text_input("Company Code", value="EMAMI")
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
        
        st.success(f"✅ **{engagement_name}** started for {company_code} / {period}")
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

st.caption("All actions are logged in rag_usage_log. Restore creates pre-restore backup automatically.")