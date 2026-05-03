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
MODELS_DIR      = BASE_DIR / "models"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FAISS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

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
# The ms-marco cross-encoder outputs raw logits (not probabilities).
# Negative scores are NORMAL and do NOT mean irrelevant.
# -12.0 is a safe floor — anything below this is genuinely unrelated noise.
# Previous value of -5.0 was killing valid cryptography/technical content.
RERANKER_SCORE_THRESHOLD = -12.0  # drop chunks scoring below this
TOP_K = 8
# If a source returns 0 chunks after threshold, take this many anyway (best-effort)
RERANKER_FALLBACK_TOP_N = 2

# ── LLM (Groq) ───────────────────────────────────────────────────────────────
# Load the key from the environment. Will raise an error later if blank.
GROQ_API_KEY    = os.getenv("GROQ_API_KEY") 
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_CLASSIFIER_MODEL = "llama-3.1-8b-instant"  # Faster, higher rate limits for classification
GROQ_TIMEOUT    = 30

# ── Fine-Tuned Model (Hybrid: Local/HF) ──────────────────────────────────────
# Set to "local" to run on your PC, or "huggingface" to use cloud inference
LEGAL_MODEL_MODE    = "huggingface" 
LEGAL_MODEL_PATH    = MODELS_DIR / "legal_model_lora"
BASE_MODEL_NAME     = "unsloth/Meta-Llama-3.1-8B-bnb-4bit"

# Hugging Face Inference API (for legal or image models)
HF_API_KEY          = os.getenv("HF_API_KEY")
HF_LEGAL_MODEL_ID   = "yakub-md/legal-rag-final"
HF_IMAGE_MODEL_ID   = "Salesforce/blip-image-captioning-large"

# ── Ollama (Local API) ───────────────────────────────────────────────────────
OLLAMA_BASE_URL      = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME    = os.getenv("OLLAMA_MODEL_NAME", "legal-model")

def verify_config():
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        print(f"[Config] WARNING: Missing env vars: {missing}")
        print("[Config] Copy backend/.env.example to backend/.env and fill values")
    else:
        print("[Config] All required env vars present")

# Call verify_config() at module load time.
verify_config()
