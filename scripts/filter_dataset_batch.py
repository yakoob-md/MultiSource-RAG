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
THRESHOLD = 7
BATCH_SIZE = 5 # Small batch to keep context window safe and thinking coherent

SYSTEM_PROMPT = """
You are a strict dataset quality evaluator for a legal AI fine-tuning pipeline.
Your task is to FILTER and SELECT only HIGH-QUALITY training samples from a dataset.

## 🔍 EVALUATION CRITERIA (STRICT)
1. Question Quality: Realistic, useful, not trivial.
2. Context Quality: Meaningful legal info.
3. Answer Faithfulness: Fully supported.
4. Structure Quality: Must have ANSWER, LEGAL BASIS, CITATIONS.
5. Citation Quality: Reject placeholders like "| - | - |". For Statutes, Section MUST be present.

## 📊 SCORING
- Score 1-10. KEEP if score >= 7.

## 🧾 OUTPUT FORMAT
Return a JSON object with a list of results:
{{
"results": [
  {{
    "sample_index": 0,
    "score": 9,
    "decision": "KEEP",
    "reason": "..."
  }},
  ...
]
}}
"""

def call_groq_batch_evaluator(client, samples_batch):
    """Evaluate a batch of samples."""
    batch_data = []
    for i, s in enumerate(samples_batch):
        batch_data.append({"index": i, "data": s})
        
    prompt = f"Evaluate these {len(samples_batch)} samples based on the criteria. Return JSON.\n\nSAMPLES:\n{json.dumps(batch_data, indent=2)}"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                model=EVALUATION_MODEL,
                max_tokens=2000,
                timeout=90
            )
            content = response.choices[0].message.content
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            return json.loads(content)
        except Exception as e:
            if "429" in str(e):
                time.sleep(30 * (attempt + 1))
            else:
                print(f"[BatchError] {e}")
                break
    return None

def main():
    client = Groq(api_key=GROQ_API_KEY)
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        all_samples = [json.loads(line) for line in f if line.strip()]

    legal_samples = [(i, s) for i, s in enumerate(all_samples) if i >= 438]
    
    # Filter out obvious bad ones locally
    filtered_indices = []
    for i, s in legal_samples:
        out_text = s.get("output", "")
        if "Not found in the given context" in out_text or "| - | - |" in out_text:
            continue
        filtered_indices.append((i, s))

    print(f"Total legal samples: {len(legal_samples)} | After local filter: {len(filtered_indices)}")
    
    # 1. Load existing results to avoid duplicates
    existing_inputs = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    existing_inputs.add(json.loads(line)["input"])
                except:
                    continue
    print(f"Loaded {len(existing_inputs)} existing samples from {OUTPUT_FILE.name}")

    total_selected = 0
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f_out:
        for b_start in range(0, len(filtered_indices), BATCH_SIZE):
            batch = filtered_indices[b_start : b_start + BATCH_SIZE]
            
            # Filter the batch to only include samples not already in existing_inputs
            new_batch = [(i, s) for i, s in batch if s["input"] not in existing_inputs]
            
            if not new_batch:
                continue

            indices, samples = zip(*new_batch)
            
            print(f"Processing batch {b_start//BATCH_SIZE + 1} ({len(samples)} new samples)...")
            results_dict = call_groq_batch_evaluator(client, samples)
            
            if results_dict and "results" in results_dict:
                for res in results_dict["results"]:
                    idx_in_batch = res.get("sample_index")
                    if idx_in_batch is None or idx_in_batch >= len(samples): continue
                    
                    score = res.get("score", 0)
                    decision = str(res.get("decision", "REJECT")).upper()
                    
                    if decision == "KEEP" or score >= THRESHOLD:
                        original_sample = samples[idx_in_batch]
                        final_sample = {
                            "instruction": original_sample["instruction"],
                            "input": original_sample["input"],
                            "output": original_sample["output"],
                            "score": score
                        }
                        f_out.write(json.dumps(final_sample, ensure_ascii=False) + "\n")
                        total_selected += 1
                        print(f"  [KEEP] Sample {indices[idx_in_batch]} | Score: {score}")
                    else:
                        print(f"  [REJECT] Sample {indices[idx_in_batch]} | Score: {score} | Reason: {res.get('reason', 'N/A')[:50]}")
            
            time.sleep(2)

    print(f"\nDone! Total selected: {total_selected}")

if __name__ == "__main__":
    main()
