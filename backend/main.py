from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.sources import router as sources_router
from backend.api.upload  import router as upload_router
from backend.api.query   import router as query_router
from backend.api.history import router as history_router

app = FastAPI(title="UMKA RAG System", version="2.0.0")

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


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}