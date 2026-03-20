# AI-RAG-BOT/app.py
import streamlit as st
import json
import os
from datetime import datetime
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

#from langchain_google_genai import ChatGoogleGenerativeAI
#from langchain_anthropic import ChatAnthropic

os.environ["LANGCHAIN_TRACING_V2"] = "false"       # comment out while using online AI Model
os.environ["LANGCHAIN_API_KEY"] = "dummy"           # prevents any accidental trace, comment out while using online AI Model
from langchain_openai import ChatOpenAI             # comment out while using online AI Model

from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

load_dotenv()

st.set_page_config(page_title="AI Policy RAG Bot", page_icon="📋", layout="wide")
st.title("          📋 AI AUDIT BOT          ")
st.caption("A Continuous Control Monitoring + Policy Compliance Agent — 100% Automated + 100% Private running locally + Audit Compliant - Built by Ashok Kumar Sharma")

# ====================== CONFIG & LOAD VECTOR STORE ======================
@st.cache_resource
def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

vectorstore = load_vectorstore()

# ====================== LLM Settings (use ctrl+l to commentout lines)======================
# llm = ChatGoogleGenerativeAI(
#    model="gemini-2.5-flash",
#    google_api_key=os.getenv("GOOGLE_API_KEY"),
#    temperature=0.0
# )

# ────────────────────────────────────────────────
# Add / replace with this block
# ────────────────────────────────────────────────
# --------------------------------------------------------------
llm = ChatOpenAI(
    base_url="http://127.0.0.1:1234/v1",          # ← LM Studio default
    api_key="lm-studio",                          # dummy key – LM Studio ignores it
    model="bartowski-qwen_qwen3.5-9b",                  # ← use the exact name/tag shown in LM Studio
    temperature=0.0,
    max_tokens=4096,                              # adjust depending on your needs
    # Optional but useful for audit-style strictness
    extra_body={"presence_penalty": 0.0, "frequency_penalty": 0.0}
)

# ------------------------------------------------------------------------
#llm = ChatAnthropic(
#    model="claude-3-5-sonnet-20241022",
#    temperature=0,
#    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
#)

# ====================== PROMPT ======================
from src.prompts import RAG_PROMPT

# ====================== DIRECTORIES & HISTORY ======================
SAVED_CHATS_DIR = "saved_chats"
os.makedirs(SAVED_CHATS_DIR, exist_ok=True)

CURRENT_CHAT_FILE = "current_chat.json"

def load_current_chat():
    if os.path.exists(CURRENT_CHAT_FILE):
        with open(CURRENT_CHAT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_current_chat(messages):
    with open(CURRENT_CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = load_current_chat()
if "chat_title" not in st.session_state:
    st.session_state.chat_title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"

# ====================== EXPORT TO PDF ======================
def generate_pdf(messages, title="Conversation"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"AI Procurement RAG Bot - {title}")
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 40

    for msg in messages:
        role = "User" if msg["role"] == "user" else "Bot"
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"{role}:")
        y -= 20
        c.setFont("Helvetica", 10)
        text = msg["content"].replace("\n", " ").strip()
        text_lines = [text[i:i+90] for i in range(0, len(text), 90)]
        for line in text_lines:
            if y < 50:
                c.showPage()
                y = height - 50
            c.drawString(70, y, line)
            y -= 15
        y -= 20

    c.save()
    buffer.seek(0)
    return buffer

# ====================== SIDEBAR – CONTROLS & SEARCH ======================
with st.sidebar:
    st.header("Chat Controls")

    # New Conversation
    if st.button("➕ New Conversation"):
        # Auto-save current one
        if st.session_state.messages:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_{timestamp}.json"
            path = os.path.join(SAVED_CHATS_DIR, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
            st.success(f"Old chat auto-saved as {filename}")

        # Start fresh
        st.session_state.messages = []
        st.session_state.chat_title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        save_current_chat(st.session_state.messages)
        st.rerun()

    # Clear current
    if st.button("🗑️ Clear Current Chat"):
        st.session_state.messages = []
        save_current_chat(st.session_state.messages)
        st.rerun()

    # Export PDF
    if st.button("📥 Export Current Chat to PDF"):
        pdf_buffer = generate_pdf(st.session_state.messages, st.session_state.chat_title)
        st.download_button(
            label="Download PDF",
            data=pdf_buffer,
            file_name=f"{st.session_state.chat_title.replace(' ', '_')}.pdf",
            mime="application/pdf",
            key="pdf_download"
        )

    # Saved chats list
    saved_files = sorted([f for f in os.listdir(SAVED_CHATS_DIR) if f.endswith(".json")], reverse=True)
    if saved_files:
        st.subheader("Saved Conversations")
        selected = st.selectbox("Load saved chat", ["None"] + saved_files)
        if selected != "None" and st.button("Load"):
            path = os.path.join(SAVED_CHATS_DIR, selected)
            with open(path, "r", encoding="utf-8") as f:
                st.session_state.messages = json.load(f)
            st.session_state.chat_title = selected.replace(".json", "")
            save_current_chat(st.session_state.messages)
            st.rerun()

    # Search in history
    st.subheader("Search Chat History")
    search_term = st.text_input("Search questions & answers", "")
    if search_term:
        matches = []
        for msg in st.session_state.messages + load_current_chat():
            if search_term.lower() in msg["content"].lower():
                role = "User" if msg["role"] == "user" else "Bot"
                matches.append(f"**{role}**: {msg['content'][:120]}...")
        if matches:
            st.write("Found matches:")
            for m in matches[:10]:
                st.markdown(m)
        else:
            st.info("No matches found")

# ====================== MAIN CHAT DISPLAY ======================
st.markdown(f"**Active Chat:** {st.session_state.chat_title}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ====================== FILE UPLOAD ======================
st.subheader("Optional: Upload PO / Invoice / Document")
uploaded_doc = st.file_uploader("Upload PDF", type=["pdf"], help="Ask questions about this file")

uploaded_text = ""
if uploaded_doc:
    with st.spinner("Processing..."):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_doc.getvalue())
            tmp_path = tmp.name

        try:
            from langchain_community.document_loaders import PyMuPDFLoader
            loader = PyMuPDFLoader(tmp_path)
            docs = loader.load()
            uploaded_text = "\n\n".join(d.page_content for d in docs)
            st.success(f"Processed '{uploaded_doc.name}' ({len(docs)} pages)")
        finally:
            os.unlink(tmp_path)

# ====================== CHAT INPUT ======================
if prompt := st.chat_input("Ask about policy, clause, contract..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching..."):
            docs = vectorstore.similarity_search(prompt, k=5)
            context = "\n\n---\n\n".join(
                f"Document: {d.metadata.get('source_file')}\nPage {d.metadata.get('page', '?')}\n\n{d.page_content}"
                for d in docs
            )

            if uploaded_text:
                context += f"\n\n--- Uploaded Document ---\n{uploaded_text[:4000]}"

            chain = RAG_PROMPT | llm
            response = chain.invoke({"context": context, "question": prompt})

            st.markdown(response.content)

            with st.expander("📚 Sources & References"):
                for i, doc in enumerate(docs, 1):
                    st.markdown(f"**{i}.** {doc.metadata.get('source_file')} | Page {doc.metadata.get('page', '?')}")

    st.session_state.messages.append({"role": "assistant", "content": response.content})
    save_current_chat(st.session_state.messages)