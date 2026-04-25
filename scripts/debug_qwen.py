import json
import os
import sys
from pathlib import Path
from groq import Groq

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)
model = "qwen/qwen3-32b"

# Read sample 450
with open("data/training/legal_rag_dataset.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    sample = json.loads(lines[450])

print(f"Sample to evaluate: {sample['input'][:100]}...")

prompt = f"Evaluate this sample. Return JSON with 'score' and 'decision'.\n\n{json.dumps(sample)}"

try:
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        # NO response_format to see raw output
    )
    print("RAW RESPONSE:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"ERROR: {e}")
