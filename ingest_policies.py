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