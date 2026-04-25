import json
import os
import time
import sys
from pathlib import Path
from groq import Groq

# Add project root to sys.path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.database.connection import get_connection

# Ensure output directory exists
OUTPUT_FILE = Path("data/training/legal_rag_dataset.jsonl")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def generate_question_for_chunk(client, text, metadata):
    """Generate a specific factual question for a given chunk of legal text."""
    prompt = f"""
    Given this legal text, generate ONE specific factual question a person might ask.
    Return ONLY the question.

    Legal text:
    {text[:500]}
    """
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=GROQ_MODEL,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating question: {e}")
        return None

def call_groq_for_ideal_answer(client, question, context):
    """Generate a structured legal answer using the provided context."""
    system_prompt = """You are a legal information assistant for Indian law. Answer using ONLY the provided context.
    Structure your answer as:
    ANSWER: [clear explanation]
    LEGAL BASIS: [exact quote from source]
    CITATIONS: [numbered list: Document | Section/Para | Court | Date]
    AMENDMENTS: [any amendments to cited sections]
    Never give legal advice. State only what the law says."""

    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating answer: {e}")
        return None

def main():
    if not GROQ_API_KEY:
        print("GROQ_API_KEY not found. Please set it in .env")
        return

    client = Groq(api_key=GROQ_API_KEY)
    
    print("Connecting to database...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Query chunks as specified
            # Note: c.unified_metadata IS NOT NULL is a strict filter.
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
                print("No rows found matching the criteria (c.chunk_type='legal' AND c.unified_metadata IS NOT NULL).")
                print("Tip: Ensure you have populated the unified_metadata column.")
                return

            print(f"Found {len(rows)} legal chunks. Starting dataset generation...")
            
            count = 0
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for row in rows:
                    text = row['chunk_text']
                    metadata = row['unified_metadata']
                    title = row['title']
                    
                    # 1. Generate question
                    question = generate_question_for_chunk(client, text, metadata)
                    if not question:
                        continue
                    
                    time.sleep(1) # Rate limiting
                    
                    # 2. Generate ideal answer
                    context = f"Source: {title}\n{text}"
                    answer = call_groq_for_ideal_answer(client, question, context)
                    if not answer:
                        continue
                    
                    # 3. Create training sample
                    sample = {
                        "instruction": "You are a legal information assistant for Indian law. Answer ONLY using provided context.",
                        "input": f"CONTEXT:\n{context}\n\nQUESTION: {question}",
                        "output": answer
                    }
                    
                    # 4. Save to JSONL
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    
                    count += 1
                    if count % 50 == 0:
                        print(f"Progress: {count} samples generated...")
                    
                    time.sleep(1) # Rate limiting
                    
            print(f"Dataset generation complete. Total examples generated: {count}")
            print(f"File saved to: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    main()
