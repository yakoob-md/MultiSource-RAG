import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.rag.query_classifier import classify_query

def run_tests():
    test_cases = [
        {
            "query": "What is IPC Section 302?",
            "check": lambda res: res.intent == "single_source" and "302" in res.ipc_sections
        },
        {
            "query": "Compare what IPC says about murder vs the 2024 SC judgment",
            "check": lambda res: res.intent == "comparison" and res.requires_compare is True
        },
        {
            "query": "What is common across all uploaded legal documents?",
            "check": lambda res: res.intent == "synthesis" and res.requires_summary is True
        }
    ]

    for i, test in enumerate(test_cases):
        print(f"Testing Query {i+1}: {test['query']}")
        try:
            res = classify_query(test['query'])
            print(f"  Result: intent={res.intent}, source_types={res.source_types}, sections={res.ipc_sections}, compare={res.requires_compare}, summary={res.requires_summary}")
            if test['check'](res):
                print(f"  Test {i+1}: PASSED")
            else:
                print(f"  Test {i+1}: FAILED")
        except Exception as e:
            print(f"  Test {i+1}: ERROR: {e}")
        print("-" * 20)

if __name__ == "__main__":
    run_tests()
