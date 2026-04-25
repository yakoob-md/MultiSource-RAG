import sys
import os
from pathlib import Path
from pydantic import BaseModel

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.api.query import query, QueryRequest

def test_endpoint():
    print("Testing Endpoint /query...")
    
    # Test 1: Auto - Single Source
    print("1. Testing auto mode - single source...")
    req1 = QueryRequest(question="What is IPC 302?", mode="auto")
    res1 = query(req1)
    print(f"   Intent: {res1['query_intent']}")
    if res1['query_intent'] == "single_source":
        print("   PASSED")
    else:
        print("   FAILED")
    print("-" * 20)

    # Test 2: Auto - Comparison
    print("2. Testing auto mode - comparison...")
    req2 = QueryRequest(question="compare IPC 302 with SC ruling", mode="auto")
    res2 = query(req2)
    print(f"   Intent: {res2['query_intent']}")
    if res2['query_intent'] == "comparison":
        print("   PASSED")
    else:
        print("   FAILED")
    print("-" * 20)

    # Test 3: Forced Mode
    print("3. Testing forced mode - comparison...")
    req3 = QueryRequest(question="What is IPC 302?", mode="compare")
    res3 = query(req3)
    print(f"   Intent: {res3['query_intent']}")
    if res3['query_intent'] == "comparison":
        print("   PASSED")
    else:
        print("   FAILED")
    print("-" * 20)

if __name__ == "__main__":
    test_endpoint()
