import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.rag_engine import get_free_form_chain

st.title("🧠 NLP Document Intelligence")
st.caption("Auto-extract audit concerns from emails, board papers, external auditor reports, journal narrations")

uploaded = st.file_uploader("Upload Document (PDF / DOCX / TXT)", type=["pdf","docx","txt"])
if uploaded:
    suffix = Path(uploaded.name).suffix.lower()
    text = ""
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(uploaded)
        text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
    elif suffix == ".docx":
        import docx2txt
        text = docx2txt.process(uploaded)
    elif suffix == ".txt":
        text = uploaded.read().decode("utf-8", errors="replace")

    st.success(f"Extracted {len(text):,} characters")
    with st.expander("📄 Raw Text Preview"):
        st.text(text[:3000])

    # Extract structured findings via LLM
    if st.button("🤖 Extract Structured Audit Findings"):
        with st.spinner("LLM analysing document..."):
            chain = get_free_form_chain()
            prompt = """You are a senior internal auditor. Analyse the following document and extract structured audit findings.
For each finding, provide:
1. Area (e.g., Finance, Procurement, HR, IT)
2. Concern Summary (1-2 sentences)
3. Severity (CRITICAL / HIGH / MEDIUM / LOW)
4. Recommended Action
5. Related Checklist Reference (if identifiable)

Format as a markdown table."""
            response = chain.invoke({"context": text[:8000], "question": prompt})
            st.markdown(response.content)

    # Narration analysis for journal entries
    st.subheader("📝 Journal Entry Narration Analysis")
    narration = st.text_area("Paste journal narration / email text here", height=150)
    if narration and st.button("🔍 Analyse Narration"):
        with st.spinner("Analysing..."):
            chain = get_free_form_chain()
            prompt = """Analyse this journal entry narration or email text for red flags:
- Round-figure amounts
- Vague descriptions
- Related-party references
- Revenue/capital misclassification keywords
- Unusual timing keywords
Return a bullet-point risk assessment."""
            response = chain.invoke({"context": narration, "question": prompt})
            st.markdown(response.content)
