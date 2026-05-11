import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import load_findings, init_audit_db, update_status
from utils.compliance_loader import load_compliance_calendar
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id

st.title("🏛️ Audit Committee Report Pack")
st.caption("Companies Act Section 177 + SEBI LODR Regulation 18 | Board-ready export")

PAGE_KEY = "audit_committee_pack"
render_engagement_selector(PAGE_KEY)
active_engagement_id = get_active_engagement_id(PAGE_KEY)
if active_engagement_id is None:
    st.info("Create an audit engagement first (Audit Session Manager), then come back to generate the committee pack.")
    st.stop()

init_audit_db()
cal = load_compliance_calendar()

# Section 1 — ATR
st.subheader("Section 1 — Action Taken Report (ATR)")
prev = load_findings(engagement_id=active_engagement_id)
atr = prev[prev["status"].isin(["Management Response","Closed"])] if not prev.empty else pd.DataFrame()
if not atr.empty:
    st.dataframe(atr[["area","finding","status"]], use_container_width=True, hide_index=True)
else:
    st.info("No previous period findings with management response yet.")

# Section 2 — New Critical Observations
st.subheader("Section 2 — New Critical Observations")
critical = load_findings(engagement_id=active_engagement_id, risk_bands=["CRITICAL","HIGH"])
if not critical.empty:
    critical = critical.sort_values("amount_at_risk", ascending=False)
    st.dataframe(critical[["area","checklist_ref","finding","amount_at_risk","risk_band"]], use_container_width=True, hide_index=True)
else:
    st.info("No HIGH/CRITICAL findings in current period.")

# Section 3 — Management Response
st.subheader("Section 3 — Management Response (Editable)")
if not critical.empty:
    for idx, row in critical.head(10).iterrows():
        with st.container():
            st.markdown(f"**#{row['id']}** — {row['finding']}")
            resp = st.text_area(f"Response #{row['id']}", key=f"resp_{row['id']}")
            owner = st.text_input("Responsible Person", key=f"owner_{row['id']}")
            due = st.date_input("Action Due Date", key=f"due_{row['id']}")
            if st.button("Save Response", key=f"save_{row['id']}"):
                update_status(row['id'], "Management Response", resp)
                st.success("Saved to SQLite for next period ATR")

# Section 4 — Board Escalation
st.subheader("Section 4 — Board Escalation Items")
if not prev.empty:
    prev["finding_date"] = pd.to_datetime(prev["finding_date"], errors="coerce")
    open_prev = prev[(prev["status"]=="Open") & (prev["risk_band"].isin(["CRITICAL","HIGH"]))]
    # Simplified: flag if same finding text appears >1 period
    rec = open_prev.groupby("finding").size().reset_index(name="periods")
    board = rec[rec["periods"] >= 2]
    if not board.empty:
        st.error(f"{len(board)} items escalated to Board (chronic + open)")
        st.dataframe(board, use_container_width=True, hide_index=True)
    else:
        st.success("No Board escalation required.")

# Export PDF
if st.button("📥 Export Board PDF"):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = letter[1]-50
    c.drawString(50,y,"Audit Committee Pack"); y-=30
    c.drawString(50,y,f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"); y-=30
    if not critical.empty:
        for _, row in critical.head(20).iterrows():
            if y<50: c.showPage(); y=letter[1]-50
            c.drawString(50,y,f"#{row['id']} {row['area']}: {row['finding'][:80]}"); y-=15
    c.save()
    st.download_button("Download Board PDF", buf.getvalue(), "audit_committee_pack.pdf", "application/pdf")
