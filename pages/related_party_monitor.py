import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import secrets

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.audit_page_helpers import render_engagement_selector, get_active_engagement_id, render_rag_report_section

PAGE_KEY = "rpm"
MODULE_NAME = "Related Party Monitor"

st.title("🔗 Related-Party Transactions Monitor")
render_engagement_selector(PAGE_KEY)
st.caption("Vendor Mgmt B.3–B.8 | SAP: FK03 | NetworkX graph analysis")

uploaded = st.file_uploader("Upload Vendor Master (CSV/Excel)", type=["csv", "xlsx"])

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    st.success(f"Loaded {len(df):,} vendors")

    with st.expander("🔧 Column Mapping"):
        pan_col = st.selectbox("PAN", ["None"] + list(df.columns), key=f"{PAGE_KEY}_pan")
        bank_col = st.selectbox("Bank Account", ["None"] + list(df.columns), key=f"{PAGE_KEY}_bank")
        addr_col = st.selectbox("Address", ["None"] + list(df.columns), key=f"{PAGE_KEY}_addr")
        name_col = st.selectbox("Vendor Name", df.columns, key=f"{PAGE_KEY}_name")
        rp_flag = st.selectbox("Related Party Flag", ["None"] + list(df.columns), key=f"{PAGE_KEY}_rp")
        amt_col = st.selectbox("Total Spend (optional)", ["None"] + list(df.columns), key=f"{PAGE_KEY}_amt")

    file_sig = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
    mapping_sig = hashlib.sha256(
        str({"pan_col": pan_col, "bank_col": bank_col, "addr_col": addr_col, "name_col": name_col, "rp_flag": rp_flag, "amt_col": amt_col}).encode("utf-8")
    ).hexdigest()[:12]
    analysis_token = f"{PAGE_KEY}-{file_sig}:{mapping_sig}"

    if st.button("▶️ Run Detection", type="primary", key=f"{PAGE_KEY}_run_btn"):
        st.session_state[f"{PAGE_KEY}_analysis_token"] = analysis_token

    if st.session_state.get(f"{PAGE_KEY}_analysis_token") != analysis_token:
        st.info("Map columns, then click **Run Detection**.")
        st.stop()

    df = df.rename(columns={name_col: "vendor_name"})
    if rp_flag != "None":
        df = df.rename(columns={rp_flag: "related_party"})
        df["related_party"] = pd.to_numeric(df["related_party"], errors="coerce").fillna(0).astype(int)
    else:
        df["related_party"] = 0

    period_str = datetime.utcnow().strftime("%Y-%m")
    dup_pan = pd.DataFrame()
    dup_bank = pd.DataFrame()
    dup_addr = pd.DataFrame()

    if pan_col != "None":
        dup_pan = df[df.duplicated(pan_col, keep=False)].copy()
        st.subheader("🚨 Exception table — duplicate PAN (Vendor Mgmt B.3)")
        if not dup_pan.empty:
            st.warning(f"**{len(dup_pan)}** vendor row(s) share a PAN with another.")
            st.dataframe(dup_pan.head(200), use_container_width=True)
        else:
            st.success("No duplicate PAN patterns.")

    if bank_col != "None":
        dup_bank = df[df.duplicated(bank_col, keep=False)].copy()
        st.subheader("🚨 Exception table — duplicate bank account (Vendor Mgmt B.3)")
        if not dup_bank.empty:
            st.warning(f"**{len(dup_bank)}** vendor row(s) share a bank account.")
            st.dataframe(dup_bank.head(200), use_container_width=True)
        else:
            st.success("No duplicate bank account patterns.")

    if addr_col != "None":
        dup_addr = df[df.duplicated(addr_col, keep=False)].copy()
        st.subheader("🚨 Exception table — duplicate address (Vendor Mgmt B.3)")
        if not dup_addr.empty:
            st.warning(f"**{len(dup_addr)}** vendor row(s) share an address.")
            st.dataframe(dup_addr.head(200), use_container_width=True)
        else:
            st.success("No duplicate address patterns.")

    conc_pct = None
    conc_rows = pd.DataFrame()
    if amt_col != "None":
        df["_spend"] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
        total = float(df["_spend"].sum())
        rp_total = float(df[df["related_party"] == 1]["_spend"].sum())
        conc_pct = (rp_total / total * 100) if total else 0.0
        st.metric("Related-Party % of Total Procurement", f"{conc_pct:.1f}%")
        st.subheader("🚨 Exception table — related-party concentration (Companies Act Sec 188)")
        if conc_pct > 10:
            st.warning(f"Related-party concentration **>{10}%** ({conc_pct:.1f}%) — Board approval / Sec 188 review.")
            conc_rows = pd.DataFrame([{"vendor_name": "Aggregate — Related-party spend share", "_spend": rp_total, "conc_pct": conc_pct}])
        else:
            st.success("Related-party spend share within **10%** threshold (informational).")

    try:
        import networkx as nx

        G = nx.Graph()
        for _, row in df.iterrows():
            G.add_node(row["vendor_name"], related=row.get("related_party", 0))
        if pan_col != "None":
            for pan, group in df.groupby(pan_col):
                names = group["vendor_name"].tolist()
                for i in range(len(names)):
                    for j in range(i + 1, len(names)):
                        G.add_edge(names[i], names[j], reason="Same PAN")
        st.metric("Graph Nodes", G.number_of_nodes())
        st.metric("Graph Edges (shared attributes)", G.number_of_edges())
    except Exception as e:
        st.info(f"NetworkX graph skipped: {e}")

    init_audit_db()
    run_id = f"{analysis_token}:v2"
    frames = []

    def _append_staging(tmp: pd.DataFrame, *, checklist_ref: str, risk_band: str, finding_fn, kind: str, entity_col: str = "vendor_name"):
        if tmp is None or tmp.empty:
            return
        out = tmp.head(500).copy()
        out["area"] = "Related Party"
        out["checklist_ref"] = checklist_ref
        out["vendor_name"] = out[entity_col].map(lambda x: str(x).strip() if pd.notna(x) else "")
        if "_spend" in out.columns:
            out["amount_at_risk"] = pd.to_numeric(out["_spend"], errors="coerce").fillna(0).abs().astype(float)
        elif amt_col != "None" and amt_col in out.columns:
            out["amount_at_risk"] = pd.to_numeric(out[amt_col], errors="coerce").fillna(0).abs().astype(float)
        else:
            out["amount_at_risk"] = 0.0
        out["risk_band"] = risk_band
        out["finding_date"] = datetime.utcnow().strftime("%Y-%m-%d")
        out["period"] = period_str
        out["source_row_ref"] = [f"{PAGE_KEY}-{kind}-{secrets.token_hex(8)}" for _ in range(len(out))]
        out["finding"] = out.apply(finding_fn, axis=1)
        frames.append(
            out[["area", "checklist_ref", "finding", "amount_at_risk", "vendor_name", "risk_band", "finding_date", "period", "source_row_ref"]]
        )

    if not dup_pan.empty:

        def _f_pan(r):
            return f"Duplicate PAN — possible common control / shell linkage (B.3), vendor **{r.get('vendor_name','')}**, PAN {r.get(pan_col,'')}"

        if amt_col != "None":
            dup_pan = dup_pan.copy()
            dup_pan["_spend"] = pd.to_numeric(dup_pan[amt_col], errors="coerce").fillna(0)
        _append_staging(dup_pan, checklist_ref="Vendor Mgmt B.3", risk_band="HIGH", finding_fn=_f_pan, kind="dup-pan")

    if not dup_bank.empty:

        def _f_bank(r):
            return f"Duplicate bank account — potential nominee / funnel account (B.3), vendor **{r.get('vendor_name','')}**"

        if amt_col != "None":
            dup_bank = dup_bank.copy()
            dup_bank["_spend"] = pd.to_numeric(dup_bank[amt_col], errors="coerce").fillna(0)
        _append_staging(dup_bank, checklist_ref="Vendor Mgmt B.3", risk_band="HIGH", finding_fn=_f_bank, kind="dup-bank")

    if not dup_addr.empty:

        def _f_addr(r):
            return f"Duplicate address — potential common premises / related grouping (B.3), vendor **{r.get('vendor_name','')}**"

        if amt_col != "None":
            dup_addr = dup_addr.copy()
            dup_addr["_spend"] = pd.to_numeric(dup_addr[amt_col], errors="coerce").fillna(0)
        _append_staging(dup_addr, checklist_ref="Vendor Mgmt B.3", risk_band="MEDIUM", finding_fn=_f_addr, kind="dup-addr")

    if conc_pct is not None and conc_pct > 10:

        def _f_conc(_r):
            return (
                f"Related-party procurement concentration **{conc_pct:.1f}%** of total spend — "
                "Companies Act **Sec 188** / Board approval and disclosure review required."
            )

        _append_staging(conc_rows, checklist_ref="Companies Act Sec 188", risk_band="CRITICAL", finding_fn=_f_conc, kind="conc", entity_col="vendor_name")

    staging_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    rag_parts = [x for x in [dup_pan, dup_bank, dup_addr] if x is not None and not x.empty]
    if rag_parts:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.concat(rag_parts, ignore_index=True).drop_duplicates()
    elif amt_col != "None" and not df.empty:
        st.session_state[f"{PAGE_KEY}_rag_df"] = df.head(500)
    else:
        st.session_state[f"{PAGE_KEY}_rag_df"] = pd.DataFrame()

    if not staging_df.empty and st.session_state.get(f"{PAGE_KEY}_draft_run_id") != run_id:
        staged = stage_findings(
            staging_df,
            module_name=MODULE_NAME,
            run_id=run_id,
            period=period_str,
            source_file_name=getattr(uploaded, "name", "manual"),
            engagement_id=get_active_engagement_id(PAGE_KEY),
        )
        st.session_state[f"{PAGE_KEY}_draft_run_id"] = run_id
        st.info(
            f"📋 **{staged} exception(s) staged for your review** (of **{len(staging_df)}** detected). "
            "Nothing has been added to the official audit trail until you confirm below. "
            "**Audit Report Centre / Audit Committee Pack** only include findings after you confirm them."
        )
        if staged < len(staging_df):
            st.warning(f"**{len(staging_df) - staged}** row(s) skipped — duplicate draft/confirmed finding (dedupe).")
    elif not staging_df.empty:
        st.caption(f"📋 Exceptions already staged (run: `{run_id}`). Review below.")
    else:
        st.info("No related-party linkage exceptions to stage.")

try:
    flagged_rag_df = st.session_state.get(f"{PAGE_KEY}_rag_df")
    if flagged_rag_df is not None and not flagged_rag_df.empty:
        render_rag_report_section("rpm", flagged_df=flagged_rag_df, module_name=MODULE_NAME)
    elif uploaded:
        st.caption("ℹ️ No flagged data for RAG report.")
except Exception as _e:
    st.caption(f"RAG report unavailable: {_e}")

current_run_id = st.session_state.get(f"{PAGE_KEY}_draft_run_id")
if current_run_id:
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption("Use the Select column in the table to confirm/discard. No separate selector is required.")

    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name=MODULE_NAME,
        status="Draft",
        engagement_id=get_active_engagement_id(PAGE_KEY),
    )
    if drafts.empty:
        st.info("No draft exceptions pending for the current run.")
    else:
        select_all = st.checkbox("Select all draft exceptions", value=False, key=f"{PAGE_KEY}_select_all_drafts")
        st.caption(f"**{len(drafts)} draft exception(s)** pending review.")
        review_df = drafts[["id", "area", "vendor_name", "finding", "amount_at_risk", "risk_band"]].copy()
        review_df.insert(0, "select", select_all)

        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "area": st.column_config.TextColumn("Area", disabled=True),
                "vendor_name": st.column_config.TextColumn("Vendor / Entity", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn("Risk Band", options=["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
            },
            key=f"{PAGE_KEY}_draft_editor_inline_select",
        )

        selected_ids = edited.loc[edited["select"] == True, "id"].astype(int).tolist()
        confirmed_by = st.text_input("Confirmed / Reviewed by (auditor name)", value="Auditor", key=f"{PAGE_KEY}_confirmed_by")

        c_confirm, c_discard = st.columns(2)
        with c_confirm:
            if st.button(
                "Confirm Selected to Official Audit Trail",
                type="primary",
                use_container_width=True,
                key=f"{PAGE_KEY}_confirm_btn",
            ):
                if not selected_ids:
                    st.warning("Select at least one exception in the table.")
                else:
                    edited_vals = {
                        int(row["id"]): {
                            "finding": row.get("finding", ""),
                            "amount_at_risk": row.get("amount_at_risk", 0),
                            "risk_band": row.get("risk_band", "MEDIUM"),
                        }
                        for _, row in edited.iterrows()
                    }
                    n = confirm_draft_findings(
                        selected_ids,
                        confirmed_by=confirmed_by.strip() or "Auditor",
                        edited_values=edited_vals,
                    )
                    st.success(f"**{n} finding(s) confirmed** and added to the official audit trail.")
                    st.rerun()

        with c_discard:
            discard_reason = st.text_input("Discard reason (optional)", key=f"{PAGE_KEY}_discard_reason")
            if st.button("Discard Selected (False Positives)", use_container_width=True, key=f"{PAGE_KEY}_discard_btn"):
                if not selected_ids:
                    st.warning("Select at least one exception in the table.")
                else:
                    n = discard_draft_findings(
                        selected_ids,
                        discarded_by=confirmed_by.strip() or "Auditor",
                        reason=discard_reason or "False positive — auditor review",
                    )
                    st.info(f"**{n} exception(s) discarded.** They will not appear in reports.")
                    st.rerun()

        csv_draft = drafts.to_csv(index=False).encode()
        st.download_button(
            "Export Draft Exceptions as CSV",
            csv_draft,
            "draft_exceptions_related_party_monitor.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )
