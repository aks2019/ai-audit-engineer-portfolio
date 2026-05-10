"""Write clean utils/audit_page_helpers.py with engagement selector added."""
import os

content = '''"""Reusable RAG Audit Report, Engagement Selector & Draft Review helpers for all Detection pages.
"""
import streamlit as st
from datetime import datetime
from io import BytesIO


def _generate_report_pdf(report_text, title="AI Audit Report"):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = letter[1] - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Generated: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    y -= 40
    for line in report_text.split(chr(10)):
        if y < 50:
            c.showPage()
            y = letter[1] - 50
        c.drawString(50, y, line[:90])
        y -= 15
    c.save()
    buffer.seek(0)
    return buffer


def render_engagement_selector(page_key):
    """Render engagement selector widget. Call near top of any detection page."""
    from core.engagements import list_engagements
    eng_key = page_key + "_engagement_id"
    eng_name_key = page_key + "_engagement_name"
    engs = list_engagements()
    if engs.empty:
        st.info("No audit engagements found. Create one in P14: Audit Planning Engine first.")
        st.session_state[eng_key] = None
        st.session_state[eng_name_key] = None
        return
    eng_options = {}
    for _, row in engs.iterrows():
        eng_options[row["id"]] = str(row["id"]) + ": " + row["name"] + " (" + row.get("status", "Planned") + ")"
    current_id = st.session_state.get(eng_key)
    ids_list = list(eng_options.keys())
    default_index = 0
    if current_id in ids_list:
        default_index = ids_list.index(current_id)
    selected_label = st.selectbox(
        "Link Findings to Engagement",
        options=list(eng_options.values()),
        index=default_index,
        key=page_key + "_eng_selector",
    )
    selected_id = int(selected_label.split(":")[0])
    if selected_id != current_id:
        st.session_state[eng_key] = selected_id
        st.session_state[eng_name_key] = eng_options[selected_id]
    st.caption(
        "Linked to **" + str(st.session_state.get(eng_name_key, eng_options[selected_id]))
        + "** | Findings tagged with engagement ID " + str(selected_id)
    )


def get_active_engagement_id(page_key):
    """Get the currently selected engagement ID from session state, or None."""
    return st.session_state.get(page_key + "_engagement_id")


def render_rag_report_section(page_key, flagged_df=None, flagged_list=None,
                               module_name="Detection", contract_text=None, vendor_name=None):
    """Render RAG Audit Report button + report display + follow-up chat."""
    if flagged_df is not None and not flagged_df.empty:
        flagged_data = flagged_df.to_dict("records")
    elif flagged_list is not None:
        flagged_data = flagged_list
    else:
        flagged_data = []
    report_key = page_key + "_audit_report"
    messages_key = page_key + "_report_messages"
    log_hash_key = page_key + "_report_log_hash"
    citations_key = page_key + "_report_citations_count"
    generated_key = page_key + "_report_generated_at"
    st.divider()
    st.subheader("AI Audit Report")
    if st.button("Generate RAG Audit Report", type="primary", use_container_width=True, key=page_key + "_rag_btn"):
        if not flagged_data:
            st.error("No flagged data available for RAG report.")
        else:
            with st.spinner("Calling Policy RAG Bot..."):
                try:
                    from utils.rag_engine import generate_rag_audit_report
                    result = generate_rag_audit_report(
                        flagged_transactions=flagged_data,
                        contract_text=contract_text,
                        vendor_name=vendor_name,
                    )
                    st.session_state[report_key] = result["audit_summary"]
                    st.session_state[messages_key] = [{"role": "assistant", "content": result["audit_summary"]}]
                    st.session_state[log_hash_key] = result.get("log_hash", "N/A")
                    st.session_state[citations_key] = len(result.get("citations", []))
                    st.session_state[generated_key] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception as e:
                    st.error("RAG report generation failed: " + str(e))
    if report_key in st.session_state and st.session_state[report_key]:
        st.success("Audit report generated via Policy RAG Bot")
        st.markdown("### Audit-Ready Executive Summary")
        st.markdown(st.session_state[report_key])
        st.caption(
            "Audit log hash: " + str(st.session_state.get(log_hash_key, "N/A"))
            + " | Citations: " + str(st.session_state.get(citations_key, 0))
            + " | Generated: " + str(st.session_state.get(generated_key, ""))
        )
        pdf_buf = _generate_report_pdf(st.session_state[report_key], title="AI " + module_name + " Audit Report")
        st.download_button("Download Audit Report as PDF", pdf_buf, "audit_report.pdf", "application/pdf", key=page_key + "_pdf_dl")
    if messages_key in st.session_state and st.session_state[messages_key]:
        with st.expander("Follow-up Query with Policy RAG Bot (refine this audit report)", expanded=False):
            for msg in st.session_state[messages_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            chat_key = page_key + "_chat_input"
            if prompt := st.chat_input("Ask follow-up question about this audit report...", key=chat_key):
                st.session_state[messages_key].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("Querying Policy RAG Bot (free-form)..."):
                        try:
                            from utils.rag_engine import get_free_form_chain, build_combined_context
                            context, _ = build_combined_context(
                                prompt, pgvector_top_k=0, standards_top_k=10, flagged_data=flagged_data
                            )
                            rich_context = (
                                context + chr(10) + chr(10)
                                + "Initial Audit Report:" + chr(10)
                                + st.session_state[report_key] + chr(10) + chr(10)
                                + "Flagged Data Summary:" + chr(10)
                                + (str(flagged_data[:10]) if flagged_data else "No data")
                            )
                            chain = get_free_form_chain()
                            response = chain.invoke({"context": rich_context, "question": prompt})
                            st.markdown(response.content)
                            st.session_state[messages_key].append({"role": "assistant", "content": response.content})
                        except Exception as e:
                            st.error("Follow-up failed: " + str(e))


def render_draft_review_section(page_key, module_name):
    """Render the Review & Confirm Findings draft workflow."""
    import pandas as pd
    from utils.audit_db import load_draft_findings, confirm_draft_findings, discard_draft_findings
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption("Exceptions are staged as drafts - nothing enters the official audit trail until you confirm here.")
    current_run_id = st.session_state.get(page_key + "_draft_run_id")
    drafts = load_draft_findings(run_id=current_run_id, module_name=module_name, status="Draft")
    if drafts.empty:
        already_confirmed = load_draft_findings(run_id=current_run_id, module_name=module_name, status="Confirmed")
        if not already_confirmed.empty:
            st.success("All " + str(len(already_confirmed)) + " exception(s) for this run have already been confirmed.")
        else:
            st.info("No staged exceptions found. Upload a file and run detection first.")
    else:
        st.caption("**" + str(len(drafts)) + " draft exception(s)** pending review  |  run " + str(current_run_id))
        review_df = drafts[["id", "vendor_name", "finding", "amount_at_risk", "risk_band"]].copy()
        edited = st.data_editor(
            review_df, use_container_width=True, hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "vendor_name": st.column_config.TextColumn("Vendor", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn("Risk Band", options=["CRITICAL", "HIGH", "MEDIUM", "LOW"]),
            },
            key=page_key + "_draft_editor",
        )
        all_ids = drafts["id"].tolist()
        id_labels = {row["id"]: "ID " + str(row["id"]) + " -- " + row["vendor_name"] for _, row in drafts.iterrows()}
        selected_ids = st.multiselect("Select exceptions to act on", options=all_ids, format_func=lambda i: id_labels.get(i, str(i)))
        confirmed_by = st.text_input("Confirmed / Reviewed by (auditor name)", value="Auditor", key=page_key + "_confirmed_by")
        c_confirm, c_discard = st.columns(2)
        with c_confirm:
            if st.button("Confirm Selected", type="primary", use_container_width=True, key=page_key + "_confirm_btn"):
                if not selected_ids:
                    st.warning("Select at least one exception to confirm.")
                else:
                    edited_vals = {int(row["id"]): {"finding": row.get("finding", ""), "amount_at_risk": row.get("amount_at_risk", 0), "risk_band": row.get("risk_band", "MEDIUM")} for _, row in edited.iterrows()}
                    n = confirm_draft_findings(selected_ids, confirmed_by=confirmed_by.strip() or "Auditor", edited_values=edited_vals)
                    st.success("**" + str(n) + " finding(s) confirmed** and added to the official audit trail.")
                    st.rerun()
        with c_discard:
            discard_reason = st.text_input("Discard reason (optional)", key=page_key + "_discard_reason")
            if st.button("Discard Selected", use_container_width=True, key=page_key + "_discard_btn"):
                if not selected_ids:
                    st.warning("Select at least one exception to discard.")
                else:
                    n = discard_draft_findings(selected_ids, discarded_by=confirmed_by.strip() or "Auditor", reason=discard_reason or "False positive - auditor review")
                    st.info("**" + str(n) + " exception(s) discarded.**")
                    st.rerun()
        csv_draft = drafts.to_csv(index=False).encode()
        st.download_button("Export Draft Exceptions as CSV", csv_draft, "draft_exceptions.csv", "text/csv", key=page_key + "_export_drafts")
'''

with open("utils/audit_page_helpers.py", "w", encoding="utf-8") as f:
    f.write(content)

import py_compile
py_compile.compile("utils/audit_page_helpers.py", doraise=True)
print("OK - file written and compiles cleanly")