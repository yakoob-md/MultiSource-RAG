from dataclasses import dataclass
from backend.rag.retriever import retrieve, RetrievedChunk
from backend.rag.query_classifier import QueryAnalysis, extract_source_filter
from backend.database.connection import get_connection
import json

@dataclass
class MultiSourceResult:
    query_intent     : str
    source_groups    : dict[str, list[RetrievedChunk]]  # source_title -> chunks
    all_chunks       : list[RetrievedChunk]
    source_count     : int

def retrieve_single_source(question: str, source_ids: list[str] | None = None, top_k: int = 8) -> MultiSourceResult:
    chunks = retrieve(question, source_ids=source_ids)
    
    source_groups = {}
    for chunk in chunks:
        if chunk.source_title not in source_groups:
            source_groups[chunk.source_title] = []
        source_groups[chunk.source_title].append(chunk)
    
    # If intent is single_source, we should ideally have only 1 source.
    # If multiple returned, we take the one with the highest total score or just the top chunk's source.
    if len(source_groups) > 1:
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

def retrieve_for_comparison(question: str, analysis: QueryAnalysis, top_k_per_source: int = 5) -> MultiSourceResult:
    source_groups = {}
    all_chunks = []
    
    # Mapping classifier types to DB queries
    for stype in analysis.source_types:
        if stype == "any": continue
        
        ids = []
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
                    print(f"[MultiRetriever] No sources found for type: {stype}")
                    continue
                
                # 2. Retrieve for these IDs
                chunks = retrieve(question, source_ids=ids)
                chunks = chunks[:top_k_per_source]
                
                for chunk in chunks:
                    if chunk.source_title not in source_groups:
                        source_groups[chunk.source_title] = []
                    source_groups[chunk.source_title].append(chunk)
                    all_chunks.append(chunk)
                    
        except Exception as e:
            print(f"[MultiRetriever] Error retrieving for {stype}: {e}")

    # If no specific types returned results or "any" was used, do a general search
    if not all_chunks and "any" in source_types:
        res = retrieve_single_source(question, top_k=top_k_per_source * 2)
        source_groups.update(res.source_groups)
        all_chunks.extend(res.all_chunks)

    return MultiSourceResult(
        query_intent="comparison",
        source_groups=source_groups,
        all_chunks=all_chunks,
        source_count=len(source_groups)
    )

def retrieve_for_synthesis(question: str, top_k: int = 16) -> MultiSourceResult:
    # Retrieve across all sources
    chunks = retrieve(question, source_ids=None)
    # Note: retrieve() returns TOP_K (8). If top_k=16 is requested, 
    # we might need to modify retriever.py, but we aren't allowed to.
    # So we'll use what we get.
    
    source_groups = {}
    for chunk in chunks:
        if chunk.source_title not in source_groups:
            source_groups[chunk.source_title] = []
        source_groups[chunk.source_title].append(chunk)
    
    # Balance: Cap each source at top_k // len(unique_sources)
    num_sources = len(source_groups)
    if num_sources > 0:
        cap = max(1, top_k // num_sources)
        balanced_chunks = []
        balanced_groups = {}
        for title, group in source_groups.items():
            balanced_groups[title] = group[:cap]
            balanced_chunks.extend(group[:cap])
        
        return MultiSourceResult(
            query_intent="synthesis",
            source_groups=balanced_groups,
            all_chunks=balanced_chunks,
            source_count=num_sources
        )
    
    return MultiSourceResult(
        query_intent="synthesis",
        source_groups={},
        all_chunks=[],
        source_count=0
    )

def multi_retrieve(question: str, analysis: QueryAnalysis) -> MultiSourceResult:
    print(f"[MultiRetriever] intent={analysis.intent} | sources={analysis.source_types}")
    
    if analysis.intent == "comparison":
        return retrieve_for_comparison(question, analysis)
    elif analysis.intent == "synthesis":
        return retrieve_for_synthesis(question)
    else: # single_source or default
        source_ids = extract_source_filter(analysis, available_source_ids=None)
        return retrieve_single_source(question, source_ids=source_ids)
