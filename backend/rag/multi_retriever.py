from dataclasses import dataclass
from backend.rag.retriever import retrieve, RetrievedChunk
from backend.rag.query_classifier import QueryAnalysis, extract_source_filter
from backend.database.connection import get_connection


@dataclass
class MultiSourceResult:
    query_intent  : str
    source_groups : dict[str, list[RetrievedChunk]]  # source_title -> chunks
    all_chunks    : list[RetrievedChunk]
    source_count  : int


def _build_source_groups(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Group chunks by their source title."""
    groups: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        groups.setdefault(chunk.source_title, []).append(chunk)
    return groups


# ── Path 1: Single source (or no user selection) ──────────────────────────────

def retrieve_single_source(question: str, source_ids: list[str] | None = None) -> MultiSourceResult:
    """Retrieve from a single best-matching source."""
    chunks = retrieve(question, source_ids=source_ids)
    source_groups = _build_source_groups(chunks)

    # Single-source intent: when no source is explicitly selected, keep only top source
    if len(source_groups) > 1 and not source_ids:
        top_source = chunks[0].source_title
        source_groups = {top_source: source_groups[top_source]}
        all_chunks = source_groups[top_source]
    else:
        all_chunks = chunks

    return MultiSourceResult(
        query_intent="single_source",
        source_groups=source_groups,
        all_chunks=all_chunks,
        source_count=len(source_groups)
    )


# ── Path 2: Multi-source explicit selection (THE CORE PRODUCT FEATURE) ────────

def retrieve_multi_selected(question: str, source_ids: list[str]) -> MultiSourceResult:
    """
    CORE MULTI-SOURCE PATH.
    Called when the user explicitly selects multiple sources in the UI.
    Retrieves a balanced chunk pool from EACH selected source independently
    so every source gets fair representation in the consolidated answer.
    """
    print(f"[MultiRetriever] Multi-selected: {len(source_ids)} sources")

    source_groups: dict[str, list[RetrievedChunk]] = {}
    all_chunks: list[RetrievedChunk] = []

    # Retrieve from each source individually for balanced representation
    chunks_per_source = max(4, 16 // max(len(source_ids), 1))

    for sid in source_ids:
        try:
            chunks = retrieve(question, source_ids=[sid])
            chunks = chunks[:chunks_per_source]
            if not chunks:
                print(f"[MultiRetriever] Source {sid} returned 0 chunks — skipping")
                continue
            title = chunks[0].source_title
            source_groups[title] = chunks
            all_chunks.extend(chunks)
            print(f"[MultiRetriever]   {title}: {len(chunks)} chunks")
        except Exception as e:
            print(f"[MultiRetriever] Error on source {sid}: {e}")

    intent = "synthesis" if len(source_groups) > 1 else "single_source"
    print(f"[MultiRetriever] Total: {len(all_chunks)} chunks from {len(source_groups)} sources | intent={intent}")

    return MultiSourceResult(
        query_intent=intent,
        source_groups=source_groups,
        all_chunks=all_chunks,
        source_count=len(source_groups)
    )


# ── Path 3: Comparison (classifier-driven) ────────────────────────────────────

def retrieve_for_comparison(question: str, analysis: QueryAnalysis, top_k_per_source: int = 5) -> MultiSourceResult:
    source_groups: dict[str, list[RetrievedChunk]] = {}
    all_chunks: list[RetrievedChunk] = []

    for stype in analysis.source_types:
        if stype == "any":
            continue
        try:
            with get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if stype == "legal_statute":
                    cursor.execute("SELECT source_id AS id FROM legal_sources WHERE doc_type = 'statute'")
                elif stype == "legal_judgment":
                    cursor.execute("SELECT source_id AS id FROM legal_sources WHERE doc_type = 'judgment'")
                elif stype == "web":
                    cursor.execute("SELECT id FROM sources WHERE type = 'url'")
                elif stype == "youtube":
                    cursor.execute("SELECT id FROM sources WHERE type = 'youtube'")
                else:
                    continue
                ids = [row['id'] for row in cursor.fetchall()]

            if not ids:
                continue

            chunks = retrieve(question, source_ids=ids)[:top_k_per_source]
            for chunk in chunks:
                source_groups.setdefault(chunk.source_title, []).append(chunk)
                all_chunks.append(chunk)
        except Exception as e:
            print(f"[MultiRetriever] Error for {stype}: {e}")

    # Fallback if classifier found nothing
    if not all_chunks:
        res = retrieve_single_source(question)
        source_groups.update(res.source_groups)
        all_chunks.extend(res.all_chunks)

    return MultiSourceResult(
        query_intent="comparison",
        source_groups=source_groups,
        all_chunks=all_chunks,
        source_count=len(source_groups)
    )


# ── Path 4: Synthesis (classifier-driven, all sources) ───────────────────────

def retrieve_for_synthesis(question: str, source_ids: list[str] | None = None) -> MultiSourceResult:
    chunks = retrieve(question, source_ids=source_ids)
    source_groups = _build_source_groups(chunks)
    num_sources = len(source_groups)

    if num_sources > 0:
        cap = max(2, 16 // num_sources)
        balanced_chunks: list[RetrievedChunk] = []
        balanced_groups: dict[str, list[RetrievedChunk]] = {}
        for title, group in source_groups.items():
            balanced_groups[title] = group[:cap]
            balanced_chunks.extend(group[:cap])
        return MultiSourceResult(
            query_intent="synthesis",
            source_groups=balanced_groups,
            all_chunks=balanced_chunks,
            source_count=num_sources
        )

    return MultiSourceResult(query_intent="synthesis", source_groups={}, all_chunks=[], source_count=0)


# ── Router ────────────────────────────────────────────────────────────────────

def multi_retrieve(question: str, analysis: QueryAnalysis) -> MultiSourceResult:
    """Route to the correct strategy based on classifier intent."""
    print(f"[MultiRetriever] intent={analysis.intent} | sources={analysis.source_types}")

    if analysis.intent == "comparison":
        return retrieve_for_comparison(question, analysis)
    elif analysis.intent == "synthesis":
        return retrieve_for_synthesis(question)
    else:  # single_source or default
        source_ids = extract_source_filter(analysis, available_source_ids=None)
        return retrieve_single_source(question, source_ids=source_ids)
