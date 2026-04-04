from functools import lru_cache
from sentence_transformers import SentenceTransformer
from backend.config import EMBEDDING_MODEL, EMBEDDING_DIM
import torch

# ── Device detection ──────────────────────────────────────────────────────────
# Uses your RTX 2050 GPU for embedding — much faster during ingestion
# of large documents. Falls back to CPU silently if CUDA is unavailable.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ── Load model once and cache it ─────────────────────────────────────────────
# lru_cache ensures the model is loaded only on the first call,
# then reused for every subsequent call — saves ~5 seconds per request.
# The model is loaded onto GPU (DEVICE) once and stays there.
@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    print(f"[Embedder] Loading {EMBEDDING_MODEL} onto {DEVICE} ...")
    model = SentenceTransformer(EMBEDDING_MODEL, device=DEVICE)

    # ── Dimension safety check ────────────────────────────────────────────────
    # Guards against a common mistake: changing EMBEDDING_MODEL in config.py
    # without updating EMBEDDING_DIM, or running against an old FAISS index
    # built with a different model.
    #
    # If this raises, you need to:
    #   1. Update EMBEDDING_DIM in config.py to match the model's actual output
    #   2. Delete data/faiss_index/ and re-ingest all documents
    actual_dim = model.get_sentence_embedding_dimension()
    if actual_dim != EMBEDDING_DIM:
        raise ValueError(
            f"[Embedder] Dimension mismatch! "
            f"Model '{EMBEDDING_MODEL}' outputs {actual_dim}-dim vectors, "
            f"but config.py has EMBEDDING_DIM={EMBEDDING_DIM}. "
            f"Update EMBEDDING_DIM in config.py and re-ingest all documents."
        )

    print(f"[Embedder] Model ready | dim={actual_dim} | device={DEVICE}")
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convert a list of text strings into embedding vectors.
    Used during document ingestion to embed chunks before storing in FAISS.

    The multilingual-e5 model requires a prefix:
      - "passage: " for documents being stored  ← used here
      - "query: "   for questions being searched ← used in embed_query()

    GPU batch encoding:
      SentenceTransformers automatically batches the input and runs
      the full batch through the GPU in one forward pass.
      For large documents this is significantly faster than CPU.

    Args:
        texts: list of raw chunk text strings

    Returns:
        list of float vectors, one per input text, each of length EMBEDDING_DIM
    """
    model    = get_model()
    prefixed = [f"passage: {t}" for t in texts]

    vectors = model.encode(
        prefixed,
        normalize_embeddings = True,   # L2 normalise → cosine similarity = dot product
        batch_size           = 32,     # process 32 chunks per GPU forward pass
        show_progress_bar    = False,
    )
    return vectors.tolist()


def embed_query(question: str) -> list[float]:
    """
    Convert a single search question into an embedding vector.
    Used at query time — only one vector, so batching is not needed.

    Uses "query: " prefix — required by e5 models for questions.
    The asymmetric prefix (passage vs query) is what makes e5 models
    work well for retrieval: the model learned different representations
    for "things to store" vs "things to search for".

    Args:
        question: the user's question string

    Returns:
        a single float vector of length EMBEDDING_DIM
    """
    model  = get_model()
    vector = model.encode(
        f"query: {question}",
        normalize_embeddings = True,
    )
    return vector.tolist()