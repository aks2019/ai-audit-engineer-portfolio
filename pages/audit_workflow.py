import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import init_audit_db, load_findings, update_status, get_workflow_history, get_sla_breaches

st.title("🔄 Audit Finding Workflow Engine")
st.caption("Status lifecycle: Open → In Progress → Management Response → Verified → Closed | SLA tracking")

init_audit_db()

# Filters
st.sidebar.subheader("🔍 Filters")
status_filter = st.sidebar.multiselect("Status", ["Open","In Progress","Management Response","Verified","Closed"], default=["Open","In Progress"])
area_filter = st.sidebar.text_input("Area (optional)")
assigned_filter = st.sidebar.text_input("Assigned To (optional)")

findings = load_findings(status=status_filter[0] if len(status_filter)==1 else None)
if not findings.empty and len(status_filter) > 1:
    findings = findings[findings["status"].isin(status_filter)]
if not findings.empty and area_filter:
    findings = findings[findings["area"].str.contains(area_filter, case=False, na=False)]
if not findings.empty and assigned_filter:
    findings = findings[findings["assigned_to"].str.contains(assigned_filter, case=False, na=False)]

# SLA Breaches alert
breaches = get_sla_breaches()
if not breaches.empty:
    st.error(f"⏰ {len(breaches)} findings have breached SLA deadline!")

if findings.empty:
    st.info("No findings match the selected filters.")
else:
    st.subheader(f"📋 Findings ({len(findings)})")
    for idx, row in findings.iterrows():
        with st.expander(f"#{row['id']} | {row['area']} | {row['risk_band']} | {row['status']}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Finding:** {row['finding']}")
            c2.markdown(f"**Amount at Risk:** ₹{row['amount_at_risk']:,.0f}")
            c3.markdown(f"**Checklist Ref:** {row['checklist_ref']}")

            # Workflow transition
            st.divider()
            new_status = st.selectbox("Transition to", ["Open","In Progress","Management Response","Verified","Closed"],
                                      index=["Open","In Progress","Management Response","Verified","Closed"].index(row["status"]),
                                      key=f"status_{row['id']}")
            changed_by = st.text_input("Changed By", value="Auditor", key=f"by_{row['id']}")
            comment = st.text_area("Comment", key=f"comment_{row['id']}")
            sla_days = st.number_input("SLA Days from today", min_value=1, max_value=90, value=15, key=f"sla_{row['id']}")
            assigned_to = st.text_input("Assign To", value=row.get("assigned_to",""), key=f"assign_{row['id']}")

            if st.button("Update Status", key=f"upd_{row['id']}"):
                sla_deadline = (datetime.today() + timedelta(days=int(sla_days))).strftime("%Y-%m-%d")
                update_status(row['id'], new_status, changed_by=changed_by, comment=comment)
                # Update SLA and assignee
                import sqlite3
                conn = sqlite3.connect("data/audit.db")
                conn.execute("UPDATE audit_findings SET sla_deadline=?, assigned_to=? WHERE id=?",
                             (sla_deadline, assigned_to, row['id']))
                conn.commit(); conn.close()
                st.success(f"Status updated to {new_status}")
                st.rerun()

            # Show workflow history
            hist = get_workflow_history(row['id'])
            if not hist.empty:
                st.caption("📜 Workflow History")
                st.dataframe(hist[["changed_at","old_status","new_status","changed_by","comment"]], use_container_width=True, hide_index=True)
