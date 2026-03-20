# AI-RAG-BOT/src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
FAISS_PATH = BASE_DIR / "faiss_index"          # ← this folder will be created automatically

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

#LLM_PROVIDER = "anthropic"                     # change to "google" if you prefer Gemini
#LLM_MODEL = "claude-3-5-sonnet-20241022"

LLM_PROVIDER = "google"                     # change to "google" if you prefer Gemini
LLM_MODEL = "gemini-2.5-flash"