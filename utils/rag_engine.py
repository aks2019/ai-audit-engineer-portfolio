import os
import hashlib
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vectorstore():
    return PGVector(
        embeddings=embeddings,
        collection_name="audit_policies",
        connection=os.getenv("NEON_CONNECTION_STRING"),
        use_jsonb=True
    )

# ====================== LLM Settings ======================
# def get_rag_chain():  # STRICT AUDIT REPORT MODE
#     llm = ChatGoogleGenerativeAI(
#         model="gemini-2.5-flash",
#         google_api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=0.0
#     )
# === LOCAL QWEN 3.5-9b (offline - secure) ========================================
def get_rag_chain():  # STRICT AUDIT REPORT MODE
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        base_url="http://127.0.0.1:1234/v1",
        api_key="lm-studio",
        model= "nvidia/nemotron-3-nano-4b", #"qwen/qwen3.5-9b", # exact name shown in LM Studio
        temperature=0.0,
        max_tokens=32000
    )
# =============================================================================================

    RAG_PROMPT = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are AI AUDIT BOT – a Continuous Control Monitoring + Policy Compliance Agent for Emami Agrotech Limited.
You are a senior internal auditor with 17+ years FMCG experience.

STRICT RESPONSE FORMAT (never deviate):
1. Direct Answer
2. Root Cause Analysis (if applicable; otherwise "Not applicable as this is a direct policy query.")
3. Risk/Compliance Implication
4. Policy/Contract Reference(s)
   * Document name + Page + exact clause/table
5. Recommended Next Audit Step

Rules:
- Answer ONLY from the uploaded policy document.
- Never hallucinate or add information.
- Keep every section concise and audit-ready.
- Always end with "📚 Sources & References"
- Use bullet points only inside sections.
- Never add extra headings or explanations."""),
        ("human", """Context (most relevant pieces):
{context}

Question: {question}
Answer:""")
    ])
    return RAG_PROMPT | llm
# ====================== LLM Settings (use ctrl+l to commentout lines)======================
# FOR USING WITH ONLINE AI MODELS:
# def get_free_form_chain():  # FREE-FORM DISCUSSION MODE
#     llm = ChatGoogleGenerativeAI(
#         model="gemini-2.5-flash",
#         google_api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=0.0
#     )
# === LOCAL QWEN 3.5-9b (offline - secure) ========================================
def get_free_form_chain():  # FREE-FORM DISCUSSION MODE
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        base_url="http://127.0.0.1:1234/v1",
        api_key="lm-studio",
        model= "nvidia/nemotron-3-nano-4b", #"qwen/qwen3.5-9b", # exact name shown in LM Studio
        temperature=0.0,
        max_tokens=32000
    )
# =============================================================================================
    
    FREE_PROMPT = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are AI AUDIT BOT – an experienced internal auditor.
Answer questions concisely and directly. Use plain English. No fixed 5-section format unless asked.
Always end with "📚 Sources & References" if files / documents were used."""),
        ("human", """Context (most relevant pieces):
{context}

Question: {question}
Answer:""")
    ])
    return FREE_PROMPT | llm

def add_documents_from_upload(uploaded_file):  # PDF only
    from langchain_community.document_loaders import PyMuPDFLoader
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    loader = PyMuPDFLoader(tmp_path)
    docs = loader.load()
    get_vectorstore().add_documents(docs)
    os.unlink(tmp_path)
    return len(docs)

def add_documents_from_csv_or_excel(uploaded_file):  # SAP CSV/Excel support
    import tempfile
    import pandas as pd
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    df = pd.read_csv(tmp_path) if suffix == ".csv" else pd.read_excel(tmp_path)
    docs = [Document(page_content=row.to_string(), metadata={"source": uploaded_file.name, "row": i}) 
            for i, row in df.iterrows()]
    get_vectorstore().add_documents(docs)
    os.unlink(tmp_path)
    return len(docs)

# For dynamic RAG review of Vendor contracts terms violation under vendor anomaly detector:
def generate_rag_audit_report(flagged_transactions, contract_text=None, vendor_name=None):
    query = f"""
Generate full audit-ready executive summary for these flagged high-risk vendor payments:
{flagged_transactions}

Vendor: {vendor_name or 'Unknown'}
Include specific clause violations from any attached contract or policy documents.
Focus on related-party, payment terms, ageing, financial limits, and anomaly thresholds.
"""
    if contract_text:
        query += f"\n\nATTACHED VENDOR CONTRACT TEXT (analyse for violations):\n{contract_text[:12000]}"

    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    retrieved_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])

    chain = get_rag_chain()
    response = chain.invoke({"context": context, "question": query})

    audit_summary = response.content if hasattr(response, "content") else str(response)

    citations = []
    for doc in retrieved_docs:
        source = doc.metadata.get("source", "pgvector policy/contract")
        page = doc.metadata.get("page", "")
        citations.append(f"{source} (page {page})")

    log_hash = hashlib.sha256(audit_summary.encode()).hexdigest()[:16]

    return {
        "audit_summary": audit_summary,
        "citations": citations,
        "log_hash": log_hash
    }