import os
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

from langchain_google_genai import ChatGoogleGenerativeAI
#from langchain_anthropic import ChatAnthropic

# os.environ["LANGCHAIN_TRACING_V2"] = "false"       # comment out while using online AI Model
# os.environ["LANGCHAIN_API_KEY"] = "dummy"           # prevents any accidental trace, comment out while using online AI Model
# from langchain_openai import ChatOpenAI             # comment out while using online AI Model

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vectorstore():
    return PGVector(
        embeddings=embeddings,
        collection_name="audit_policies",
        connection=os.getenv("NEON_CONNECTION_STRING"),
        use_jsonb=True
    )

# ====================== LLM Settings (use ctrl+l to commentout lines)======================
# FOR USING WITH OFFLINE AI MODELS:
# def get_rag_chain():
#     # === GEMINI (online - default) ===
#     # llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.0)

#     # === LOCAL QWEN 3.5-9b (offline - secure) ===
#     from langchain_openai import ChatOpenAI
#     llm = ChatOpenAI(
#         base_url="http://127.0.0.1:1234/v1",
#         api_key="lm-studio",
#         model="bartowski-qwen_qwen3.5-9b",   # exact name shown in LM Studio
#         temperature=0.0,
#         max_tokens=4096
#     )

#     RAG_PROMPT = ChatPromptTemplate.from_messages([ ... ])   # keep the same prompt above
#     return RAG_PROMPT | llm
#--------------------------------------------------------------------------------------------------
# FOR USING WITH ONLINE AI MODELS:
def get_rag_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0
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

def add_documents_from_upload(uploaded_file):
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