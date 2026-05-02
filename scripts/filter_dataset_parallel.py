import asyncio
import json
import os
import re
import sys
import random
from pathlib import Path
from groq import AsyncGroq

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY

# --- CONFIGURATION ---
MODEL = "llama-3.1-8b-instant" # Fast model for filtering
INPUT_FILE = Path("data/training/legal_rag_dataset_blueprint_raw.jsonl")
FINAL_OUTPUT_FILE = Path("data/training/legal_rag_dataset_filtered.jsonl") # Appending to your existing file
CONCURRENCY_LIMIT = 3 # Lowered to 3 to stay under 6000 TPM limit

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
        
        max_retries = 5
        for attempt in range(max_retries):
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
                match = re.search(r'(\{.*\})', content, re.DOTALL)
                if match:
                    result = json.loads(match.group(1))
                    return sample, result
                return None, None
                
            except Exception as e:
                if "429" in str(e):
                    wait = 10 * (attempt + 1)
                    print(f"[RateLimit] Sample {index} waiting {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    print(f"Sample {index} failed: {e}")
                    return None, None
        return None, None

def get_already_filtered_inputs():
    """Get a set of inputs already in the filtered file to avoid duplicates."""
    processed = set()
    if not FINAL_OUTPUT_FILE.exists(): return processed
    with open(FINAL_OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                inp = data.get("input", "")
                # Ensure it's a string so it can be hashed in a set
                if isinstance(inp, dict): inp = json.dumps(inp)
                processed.add(str(inp))
            except: continue
    return processed

async def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = AsyncGroq(api_key=GROQ_API_KEY)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    already_processed = get_already_filtered_inputs()

    if not INPUT_FILE.exists():
        print(f"Input file {INPUT_FILE} not found.")
        return

    all_samples = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                all_samples.append(json.loads(line))
            except: continue
    
    # Only process samples that aren't already filtered
    samples_to_process = []
    for s in all_samples:
        inp = s.get("input", "")
        if isinstance(inp, dict): inp = json.dumps(inp)
        if str(inp) not in already_processed:
            samples_to_process.append(s)

    if not samples_to_process:
        print("All samples already processed!")
        return

    print(f"Filtering {len(samples_to_process)} NEW samples (Concurrency={CONCURRENCY_LIMIT})...")

    tasks = [evaluate_sample(client, semaphore, sample, i) for i, sample in enumerate(samples_to_process)]
    
    # Process in smaller chunks to avoid total failure
    chunk_size = 20
    total_kept = 0
    
    for i in range(0, len(tasks), chunk_size):
        chunk = tasks[i:i + chunk_size]
        results = await asyncio.gather(*chunk)
        
        with open(FINAL_OUTPUT_FILE, "a", encoding="utf-8") as f_out:
            for sample, result in results:
                if sample and result and (result.get("score", 0) >= 7 or result.get("decision") == "KEEP"):
                    # Append score to sample
                    sample["score"] = result.get("score")
                    f_out.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    total_kept += 1
        
        print(f"Progress: {min(i + chunk_size, len(tasks))}/{len(tasks)} | Kept {total_kept} new samples")
        await asyncio.sleep(2) # Brief pause between chunks

    print(f"\n✅ DONE! Appended {total_kept} high-quality samples to {FINAL_OUTPUT_FILE.name}")

if __name__ == "__main__":
    asyncio.run(main())
