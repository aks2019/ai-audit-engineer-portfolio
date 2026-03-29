# This script ingests all PDF files from the data/raw directory and indexes them into pgvector.
# Just run the ingest script once (or whenever you add new contracts) and your system becomes fully dynamic:
# Drop any new vendor contract PDF into data/raw
# Run python ingest_policies.py, Both bots (audit_bot & payment_anomaly_detector) instantly see it forever (no upload needed again).

import os
from utils.rag_engine import get_vectorstore
from langchain_community.document_loaders import PyMuPDFLoader
from pathlib import Path

print("🔄 Indexing all PDFs from data/raw into pgvector...")

vectorstore = get_vectorstore()
data_raw = Path("data/raw")

for pdf_file in data_raw.glob("*.pdf"):
    print(f"Processing: {pdf_file.name}")
    loader = PyMuPDFLoader(str(pdf_file))
    docs = loader.load()
    vectorstore.add_documents(docs)
    print(f"✅ Indexed {len(docs)} pages from {pdf_file.name}")

print("🎉 All policies indexed! You can now ask any question without uploading.")