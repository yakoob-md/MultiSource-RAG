from dataclasses import dataclass
from backend.config import TOP_K
from backend.ingestion.embedder import embed_query
from backend.vectorstore.faiss_store import search_vectors
from backend.database.connection import get_connection
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
import torch

# ── Device detection ──────────────────────────────────────────────────────────
# Automatically uses your RTX 2050 GPU if CUDA is available,
# falls back to CPU silently if not. No manual configuration needed.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Retriever] Reranker device: {DEVICE}")

# ── Reranker model ────────────────────────────────────────────────────────────
# Loaded once at module import time so it is not reloaded on every query.
# cross-encoder/ms-marco-MiniLM-L-6-v2:
#   - Trained specifically for query-passage relevance scoring
#   - Small (22M params) → fast even on CPU, very fast on GPU
#   - Reads query AND passage together → much more accurate than embeddings alone
#   - Downloads automatically from HuggingFace on first run (~85 MB)
_reranker: CrossEncoder | None = None

def _get_reranker() -> CrossEncoder:
    """
    Lazy-load the cross-encoder reranker model.
    Loaded once and cached in the module-level _reranker variable.
    Uses GPU if available (set by DEVICE above).
    """
    global _reranker
    if _reranker is None:
        print(f"[Retriever] Loading reranker model onto {DEVICE} ...")
        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            device=DEVICE,
            max_length=512,   # max tokens per (query, passage) pair
        )
        print("[Retriever] Reranker ready.")
    return _reranker


@dataclass
class RetrievedChunk:
    """
    One retrieved chunk with everything the LLM and frontend need.

    Fields:
        chunk_id    : UUID of the chunk
        source_id   : UUID of the parent source
        source_type : "pdf" | "url" | "youtube"
        source_title: human readable name e.g. "attention.pdf"
        chunk_text  : the actual text content
        score       : final reranker score (higher = more relevant)
        page_number : PDF page number (None for url/youtube)
        timestamp_s : YouTube timestamp in seconds (None for pdf/url)
        url_ref     : source URL (None for pdf)
        language    : language code e.g. "en"
    """
    chunk_id    : str
    source_id   : str
    source_type : str
    source_title: str
    chunk_text  : str
    score       : float
    page_number : int   | None
    timestamp_s : int   | None
    url_ref     : str   | None
    language    : str


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    vector_hits : list[dict],
    bm25_hits   : list[dict],
    k           : int = 60,
) -> list[dict]:
    """
    Merge two ranked lists into one using Reciprocal Rank Fusion (RRF).

    Each candidate gets a score of 1/(k+rank) from each list.
    Candidates appearing in both lists accumulate scores from both.
    k=60 is the empirically validated default (Cormack et al. 2009).

    Args:
        vector_hits : ranked list from FAISS vector search
        bm25_hits   : ranked list from BM25 keyword search
        k           : RRF constant

    Returns:
        list of {"chunk_id": ..., "score": ...} sorted by RRF score descending
    """
    rrf_scores: dict[str, float] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        cid = hit["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)

    for rank, hit in enumerate(bm25_hits, start=1):
        cid = hit["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)

    merged = [
        {"chunk_id": cid, "score": score}
        for cid, score in rrf_scores.items()
    ]
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged


# ── BM25 search ───────────────────────────────────────────────────────────────

def _bm25_search(
    question      : str,
    candidate_rows: list[dict],
    top_k         : int,
) -> list[dict]:
    """
    Run BM25 keyword search over a set of candidate chunk rows.
    Runs in-memory on the candidate pool — no external service needed.

    Args:
        question       : the user's query string
        candidate_rows : list of MySQL row dicts with "chunk_id" and "chunk_text"
        top_k          : how many results to return

    Returns:
        list of {"chunk_id": ..., "score": ...} sorted by BM25 score descending
    """
    if not candidate_rows:
        return []

    import re
    def tokenise(text: str) -> list[str]:
        return re.findall(r'\b\w+\b', text.lower())

    corpus       = [tokenise(row["chunk_text"]) for row in candidate_rows]
    query_tokens = tokenise(question)

    bm25   = BM25Okapi(corpus)
    scores = bm25.get_scores(query_tokens)

    scored = [
        {"chunk_id": candidate_rows[i]["chunk_id"], "score": float(scores[i])}
        for i in range(len(candidate_rows))
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)

    hits = [s for s in scored if s["score"] > 0]
    return hits[:top_k]


# ── Cross-encoder reranker ────────────────────────────────────────────────────

def _rerank(
    question: str,
    chunks  : list[RetrievedChunk],
    top_n   : int,
) -> list[RetrievedChunk]:
    """
    Rerank a list of chunks using a cross-encoder model on GPU.

    How cross-encoder reranking differs from embedding-based retrieval:

        Bi-encoder (used for FAISS vector search):
            embed(query)  →  vector A
            embed(chunk)  →  vector B
            score = cosine(A, B)
            Query and chunk are encoded INDEPENDENTLY.
            Fast but less accurate — the model never sees them together.

        Cross-encoder (used here):
            score = model(query + [SEP] + chunk)
            Query and chunk are fed TOGETHER into the transformer.
            The model attends across both texts simultaneously.
            Much more accurate relevance judgment, slower but GPU helps.

    The retrieve-then-rerank pattern:
        1. Fast bi-encoder + BM25 retrieval gives ~24 candidates quickly
        2. Cross-encoder reranks those 24 candidates → returns best TOP_K
        Best accuracy of cross-encoder, speed of bi-encoder.

    On your RTX 2050:
        Scoring 24 (query, chunk) pairs takes ~50-150ms total.
        Model is loaded once and stays on GPU between queries.

    Args:
        question : the user's query string
        chunks   : candidate RetrievedChunk objects from hybrid search
        top_n    : how many to return after reranking

    Returns:
        list of RetrievedChunk reranked by cross-encoder score, length = top_n
    """
    if not chunks:
        return []

    reranker = _get_reranker()

    # Build (query, passage) pairs — exactly what the cross-encoder expects
    pairs = [(question, chunk.chunk_text) for chunk in chunks]

    # Score all pairs in one batched forward pass on GPU
    # show_progress_bar=False keeps server logs clean
    scores = reranker.predict(pairs, show_progress_bar=False)

    # Attach reranker scores and sort descending
    for chunk, score in zip(chunks, scores):
        chunk.score = float(score)

    chunks.sort(key=lambda x: x.score, reverse=True)

    return chunks[:top_n]


# ── Main retrieval function ───────────────────────────────────────────────────

def retrieve(question: str, source_ids: list[str] | None = None) -> list[RetrievedChunk]:
    """
    Full retrieval pipeline — hybrid search + GPU reranking:

    1. Embed the question into a vector
    2. Vector search via FAISS            → semantic candidates
    3. Fetch candidate pool from MySQL
    4. BM25 keyword search                → keyword candidates
    5. Reciprocal Rank Fusion             → merged ~24 candidates
    6. Cross-encoder reranking on GPU     → precise top TOP_K
    7. Return final TOP_K RetrievedChunk objects to the generator

    Args:
        question   : the user's question string
        source_ids : optional list of source UUIDs to restrict search to

    Returns:
        list of RetrievedChunk ordered by reranker score (highest first)
    """
    # Candidate pool for BM25 + RRF before reranking
    CANDIDATE_POOL_SIZE = TOP_K * 8

    # How many RRF results to pass into the reranker
    # Reranker evaluates 3x TOP_K candidates, selects the best TOP_K
    RERANK_POOL = TOP_K * 3

    # ── Step 1: Embed the question ────────────────────────────────────────────
    query_vector = embed_query(question)

    # ── Step 2: Vector search — fetch large pool ──────────────────────────────
    fetch_k  = CANDIDATE_POOL_SIZE * 5 if source_ids else CANDIDATE_POOL_SIZE
    raw_hits = search_vectors(query_vector, top_k=fetch_k)

    if not raw_hits:
        return []

    # ── Step 3: Fetch chunk details from MySQL ────────────────────────────────
    chunk_ids    = [hit["chunk_id"] for hit in raw_hits]
    placeholders = ", ".join(["%s"] * len(chunk_ids))

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT
                c.id            AS chunk_id,
                c.source_id,
                c.chunk_text,
                c.page_number,
                c.timestamp_s,
                c.url_ref,
                s.type          AS source_type,
                s.title         AS source_title,
                s.language
            FROM chunks c
            JOIN sources s ON s.id = c.source_id
            WHERE c.id IN ({placeholders})
        """, chunk_ids)

        candidate_rows = cursor.fetchall()

    if not candidate_rows:
        return []

    # ── Step 4: Filter by source_ids if specified ─────────────────────────────
    if source_ids:
        candidate_rows = [r for r in candidate_rows if r["source_id"] in source_ids]

    if not candidate_rows:
        return []

    # ── Step 5: BM25 keyword search over the candidate pool ───────────────────
    surviving_ids        = {r["chunk_id"] for r in candidate_rows}
    vector_hits_filtered = [h for h in raw_hits if h["chunk_id"] in surviving_ids]

    bm25_hits = _bm25_search(question, candidate_rows, top_k=CANDIDATE_POOL_SIZE)

    # ── Step 6: Reciprocal Rank Fusion → top RERANK_POOL candidates ───────────
    fused = _reciprocal_rank_fusion(vector_hits_filtered, bm25_hits)
    fused = fused[:RERANK_POOL]

    # ── Step 7: Build RetrievedChunk objects for the reranker ─────────────────
    row_map = {row["chunk_id"]: row for row in candidate_rows}

    pre_rerank_chunks = []
    for hit in fused:
        cid = hit["chunk_id"]
        if cid not in row_map:
            continue
        row = row_map[cid]
        pre_rerank_chunks.append(RetrievedChunk(
            chunk_id    = row["chunk_id"],
            source_id   = row["source_id"],
            source_type = row["source_type"],
            source_title= row["source_title"],
            chunk_text  = row["chunk_text"],
            score       = hit["score"],   # RRF score — replaced by reranker below
            page_number = row["page_number"],
            timestamp_s = row["timestamp_s"],
            url_ref     = row["url_ref"],
            language    = row["language"],
        ))

    # ── Step 8: Cross-encoder reranking on GPU ────────────────────────────────
    # Scores the RERANK_POOL candidates with full query-passage attention,
    # returns only the best TOP_K with reranker scores attached
    final_chunks = _rerank(question, pre_rerank_chunks, top_n=TOP_K)

    return final_chunks