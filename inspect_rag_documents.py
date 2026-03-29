# Production tip: (FMCG audit compliance): 
# Run inspect_rag_documents.py before every major audit to confirm only current contracts are indexed. 
# Cleanup old test contracts immediately to keep the repository clean.
import os
from dotenv import load_dotenv
from utils.rag_engine import get_vectorstore

load_dotenv()

vectorstore = get_vectorstore()

# List all documents in the collection
docs = vectorstore.similarity_search("", k=50)  # empty query = return everything

print(f"Total documents in pgvector 'audit_policies': {len(docs)}\n")

for i, doc in enumerate(docs, 1):
    source = doc.metadata.get("source", "Unknown")
    page = doc.metadata.get("page", "N/A")
    print(f"{i:2d}. Source: {source} | Page: {page}")
    print(f"    Preview: {doc.page_content[:150]}...\n")
