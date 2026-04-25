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

# --- CONFIGURATION ---
EVALUATION_MODEL = "qwen/qwen3-32b" 
INPUT_FILE = Path("data/training/legal_rag_dataset.jsonl")
OUTPUT_FILE = Path("data/training/legal_rag_dataset_filtered.jsonl")
THRESHOLD = 7  # Lowered to 7 as per user's < 100 samples rule

# Load the system prompt from the updated rag_prompt.txt
SYSTEM_PROMPT = """
You are a strict dataset quality evaluator for a legal AI fine-tuning pipeline.
Your task is to FILTER and SELECT only HIGH-QUALITY training samples from a dataset.

## 🔍 EVALUATION CRITERIA (STRICT)
1. Question Quality: Realistic, useful, not trivial.
2. Context Quality: Meaningful legal info, not fragmented.
3. Answer Faithfulness: Fully supported, no hallucinations.
4. Structure Quality: Must have ANSWER, LEGAL BASIS, CITATIONS.
5. Citation Quality: Be strict. Reject placeholders like "| - | - |". 
   NOTE: For Statutes/Acts, "Court" may be "N/A" or "Legislature", but Section MUST be present.

## 📊 SCORING
- Total score must be from 1 to 10 (10 is perfect).
- KEEP only if score >= {threshold}. Otherwise REJECT.

## 🧾 OUTPUT FORMAT
Return ONLY a valid JSON object:
{{
"score": 9,
"decision": "KEEP",
"reason": "brief reason"
}}
"""

def call_groq_evaluator(client, sample):
    """Call Groq to evaluate a single training sample."""
    sample_str = json.dumps(sample, indent=2)
    prompt = f"Evaluate this sample based on the criteria. Return ONLY a JSON object with 'score', 'decision', and 'reason'.\n\nSAMPLE:\n{sample_str}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.format(threshold=THRESHOLD)},
                    {"role": "user", "content": prompt}
                ],
                model=EVALUATION_MODEL,
                max_tokens=1000,
                timeout=45
            )
            content = response.choices[0].message.content
            
            # Clean think tags
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # Extract JSON from code block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            return json.loads(content)
        except Exception as e:
            if "429" in str(e):
                wait_time = 30 * (attempt + 1)
                print(f"[RateLimit] Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[EvalError] {e}")
                break
    return None

def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    
    if not INPUT_FILE.exists():
        print(f"Input file {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    total_processed = len(samples)
    total_selected = 0
    
    # Check if we already have some filtered samples to resume
    processed_count = 0
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            processed_count = sum(1 for _ in f)
        print(f"Resuming from {processed_count} already selected samples.")

    print(f"Starting filtering of {total_processed} samples (skipping first 438)...")
    
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f_out:
        # Start from 438, but also skip what we already processed if resuming
        # Actually, let's just start fresh for simplicity as requested
        for i, sample in enumerate(samples):
            if i < 438: continue
            
            # Local skip for obvious bad ones
            out_text = sample.get("output", "")
            if "Not found in the given context" in out_text:
                continue

            result = call_groq_evaluator(client, sample)
            
            if result:
                score = result.get('score', 0)
                decision = str(result.get('decision', 'REJECT')).upper()
                reason = result.get('reason', 'No reason')
                
                if decision == "KEEP" or score >= THRESHOLD:
                    final_sample = {
                        "instruction": sample["instruction"],
                        "input": sample["input"],
                        "output": sample["output"],
                        "score": score
                    }
                    f_out.write(json.dumps(final_sample, ensure_ascii=False) + "\n")
                    total_selected += 1
                
                print(f"Sample {i+1}: Score={score} | {decision} | {reason[:50]}...")
            
            if (i + 1) % 5 == 0:
                print(f"--- Progress: {i+1}/{total_processed} | Selected: {total_selected} ---")
            
            time.sleep(1) # Be gentle on the rate limits

    print("\n" + "="*30)
    print("📊 FINAL FILTERING REPORT")
    print(f"Total processed (legal): {total_processed - 438}")
    print(f"Total selected: {total_selected}")
    print("="*30)

if __name__ == "__main__":
    main()
