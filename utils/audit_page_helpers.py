"""Reusable RAG Audit Report & Follow-up Chat helpers for all Detection pages.
Mirrors the anomaly_detector.py pattern.
"""
import streamlit as st
from datetime import datetime
from io import BytesIO


def _generate_report_pdf(report_text: str, title: str = "AI Audit Report") -> BytesIO:
    """Generate a PDF buffer from report text."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = letter[1] - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    y -= 40
    for line in report_text.split("\n"):
        if y < 50:
            c.showPage()
            y = letter[1] - 50
        c.drawString(50, y, line[:90])
        y -= 15
    c.save()
    buffer.seek(0)
    return buffer


def render_rag_report_section(
    page_key: str,
    flagged_df=None,
    flagged_list=None,
    module_name: str = "Detection",
    contract_text: str = None,
    vendor_name: str = None,
):
    """Render Generate RAG Audit Report button + report display + follow-up chat.

    Usage (at end of any detection page):
        from utils.audit_page_helpers import render_rag_report_section
        render_rag_report_section("brs", flagged_df=unmatched_bank, module_name="BRS Reconciliation")
    """
    if flagged_df is not None and not flagged_df.empty:
        flagged_data = flagged_df.to_dict("records")
    elif flagged_list is not None:
        flagged_data = flagged_list
    else:
        flagged_data = []

    report_key = f"{page_key}_audit_report"
    messages_key = f"{page_key}_report_messages"
    log_hash_key = f"{page_key}_report_log_hash"
    citations_key = f"{page_key}_report_citations_count"
    generated_key = f"{page_key}_report_generated_at"

    st.divider()
    st.subheader("🤖 AI Audit Report")

    if st.button(
        "🔍 Generate RAG Audit Report",
        type="primary",
        use_container_width=True,
        key=f"{page_key}_rag_btn"
    ):
        if not flagged_data:
            st.error("No flagged data available for RAG report.")
        else:
            with st.spinner("Calling Policy RAG Bot..."):
                try:
                    from utils.rag_engine import generate_rag_audit_report
                    result = generate_rag_audit_report(
                        flagged_transactions=flagged_data,
                        contract_text=contract_text,
                        vendor_name=vendor_name
                    )
                    st.session_state[report_key] = result["audit_summary"]
                    st.session_state[messages_key] = [
                        {"role": "assistant", "content": result["audit_summary"]}
                    ]
                    st.session_state[log_hash_key] = result.get("log_hash", "N/A")
                    st.session_state[citations_key] = len(result.get("citations", []))
                    st.session_state[generated_key] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                except Exception as e:
                    st.error(f"RAG report generation failed: {e}")

    # --- Render report from session_state ---
    if report_key in st.session_state and st.session_state[report_key]:
        st.success("✅ Audit report generated via Policy RAG Bot")
        st.markdown("### Audit-Ready Executive Summary")
        st.markdown(st.session_state[report_key])
        st.caption(
            f"Audit log hash: `{st.session_state.get(log_hash_key, 'N/A')}` | "
            f"Citations: {st.session_state.get(citations_key, 0)} | "
            f"Generated: {st.session_state.get(generated_key, '')}"
        )
        pdf_buf = _generate_report_pdf(st.session_state[report_key], title=f"AI {module_name} Audit Report")
        st.download_button(
            "📥 Download Audit Report as PDF",
            pdf_buf,
            "audit_report.pdf",
            "application/pdf",
            key=f"{page_key}_pdf_dl"
        )

    # --- Follow-up chat ---
    if messages_key in st.session_state and st.session_state[messages_key]:
        with st.expander("🔄 Follow-up Query with Policy RAG Bot (refine this audit report)", expanded=False):
            for msg in st.session_state[messages_key]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            chat_key = f"{page_key}_chat_input"
            if prompt := st.chat_input("Ask follow-up question about this audit report...", key=chat_key):
                st.session_state[messages_key].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("Querying Policy RAG Bot (free-form)..."):
                        try:
                            from utils.rag_engine import get_free_form_chain, build_combined_context
                            context, _ = build_combined_context(
                                prompt, pgvector_top_k=0, standards_top_k=10,
                                flagged_data=flagged_data
                            )
                            rich_context = f"""{context}

Initial Audit Report:
{st.session_state[report_key]}

Flagged Data Summary:
{str(flagged_data[:10]) if flagged_data else 'No data'}"""
                            chain = get_free_form_chain()
                            response = chain.invoke({"context": rich_context, "question": prompt})
                            st.markdown(response.content)
                            st.session_state[messages_key].append(
                                {"role": "assistant", "content": response.content}
                            )
                        except Exception as e:
                            st.error(f"Follow-up failed: {e}")


def render_draft_review_section(page_key: str, module_name: str):
    """Render the 'Review & Confirm Findings' draft workflow.

    Usage (at end of any detection page):
        from utils.audit_page_helpers import render_draft_review_section
        render_draft_review_section("brs", "BRS Reconciliation")
    """
    import pandas as pd
    from utils.audit_db import load_draft_findings, confirm_draft_findings, discard_draft_findings

    st.divider()
    st.subheader("✅ Review & Confirm Findings")
    st.caption(
        "Exceptions are **staged as drafts** — nothing enters the official audit trail "
        "until you confirm here. Edit finding text or risk band before confirming. "
        "Discard false positives without them appearing in any report."
    )

    current_run_id = st.session_state.get(f"{page_key}_draft_run_id")
    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name=module_name,
        status="Draft"
    )

    if drafts.empty:
        already_confirmed = load_draft_findings(
            run_id=current_run_id,
            module_name=module_name,
            status="Confirmed"
        )
        if not already_confirmed.empty:
            st.success(
                f"All {len(already_confirmed)} exception(s) for this run have already "
                "been confirmed and added to the audit trail."
            )
        else:
            st.info("No staged exceptions found. Upload a file and run detection first.")
    else:
        st.caption(
            f"**{len(drafts)} draft exception(s)** pending review  |  "
            f"run `{current_run_id}`"
        )

        review_df = drafts[["id", "vendor_name", "finding", "amount_at_risk", "risk_band"]].copy()
        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "vendor_name": st.column_config.TextColumn("Vendor", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk ₹", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn(
                    "Risk Band", options=["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                ),
            },
            key=f"{page_key}_draft_editor"
        )

        all_ids = drafts["id"].tolist()
        id_labels = {
            row["id"]: f"ID {row['id']} — {row['vendor_name']} (₹{row['amount_at_risk']:,.0f}, {row['risk_band']})"
            for _, row in drafts.iterrows()
        }
        selected_ids = st.multiselect(
            "Select exceptions to act on",
            options=all_ids,
            default=all_ids,
            format_func=lambda i: id_labels.get(i, str(i))
        )

        confirmed_by = st.text_input(
            "Confirmed / Reviewed by (auditor name)",
            value="Auditor",
            key=f"{page_key}_confirmed_by"
        )

        c_confirm, c_discard = st.columns(2)

        with c_confirm:
            if st.button(
                "✅ Confirm Selected → Official Audit Trail",
                type="primary", use_container_width=True, key=f"{page_key}_confirm_btn"
            ):
                if not selected_ids:
                    st.warning("Select at least one exception to confirm.")
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
                        edited_values=edited_vals
                    )
                    st.success(
                        f"✅ **{n} finding(s) confirmed** and added to the official "
                        "audit trail. They will now appear in all reports."
                    )
                    st.rerun()

        with c_discard:
            discard_reason = st.text_input(
                "Discard reason (optional)", key=f"{page_key}_discard_reason"
            )
            if st.button(
                "🗑️ Discard Selected (False Positives)",
                use_container_width=True, key=f"{page_key}_discard_btn"
            ):
                if not selected_ids:
                    st.warning("Select at least one exception to discard.")
                else:
                    n = discard_draft_findings(
                        selected_ids,
                        discarded_by=confirmed_by.strip() or "Auditor",
                        reason=discard_reason or "False positive — auditor review"
                    )
                    st.info(f"🗑️ **{n} exception(s) discarded.** They will not appear in reports.")
                    st.rerun()

        csv_draft = drafts.to_csv(index=False).encode()
        st.download_button(
            "📥 Export Draft Exceptions as CSV",
            csv_draft, "draft_exceptions.csv", "text/csv",
            key=f"{page_key}_export_drafts"
        )
