import asyncio
import json
import os
import re
import sys
from pathlib import Path
from groq import AsyncGroq

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY

# --- CONFIGURATION ---
MODEL = "llama-3.1-8b-instant" # Fast model for filtering
INPUT_FILE = Path("data/training/legal_rag_dataset_blueprint_raw.jsonl")
FINAL_OUTPUT_FILE = Path("data/training/legal_rag_dataset_filtered.jsonl") # Appending to your existing file
CONCURRENCY_LIMIT = 10 # Number of simultaneous API calls

SYSTEM_PROMPT = """
You are a strict dataset quality evaluator for a legal AI.
Your task is to FILTER and SELECT only HIGH-QUALITY training samples.

## EVALUATION CRITERIA:
1. Grounding: Answer must be 100% supported by the context.
2. Diversity: Keep Simple, Conversational, and No-Answer cases if they are clear.
3. Structure: Structured answers must have Citations. Simple answers must be clear.

## SCORING:
- Return score 1-10.
- KEEP only if score >= 7.

## OUTPUT FORMAT:
Return ONLY JSON: {"score": 9, "decision": "KEEP", "reason": "..."}
"""

async def evaluate_sample(client, semaphore, sample, index):
    async with semaphore:
        prompt = f"Evaluate this sample:\n{json.dumps(sample, indent=2)}"
        
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                model=MODEL,
                max_tokens=500,
                temperature=0,
            )
            content = response.choices[0].message.content
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            result = json.loads(content)
            
            return sample, result
        except Exception as e:
            print(f"Sample {index} failed: {e}")
            return None, None

async def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = AsyncGroq(api_key=GROQ_API_KEY)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    if not INPUT_FILE.exists():
        print(f"Input file {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    print(f"Filtering {len(samples)} samples with concurrency={CONCURRENCY_LIMIT}...")

    tasks = [evaluate_sample(client, semaphore, sample, i) for i, sample in enumerate(samples)]
    results = await asyncio.gather(*tasks)

    total_kept = 0
    with open(FINAL_OUTPUT_FILE, "a", encoding="utf-8") as f_out:
        for sample, result in results:
            if sample and result and (result.get("score", 0) >= 7 or result.get("decision") == "KEEP"):
                # Append score to sample
                sample["score"] = result.get("score")
                f_out.write(json.dumps(sample, ensure_ascii=False) + "\n")
                total_kept += 1

    print(f"\n✅ DONE!")
    print(f"Filtered {len(samples)} -> Kept {total_kept} high-quality samples.")
    print(f"Appended to: {FINAL_OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
