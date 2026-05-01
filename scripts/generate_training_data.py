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
GENERATION_MODEL = "llama-3.1-8b-instant" # High rate limit for fast generation
FALLBACK_MODEL = "llama-3.3-70b-versatile"
OUTPUT_FILE = Path("data/training/legal_rag_dataset_blueprint_raw.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_processed_count():
    """Count how many chunks were already successfully processed."""
    if not OUTPUT_FILE.exists(): return 0
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        # Every 3 samples in the file represent 1 chunk processed
        lines = sum(1 for _ in f)
        return lines // 3

def clean_context(text):
    """Clean OCR garbage, excessive newlines, and line breaks."""
    text = re.sub(r'\n+', '\n', text) # Remove multiple newlines
    text = re.sub(r'[^\x00-\x7F]+', ' ', text) # Remove non-ascii (garbage)
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
    return text.strip()

def call_groq_with_retry(client, messages, model=GENERATION_MODEL, max_tokens=4096):
    """Call Groq with automatic retry and model fallback."""
    models_to_try = [model, FALLBACK_MODEL]
    
    for current_model in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    messages=messages,
                    model=current_model,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    timeout=90
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str:
                    wait_time = 15 * (attempt + 1)
                    print(f"[RateLimit] {current_model} busy. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif "decommissioned" in err_str or "model_not_found" in err_str:
                    print(f"[ModelError] {current_model} not available, trying fallback...")
                    break 
                else:
                    print(f"[GroqError] {current_model}: {e}")
                    return None
    return None

def generate_blueprint_samples(client, context, title):
    """Generate 3 DIVERSE Q&A pairs for a single chunk with truncation to prevent token overflow."""
    
    # Truncate context to ~1200 chars to be safe on 8B/70B output limits
    clean_text = clean_context(context)[:1200] 
    
    system_prompt = f"""You are a legal data engineer. Create 3 diverse training samples for a Legal RAG system.
    
    ## DIVERSITY RULES:
    Sample 1: STRICT - Formal legal question. Structured output (ANSWER, LEGAL BASIS, CITATIONS).
    Sample 2: SIMPLE - Messy, real-user query. Output in "Simple Terms" for a layperson.
    Sample 3: SPECIAL - Either a "No Answer" case or a "Conversational" follow-up.
    
    ## OUTPUT FORMAT:
    Return ONLY a JSON list of 3 objects. No preamble, no markdown formatting.
    [
      {{"instruction": "...", "input": "...", "output": "..."}},
      ...
    ]
    
    Ensure 'input' includes 'CONTEXT:\nSource: {title}\n{clean_text}\n\nQUESTION: [the question]'
    DO NOT use any information outside the provided context.
    """
    
    user_prompt = f"CONTEXT:\n{clean_text}"
    
    content = call_groq_with_retry(client, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])
    
    if not content: return []
    
    try:
        match = re.search(r'(\[.*\])', content, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        else:
            return json.loads(content)
    except Exception as e:
        print(f"[ParseError] {e}. DEBUG: {content[:100]}...")
        return []

def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    skip_count = get_processed_count()
    
    print(f"Connecting to database... Using primary: {GENERATION_MODEL}")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            # Fetch more to allow for resuming
            query = """
            SELECT c.chunk_text, s.title
            FROM chunks c
            JOIN sources s ON c.source_id = s.id
            WHERE c.chunk_type = 'legal' 
            LIMIT 500
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                print("No rows found.")
                return

            print(f"Resuming from chunk {skip_count+1}. Target: 150 chunks (~450 samples).")
            
            total_generated = skip_count * 3
            chunks_processed = skip_count
            
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for i, row in enumerate(rows):
                    if i < skip_count: continue # Skip already processed
                    if chunks_processed >= 150: break # Goal reached
                    
                    samples = generate_blueprint_samples(client, row['chunk_text'], row['title'])
                    
                    if samples:
                        for sample in samples:
                            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                            total_generated += 1
                        chunks_processed += 1
                    
                    f.flush()
                    print(f"[{chunks_processed}/150] Generated {len(samples)} samples. Total in file: {total_generated}")
                    
                    # 8B is fast, so we only need a tiny sleep
                    time.sleep(0.5) 
                    
            print(f"\n✅ DONE! Dataset ready in {OUTPUT_FILE}")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
