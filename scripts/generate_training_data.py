import json
import os
import time
import sys
import re
import random
from pathlib import Path
from groq import Groq

# Add project root to sys.path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY
from backend.database.connection import get_connection

# --- CONFIGURATION ---
GENERATION_MODEL = "llama-3.1-70b-versatile" # Using 70B for better diversity, falling back to 8B if needed
OUTPUT_FILE = Path("data/training/legal_rag_dataset_blueprint_raw.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def clean_context(text):
    """Clean OCR garbage, excessive newlines, and line breaks."""
    text = re.sub(r'\n+', '\n', text) # Remove multiple newlines
    text = re.sub(r'[^\x00-\x7F]+', ' ', text) # Remove non-ascii (garbage)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    return text.strip()

def call_groq_with_retry(client, messages, model=GENERATION_MODEL, max_tokens=1500):
    """Call Groq with automatic retry logic for rate limits (429)."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=0.8, # Higher temp for diversity
                timeout=60
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e):
                wait_time = 20 * (attempt + 1)
                print(f"[RateLimit] Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[GroqError] {e}")
                return None
    return None

def generate_blueprint_samples(client, context, title):
    """Generate 3 DIVERSE Q&A pairs for a single chunk in ONE call."""
    
    clean_text = clean_context(context)
    
    system_prompt = f"""You are a legal data engineer. Create 3 diverse training samples for a Legal RAG system using the provided context.
    
    ## DIVERSITY RULES:
    Sample 1: STRICT - Formal legal question. Structured output (ANSWER, LEGAL BASIS, CITATIONS).
    Sample 2: SIMPLE - Messy, real-user query (e.g. "my friend did X..."). Output in "Simple Terms" for a layperson.
    Sample 3: SPECIAL - Either a "No Answer" case (if info is missing) or a "Conversational" follow-up style.
    
    ## FORMAT:
    Return a JSON LIST of 3 objects:
    [
      {{"instruction": "...", "input": "...", "output": "..."}},
      ...
    ]
    
    Ensure 'input' includes 'CONTEXT:\nSource: {title}\n{clean_text}\n\nQUESTION: [the question]'

    DO NOT use any information outside the provided context. If answer is not present, explicitly say so.
    """
    
    user_prompt = f"CONTEXT:\n{clean_text}"
    
    content = call_groq_with_retry(client, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    
    if not content: return []
    
    try:
        # Extract JSON if model wraps in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except:
        print(f"[ParseError] Failed to parse 3-pack JSON")
        return []

def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    
    print(f"Connecting to database... Using model: {GENERATION_MODEL}")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            # Pick 150 random chunks to get ~450 samples total (since we do 3-packs)
            query = """
            SELECT c.chunk_text, s.title
            FROM chunks c
            JOIN sources s ON c.source_id = s.id
            WHERE c.chunk_type = 'legal' 
            ORDER BY RAND()
            LIMIT 150
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                print("No rows found.")
                return

            print(f"Generating ~450 Blueprint samples from {len(rows)} chunks...")
            
            total_generated = 0
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for i, row in enumerate(rows):
                    samples = generate_blueprint_samples(client, row['chunk_text'], row['title'])
                    
                    for sample in samples:
                        f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                        total_generated += 1
                    
                    f.flush()
                    print(f"[{i+1}/{len(rows)}] Generated {len(samples)} samples. Total: {total_generated}")
                    
                    # Be gentle on Groq 70B rate limits
                    time.sleep(2) 
                    
            print(f"\n✅ DONE! Generated {total_generated} blueprint samples in {OUTPUT_FILE}")
            print("Next step: Run the Parallel Filter to clean these and append to your main dataset.")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
