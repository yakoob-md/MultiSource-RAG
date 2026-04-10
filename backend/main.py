from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.api.sources import router as sources_router
from backend.api.upload  import router as upload_router
from backend.api.query   import router as query_router
from backend.api.history import router as history_router
from backend.api.stream  import router as stream_router
from backend.ingestion.embedder import get_model as preload_embedder
from backend.rag.retriever import _get_reranker as preload_reranker

import asyncio

def _load_models(app: FastAPI):
    print("[Startup] ✨ Thread loading heavy ML models into memory... This might take ~5-15 seconds.")
    preload_embedder()
    preload_reranker()
    print("[Startup] 🚀 Models fully loaded! Ready for blazing-fast queries.")
    app.state.models_ready.set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.models_ready = asyncio.Event()
    # Offload the blocking CPU/disk work so FastAPI doesn't freeze the frontend
    asyncio.create_task(asyncio.to_thread(_load_models, app))
    yield

app = FastAPI(title="UMKA RAG System", version="2.0.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows the React frontend on port 5173 to talk to this backend on port 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(sources_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(history_router)
app.include_router(stream_router)



@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}