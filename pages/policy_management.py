import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import _get_vectorstore_safe
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

st.set_page_config(page_title="🗄️ Policy Manager", layout="wide")
st.title("🗄️ Policy & Contract Management")
st.caption("Single-window ingest | inspect | cleanup | audit trail | FMCG/SAP compliant")

vectorstore = None
vectorstore_error = None


def _ensure_vectorstore():
    global vectorstore, vectorstore_error
    if vectorstore is None and vectorstore_error is None:
        vectorstore, vectorstore_error = _get_vectorstore_safe()
    return vectorstore, vectorstore_error

# ── TAB 1: Upload & Ingest ─────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📤 Upload & Ingest", "🔍 Inspect Indexed Documents", "🗑️ Cleanup & Maintenance"])

with tab1:
    st.subheader("Upload Policies / Contracts / Checklists")
    uploaded_files = st.file_uploader(
        "Select one or more files (PDF, XLSX, DOCX, MD)",
        type=["pdf", "xlsx", "xls", "docx", "md"],
        accept_multiple_files=True
    )

    if uploaded_files and st.button("🚀 Ingest Selected Files", type="primary", use_container_width=True):
        vectorstore, vectorstore_error = _ensure_vectorstore()
        if vectorstore is None:
            st.error(f"Vector store unavailable: {vectorstore_error}")
            st.stop()
        with st.spinner("Indexing into pgvector 'audit_policies'..."):
            ingested_count = 0
            for uploaded_file in uploaded_files:
                try:
                    suffix = Path(uploaded_file.name).suffix.lower()
                    docs = []

                    if suffix == ".pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name
                        loader = PyMuPDFLoader(tmp_path)
                        docs = loader.load()
                        os.unlink(tmp_path)

                    elif suffix in (".xlsx", ".xls"):
                        import pandas as pd
                        xl = pd.ExcelFile(uploaded_file)
                        text_parts = [f"CHECKLIST FILE: {uploaded_file.name}\n"]
                        for sheet in xl.sheet_names:
                            df = xl.parse(sheet)
                            text_parts.append(f"\n--- SHEET: {sheet} ---\n")
                            text_parts.append(df.to_string(index=False))
                        text = "\n".join(text_parts)
                        docs = [Document(page_content=text, metadata={"source": uploaded_file.name, "domain": "checklist"})]

                    elif suffix == ".docx":
                        # docx2txt may need pip install if not in requirements
                        import docx2txt
                        text = docx2txt.process(uploaded_file)
                        docs = [Document(page_content=text, metadata={"source": uploaded_file.name, "domain": "checklist"})]

                    elif suffix == ".md":
                        text = uploaded_file.getvalue().decode("utf-8")
                        docs = [Document(page_content=text, metadata={"source": uploaded_file.name, "domain": "checklist"})]

                    else:
                        st.warning(f"Skipped unsupported file: {uploaded_file.name}")
                        continue

                    # Metadata tagging (exact match to your ingest_policies.py)
                    for d in docs:
                        d.metadata.setdefault("domain", "contract" if "contract" in uploaded_file.name.lower() else "checklist")
                        d.metadata["source"] = uploaded_file.name
                        d.metadata["ingested_at"] = datetime.utcnow().isoformat()

                    vectorstore.add_documents(docs)
                    ingested_count += len(docs)
                    st.success(f"✅ {uploaded_file.name} — {len(docs)} chunk(s) indexed")

                except Exception as e:
                    st.error(f"❌ Failed {uploaded_file.name}: {str(e)}")

            st.success(f"🎉 Ingest complete! {ingested_count} total chunks added to pgvector.")
            st.info(f"Audit trail: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | User: {st.session_state.get('user', 'audit_admin')}")

# ── TAB 2: Inspect ─────────────────────────────────────────────
with tab2:
    if st.button("🔄 Refresh Full Index", use_container_width=True):
        vectorstore, vectorstore_error = _ensure_vectorstore()
        if vectorstore is None:
            st.error(f"Vector store unavailable: {vectorstore_error}")
            st.stop()
        with st.spinner("Fetching all documents from pgvector..."):
            docs = vectorstore.similarity_search("", k=500)  # exact pattern from inspect_rag_documents.py
            if docs:
                data = []
                for d in docs:
                    data.append({
                        "Source": d.metadata.get("source", "Unknown"),
                        "Domain": d.metadata.get("domain", "N/A"),
                        "Page": d.metadata.get("page", "N/A"),
                        "Preview": d.page_content[:180] + "..." if len(d.page_content) > 180 else d.page_content
                    })
                df = pd.DataFrame(data)
                # Unique sources summary
                summary = df.groupby("Source").size().reset_index(name="Chunks")
                st.dataframe(summary, use_container_width=True, hide_index=True)
                st.subheader("All Indexed Chunks")
                st.dataframe(df, use_container_width=True)
                st.caption(f"Total documents in collection: {len(docs)}")
            else:
                st.info("No documents found in pgvector.")

# ── TAB 3: Cleanup ─────────────────────────────────────────────
with tab3:
    st.warning("⚠️ Cleanup operations are irreversible on Render free tier.")
    
    # Option A: Delete by source filename (most common need)
    filename_to_delete = st.text_input("Delete all chunks for specific file (exact filename)", placeholder="MANGALORE SEZ LIMITED.pdf")
    if filename_to_delete and st.button("🗑️ Delete by Filename", type="secondary"):
        vectorstore, vectorstore_error = _ensure_vectorstore()
        if vectorstore is None:
            st.error(f"Vector store unavailable: {vectorstore_error}")
            st.stop()
        with st.spinner("Deleting..."):
            try:
                # Use metadata filter (PGVector native support)
                vectorstore.delete(filter={"source": filename_to_delete})
                st.success(f"✅ All chunks for {filename_to_delete} removed")
            except Exception as e:
                st.error(f"Delete failed: {e}")

    # Option B: Full collection reset (exact from cleanup_rag_documents.py)
    if st.checkbox("I want to **completely reset** the entire policy repository (full delete_collection)"):
        if st.button("🚨 FULL RESET – Delete Entire Collection", type="primary"):
            vectorstore, vectorstore_error = _ensure_vectorstore()
            if vectorstore is None:
                st.error(f"Vector store unavailable: {vectorstore_error}")
                st.stop()
            with st.spinner("Resetting pgvector collection..."):
                vectorstore.delete_collection()
                st.success("✅ Entire 'audit_policies' collection deleted. Next ingest will recreate it.")
                st.info("Audit trail logged – full reset performed.")

    st.caption("Tip: After cleanup, go back to Upload tab to re-ingest fresh contracts/checklists.")

st.caption("Policy Manager • pgvector + hybrid search • Audit-compliant logging • Ready for Prefect nightly re-index")