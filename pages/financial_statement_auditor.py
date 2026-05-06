import streamlit as st
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from checks.financial_statement import generate_fs_review_report

try:
    from utils.rag_engine import generate_financial_audit_report
except ImportError:
    generate_financial_audit_report = None

st.set_page_config(page_title="Financial Statement Auditor", page_icon="📊", layout="wide")

st.title("📊 SAP Financial Statement Auditor")
st.caption("Deterministic Checks First → AI Explanation | Ind AS/AS/CARO/Schedule III Compliant")

# ── SESSION STATE ────────────────────────────────────────────────
if "fs_deterministic_done" not in st.session_state:
    st.session_state["fs_deterministic_done"] = False
if "fs_deterministic_report" not in st.session_state:
    st.session_state["fs_deterministic_report"] = {}
if "fs_ai_explanation" not in st.session_state:
    st.session_state["fs_ai_explanation"] = None

# ── STEP 1: UPLOAD ───────────────────────────────────────────────
st.subheader("📤 Step 1: Upload Trial Balance & Supporting Data")

uploaded_tb = st.file_uploader(
    "Upload Current SAP Trial Balance (CSV/Excel)",
    type=["csv", "xlsx"],
    key="fs_tb_upload"
)

# Optional supporting data
with st.expander("🔧 Optional Supporting Data (for deeper checks)", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded_inventory = st.file_uploader("Inventory Register (CSV/Excel)", type=["csv", "xlsx"], key="fs_inv")
    with col2:
        uploaded_ppe = st.file_uploader("PPE Register (CSV/Excel)", type=["csv", "xlsx"], key="fs_ppe")
    with col3:
        uploaded_cl = st.file_uploader("Contingent Liabilities (CSV/Excel)", type=["csv", "xlsx"], key="fs_cl")

    entity_turnover = st.number_input("Entity Turnover (₹)", value=0.0, step=1000000.0, format="%.0f")
    entity_listed = st.checkbox("Listed Company?", value=False)
    entity_net_worth = st.number_input("Net Worth (₹)", value=0.0, step=1000000.0, format="%.0f")

entity_info = {
    "turnover": entity_turnover,
    "listed": entity_listed,
    "net_worth": entity_net_worth,
}

# ── STEP 2: RUN DETERMINISTIC CHECKS ─────────────────────────────
if uploaded_tb:
    try:
        tb_df = pd.read_csv(uploaded_tb) if uploaded_tb.name.endswith(".csv") else pd.read_excel(uploaded_tb)
        st.success(f"✅ Trial Balance loaded: {len(tb_df)} rows, {len(tb_df.columns)} columns")

        with st.expander("🔍 Preview TB"):
            st.dataframe(tb_df.head(20), use_container_width=True)

        # Optional dataframes
        inventory_df = pd.DataFrame()
        ppe_df = pd.DataFrame()
        cl_df = pd.DataFrame()

        if uploaded_inventory:
            inventory_df = pd.read_csv(uploaded_inventory) if uploaded_inventory.name.endswith(".csv") else pd.read_excel(uploaded_inventory)
            st.success(f"📦 Inventory: {len(inventory_df)} rows")
        if uploaded_ppe:
            ppe_df = pd.read_csv(uploaded_ppe) if uploaded_ppe.name.endswith(".csv") else pd.read_excel(uploaded_ppe)
            st.success(f"🏭 PPE: {len(ppe_df)} rows")
        if uploaded_cl:
            cl_df = pd.read_csv(uploaded_cl) if uploaded_cl.name.endswith(".csv") else pd.read_excel(uploaded_cl)
            st.success(f"⚠️ Contingent Liabilities: {len(cl_df)} rows")

        st.divider()
        st.subheader("🚀 Step 2: Run Deterministic Financial Statement Review")

        col_run, col_clear = st.columns([1, 3])
        with col_run:
            run_det = st.button("🔍 Run Deterministic FS Review", type="primary", use_container_width=True)
        with col_clear:
            if st.button("🗑️ Clear Results"):
                st.session_state["fs_deterministic_done"] = False
                st.session_state["fs_deterministic_report"] = {}
                st.session_state["fs_ai_explanation"] = None
                st.rerun()

        if run_det:
            with st.spinner("Running deterministic checks (Ind AS/AS/CARO/Schedule III)..."):
                report = generate_fs_review_report(
                    tb_df,
                    entity_info=entity_info,
                    inventory_df=inventory_df if not inventory_df.empty else None,
                    ppe_df=ppe_df if not ppe_df.empty else None,
                    cl_df=cl_df if not cl_df.empty else None,
                )
                st.session_state["fs_deterministic_report"] = report
                st.session_state["fs_deterministic_done"] = True
                st.session_state["fs_ai_explanation"] = None

        # ── STEP 3: DISPLAY DETERMINISTIC RESULTS ─────────────────
        if st.session_state["fs_deterministic_done"]:
            report = st.session_state["fs_deterministic_report"]

            st.divider()
            st.subheader("📊 Deterministic Review Results")

            # Executive Summary
            summary = report.get("summary", {})
            sm1, sm2, sm3, sm4 = st.columns(4)
            sm1.metric("Total Issues", summary.get("total_issues", 0))
            sm2.metric("🔴 Critical", summary.get("critical_issues", 0), delta_color="inverse")
            sm3.metric("🟠 Medium", summary.get("medium_issues", 0))
            sm4.metric("🟡 Low", summary.get("low_issues", 0))

            st.caption(f"Report generated: {report.get('report_date', '')}")

            # Per-check results
            checks = report.get("checks", {})
            for check_name, result in checks.items():
                issues = result.get("issues", [])
                status_icon = "🔴" if any(i.get("severity") == "HIGH" for i in issues) else "🟠" if any(i.get("severity") == "MEDIUM" for i in issues) else "🟢"

                with st.expander(f"{status_icon} {check_name.replace('_', ' ').title()} ({len(issues)} issues)", expanded=(len(issues) > 0)):
                    if check_name == "schedule_iii_mapping":
                        st.markdown(f"**Mapping Confidence:** {result.get('mapping_confidence', 'N/A')}%")
                        if result.get("unmatched_accounts"):
                            st.markdown("**Unmatched Accounts:**")
                            st.dataframe(pd.DataFrame(result["unmatched_accounts"]), use_container_width=True)

                    elif check_name == "ind_as_applicability":
                        st.markdown(f"**Framework:** {result.get('framework', 'N/A')}")
                        st.markdown(f"**Applies Ind AS:** {result.get('applies_ind_as', 'N/A')}")
                        st.markdown(f"**Applicable From:** {result.get('applicable_from', 'N/A')}")

                    elif check_name == "related_party":
                        st.markdown(f"**Disclosure Required:** {result.get('disclosure_required', 'N/A')}")
                        st.markdown(f"**RP Transactions:** {len(result.get('rp_transactions', []))}")

                    elif check_name == "ppe_ageing":
                        st.markdown(f"**Total Assets:** {result.get('total_assets', 'N/A')}")
                        st.markdown(f"**Critical Issues:** {result.get('critical_count', 0)}")

                    elif check_name == "revenue_recognition":
                        st.markdown(f"**Total Revenue:** {result.get('total_revenue', 0):,.0f}")
                        st.markdown(f"**Compliance:** {result.get('compliance_status', 'N/A')}")

                    elif check_name == "inventory_nrv":
                        st.markdown(f"**Total Items:** {result.get('total_items', 'N/A')}")
                        st.markdown(f"**Slow-Moving:** {result.get('slow_moving_count', 0)} | **NRV Loss:** {result.get('nrv_loss_count', 0)}")

                    elif check_name == "borrowings_msme_statutory":
                        st.markdown(f"**MSME Issues:** {len(result.get('msme_issues', []))}")
                        st.markdown(f"**Statutory Issues:** {len(result.get('statutory_issues', []))}")

                    elif check_name == "contingent_liabilities":
                        st.markdown(f"**Total CL:** {result.get('total_contingent_liabilities', 0):,.0f}")
                        st.markdown(f"**Provision Required:** {result.get('provision_required', 0)}")

                    # Issues table
                    if issues:
                        st.markdown(f"**🚨 Issues ({len(issues)}):**")
                        issues_df = pd.DataFrame(issues)

                        def highlight_severity(val):
                            if val == "HIGH":
                                return "background-color: #ff4b4b; color: white"
                            elif val == "MEDIUM":
                                return "background-color: #ffa726; color: white"
                            elif val == "LOW":
                                return "background-color: #66bb6a; color: white"
                            return ""

                        styled = issues_df.style.applymap(highlight_severity, subset=["severity"]) if "severity" in issues_df.columns else issues_df
                        st.dataframe(styled, use_container_width=True)
                    else:
                        st.success("No issues detected.")

            # Download deterministic report
            st.divider()
            csv_det = pd.DataFrame([{
                "check": k,
                "issues": len(v.get("issues", [])),
            } for k, v in checks.items()])
            st.download_button(
                "📥 Download Deterministic Report Summary",
                csv_det.to_csv(index=False).encode(),
                f"fs_deterministic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )

            # ── STEP 4: AI EXPLANATION (Optional, after deterministic) ───
            st.divider()
            st.subheader("🤖 Step 3: AI Explanation (Optional)")
            st.caption("Run AI only after reviewing deterministic results. AI provides narrative explanation, not primary findings.")

            if not generate_financial_audit_report:
                st.warning("🚫 AI Explanation module unavailable (DB connection not configured). Install `langchain-postgres` or configure DB to enable.")
            else:
                if st.button("✨ Generate AI Explanation", type="secondary", use_container_width=True):
                    with st.spinner("AI analyzing deterministic findings for narrative explanation..."):
                        try:
                            deterministic_summary = {
                                "total_issues": summary.get("total_issues", 0),
                                "critical": summary.get("critical_issues", 0),
                                "medium": summary.get("medium_issues", 0),
                                "low": summary.get("low_issues", 0),
                                "checks": {k: len(v.get("issues", [])) for k, v in checks.items()},
                            }
                            ai_result = generate_financial_audit_report({"deterministic_summary": deterministic_summary})
                            st.session_state["fs_ai_explanation"] = ai_result
                        except Exception as e:
                            st.error(f"AI Explanation failed: {e}")

                if st.session_state["fs_ai_explanation"]:
                    ai_result = st.session_state["fs_ai_explanation"]
                    st.markdown("### AI Narrative Explanation")
                    st.markdown(ai_result.get("audit_summary", "No summary generated."))
                    with st.expander("📚 Sources & Citations"):
                        for cit in ai_result.get("citations", []):
                            st.markdown(f"- {cit}")

    except Exception as e:
        st.error(f"Error processing file: {e}")

else:
    st.info("👆 Upload a Trial Balance to begin the deterministic financial statement review.")

st.divider()
st.caption("**Financial Statement Auditor** | Deterministic Checks First → AI Explanation | Ind AS/AS/CARO/Schedule III")