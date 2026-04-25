import json
import os
import time
import sys
import re
from pathlib import Path
from groq import Groq

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)
model = "qwen/qwen3-32b"

SYSTEM_PROMPT = """
You are a strict dataset quality evaluator for a legal AI fine-tuning pipeline.
Your task is to FILTER and SELECT only HIGH-QUALITY training samples from a dataset.

## 🔍 EVALUATION CRITERIA (STRICT)
1. Question Quality: Realistic, useful, not trivial.
2. Context Quality: Meaningful legal info, not fragmented.
3. Answer Faithfulness: Fully supported, no hallucinations.
4. Structure Quality: Must have ANSWER, LEGAL BASIS, CITATIONS.
5. Citation Quality: No placeholders like "| - | - |".

## 📊 SCORING
- Total score must be from 1 to 10 (10 is perfect).
- KEEP only if score >= 8. Otherwise REJECT.

## 🧾 OUTPUT FORMAT
Return ONLY a valid JSON object:
{
"score": 9,
"decision": "KEEP",
"reason": "brief reason"
}
"""

def main():
    with open("data/training/legal_rag_dataset.jsonl", "r", encoding="utf-8") as f:
        lines = f.readlines()
        test_samples = lines[450:455]
        
    for i, line in enumerate(test_samples):
        sample = json.loads(line)
        print(f"Testing Sample {i+1}...")
        
        prompt = f"Evaluate this sample. Return ONLY a JSON object with 'score', 'decision', and 'reason'.\n\nSAMPLE:\n{json.dumps(sample, indent=2)}"
        
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            model=model,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        print(f"RAW: {content}")
        try:
            # Extract JSON from code block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)
            print(f"Result: {result}")
        except:
            print("Failed to parse JSON")
        print("-" * 20)

if __name__ == "__main__":
    main()
