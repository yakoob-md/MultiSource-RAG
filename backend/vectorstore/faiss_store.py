import json
import numpy as np
import faiss
from pathlib import Path
from backend.config import FAISS_INDEX_PATH, FAISS_IDMAP_PATH, EMBEDDING_DIM


# ── Internal state ────────────────────────────────────────────────────────────
# _index    : the FAISS index object (holds all vectors)
# _id_map   : list of chunk UUIDs in the same order as vectors in the index
#             index position 0 → _id_map[0] = "uuid-of-chunk-0"
_index: faiss.IndexFlatIP | None = None
_id_map: list[str] = []


def _get_index() -> faiss.IndexFlatIP:
    """
    Load the FAISS index from disk if it exists, otherwise create a new one.
    IndexFlatIP = Inner Product search (works with normalized vectors = cosine similarity)
    """
    global _index, _id_map

    if _index is not None:
        return _index

    if Path(FAISS_INDEX_PATH).exists():
        print("[FAISS] Loading existing index from disk...")
        _index = faiss.read_index(str(FAISS_INDEX_PATH))
        with open(FAISS_IDMAP_PATH, "r") as f:
            _id_map = json.load(f)
        print(f"[FAISS] Loaded {len(_id_map)} vectors")
    else:
        print(f"[FAISS] WARNING: No index found at {FAISS_INDEX_PATH}. Ingest documents first.")
        print("[FAISS] Creating new empty index...")
        _index = faiss.IndexFlatIP(EMBEDDING_DIM)
        _id_map = []

    return _index


def _save():
    """Persist index and id_map to disk after every write operation."""
    faiss.write_index(_index, str(FAISS_INDEX_PATH))
    with open(FAISS_IDMAP_PATH, "w") as f:
        json.dump(_id_map, f)


def add_vectors(chunk_ids: list[str], vectors: list[list[float]]):
    """
    Add new vectors to the FAISS index.

    Args:
        chunk_ids : list of chunk UUIDs (same order as vectors)
        vectors   : list of embedding vectors
    """
    global _id_map

    index = _get_index()
    matrix = np.array(vectors, dtype=np.float32)
    index.add(matrix)
    _id_map.extend(chunk_ids)
    _save()
    print(f"[FAISS] Added {len(chunk_ids)} vectors. Total: {len(_id_map)}")


def search_vectors(query_vector: list[float], top_k: int) -> list[dict]:
    """
    Search for the most similar vectors to the query.

    Args:
        query_vector : embedding of the user's question
        top_k        : number of results to return

    Returns:
        list of dicts with chunk_id and similarity score
        e.g. [{"chunk_id": "uuid-...", "score": 0.92}, ...]
    """
    index = _get_index()

    if index.ntotal == 0:
        return []

    query = np.array([query_vector], dtype=np.float32)
    scores, positions = index.search(query, min(top_k, index.ntotal))

    results = []
    for score, pos in zip(scores[0], positions[0]):
        if pos == -1:           # FAISS returns -1 for empty slots
            continue
        results.append({
            "chunk_id": _id_map[pos],
            "score": float(score)
        })

    return results


def delete_vectors(chunk_ids: set[str]):
    """
    Remove vectors for a specific source from the index.
    FAISS doesn't support direct deletion, so we rebuild the index
    keeping only the vectors whose IDs are NOT in chunk_ids.

    Args:
        chunk_ids : set of chunk UUIDs to delete
    """
    global _index, _id_map

    index = _get_index()

    if index.ntotal == 0:
        return

    # Collect all existing vectors
    all_vectors = faiss.rev_swig_ptr(index.get_xb(), index.ntotal * EMBEDDING_DIM)
    all_vectors = np.array(all_vectors, dtype=np.float32).reshape(index.ntotal, EMBEDDING_DIM)

    # Keep only vectors whose IDs are not being deleted
    keep_indices = [i for i, cid in enumerate(_id_map) if cid not in chunk_ids]

    if not keep_indices:
        # All vectors deleted — reset to empty
        _index = faiss.IndexFlatIP(EMBEDDING_DIM)
        _id_map = []
    else:
        kept_vectors = all_vectors[keep_indices]
        new_index = faiss.IndexFlatIP(EMBEDDING_DIM)
        new_index.add(kept_vectors)
        _index = new_index
        _id_map = [_id_map[i] for i in keep_indices]

    _save()
    print(f"[FAISS] Deleted {len(chunk_ids)} vectors. Remaining: {len(_id_map)}")


def get_total_vectors() -> int:
    """Returns total number of vectors currently stored."""
    return _get_index().ntotal

def get_stats() -> dict:
    """Returns diagnostic statistics for the FAISS index."""
    exists = Path(FAISS_INDEX_PATH).exists()
    return {
        "total_vectors": _get_index().ntotal if exists else 0,
        "index_path": str(FAISS_INDEX_PATH),
        "exists": exists
    }