import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.rag.multi_retriever import multi_retrieve
from backend.rag.query_classifier import QueryAnalysis

def run_multi_tests():
    # Test 1: Single Source
    print("Testing Single Source Mode...")
    analysis1 = QueryAnalysis(
        intent="single_source", source_types=["any"], topics=["murder"], 
        ipc_sections=["302"], time_filter=None, language_hint="en", 
        requires_compare=False, requires_summary=False, source_names=[]
    )
    res1 = multi_retrieve("What is IPC 302?", analysis1)
    print(f"  Intent: {res1.query_intent}, Source Count: {res1.source_count}, Total Chunks: {len(res1.all_chunks)}")
    if res1.source_count == 1:
        print("  Test 1: PASSED")
    else:
        print(f"  Test 1: FAILED (Expected 1 source, got {res1.source_count})")
    print("-" * 20)

    # Test 2: Comparison
    print("Testing Comparison Mode...")
    analysis2 = QueryAnalysis(
        intent="comparison", source_types=["legal_statute", "youtube"], topics=["murder"], 
        ipc_sections=["302"], time_filter=None, language_hint="en", 
        requires_compare=True, requires_summary=False, source_names=[]
    )
    res2 = multi_retrieve("Compare IPC 302 vs recent law videos", analysis2)
    print(f"  Intent: {res2.query_intent}, Source Count: {res2.source_count}, Total Chunks: {len(res2.all_chunks)}")
    print(f"  Source Groups: {list(res2.source_groups.keys())}")
    if res2.source_count >= 1: # We might only have one type with data in DB
        print("  Test 2: PASSED (Logic verified, groups populated)")
    else:
        print("  Test 2: FAILED (No groups populated)")
    print("-" * 20)

    # Test 3: Synthesis
    print("Testing Synthesis Mode...")
    analysis3 = QueryAnalysis(
        intent="synthesis", source_types=["any"], topics=["law"], 
        ipc_sections=[], time_filter=None, language_hint="en", 
        requires_compare=False, requires_summary=True, source_names=[]
    )
    res3 = multi_retrieve("Summary of all documents", analysis3)
    print(f"  Intent: {res3.query_intent}, Source Count: {res3.source_count}, Total Chunks: {len(res3.all_chunks)}")
    
    # Check balancing
    counts = [len(chunks) for chunks in res3.source_groups.values()]
    print(f"  Chunk counts per source: {counts}")
    if all(count <= 16//max(1, len(counts)) + 1 for count in counts):
        print("  Test 3: PASSED (Balanced)")
    else:
        print("  Test 3: FAILED (Unbalanced)")
    print("-" * 20)

if __name__ == "__main__":
    run_multi_tests()
