import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.rag.multi_generator import generate_multi_answer
from backend.rag.multi_retriever import MultiSourceResult
from backend.rag.retriever import RetrievedChunk

def test_generator_formats():
    # Mock chunks
    chunk1 = RetrievedChunk(
        chunk_id="1", source_id="s1", source_type="pdf", source_title="IPC",
        chunk_text="Section 302: Punishment for murder...", score=0.9,
        page_number=45, timestamp_s=None, url_ref=None, language="en"
    )
    chunk2 = RetrievedChunk(
        chunk_id="2", source_id="s2", source_type="pdf", source_title="SC Judgment 2024",
        chunk_text="The court held that in cases of murder...", score=0.8,
        page_number=10, timestamp_s=None, url_ref=None, language="en"
    )

    # 1. Test Single Source
    print("Testing Single Source Answer format...")
    res1 = MultiSourceResult(
        query_intent="single_source", source_groups={"IPC": [chunk1]}, 
        all_chunks=[chunk1], source_count=1
    )
    ans1 = generate_multi_answer("What is IPC 302?", res1)
    print(f"Answer starts with: {ans1.answer[:100]}...")
    required1 = ["ANSWER:", "LEGAL BASIS:", "CITATIONS:"]
    for req in required1:
        if req in ans1.answer:
            print(f"  {req}: FOUND")
        else:
            print(f"  {req}: MISSING")
    print("-" * 20)

    # 2. Test Comparison
    print("Testing Comparison Answer format...")
    res2 = MultiSourceResult(
        query_intent="comparison", source_groups={"IPC": [chunk1], "SC Judgment 2024": [chunk2]}, 
        all_chunks=[chunk1, chunk2], source_count=2
    )
    ans2 = generate_multi_answer("Compare IPC vs SC", res2)
    print(f"Answer starts with: {ans2.answer[:100]}...")
    required2 = ["SOURCE A", "SOURCE B", "KEY DIFFERENCES"]
    for req in required2:
        if req in ans2.answer:
            print(f"  {req}: FOUND")
        else:
            print(f"  {req}: MISSING")
    print("-" * 20)

    # 3. Test Synthesis
    print("Testing Synthesis Answer format...")
    res3 = MultiSourceResult(
        query_intent="synthesis", source_groups={"IPC": [chunk1], "SC Judgment 2024": [chunk2]}, 
        all_chunks=[chunk1, chunk2], source_count=2
    )
    ans3 = generate_multi_answer("Summarize murder laws", res3)
    print(f"Answer starts with: {ans3.answer[:100]}...")
    required3 = ["SYNTHESIS:", "BY SOURCE:", "COMMON THEMES"]
    for req in required3:
        if req in ans3.answer:
            print(f"  {req}: FOUND")
        else:
            print(f"  {req}: MISSING")
    print("-" * 20)

if __name__ == "__main__":
    test_generator_formats()
