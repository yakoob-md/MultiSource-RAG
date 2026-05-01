import json
from collections import Counter
import re

file_path = r'c:\Users\dabaa\OneDrive\Desktop\dektop_content\Rag_System_2\data\training\legal_rag_dataset_filtered.jsonl'

sources = []
scores = []

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # Find Source in input
            match = re.search(r'Source: (.*?)\n', data.get('input', ''))
            if match:
                sources.append(match.group(1))
            scores.append(data.get('score', 0))

    source_counts = Counter(sources)
    score_counts = Counter(scores)

    print(f"Total Samples: {len(sources)}")
    print("\n--- Source Distribution ---")
    for source, count in source_counts.most_common():
        print(f"{source}: {count}")

    print("\n--- Score Distribution ---")
    for score, count in sorted(score_counts.items()):
        print(f"Score {score}: {count}")

except Exception as e:
    print(f"Error: {e}")
