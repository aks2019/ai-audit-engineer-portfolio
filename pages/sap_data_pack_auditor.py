import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path
import hashlib
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from checks.sap import (
    SAP_DATA_PACKS,
    validate_sap_pack,
    generate_sap_audit_report,
)
from utils.audit_db import (
    init_audit_db,
    stage_findings,
    load_draft_findings,
    confirm_draft_findings,
    discard_draft_findings,
)
from utils.audit_page_helpers import (
    render_engagement_selector,
    get_active_engagement_id,
    render_rag_report_section,
)

st.set_page_config(page_title="SAP Data Pack Auditor", page_icon="📦", layout="wide")

PAGE_KEY = "sap_data_pack"
MODULE_NAME = "SAP Data Pack Auditor"


def _normalize_risk_band(sev) -> str:
    x = str(sev or "MEDIUM").strip().upper()
    if x in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        return x
    if x in ("SEVERE", "C"):
        return "CRITICAL"
    return "MEDIUM"


render_engagement_selector(PAGE_KEY)

# ── SESSION STATE ──────────────────────────────────────────────────
if "sap_packs" not in st.session_state:
    st.session_state["sap_packs"] = {}
if "sap_analysis_done" not in st.session_state:
    st.session_state["sap_analysis_done"] = False
if "sap_report" not in st.session_state:
    st.session_state["sap_report"] = {}
if "sap_all_issues" not in st.session_state:
    st.session_state["sap_all_issues"] = []
if f"{PAGE_KEY}_draft_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_draft_run_id"] = None
if f"{PAGE_KEY}_last_staged_issues_fp" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = None
if f"{PAGE_KEY}_draft_row_sel" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
if f"{PAGE_KEY}_row_sel_run_id" not in st.session_state:
    st.session_state[f"{PAGE_KEY}_row_sel_run_id"] = None
if "sap_column_maps" not in st.session_state:
    st.session_state["sap_column_maps"] = {}

st.title("📦 SAP Data Pack Auditor")
st.markdown("**100% Population Testing • FBL1N · FBL5N · FBL3N · MB51 · MB52 · AS03 · SUIM**")

# ── SAP Module Hub (Tools ↔ Data Packs ↔ T-codes) ─────────────────────────────
st.subheader("🧭 SAP Module Hub (Tools ↔ Data Packs ↔ T-codes)")

# Inferred mapping: which audit tools typically pair with which SAP extracts.
# Source of truth for the available extracts is `checks/sap/SAP_DATA_PACKS`.
tcode_to_tool = {
    "FBL1N": "Duplicate Invoice Detector",
    "FBL5N": "Receivables & Bad Debt",
    "FBL3N": "BRS Reconciliation",
    "MB51": "Inventory Anomaly",
    "MB52": "Inventory Anomaly",
    "AS03": "Fixed Asset Auditor",
    "SUIM": "ITGC & SAP Access",
}

module_to_pack_types = {
    "FI": ["FBL1N", "FBL5N", "FBL3N", "AS03"],
    "MM": ["MB51", "MB52"],
    "IT_Security": ["SUIM"],
}

hub_rows = []
for sap_module, pack_types in module_to_pack_types.items():
    available_pack_types = [p for p in pack_types if p in SAP_DATA_PACKS]
    tools = sorted({tcode_to_tool.get(p, "SAP Data Pack Auditor") for p in available_pack_types})
    tcode_hints = [SAP_DATA_PACKS[p]["sap_tcode"] for p in available_pack_types]
    hub_rows.append(
        {
            "SAP Module": sap_module,
            "Tools": ", ".join(tools),
            "Data Packs": ", ".join(available_pack_types),
            "T-code Hints": ", ".join(tcode_hints),
        }
    )

hub_df = pd.DataFrame(hub_rows)
st.dataframe(hub_df, use_container_width=True, hide_index=True)

# ── SIDEBAR: Data Pack Reference ──────────────────────────────────
with st.sidebar:
    st.header("📋 Data Pack Reference")
    for tcode, info in SAP_DATA_PACKS.items():
        with st.expander(f"{tcode} — {info['name']}"):
            st.caption(info["description"])
            st.markdown("**Required:**")
            for col in info["required_columns"]:
                st.markdown(f"- `{col}`")
            st.markdown("**Procedures:**")
            for proc in info["audit_procedures"]:
                st.markdown(f"- {proc}")

    st.divider()
    st.caption(
        "Download standard SAP extracts using the listed T-codes. "
        "Upload one or more packs, then run **Analyze All** for a consolidated report."
    )

# ── STEP 1: Upload SAP Data Packs ─────────────────────────────────
st.subheader("📤 Step 1: Upload SAP Data Packs")

upload_method = st.radio(
    "Upload method",
    ["Single File (select pack type)", "Bulk Upload (auto-detect or manual map)"],
    horizontal=True,
)

if upload_method == "Single File (select pack type)":
    col1, col2 = st.columns([1, 1])
    with col1:
        pack_type = st.selectbox(
            "Select SAP Data Pack Type",
            list(SAP_DATA_PACKS.keys()),
            format_func=lambda x: f"{x} — {SAP_DATA_PACKS[x]['name']}",
        )
    with col2:
        uploaded_file = st.file_uploader(
            f"Upload {pack_type} Extract (CSV/Excel)",
            type=["csv", "xlsx"],
            key=f"single_{pack_type}",
        )

    if uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)

            # ── Smart Auto-Map: Exact match first, then case-insensitive, then fuzzy ───
            expected_cols = SAP_DATA_PACKS[pack_type]["expected_columns"]
            required_cols = SAP_DATA_PACKS[pack_type]["required_columns"]

            # Strip whitespace from uploaded columns
            df_raw.columns = [c.strip() for c in df_raw.columns]

            # Build smart default mapping
            auto_map = {}
            for ec in expected_cols:
                # Exact match
                if ec in df_raw.columns:
                    auto_map[ec] = ec
                    continue
                # Case-insensitive match
                for c in df_raw.columns:
                    if c.lower() == ec.lower():
                        auto_map[ec] = c
                        break
                else:
                    # Fuzzy match — contains substring
                    for c in df_raw.columns:
                        if ec.lower() in c.lower() or c.lower() in ec.lower():
                            auto_map[ec] = c
                            break

            st.markdown("---")
            st.subheader("🔧 Column Mapping")
            st.caption("Map your file's columns to the required SAP audit schema. Required fields must be set before analysis runs.")

            col_map = {}
            missing_required = []

            # Required columns — must be mapped
            st.markdown("**Required Mappings:**")
            req_cols_ui = st.columns(min(len(required_cols), 4))
            for i, col in enumerate(required_cols):
                with req_cols_ui[i % 4]:
                    default_idx = list(df_raw.columns).index(auto_map.get(col, col)) + 1 if auto_map.get(col) in df_raw.columns else 0
                    mapped = st.selectbox(
                        f"**{col}** *(required)*",
                        ["— Select —"] + list(df_raw.columns),
                        index=default_idx,
                        key=f"req_{pack_type}_{col}",
                    )
                    if mapped != "— Select —":
                        col_map[col] = mapped

            # Optional / expected columns
            optional_cols = [c for c in expected_cols if c not in required_cols]
            if optional_cols:
                st.markdown("**Optional Mappings:**")
                opt_cols_ui = st.columns(min(len(optional_cols), 4))
                for i, col in enumerate(optional_cols):
                    with opt_cols_ui[i % 4]:
                        default_idx = list(df_raw.columns).index(auto_map.get(col, col)) + 1 if auto_map.get(col) in df_raw.columns else 0
                        mapped = st.selectbox(
                            f"{col} (optional)",
                            ["— Select —"] + list(df_raw.columns),
                            index=default_idx,
                            key=f"opt_{pack_type}_{col}",
                        )
                        if mapped != "— Select —":
                            col_map[col] = mapped

            # Apply mapping only when all required are set
            missing_required = [c for c in required_cols if c not in col_map]

            if missing_required:
                st.warning(f"⚠️ Please map all required columns: {missing_required}")
            else:
                # Apply rename
                rename_map = {v: k for k, v in col_map.items()}
                df = df_raw.rename(columns=rename_map)

                # Strip whitespace from column names
                df.columns = [c.strip() for c in df.columns]

                validation = validate_sap_pack(df, pack_type)

                st.session_state["sap_packs"][pack_type] = {
                    "df": df,
                    "filename": uploaded_file.name,
                    "validation": validation,
                }

                if validation["status"] == "VALID":
                    st.success(
                        f"✅ {pack_type} loaded: {validation['row_count']} rows, "
                        f"{validation['column_count']} columns"
                    )
                    if validation.get("extra_columns"):
                        st.info(f"Extra columns (ignored): {', '.join(validation['extra_columns'])}")
                else:
                    st.error(
                        f"⚠️ Schema issues: Missing required: {validation.get('missing_required', [])}"
                    )
                    if validation.get("missing_expected"):
                        st.warning(f"Missing expected: {', '.join(validation['missing_expected'])}")

                with st.expander("🔍 Preview Data"):
                    st.dataframe(df.head(20), use_container_width=True)

                # Reset analysis state when new file uploaded
                st.session_state["sap_analysis_done"] = False
                st.session_state["sap_report"] = {}
                st.session_state["sap_all_issues"] = []
                st.session_state[f"{PAGE_KEY}_draft_run_id"] = None
                st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = None
                st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
                st.session_state[f"{PAGE_KEY}_row_sel_run_id"] = None

        except Exception as e:
            st.error(f"Failed to read file: {e}")

else:
    bulk_files = st.file_uploader(
        "Upload one or more SAP extract files (CSV/Excel)",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        key="bulk_upload",
    )

    if bulk_files:
        for bf in bulk_files:
            st.markdown(f"---")
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown(f"**📄 {bf.name}** ({bf.size / 1024:.1f} KB)")
            with col_b:
                assigned_type = st.selectbox(
                    f"Map to SAP Pack",
                    ["(Auto-detect)"] + list(SAP_DATA_PACKS.keys()),
                    key=f"map_{bf.name}",
                )

            try:
                df = pd.read_csv(bf) if bf.name.endswith(".csv") else pd.read_excel(bf)

                if assigned_type == "(Auto-detect)":
                    best_match = None
                    best_score = 0
                    for pt, info in SAP_DATA_PACKS.items():
                        match_count = sum(1 for c in info["required_columns"] if c in df.columns)
                        if match_count > best_score:
                            best_score = match_count
                            best_match = pt
                    assigned_type = best_match if best_match and best_score >= 2 else None
                    if assigned_type:
                        st.caption(f"🔍 Auto-detected: **{assigned_type}** — {SAP_DATA_PACKS[assigned_type]['name']}")
                    else:
                        st.warning("Could not auto-detect. Please select manually.")

                if assigned_type and assigned_type in SAP_DATA_PACKS:
                    validation = validate_sap_pack(df, assigned_type)
                    st.session_state["sap_packs"][assigned_type] = {
                        "df": df,
                        "filename": bf.name,
                        "validation": validation,
                    }
                    if validation["status"] == "VALID":
                        st.success(f"✅ Valid: {validation['row_count']} rows")
                    else:
                        st.error(f"Schema issues — Missing required: {validation.get('missing_required', [])}")
                    with st.expander(f"Preview: {bf.name}"):
                        st.dataframe(df.head(10), use_container_width=True)
                else:
                    st.error("Please assign a valid SAP pack type.")
            except Exception as e:
                st.error(f"Failed to read {bf.name}: {e}")

        if bulk_files:
            st.session_state["sap_analysis_done"] = False
            st.session_state["sap_report"] = {}
            st.session_state["sap_all_issues"] = []
            st.session_state[f"{PAGE_KEY}_draft_run_id"] = None
            st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = None
            st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
            st.session_state[f"{PAGE_KEY}_row_sel_run_id"] = None

# ── STEP 2: Loaded Packs Summary ──────────────────────────────────
if st.session_state["sap_packs"]:
    st.divider()
    st.subheader(f"📦 Loaded Data Packs ({len(st.session_state['sap_packs'])})")

    packs_summary = []
    for pt, data in st.session_state["sap_packs"].items():
        v = data["validation"]
        packs_summary.append({
            "Pack": f"{pt} — {SAP_DATA_PACKS[pt]['name']}",
            "File": data["filename"],
            "Status": v["status"],
            "Rows": v["row_count"],
            "Columns": v["column_count"],
            "Missing Required": ", ".join(v.get("missing_required", [])) or "None",
        })
    st.dataframe(pd.DataFrame(packs_summary), use_container_width=True, hide_index=True)

    # ── STEP 3: Run Analysis ───────────────────────────────────────
    st.divider()
    st.subheader("🚀 Step 2: Run Audit Analysis")

    col_btn, col_clr = st.columns([1, 3])
    with col_btn:
        run_analysis = st.button(
            "🔍 Analyze All Packs",
            type="primary",
            use_container_width=True,
        )
    with col_clr:
        if st.button("🗑️ Clear All Packs"):
            st.session_state["sap_packs"] = {}
            st.session_state["sap_analysis_done"] = False
            st.session_state["sap_report"] = {}
            st.session_state["sap_all_issues"] = []
            st.session_state[f"{PAGE_KEY}_draft_run_id"] = None
            st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = None
            st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
            st.session_state[f"{PAGE_KEY}_row_sel_run_id"] = None
            st.rerun()

    if run_analysis:
        with st.spinner("Running SAP data pack audit checks..."):
            packs_dict = {pt: data["df"] for pt, data in st.session_state["sap_packs"].items()}
            report = generate_sap_audit_report(packs_dict)
            st.session_state["sap_report"] = report
            st.session_state["sap_analysis_done"] = True

            # Collect all issues
            all_issues = []
            for pr in report.get("packs_processed", []):
                for issue in pr.get("analysis", {}).get("issues", []):
                    issue["pack_type"] = pr["pack_type"]
                    all_issues.append(issue)
            st.session_state["sap_all_issues"] = all_issues

            # Stable ordering for fingerprint (avoid spurious re-stage if iteration order differs)
            issues_for_fp = sorted(
                all_issues,
                key=lambda x: (
                    str(x.get("pack_type", "")),
                    str(x.get("type", "")),
                    str(x.get("vendor") or x.get("customer") or x.get("user") or ""),
                    str(x.get("description", ""))[:120],
                ),
            )

            # Generate stable run_id based on uploaded files (version suffix bypasses stale dedupe windows)
            file_bytes = b"".join([d["df"].to_csv(index=False).encode() for d in st.session_state["sap_packs"].values()])
            file_run_id = f"{hashlib.sha256(file_bytes).hexdigest()[:12]}:sap-v3"

            # Fingerprint of analysis output — prevents duplicate DB inserts on every "Analyze All" click
            issues_fp = hashlib.sha256(
                json.dumps(issues_for_fp, sort_keys=True, default=str).encode("utf-8", errors="replace")
            ).hexdigest()[:20]
            eng_id = get_active_engagement_id(PAGE_KEY)
            composite_fp = hashlib.sha256(f"{issues_fp}|{eng_id}".encode()).hexdigest()[:24]

            # Stage findings using the draft workflow (Maker-Checker)
            if all_issues:
                init_audit_db()

                already_fp = st.session_state.get(f"{PAGE_KEY}_last_staged_issues_fp")
                if already_fp == composite_fp:
                    st.session_state[f"{PAGE_KEY}_draft_run_id"] = file_run_id
                    st.info(
                        "Draft findings **already staged** for this analysis result — skipped inserting duplicates. "
                        "Scroll to **Review & Confirm Findings**, or **Clear All Packs** and re-upload if you need a clean run."
                    )
                else:
                    staged_rows = []
                    for issue in all_issues:
                        entity_name = issue.get("vendor") or issue.get("customer") or issue.get("user") or issue.get("asset") or issue.get("material") or "Unknown"
                        pack_type = issue.get("pack_type", "UNKNOWN")
                        issue_type = issue.get("type", "Unknown")
                        ref_key = f"{pack_type}|{issue_type}|{entity_name}|{issue.get('description', '')}|{issue.get('conflict', '')}"
                        # Deterministic ref so SQLite dedupe works across reruns / identical issues
                        src_ref = f"{PAGE_KEY}-{hashlib.sha256(ref_key.encode('utf-8', errors='replace')).hexdigest()[:24]}"

                        staged_rows.append({
                            "area": f"SAP-{pack_type}",
                            "checklist_ref": f"SAP {pack_type} Audit / Companies Act Schedule III",
                            "finding": (
                                f"[{pack_type}] {issue_type} — "
                                f"{issue.get('description', issue.get('conflict', ''))} | "
                                f"Entity: {entity_name}"
                            ),
                            "amount_at_risk": float(issue.get("amount", 0) or 0),
                            "vendor_name": str(entity_name),
                            "risk_band": _normalize_risk_band(issue.get("severity")),
                            "finding_date": datetime.utcnow().strftime("%Y-%m-%d"),
                            "period": datetime.utcnow().strftime("%Y-%m"),
                            "source_row_ref": src_ref,
                        })

                    all_flagged = pd.DataFrame(staged_rows)
                    source_filename = ", ".join([d["filename"] for d in st.session_state["sap_packs"].values()])

                    staged = stage_findings(
                        all_flagged,
                        module_name=MODULE_NAME,
                        run_id=file_run_id,
                        period=datetime.utcnow().strftime("%Y-%m"),
                        source_file_name=source_filename,
                        engagement_id=get_active_engagement_id(PAGE_KEY),
                    )
                    st.session_state[f"{PAGE_KEY}_draft_run_id"] = file_run_id
                    st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = composite_fp

                    st.success(
                        f"✅ **{staged} exception(s) staged for your review** (of **{len(all_flagged)}** detected). "
                        "Nothing has been added to the official audit trail yet. "
                        "Scroll down to **Review & Confirm Findings** to approve or discard."
                    )
                    if staged < len(all_flagged):
                        st.warning(
                            f"**{len(all_flagged) - staged}** row(s) skipped — identical draft/confirmed finding exists (dedupe)."
                        )
            else:
                st.session_state[f"{PAGE_KEY}_last_staged_issues_fp"] = None
                st.success("✅ No issues detected across all data packs. No findings to stage.")

    # ── STEP 4: Display Results ────────────────────────────────────
    if st.session_state["sap_analysis_done"] and st.session_state["sap_report"]:
        report = st.session_state["sap_report"]

        st.divider()
        st.subheader("📊 Audit Results")

        # Executive Summary
        summary = report.get("summary", {})
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Issues", summary.get("total_issues", 0))
        mc2.metric("🔴 Critical", summary.get("critical_issues", 0), delta_color="inverse")
        mc3.metric("🟠 Medium", summary.get("medium_issues", 0))
        mc4.metric("🟡 Low", summary.get("low_issues", 0))
        st.caption(f"Report generated: {report.get('report_date', '')}")

        all_issues_tbl = st.session_state.get("sap_all_issues") or []
        if all_issues_tbl:
            st.divider()
            st.subheader("🚨 Exception table — consolidated SAP data pack findings (all packs)")
            st.caption("Rows mirror automated checks across uploaded extracts; confirm below to post to the official trail.")
            st.dataframe(pd.DataFrame(all_issues_tbl), use_container_width=True, hide_index=True)

        st.divider()

        # Per-pack detailed results
        for pack_result in report.get("packs_processed", []):
            pack_type = pack_result["pack_type"]
            validation = pack_result.get("validation", {})
            analysis = pack_result.get("analysis", {})

            pack_label = (
                f"{pack_type} — {SAP_DATA_PACKS[pack_type]['name']}"
                if pack_type in SAP_DATA_PACKS else pack_type
            )
            issue_count = len(analysis.get("issues", []))

            with st.expander(
                f"{'✅' if issue_count == 0 else '⚠️'} {pack_label} "
                f"({issue_count} issues)",
                expanded=(issue_count > 0),
            ):
                col_v1, col_v2, col_v3 = st.columns(3)
                col_v1.caption(f"Rows: {validation.get('row_count', 'N/A')}")
                col_v2.caption(f"Status: {validation.get('status', 'N/A')}")
                col_v3.caption(f"T-Code: {validation.get('tcode', 'N/A')}")

                # Analysis metrics
                if pack_type in ("FBL1N", "FBL5N"):
                    if pack_type == "FBL1N":
                        st.markdown(
                            f"**Vendors:** {analysis.get('total_vendors', 'N/A')} | "
                            f"**Overdue >90 days:** {analysis.get('overdue_90_count', 0)}"
                        )
                        if analysis.get("vendor_summary"):
                            st.markdown("**Vendor Outstanding Summary:**")
                            st.dataframe(
                                pd.DataFrame(analysis["vendor_summary"]).head(10),
                                use_container_width=True,
                            )
                    else:
                        st.markdown(
                            f"**Customers:** {analysis.get('total_customers', 'N/A')} | "
                            f"**Total Receivables:** {analysis.get('total_receivables', 0):,.0f} | "
                            f"**Overdue >90 days:** {analysis.get('overdue_90_count', 0)}"
                        )

                elif pack_type == "FBL3N":
                    st.markdown(
                        f"**GL Records:** {analysis.get('total_records', 'N/A')} | "
                        f"**Manual Postings:** {analysis.get('manual_postings', 0)}"
                    )

                elif pack_type in ("MB51", "MB52"):
                    st.markdown(
                        f"**Movements:** {analysis.get('total_movements', 'N/A')} | "
                        f"**Negative Qty:** {analysis.get('negative_qty_count', 0)}"
                    )
                    if analysis.get("movement_summary"):
                        st.markdown("**Movement Type Summary:**")
                        st.dataframe(
                            pd.DataFrame(analysis["movement_summary"]).head(10),
                            use_container_width=True,
                        )

                elif pack_type == "AS03":
                    st.markdown(
                        f"**Assets:** {analysis.get('total_assets', 'N/A')} | "
                        f"**Fully Depreciated:** {analysis.get('fully_depreciated_count', 0)} | "
                        f"**Potential Impairment:** {analysis.get('potential_impairment_count', 0)}"
                    )

                elif pack_type == "SUIM":
                    st.markdown(
                        f"**Users:** {analysis.get('total_users', 'N/A')} | "
                        f"**SoD Conflicts:** {analysis.get('sod_conflicts', 0)} | "
                        f"**Inactive Users:** {analysis.get('inactive_users', 0)}"
                    )

                # Issues table
                issues = analysis.get("issues", [])
                if issues:
                    st.markdown(f"**🚨 Flagged Issues ({len(issues)}):**")
                    issues_df = pd.DataFrame(issues)

                    def highlight_severity(val):
                        if val == "HIGH":
                            return "background-color: #ff4b4b; color: white"
                        elif val == "MEDIUM":
                            return "background-color: #ffa726; color: white"
                        elif val == "LOW":
                            return "background-color: #66bb6a; color: white"
                        return ""

                    styled_df = (
                        issues_df.style.applymap(highlight_severity, subset=["severity"])
                        if "severity" in issues_df.columns
                        else issues_df
                    )
                    st.dataframe(styled_df, use_container_width=True)
                else:
                    st.success("No issues detected for this pack.")

        # ── Download Findings CSV ──────────────────────────────────
        all_issues = st.session_state["sap_all_issues"]
        if all_issues:
            st.divider()
            csv_export = pd.DataFrame(all_issues).to_csv(index=False).encode()
            st.download_button(
                "📥 Download All Findings (CSV)",
                csv_export,
                f"sap_findings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
            )

        # ── AI AUDIT REPORT (RAG) ──────────────────────────────────
        flagged_df = pd.DataFrame(st.session_state["sap_all_issues"]) if st.session_state["sap_all_issues"] else pd.DataFrame()
        render_rag_report_section(
            PAGE_KEY,
            flagged_df=flagged_df if not flagged_df.empty else None,
            module_name=MODULE_NAME,
        )

else:
    st.info(
        "👆 Upload one or more SAP data pack extracts above to begin. "
        "Refer to the sidebar for expected column formats and required T-codes."
    )

# ── REVIEW & CONFIRM FINDINGS (Maker-Checker) ─────────────────────
current_run_id = st.session_state.get(f"{PAGE_KEY}_draft_run_id")
if current_run_id:
    st.divider()
    st.subheader("Review & Confirm Findings")
    st.caption(
        "Use the Select column in the table to confirm/discard. "
        "**Audit Report Centre / Audit Committee Pack** only include findings after you confirm them."
    )

    drafts = load_draft_findings(
        run_id=current_run_id,
        module_name=MODULE_NAME,
        status="Draft",
        engagement_id=get_active_engagement_id(PAGE_KEY),
    )
    if drafts.empty:
        st.info("No draft exceptions pending for the current analysis run.")
    else:
        if st.session_state.get(f"{PAGE_KEY}_row_sel_run_id") != current_run_id:
            st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
            st.session_state[f"{PAGE_KEY}_row_sel_run_id"] = current_run_id

        row_sel = st.session_state[f"{PAGE_KEY}_draft_row_sel"]
        ids_set = set(int(x) for x in drafts["id"].tolist())
        for k in list(row_sel.keys()):
            if int(k) not in ids_set:
                del row_sel[k]

        st.caption(f"**{len(drafts)} draft exception(s)** pending review.")
        c_sel1, c_sel2, c_sel3 = st.columns([1, 1, 2])
        with c_sel1:
            if st.button("Select all in table", use_container_width=True, key=f"{PAGE_KEY}_sel_all_btn"):
                for i in drafts["id"].astype(int):
                    row_sel[int(i)] = True
                st.session_state[f"{PAGE_KEY}_draft_row_sel"] = row_sel
                st.rerun()
        with c_sel2:
            if st.button("Clear row selection", use_container_width=True, key=f"{PAGE_KEY}_sel_clear_btn"):
                st.session_state[f"{PAGE_KEY}_draft_row_sel"] = {}
                st.rerun()

        review_df = drafts[["id", "area", "vendor_name", "finding", "amount_at_risk", "risk_band"]].copy()
        review_df.insert(0, "select", review_df["id"].map(lambda i: bool(row_sel.get(int(i), False))))

        edited = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "area": st.column_config.TextColumn("Area", disabled=True),
                "vendor_name": st.column_config.TextColumn("Entity", disabled=True),
                "finding": st.column_config.TextColumn("Finding (editable)", width="large"),
                "amount_at_risk": st.column_config.NumberColumn("Amount at Risk", format="%.0f"),
                "risk_band": st.column_config.SelectboxColumn(
                    "Risk Band",
                    options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                ),
            },
            key=f"{PAGE_KEY}_draft_editor_inline_select",
        )

        for _, row in edited.iterrows():
            row_sel[int(row["id"])] = bool(row.get("select", False))
        st.session_state[f"{PAGE_KEY}_draft_row_sel"] = row_sel

        selected_ids = edited.loc[edited["select"] == True, "id"].astype(int).tolist()
        confirmed_by = st.text_input(
            "Confirmed / Reviewed by (auditor name)",
            value="Auditor",
            key=f"{PAGE_KEY}_confirmed_by",
        )

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
            discard_reason = st.text_input(
                "Discard reason (optional)",
                key=f"{PAGE_KEY}_discard_reason",
            )
            if st.button(
                "Discard Selected (False Positives)",
                use_container_width=True,
                key=f"{PAGE_KEY}_discard_btn",
            ):
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
            "draft_exceptions_sap_data_pack_auditor.csv",
            "text/csv",
            key=f"{PAGE_KEY}_export_drafts",
        )

st.divider()
st.caption(
    "**SAP Data Pack Auditor** | FBL1N · FBL5N · FBL3N · MB51 · MB52 · AS03 · SUIM | "
    "Powered by `checks/sap` engine | Draft → Review → Confirm workflow"
)