import json
import os
import time
import sys
from pathlib import Path
from groq import Groq

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY

EVALUATION_MODEL = "llama-3.1-8b-instant" 
INPUT_FILE = Path("data/training/legal_rag_dataset.jsonl")

SYSTEM_PROMPT = """
You are a strict dataset quality evaluator for a legal AI fine-tuning pipeline.
Your task is to FILTER and SELECT only HIGH-QUALITY training samples from a dataset.

## 🧾 OUTPUT FORMAT
Return ONLY a valid JSON object:
{
"score": 9,
"decision": "KEEP" or "REJECT",
"reason": "brief reason"
}
"""

def main():
    client = Groq(api_key=GROQ_API_KEY)
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        # Read a few from the legal section (after 450)
        lines = f.readlines()
        test_samples = lines[450:460]
        
    for i, line in enumerate(test_samples):
        sample = json.loads(line)
        print(f"Testing Sample {i+1}...")
        
        prompt = f"Evaluate this sample:\n\n{json.dumps(sample, indent=2)}"
        
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            model=EVALUATION_MODEL,
            response_format={"type": "json_object"},
            max_tokens=500
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"Result: {result}")
        print("-" * 20)

if __name__ == "__main__":
    main()
