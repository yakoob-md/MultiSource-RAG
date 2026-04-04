import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load Environment Variables ───────────────────────────────────────────────
# This looks for a .env file in the same directory or parent directories 
# and loads the variables into the system environment
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── Root Paths ───────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent.parent
DATA_DIR        = BASE_DIR / "data"
UPLOAD_DIR      = DATA_DIR / "uploaded_files"
FAISS_DIR       = DATA_DIR / "faiss_index"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FAISS_DIR.mkdir(parents=True, exist_ok=True)

# ── MySQL ─────────────────────────────────────────────────────────────────────
# Replace hardcoded strings with os.getenv. Provide fallbacks if desired.
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 3306))
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mysql")
DB_NAME     = os.getenv("DB_NAME", "rag_system")

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIM   = 1024

# ── FAISS ─────────────────────────────────────────────────────────────────────
FAISS_INDEX_PATH  = FAISS_DIR / "index.faiss"
FAISS_IDMAP_PATH  = FAISS_DIR / "id_map.json"

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K = 8

# ── LLM (Groq) ───────────────────────────────────────────────────────────────
# Load the key from the environment. Will raise an error later if blank.
GROQ_API_KEY    = os.getenv("GROQ_API_KEY") 
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_TIMEOUT    = 30
