import json
from pathlib import Path

INPUT_FILE = Path("data/training/legal_rag_dataset.jsonl")

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    count = 0
    for line in lines:
        sample = json.loads(line)
        output_text = sample.get("output", "")
        # Local filter logic
        if "| - | - |" in output_text or "Not applicable" in output_text or "ANSWER: Not found" in output_text:
            continue
        count += 1
    
    print(f"Total samples: {len(lines)}")
    print(f"Samples passing local filter: {count}")

if __name__ == "__main__":
    main()
