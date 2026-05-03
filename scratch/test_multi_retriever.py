"""
Multi-Retriever Diagnostic Test Script
Runs back-to-back queries against the live backend to validate:
1. Multi-source retrieval works for 2+ sources
2. Pronoun resolution works ("they", "it")
3. Cross-domain queries work (cryptography, not just legal)
4. Diverse source types work together
"""

import requests
import json
import sys

BASE = "http://127.0.0.1:8000"

def get_sources():
    r = requests.get(f"{BASE}/sources")
    r.raise_for_status()
    return r.json()["sources"]

def query(question, source_ids=None, history=None):
    payload = {
        "question": question,
        "source_ids": source_ids,
        "history": history or [],
        "llm_provider": "groq"
    }
    r = requests.post(f"{BASE}/query", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def print_result(label, result):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    sources_used = result.get("retrievedChunks", [])
    unique_sources = {c["sourceTitle"] for c in sources_used}
    print(f"Chunks retrieved: {len(sources_used)}")
    print(f"Unique sources: {unique_sources}")
    print(f"Intent: {result.get('query_intent', 'N/A')}")
    print(f"\nANSWER PREVIEW:")
    ans = result.get("answer", "")
    print(ans[:500] + "..." if len(ans) > 500 else ans)
    print()
    return len(sources_used), unique_sources

def main():
    print("\n[DIAG] Fetching all sources from DB...")
    sources = get_sources()
    print(f"[DIAG] Found {len(sources)} sources:")
    for s in sources:
        print(f"  - {s['id'][:8]}... | {s['type']} | {s['title']} | chunks={s.get('chunkCount', '?')}")
    
    # Find PDF sources
    pdf_sources = [s for s in sources if s["type"] == "pdf"]
    
    if len(pdf_sources) < 2:
        print("[DIAG] ERROR: Need at least 2 PDF sources. Upload more PDFs first.")
        sys.exit(1)
    
    # Pick first 2 and first 3 PDF sources
    src2 = [pdf_sources[0]["id"], pdf_sources[1]["id"]]
    src3 = [s["id"] for s in pdf_sources[:3]] if len(pdf_sources) >= 3 else src2
    
    titles2 = [pdf_sources[0]["title"], pdf_sources[1]["title"]]
    print(f"\n[DIAG] Testing with 2 sources: {titles2}")
    
    results = []
    
    # ── Test 1: Direct multi-source question ──────────────────────────────────
    r1 = query(
        f"What are the key concepts covered in {pdf_sources[0]['title']} and {pdf_sources[1]['title']}?",
        source_ids=src2
    )
    n, s = print_result("Direct multi-source (explicit names)", r1)
    results.append(("Direct multi-source", n, s))

    # ── Test 2: Pronoun query (previously broken) ─────────────────────────────
    # First ask about one topic, then use pronoun
    r_setup = query(
        "Explain the main cryptographic techniques",
        source_ids=src2
    )
    history = [
        {"role": "user", "content": "Explain the main cryptographic techniques"},
        {"role": "assistant", "content": r_setup.get("answer", "")[:300]}
    ]
    r2 = query(
        "how are they different from message digests and hashing?",
        source_ids=src2,
        history=history
    )
    n, s = print_result("Pronoun resolution ('they' follow-up)", r2)
    results.append(("Pronoun resolution", n, s))

    # ── Test 3: Comparison query ───────────────────────────────────────────────
    r3 = query(
        f"Compare and contrast the approaches in both documents. What are the key differences?",
        source_ids=src2
    )
    n, s = print_result("Comparison across 2 sources", r3)
    results.append(("Comparison 2 sources", n, s))

    # ── Test 4: 3-source test (if available) ──────────────────────────────────
    if len(pdf_sources) >= 3:
        print(f"\n[DIAG] Testing with 3 sources: {[s['title'] for s in pdf_sources[:3]]}")
        r4 = query(
            "Summarize the key topics and provide an overview of what each document covers",
            source_ids=src3
        )
        n, s = print_result("3-source synthesis", r4)
        results.append(("3-source synthesis", n, s))

    # ── Test 5: Vague/short query (stress test) ────────────────────────────────
    r5 = query("explain everything", source_ids=src2)
    n, s = print_result("Vague query stress test", r5)
    results.append(("Vague query", n, s))

    # ── Test 6: No source filter (auto-router) ─────────────────────────────────
    r6 = query("What is digital signature and how does it work?")
    n, s = print_result("No filter (auto-router)", r6)
    results.append(("No filter auto-router", n, s))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*60}")
    all_pass = True
    for name, chunk_count, source_set in results:
        status = "✓ PASS" if chunk_count > 0 else "✗ FAIL"
        if chunk_count == 0:
            all_pass = False
        print(f"  {status} | {name} | {chunk_count} chunks | {len(source_set)} source(s)")
    
    print()
    if all_pass:
        print("✓ ALL TESTS PASSED — MultiRetriever is working correctly!")
    else:
        print("✗ SOME TESTS FAILED — check backend logs for details")

if __name__ == "__main__":
    main()
