import os
import hashlib
from pathlib import Path
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
#from langchain_google_genai import ChatGoogleGenerativeAI
os.environ["LANGCHAIN_TRACING_V2"] = "false"       # comment out while using online AI Model
os.environ["LANGCHAIN_API_KEY"] = "dummy"           # prevents any accidental trace, comment out while using online AI Model
from langchain_openai import ChatOpenAI             # comment out while using online AI Model
from langchain_community.chat_models import ChatOpenAI
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

def _get_vectorstore_safe():
    """Returns (vectorstore, error_message). error_message is None on success."""
    try:
        return get_vectorstore(), None
    except Exception as e:
        return None, str(e)

def get_rag_chain():
    llm = ChatOpenAI(
        base_url="http://127.0.0.1:8080/v1",
        api_key="llama.cpp",
        model="NVIDIA-Nemotron-3-Nano-4B-Q4_K_M",
        temperature=0.7,
        max_tokens=2048,
        timeout=120,
        max_retries=1,
    )
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

def get_free_form_chain():
    llm = ChatOpenAI(
        base_url="http://127.0.0.1:8080/v1",
        api_key="llama.cpp",
        model="NVIDIA-Nemotron-3-Nano-4B-Q4_K_M",
        temperature=0.7,
        max_tokens=2048,
        timeout=120,
        max_retries=1,
    )
    FREE_PROMPT = ChatPromptTemplate.from_messages([
        SystemMessage(content="""You are AI AUDIT BOT – a senior internal auditor with 17+ years FMCG experience.
Answer questions concisely and directly. Use plain English. No fixed 5-section format unless asked.
Always end with "📚 Sources & References" if documents were used."""),
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

def add_documents_from_csv_or_excel_or_office(uploaded_file):  # CSV, XLSX, DOCX, PPTX
    import tempfile
    suffix = Path(uploaded_file.name).suffix.lower()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        if suffix in [".csv", ".xlsx"]:
            import pandas as pd
            df = pd.read_csv(tmp_path) if suffix == ".csv" else pd.read_excel(tmp_path)
            docs = [Document(page_content=row.to_string(), metadata={"source": uploaded_file.name, "row": i}) 
                    for i, row in df.iterrows()]
        elif suffix == ".docx":
            import docx2txt
            text = docx2txt.process(tmp_path)
            docs = [Document(page_content=text, metadata={"source": uploaded_file.name})]
        elif suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(tmp_path)
            text = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            docs = [Document(page_content=text, metadata={"source": uploaded_file.name})]
        else:
            docs = []

        get_vectorstore().add_documents(docs)
        return len(docs)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

def generate_rag_audit_report(flagged_transactions, contract_text=None, vendor_name=None):
    # Cap payload to top 15 rows to avoid overwhelming the local model context
    sample = flagged_transactions[:15] if isinstance(flagged_transactions, list) else flagged_transactions

    query = f"""
Generate full audit-ready executive summary for these flagged high-risk vendor payments:
{sample}

Vendor: {vendor_name or 'Unknown'}
Include specific clause violations from any attached contract or policy documents.
Focus on related-party, payment terms, ageing, financial limits, and anomaly thresholds.
"""
    if contract_text:
        query += f"\n\nATTACHED VENDOR CONTRACT TEXT (analyse for violations):\n{contract_text[:4000]}"

    vectorstore, db_error = _get_vectorstore_safe()
    if vectorstore is None:
        return {
            "audit_summary": f"⚠️ **Policy database unavailable** — could not connect to Neon.\n\n`{db_error}`\n\nCheck your internet connection or verify the Neon project is active.",
            "citations": [],
            "log_hash": "offline",
        }
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    retrieved_docs = retriever.invoke(query[:1000])  # use short search query for retrieval
    context = "\n\n".join([doc.page_content[:500] for doc in retrieved_docs])

    try:
        chain = get_rag_chain()
        response = chain.invoke({"context": context, "question": query})
    except Exception as e:
        return {
            "audit_summary": f"⚠️ **LLM call failed** — local model did not respond.\n\n`{e}`\n\nEnsure llama.cpp is running on `http://127.0.0.1:8080` and the model is loaded.",
            "citations": [],
            "log_hash": "llm-error",
        }

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