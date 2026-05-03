from dataclasses import dataclass
from backend.config import TOP_K, RERANKER_SCORE_THRESHOLD, RERANKER_FALLBACK_TOP_N
from backend.ingestion.embedder import embed_query
from backend.vectorstore.faiss_store import search_vectors
from backend.database.connection import get_connection
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
import torch

# ── Device detection ──────────────────────────────────────────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Retriever] Reranker device: {DEVICE}")

# ── Reranker model ────────────────────────────────────────────────────────────
_reranker: CrossEncoder | None = None

def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"[Retriever] Loading reranker model onto {DEVICE} ...")
        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            device=DEVICE,
            max_length=512,
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
    Merge two ranked lists using Reciprocal Rank Fusion (RRF).
    k=60 is the empirically validated default (Cormack et al. 2009).
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
    """Run BM25 keyword search over a set of candidate chunk rows."""
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
    Rerank candidates using a cross-encoder model.
    Query and chunk are fed TOGETHER — much more accurate than embedding similarity.
    """
    if not chunks:
        return []

    reranker = _get_reranker()
    pairs = [(question, chunk.chunk_text) for chunk in chunks]
    scores = reranker.predict(pairs, show_progress_bar=False)

    for chunk, score in zip(chunks, scores):
        chunk.score = float(score)

    chunks.sort(key=lambda x: x.score, reverse=True)
    return chunks[:top_n]


# ── Main retrieval function ───────────────────────────────────────────────────

def retrieve(
    question   : str,
    source_ids : list[str] | None = None,
    min_chunks : int = 0,
) -> list[RetrievedChunk]:
    """
    Full retrieval pipeline — hybrid search + GPU reranking:

    1. Embed the question into a vector
    2. Vector search via FAISS              (large pool, bigger when source-filtered)
    3. Fetch chunk details from MySQL
    4. BM25 keyword search
    5. Reciprocal Rank Fusion              → merged candidates
    6. Cross-encoder reranking on GPU
    7. Threshold filter with fallback      → guaranteed min_chunks

    Args:
        question   : user's question string
        source_ids : optional list of source UUIDs to restrict search to
        min_chunks : if > 0 and threshold kills everything, return at least
                     min_chunks results anyway (prevents silent source skips)

    Returns:
        list of RetrievedChunk ordered by reranker score (highest first)
    """
    CANDIDATE_POOL_SIZE = TOP_K * 8
    RERANK_POOL = TOP_K * 3

    # ── Step 1: Embed the question ────────────────────────────────────────────
    try:
        query_vector = embed_query(question)
    except Exception as e:
        print(f"[Retriever] Error embedding query: {e}")
        return []

    # ── Step 2: FAISS vector search ───────────────────────────────────────────
    # When filtering by source, we must fetch MANY more vectors from the global
    # index because the relevant chunks for a small source (80 chunks) may be
    # ranked anywhere among 6000+ total vectors.
    # Strategy: fetch at least 600 per source_id, up to 3000 total.
    try:
        if source_ids:
            fetch_k = min(max(len(source_ids) * 600, 1200), 3000)
            print(f"[Retriever] Source-filtered fetch: {fetch_k} vectors for {len(source_ids)} source(s)")
        else:
            fetch_k = CANDIDATE_POOL_SIZE
        raw_hits = search_vectors(query_vector, top_k=fetch_k)
    except Exception as e:
        print(f"[Retriever] Error in FAISS search: {e}")
        return []

    if not raw_hits:
        return []

    # ── Step 3: Fetch chunk details from MySQL ────────────────────────────────
    try:
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
    except Exception as e:
        print(f"[Retriever] Error fetching from MySQL: {e}")
        return []

    if not candidate_rows:
        return []

    # ── Step 4: Filter by source_ids ─────────────────────────────────────────
    if source_ids:
        source_id_set = set(source_ids)
        candidate_rows = [r for r in candidate_rows if r["source_id"] in source_id_set]
        print(f"[Retriever] After source filter: {len(candidate_rows)} candidate rows")

    if not candidate_rows:
        return []

    # ── Step 5: BM25 keyword search ───────────────────────────────────────────
    try:
        surviving_ids        = {r["chunk_id"] for r in candidate_rows}
        vector_hits_filtered = [h for h in raw_hits if h["chunk_id"] in surviving_ids]
        bm25_hits = _bm25_search(question, candidate_rows, top_k=CANDIDATE_POOL_SIZE)
    except Exception as e:
        print(f"[Retriever] Error in BM25 search: {e}")
        bm25_hits = []
        vector_hits_filtered = [h for h in raw_hits if h["chunk_id"] in surviving_ids]

    # ── Step 6: Reciprocal Rank Fusion ────────────────────────────────────────
    try:
        fused = _reciprocal_rank_fusion(vector_hits_filtered, bm25_hits)
        fused = fused[:RERANK_POOL]
    except Exception as e:
        print(f"[Retriever] Error in RRF fusion: {e}")
        return []

    # ── Step 7: Build RetrievedChunk objects ──────────────────────────────────
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
            score       = hit["score"],
            page_number = row["page_number"],
            timestamp_s = row["timestamp_s"],
            url_ref     = row["url_ref"],
            language    = row["language"],
        ))

    # ── Step 8: Cross-encoder reranking ───────────────────────────────────────
    try:
        final_chunks = _rerank(question, pre_rerank_chunks, top_n=TOP_K)
        for c in final_chunks:
            print(f"[Retriever] Chunk {c.chunk_id[:8]} rerank score: {c.score:.4f}")
    except Exception as e:
        print(f"[Retriever] Error in cross-encoder reranking: {e}")
        return pre_rerank_chunks[:TOP_K]

    # ── Step 9: Threshold filter + guaranteed minimum fallback ────────────────
    passing = [c for c in final_chunks if c.score >= RERANKER_SCORE_THRESHOLD]
    if passing:
        return passing

    # Fallback: the threshold killed everything (common with pronoun queries or
    # vague wording). Return the top few anyway so the source isn't silently
    # dropped — the LLM will handle weak context gracefully.
    effective_fallback = max(min_chunks, RERANKER_FALLBACK_TOP_N if source_ids else 0)
    if effective_fallback > 0 and final_chunks:
        print(
            f"[Retriever] ⚠ All chunks below threshold ({RERANKER_SCORE_THRESHOLD}). "
            f"Fallback: returning top {effective_fallback} "
            f"(best={final_chunks[0].score:.4f}, source_ids={source_ids})"
        )
        return final_chunks[:effective_fallback]

    return []