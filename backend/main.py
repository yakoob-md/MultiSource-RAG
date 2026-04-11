import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.sources import router as sources_router
from backend.api.upload  import router as upload_router
from backend.api.query   import router as query_router
from backend.api.history import router as history_router
from backend.api.stream  import router as stream_router
from backend.api.legal_routes import router as legal_router

from backend.ingestion.embedder import get_model as preload_embedder
from backend.rag.retriever import _get_reranker as preload_reranker

# ── Model Pre-loading ──────────────────────────────────────────────────────────

def _load_models(app: FastAPI):
    """
    Load heavy ML models in a separate thread during startup so that the
    FastAPI worker remains responsive for high-level setup.
    """
    print("[Startup] ✨ Thread loading heavy ML models into memory... This might take ~5-15 seconds.")
    try:
        preload_embedder()
        preload_reranker()
        print("[Startup] 🚀 Models fully loaded! Ready for blazing-fast queries.")
    except Exception as e:
        print(f"[Startup] ❌ Model loading failed: {e}")
    finally:
        app.state.models_ready.set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state
    app.state.models_ready = asyncio.Event()
    # Offload the blocking CPU/disk work so FastAPI doesn't freeze
    asyncio.create_task(asyncio.to_thread(_load_models, app))
    yield

# ── App Initialization ─────────────────────────────────────────────────────────

app = FastAPI(
    title="UMKA RAG System",
    description="Advanced RAG system for Multi-Source Information Retrieval (PDF, Web, YouTube, Legal)",
    version="2.1.0",
    lifespan=lifespan
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router Registration ───────────────────────────────────────────────────────

app.include_router(sources_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(history_router)
app.include_router(stream_router)
app.include_router(legal_router)

# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "version": "2.1.0",
        "models_ready": app.state.models_ready.is_set()
    }