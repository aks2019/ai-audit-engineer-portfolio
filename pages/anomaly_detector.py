import streamlit as st
import pandas as pd
import plotly.express as px
from sklearn.ensemble import IsolationForest
import numpy as np
from datetime import datetime
import hashlib
import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from utils.redis_cache import save_session_to_redis, load_session_from_redis

# === FIX IMPORT PATH FOR UTILS FOLDER ===
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import generate_rag_audit_report, get_free_form_chain
from utils.redis_cache import save_session_to_redis, load_session_from_redis

# === SESSION STATE (all previous + persistent report) ===
if "messages" not in st.session_state:
    st.session_state.messages = load_session_from_redis("current_chat")
if "flagged_df" not in st.session_state:
    st.session_state.flagged_df = pd.DataFrame()
if "contract_text" not in st.session_state:
    st.session_state.contract_text = ""
if "contract_attached" not in st.session_state:
    st.session_state.contract_attached = False
if "contract_vendor" not in st.session_state:
    st.session_state.contract_vendor = ""
if "report_messages" not in st.session_state:
    st.session_state.report_messages = []
if "initial_audit_report" not in st.session_state:
    st.session_state.initial_audit_report = ""
if "report_log_hash" not in st.session_state:
    st.session_state.report_log_hash = ""
if "report_citations_count" not in st.session_state:
    st.session_state.report_citations_count = 0
if "report_generated_at" not in st.session_state:
    st.session_state.report_generated_at = ""


def _generate_report_pdf(report_text: str) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = letter[1] - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "AI Vendor Payment Anomaly Audit Report")
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

st.title("🚨 AI Vendor Payment Anomaly Detector")
st.markdown("**100% Population Testing • SAP FICO-MM + Dynamic Contract RAG via Policy Bot**")

uploaded_file = st.file_uploader(
    "Upload any vendor payments CSV/Excel (real SAP / Caseware IDEA export)",
    type=["csv", "xlsx"]
)

if uploaded_file:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success(f"✅ Loaded {len(df):,} transactions successfully!")

        with st.expander("🔧 Column Mapping", expanded=True):
            st.caption("Map your file's columns to the required audit roles. Required fields must be set before the model runs.")
            cm_c1, cm_c2 = st.columns(2)
            with cm_c1:
                amount_col = st.selectbox("Amount Column (required)", df.columns)
            with cm_c2:
                vendor_col = st.selectbox("Vendor Name Column (required)", df.columns)

            optional_cols = ["category", "plant_code", "related_party", "days_overdue"]
            mapping = {}
            opt_cols = st.columns(4)
            for i, col in enumerate(optional_cols):
                with opt_cols[i]:
                    mapping[col] = st.selectbox(
                        f"{col} (optional)",
                        ["None"] + list(df.columns),
                        index=0 if col not in df.columns else list(df.columns).index(col) + 1
                    )

        df = df.rename(columns={amount_col: "amount", vendor_col: "vendor_name"})

        for internal in optional_cols:
            mapped = mapping[internal]
            if mapped != "None":
                df[internal] = df[mapped]
            else:
                df[internal] = 0 if internal in ["related_party", "days_overdue"] else "Unknown"

        _SHAP_COLS = ["amount", "days_overdue", "related_party"]

        with st.spinner("Running Isolation Forest + XGBoost Semi-Supervised Scoring..."):
            X = df[_SHAP_COLS].copy().fillna(0)
            iso = IsolationForest(contamination=0.05, random_state=42)
            anomaly_array = iso.fit_predict(X)
            df["anomaly_score"] = pd.Series(anomaly_array, index=df.index).map({-1: 1, 1: 0})
            decision = iso.decision_function(X)
            df["anomaly_probability"] = 1 - (decision - decision.min()) / (decision.max() - decision.min() + 1e-8)

            # ── XGBoost semi-supervised refinement (pseudo-labels from IsolationForest) ──
            try:
                from xgboost import XGBRegressor
                xgb = XGBRegressor(
                    n_estimators=100, max_depth=3, learning_rate=0.1,
                    subsample=0.8, colsample_bytree=0.8,
                    objective="reg:squarederror", random_state=42, n_jobs=-1
                )
                xgb.fit(X, df["anomaly_probability"])
                df["xgb_risk_score"] = xgb.predict(X)
            except Exception:
                df["xgb_risk_score"] = df["anomaly_probability"]

            df["related_party_risk"] = (df["related_party"] == 1) & (df["anomaly_score"] == 1)
            df["overdue_risk"] = df["days_overdue"] > 30

            if "days_overdue" in df.columns:
                df["ageing_bucket"] = pd.cut(
                    df["days_overdue"],
                    bins=[-np.inf, 0, 30, 90, 180, 365, np.inf],
                    labels=["Not Due", "0-30", "31-90", "91-180", "181-365", "365+"]
                )

            st.success("✅ AI model + full ageing scrutiny executed successfully on real SAP data!")

        # Critical Ageing Scrutiny + Risk Filters + Charts + Flagged Table + Download (full original UI)
        st.subheader("📊 Critical Vendor Payment Ageing Scrutiny")
        if "ageing_bucket" in df.columns:
            bucket_summary = df.groupby("ageing_bucket", observed=False)["amount"].agg(["count", "sum"]).round(2)
            bucket_summary = bucket_summary.reset_index()
            st.dataframe(bucket_summary, use_container_width=True, hide_index=True)

        critical = df[(df["days_overdue"] > 90) & (df["amount"] > df["amount"].quantile(0.95))]
        if not critical.empty:
            st.info(f"⚠️ {len(critical)} Critical high-overdue + high-amount vendors")
            st.dataframe(critical[["vendor_name", "amount", "days_overdue", "category", "plant_code"]], use_container_width=True)

        if "related_party" in df.columns and df["related_party"].sum() > 0:
            st.info(f"⚠️ Related-party exposure: {df[(df['related_party']==1)]['amount'].sum():,.0f} ₹ | {df[(df['related_party']==1) & (df['anomaly_score']==1)].shape[0]} flagged")

        st.sidebar.header("🔍 Risk Filters")
        min_amount = st.sidebar.slider("Minimum Amount (₹)", 0, int(df["amount"].max()), 100000)
        risk_threshold = st.sidebar.slider("Minimum Anomaly Probability", 0.0, 1.0, 0.8)

        filtered = df[df["amount"] >= min_amount].copy()
        filtered = filtered[filtered["anomaly_probability"] >= risk_threshold]

        st.session_state.flagged_df = filtered.copy()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Transactions", f"{len(df):,}")
        col2.metric("High-Risk Flagged", f"{(df['anomaly_score'] == 1).sum():,}")
        col3.metric("Risk %", f"{(df['anomaly_score'] == 1).mean()*100:.1f}%")

        colA, colB = st.columns(2)
        with colA:
            st.subheader("Top 20 Highest Risk Payments")
            top20 = filtered.nlargest(20, "amount")
            fig_bar = px.bar(top20, x="vendor_name", y="amount", color="anomaly_probability")
            st.plotly_chart(fig_bar, use_container_width=True)
        with colB:
            st.subheader("Amount vs Anomaly Probability")
            fig_scatter = px.scatter(filtered, x="amount", y="anomaly_probability",
                                     color="anomaly_score", hover_data=["vendor_name"])
            st.plotly_chart(fig_scatter, use_container_width=True)

        # 4th metric
        overdue_credit = df[df["days_overdue"] > df.get("credit_terms_days", 30)]["amount"].sum()
        col4, col5 = st.columns(2)
        col4.metric("Overdue Credit Exposure ₹", f"{overdue_credit:,.0f}")
        col5.metric("Avg XGB Risk Score", f"{df['xgb_risk_score'].mean():.3f}")

        st.subheader("🚨 Flagged High-Risk Transactions")
        st.dataframe(filtered, use_container_width=True)

        csv = filtered.to_csv(index=False).encode()
        st.download_button("📥 Download Flagged Transactions as CSV", csv, "flagged_high_risk.csv", "text/csv")

        # ── Checklist-grounded rule flags ───────────────────────────────
        with st.expander("📋 Checklist-Grounded Rule Flags"):
            rules = []
            if "credit_terms_days" in df.columns:
                credit_breach = df[df["days_overdue"] > df["credit_terms_days"]]
                if not credit_breach.empty:
                    rules.append(f"Credit breach: {len(credit_breach)} rows (Vendor Checklist E.1)")
            if "tolerance_override_flag" in df.columns:
                tol = df[df["tolerance_override_flag"] == 1]
                if not tol.empty:
                    rules.append(f"Tolerance override: {len(tol)} rows (Purchasing D.7)")
            related_high = df[(df["related_party"] == 1) & (df["xgb_risk_score"] > 0.8)]
            if not related_high.empty:
                rules.append(f"Related-party high-risk: {len(related_high)} rows (Vendor Mgmt B.3)")
            if rules:
                for r in rules:
                    st.warning(r)
            else:
                st.info("No checklist rule flags triggered.")

        # ── Benford's Law Analysis ──────────────────────────────────────
        with st.expander("🔢 Benford's Law Analysis (First-Digit Test)"):
            def benford_analysis(amounts):
                expected = {1:30.1, 2:17.6, 3:12.5, 4:9.7, 5:7.9, 6:6.7, 7:5.8, 8:5.1, 9:4.6}
                first_digits = amounts[amounts > 0].astype(str).str[0].astype(int)
                observed = first_digits.value_counts(normalize=True).sort_index() * 100
                result = pd.DataFrame({"digit": list(expected.keys()),
                                       "expected_pct": list(expected.values()),
                                       "observed_pct": [observed.get(d, 0) for d in expected]})
                result["deviation"] = abs(result["observed_pct"] - result["expected_pct"])
                result["flag"] = result["deviation"] > 5
                return result
            benford = benford_analysis(df["amount"])
            fig_benford = px.bar(benford, x="digit", y=["expected_pct", "observed_pct"],
                                 barmode="group", title="Benford's Law: Expected vs Observed")
            st.plotly_chart(fig_benford, use_container_width=True)
            if benford["flag"].any():
                st.warning(f"Benford deviation >5% on digits: {list(benford[benford['flag']]['digit'])}")

        # ── SQLite Audit Trail Logging ──────────────────────────────────
        from utils.audit_db import init_audit_db
        from utils.base_audit_check import BaseAuditCheck
        init_audit_db()
        run_id = hashlib.sha256(str(datetime.utcnow()).encode()).hexdigest()[:12]
        class _PaymentAnomalyCheck(BaseAuditCheck):
            name = "Payment Anomaly"
            checklist_ref = "SAP Unit 1.18 / Vendor Mgmt E.1–E.4"
            sap_tcode_primary = "ZVOTAGE"
            def detect(self, df: pd.DataFrame) -> pd.DataFrame:
                return df
            sap_tcode_standard_alt = "FBL1N / S_ALR_87012085"
        checker = _PaymentAnomalyCheck()
        log_df = filtered.copy()
        log_df["flag_reason"] = "High-risk payment anomaly (IsolationForest + XGBoost ensemble)"
        log_df["risk_band"] = log_df["xgb_risk_score"].apply(lambda s: "CRITICAL" if s > 0.9 else "HIGH" if s > 0.7 else "MEDIUM")
        if not log_df.empty:
            checker.log_to_db(log_df, area="Vendor Payments", period=datetime.utcnow().strftime("%Y-%m"), run_id=run_id)
            st.caption(f"📝 {len(log_df)} findings logged to audit.db (run_id: {run_id})")

        # ── SHAP Risk Driver Analysis ─────────────────────────────────────
        with st.expander("🔍 SHAP Risk Driver Analysis", expanded=False):
            try:
                import shap
                flagged_X = X.loc[filtered.index].reset_index(drop=True)
                if flagged_X.empty:
                    st.info("No flagged transactions to explain.")
                else:
                    explainer = shap.Explainer(iso, X)
                    shap_vals = explainer(flagged_X).values

                    # Feature importance bar chart
                    mean_abs = np.abs(shap_vals).mean(axis=0)
                    fig_imp = px.bar(
                        x=_SHAP_COLS, y=mean_abs,
                        labels={"x": "Feature", "y": "Mean |SHAP Value|"},
                        title="Feature Contribution to Anomaly Score (Mean |SHAP|)",
                        color=mean_abs, color_continuous_scale="Reds",
                    )
                    fig_imp.update_layout(coloraxis_showscale=False)
                    st.plotly_chart(fig_imp, use_container_width=True)

                    # Per-transaction plain-English explanation
                    explanations = []
                    for i in range(len(shap_vals)):
                        row_shap = shap_vals[i]
                        row_vals = flagged_X.iloc[i]
                        top2 = np.argsort(np.abs(row_shap))[::-1][:2]
                        parts = []
                        for j in top2:
                            name = _SHAP_COLS[j]
                            val = row_vals[name]
                            sv = row_shap[j]
                            if name == "amount":
                                parts.append(f"amount ₹{val:,.0f} ({sv:+.3f})")
                            elif name == "days_overdue" and val > 0:
                                parts.append(f"{int(val)} days overdue ({sv:+.3f})")
                            elif name == "related_party" and val > 0:
                                parts.append(f"related-party ({sv:+.3f})")
                        explanations.append("Driven by: " + " + ".join(parts) if parts else "Combined risk signals")

                    shap_table = filtered[["vendor_name", "amount", "anomaly_probability"]].copy().reset_index(drop=True)
                    shap_table["risk_drivers"] = explanations
                    st.dataframe(shap_table, use_container_width=True, hide_index=True)
            except Exception as shap_err:
                st.warning(f"SHAP explanation unavailable: {shap_err}")

        st.subheader("📄 Optional: Attach One-Off Vendor Contract")
        st.caption("Main reference = full pgvector repository")
        uploaded_contract = st.file_uploader(
            "Upload ONE-OFF vendor contract PDF (optional)",
            type="pdf", key="contract_uploader"
        )
        if uploaded_contract:
            from pypdf import PdfReader
            reader = PdfReader(uploaded_contract)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            st.session_state.contract_text = text
            st.session_state.contract_attached = True
            st.session_state.contract_vendor = filtered["vendor_name"].iloc[0] if not filtered.empty else "Unknown"
            st.success(f"✅ One-off contract '{uploaded_contract.name}' ready for RAG analysis")

        # === GENERATE INITIAL REPORT ===
        if st.button("🔍 Generate RAG Audit Report", type="primary", use_container_width=True):
            if st.session_state.flagged_df.empty:
                st.error("No flagged transactions to audit.")
            else:
                with st.spinner("Calling Policy RAG Bot..."):
                    result = generate_rag_audit_report(
                        flagged_transactions=st.session_state.flagged_df.to_dict(orient="records"),
                        contract_text=st.session_state.contract_text if st.session_state.contract_attached else None,
                        vendor_name=st.session_state.contract_vendor
                    )
                    st.session_state.initial_audit_report = result["audit_summary"]
                    st.session_state.report_messages = [{"role": "assistant", "content": result["audit_summary"]}]
                    st.session_state.report_log_hash = result.get("log_hash", "N/A")
                    st.session_state.report_citations_count = len(result.get("citations", []))
                    st.session_state.report_generated_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

        # Render report from session_state — persists across all reruns
        if st.session_state.initial_audit_report:
            st.success("✅ Audit report generated via Policy RAG Bot")
            st.markdown("### Audit-Ready Executive Summary")
            st.markdown(st.session_state.initial_audit_report)
            st.caption(
                f"Audit log hash: `{st.session_state.report_log_hash}` | "
                f"Citations: {st.session_state.report_citations_count} | "
                f"Generated: {st.session_state.report_generated_at}"
            )
            pdf_buffer = _generate_report_pdf(st.session_state.initial_audit_report)
            st.download_button(
                "📥 Download Audit Report as PDF",
                pdf_buffer,
                "audit_report.pdf",
                "application/pdf",
                key="pdf_download_btn"
            )

        # === FOLLOW-UP CHAT WITH RICH CONTEXT (fixes hallucination) ===
        if st.session_state.report_messages:
            with st.expander("🔄 Follow-up Query with Policy RAG Bot (refine this audit report)", expanded=False):
                for msg in st.session_state.report_messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                if prompt := st.chat_input("Ask follow-up question about this audit report..."):
                    st.session_state.report_messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    with st.chat_message("assistant"):
                        with st.spinner("Querying Policy RAG Bot (free-form)..."):
                            # Build rich context from flagged_df + initial report
                            flagged_summary = st.session_state.flagged_df.nlargest(10, "amount")[["vendor_name", "amount", "anomaly_probability", "days_overdue"]].to_string()
                            rich_context = f"""
Flagged Transactions Summary:
{flagged_summary}

Initial Audit Report:
{st.session_state.initial_audit_report}

Contract Text (if attached):
{st.session_state.contract_text[:8000] if st.session_state.contract_attached else 'No contract attached'}
"""
                            free_chain = get_free_form_chain()
                            response = free_chain.invoke({"context": rich_context, "question": prompt})
                            st.markdown(response.content)
                            st.session_state.report_messages.append({"role": "assistant", "content": response.content})

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

else:
    st.info("👆 Upload any real SAP vendor payment file — only amount + vendor_name required.")

st.caption("Dynamic multi-vendor Contract RAG via full pgvector repository | Interactive follow-up with persistent context + PDF export")
