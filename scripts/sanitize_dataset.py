import json
import re
from pathlib import Path

FILE_PATH = Path("data/training/legal_rag_dataset_filtered.jsonl")
CLEAN_FILE_PATH = Path("data/training/legal_rag_dataset_final.jsonl")

def format_output(output):
    """Convert dict outputs or string-wrapped dicts to clean strings."""
    # 1. Handle actual dictionaries
    if isinstance(output, dict):
        if "ANSWER" in output:
            parts = []
            parts.append(f"ANSWER: {output.get('ANSWER', '')}")
            if "LEGAL BASIS" in output: parts.append(f"LEGAL BASIS: {output['LEGAL BASIS']}")
            if "CITATIONS" in output: parts.append(f"CITATIONS: {output['CITATIONS']}")
            return "\n\n".join(parts)
        # Handle other types like {'Simple Terms': "..."}
        return next(iter(output.values())) if output else str(output)
    
    # 2. Handle strings that LOOK like dicts (e.g. "{'Response': '...'}")
    if isinstance(output, str) and output.strip().startswith("{") and output.strip().endswith("}"):
        try:
            # Try to extract the content inside the first set of quotes after a colon
            # This handles "{'Simple Terms': 'The answer is X'}" -> "The answer is X"
            match = re.search(r':\s*["\'](.*)["\']\s*\}', output, re.DOTALL)
            if match:
                return match.group(1).strip()
        except:
            pass
            
    return str(output)

def sanitize():
    if not FILE_PATH.exists():
        print("File not found.")
        return

    print(f"Sanitizing {FILE_PATH}...")
    
    samples = []
    dropped_missing_context = 0
    dropped_low_score = 0
    formatted_count = 0

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                sample = json.loads(line)
                
                # 1. Quality Filter (Score 7+)
                if sample.get("score") is not None and int(sample.get("score")) < 7:
                    dropped_low_score += 1
                    continue

                # 2. Fix output formatting
                original_output = sample.get("output")
                sample["output"] = format_output(original_output)
                if sample["output"] != str(original_output):
                    formatted_count += 1
                
                # 3. Check for Context in Input
                if "CONTEXT:" not in str(sample.get("input", "")):
                    dropped_missing_context += 1
                    continue
                
                samples.append(sample)
            except:
                continue

    # Write to final file
    with open(CLEAN_FILE_PATH, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"\n[DONE] SANITIZATION COMPLETE")
    print(f"Total samples processed: {len(samples) + dropped_missing_context + dropped_low_score}")
    print(f"Formatted outputs cleaned: {formatted_count}")
    print(f"Dropped (low score < 7): {dropped_low_score}")
    print(f"Dropped (missing context): {dropped_missing_context}")
    print(f"FINAL dataset size: {len(samples)} samples")
    print(f"Saved to: {CLEAN_FILE_PATH}")

if __name__ == "__main__":
    sanitize()
