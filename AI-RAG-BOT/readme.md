User (Streamlit chat UI)
       ↓ query + optional uploaded PO/invoice PDF
       ↓
Router / Guardrail (simple LangChain chain or LangGraph node)
       ↓
Retriever ← Vector Store (Chroma / FAISS local or Pinecone free tier)
       ↑     ↑
       |     Embeddings (sentence-transformers/all-MiniLM-L6-v2 or voyage-lite-02-instruct free tier)
       |     ↑
       Documents (SOPs, GST circulars, vendor contracts, procurement policy PDFs)
             ↓
             Chunking + Metadata (RecursiveCharacterTextSplitter + source/page metadata)
                   ↓
LLM call (Claude 3.5 Sonnet / Gemini 1.5 Flash / Grok / Llama 3.1 70B via Groq free tier)
       ↓
Answer + Citations + Confidence score + Follow-up suggestions
       ↓
Streamlit response (streaming + sources expandable)

ai-procurement-rag-bot/                  ← new repo or new folder in existing portfolio repo
├── app.py                               ← main Streamlit entry point
├── requirements.txt
├── .env                                 ← gitignore this!
├── .streamlit/
│   └── config.toml                      ← theme, server settings
├── src/
│   ├── __init__.py
│   ├── config.py                        ← constants, paths, model names
│   ├── document_processor.py            ← PDF loading, chunking, metadata
│   ├── embedding.py                     ← embedding model init & caching
│   ├── vectorstore.py                   ← Chroma/FAISS create/load/upsert
│   ├── retrieval_chain.py               ← basic RAG chain
│   ├── agent.py                         ← LangGraph agent (optional phase 2)
│   └── prompts.py                       ← all system/user prompts here
├── data/
│   ├── raw/                             ← put your real PDFs here (gitignore large files)
│   └── processed/                       ← optional: chunked json dumps
├── chroma_db/                           ← Chroma persistent folder (gitignore or .dockerignore)
├── notebooks/                           ← Jupyter for experiments (gitignore)
│   └── 01_ingest_and_test.ipynb
└── README.md                            ← how to run, architecture diagram, screenshots