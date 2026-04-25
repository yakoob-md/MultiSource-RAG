import json
import os
import time
import sys
import re
from pathlib import Path
from groq import Groq

# Add project root to sys.path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY
from backend.database.connection import get_connection

# --- CONFIGURATION ---
# Switching to a smaller model (8B) to resolve rate limit issues (higher TPD/RPD)
GENERATION_MODEL = "llama-3-8b-8192" 
OUTPUT_FILE = Path("data/training/legal_rag_dataset.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_already_processed_chunks():
    """Read the output file to see which chunks are already done (to support resuming)."""
    processed_questions = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # We use the question as a proxy for the chunk (imperfect but works for resumes)
                    # Or we could have saved the chunk_id in the JSON. 
                    # For now, let's just check the question content.
                    processed_questions.add(data.get("input", ""))
                except:
                    continue
    return processed_questions

def call_groq_with_retry(client, messages, model=GENERATION_MODEL, max_tokens=500):
    """Call Groq with automatic retry logic for rate limits (429)."""
    max_retries = 5
    base_delay = 5
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                timeout=30
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg:
                # Try to parse wait time from error: "Please try again in 3m55.008s"
                wait_time = base_delay * (2 ** attempt) # Default exponential backoff
                
                # Regex to find time in error message
                match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", err_msg)
                if match:
                    m = int(match.group(1)) if match.group(1) else 0
                    s = float(match.group(2))
                    wait_time = (m * 60) + s + 2 # Add a small buffer
                
                print(f"[RateLimit] Hit 429. Waiting {wait_time:.1f}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                print(f"[GroqError] {err_msg}")
                return None
    return None

def generate_question_for_chunk(client, text, metadata):
    prompt = f"""
    Given this legal text, generate ONE specific factual question a person might ask.
    Return ONLY the question.

    Legal text:
    {text[:500]}
    """
    return call_groq_with_retry(client, [{"role": "user", "content": prompt}], max_tokens=100)

def call_groq_for_ideal_answer(client, question, context):
    system_prompt = """You are a legal information assistant for Indian law. Answer using ONLY the provided context.
    Structure your answer as:
    ANSWER: [clear explanation]
    LEGAL BASIS: [exact quote from source]
    CITATIONS: [numbered list: Document | Section/Para | Court | Date]
    AMENDMENTS: [any amendments to cited sections]
    Never give legal advice. State only what the law says."""

    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    return call_groq_with_retry(client, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ], max_tokens=600)

def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    processed_inputs = get_already_processed_chunks()
    
    print(f"Connecting to database... Using model: {GENERATION_MODEL}")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            query = """
            SELECT c.chunk_text, c.unified_metadata, s.title
            FROM chunks c
            JOIN sources s ON c.source_id = s.id
            WHERE c.chunk_type = 'legal' AND c.unified_metadata IS NOT NULL
            LIMIT 2000
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                print("No rows found matching criteria.")
                return

            print(f"Found {len(rows)} legal chunks. Resuming from {len(processed_inputs)} already generated.")
            
            count = 0
            # Open in append mode
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for row in rows:
                    text = row['chunk_text']
                    title = row['title']
                    metadata = row['unified_metadata']
                    
                    # 1. Generate question
                    question = generate_question_for_chunk(client, text, metadata)
                    if not question: continue
                    
                    # Simple check for duplication (by question prompt)
                    context = f"Source: {title}\n{text}"
                    input_str = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
                    if input_str in processed_inputs:
                        continue
                    
                    time.sleep(0.5) # Reduced sleep since we have 429 handling now
                    
                    # 2. Generate ideal answer
                    answer = call_groq_for_ideal_answer(client, question, context)
                    if not answer: continue
                    
                    # 3. Create training sample
                    sample = {
                        "instruction": "You are a legal information assistant for Indian law. Answer ONLY using provided context.",
                        "input": input_str,
                        "output": answer
                    }
                    
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    f.flush() # Ensure it's written in case of crash
                    
                    count += 1
                    if count % 10 == 0:
                        print(f"Progress: {count} NEW samples generated (Total in file: {len(processed_inputs) + count})...")
                    
                    time.sleep(0.5)
                    
            print(f"Dataset generation complete. Total NEW examples generated: {count}")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
