import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.rag.retriever import retrieve
from backend.rag.generator import generate_answer

question = "What is a neural network and how does it work?"

print(f"Question: {question}")
print("Retrieving chunks...")
chunks = retrieve(question)
print(f"Retrieved {len(chunks)} chunks\n")

print("Generating answer (this may take 15-30 seconds)...")
result = generate_answer(question, chunks)

print("\n" + "="*60)
print("ANSWER:")
print("="*60)
print(result.answer)

print("\n" + "="*60)
print("CITATIONS:")
print("="*60)
for i, citation in enumerate(result.citations, 1):
    print(f"\n[{i}] {citation.source_type.upper()}: {citation.source_title}")
    print(f"     Reference : {citation.reference}")
    print(f"     Score     : {citation.score:.4f}")
    print(f"     Snippet   : {citation.snippet[:80]}...")