# backend/main.py — FIXED VERSION
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
from backend.api.image_routes import router as image_router
from backend.api.legal_query_routes import router as legal_query_router

from backend.ingestion.embedder import get_model as preload_embedder
from backend.rag.retriever import _get_reranker as preload_reranker
from backend.core.llm_provider import llm_provider
from backend.config import LEGAL_MODEL_MODE

def _load_models(app: FastAPI):
    print("[Startup] Loading ML models...")
    try:
        preload_embedder()
        preload_reranker()
        
        # Only preload local LLM if explicitly requested, to avoid OOM on startup
        if LEGAL_MODEL_MODE == "local":
             print("[Startup] Preloading Local LLM (this may take a minute)...")
             # We use lazy loading inside llm_provider, 
             # but we can trigger it here if we want immediate readiness.
             # However, for RTX 2050 (4GB), it's safer to load on first use.
             pass 
             
        print("[Startup] Models ready.")
    except Exception as e:
        print(f"[Startup] Model load failed: {e}")
    finally:
        app.state.models_ready.set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models_ready = asyncio.Event()
    asyncio.create_task(asyncio.to_thread(_load_models, app))
    yield

app = FastAPI(
    title="UMKA RAG System",
    version="2.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Core routes (no prefix) ───────────────────────────────────────────────────
app.include_router(sources_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(history_router)
app.include_router(stream_router)

# ── Legal routes under /legal prefix ─────────────────────────────────────────
# This fixes the 404 on /legal/legal-sources that the frontend expects
app.include_router(legal_router,       prefix="/legal", tags=["legal"])
app.include_router(legal_query_router, tags=["legal"])   # /legal-query stays at root

# ── Image routes under /images prefix ────────────────────────────────────────
app.include_router(image_router, prefix="/images", tags=["images"])

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "2.2.0",
        "models_ready": app.state.models_ready.is_set()
    }