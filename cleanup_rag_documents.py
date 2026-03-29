import os
from dotenv import load_dotenv
from utils.rag_engine import get_vectorstore

load_dotenv()

vectorstore = get_vectorstore()

# ================== CHOOSE ONE OPTION ==================
# Option A: Delete ONE specific contract by filename
# filename_to_delete = "MANGALORE SEZ LIMITED.pdf"   # ← change this

# docs = vectorstore.similarity_search("", k=100)
# ids_to_delete = [doc.metadata["id"] for doc in docs 
#                  if doc.metadata.get("source", "").endswith(filename_to_delete)]

# if ids_to_delete:
#     vectorstore.delete(ids=ids_to_delete)
#     print(f"✅ Deleted {len(ids_to_delete)} chunks for {filename_to_delete}")
# else:
#     print("No matching document found")

# Option B: Delete ALL documents (full reset)
vectorstore.delete_collection()
print("✅ Entire collection 'audit_policies' deleted")
