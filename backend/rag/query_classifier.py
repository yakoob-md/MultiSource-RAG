import json
import re
from dataclasses import dataclass
from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.database.connection import get_connection

@dataclass
class QueryAnalysis:
    intent          : str      # "single_source" | "comparison" | "synthesis"
    source_types    : list[str]  # ["legal_statute", "legal_judgment", "web", "youtube", "any"]
    topics          : list[str]  # extracted topics like ["murder", "302", "IPC"]
    ipc_sections    : list[str]  # ["302", "304"] if mentioned
    time_filter     : str | None # "2024" if year mentioned
    language_hint   : str        # "en" | "hi" — detected from query language
    requires_compare: bool       # True if "compare", "difference", "vs" in query
    requires_summary: bool       # True if "common", "all documents", "across" in query
    source_names    : list[str]  # ["IPC", "CrPC"] if explicitly named

def classify_query(question: str) -> QueryAnalysis:
    client = Groq(api_key=GROQ_API_KEY)
    
    system_prompt = """
    Classify this legal query. Return ONLY valid JSON with these exact keys:
    {
      "intent": "single_source" | "comparison" | "synthesis",
      "source_types": list of "legal_statute"|"legal_judgment"|"web"|"youtube"|"any",
      "topics": list of topic strings,
      "ipc_sections": list of section numbers as strings,
      "time_filter": year string or null,
      "language_hint": "en" or "hi",
      "requires_compare": boolean,
      "requires_summary": boolean,
      "source_names": list of named sources like ["IPC", "CrPC", "Constitution"]
    }

    Intent rules:
    - single_source: factual question about one law/concept
    - comparison: explicitly asks to compare, contrast, or find differences between two things
    - synthesis: asks for common themes, summary across multiple documents, or general overview
    """

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {question}"}
            ],
            model=GROQ_MODEL,
            max_tokens=300,
            stream=False,
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        return QueryAnalysis(
            intent=data.get("intent", "single_source"),
            source_types=data.get("source_types", ["any"]),
            topics=data.get("topics", []),
            ipc_sections=data.get("ipc_sections", []),
            time_filter=data.get("time_filter"),
            language_hint=data.get("language_hint", "en"),
            requires_compare=data.get("requires_compare", False),
            requires_summary=data.get("requires_summary", False),
            source_names=data.get("source_names", [])
        )
    except Exception as e:
        print(f"[QueryClassifier] Error: {e}")
        return QueryAnalysis(
            intent="single_source", 
            source_types=["any"], 
            topics=[], 
            ipc_sections=[], 
            time_filter=None, 
            language_hint="en", 
            requires_compare=False, 
            requires_summary=False, 
            source_names=[]
        )

def extract_source_filter(analysis: QueryAnalysis, available_source_ids: list[str]) -> list[str] | None:
    if "any" in analysis.source_types and not analysis.source_names:
        return None
        
    source_ids = []
    
    # If explicitly named sources are found
    if analysis.source_names:
        try:
            with get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                for name in analysis.source_names:
                    # Search in sources table for title matches
                    query = "SELECT id FROM sources WHERE title LIKE %s"
                    cursor.execute(query, (f"%{name}%",))
                    rows = cursor.fetchall()
                    source_ids.extend([row['id'] for row in rows])
        except Exception as e:
            print(f"[QueryClassifier] DB Error in filter extraction: {e}")

    # If source types are specified (e.g., youtube, web)
    # This logic can be expanded based on how source_type is stored in DB
    
    # Deduplicate and filter by available_source_ids if provided
    source_ids = list(set(source_ids))
    if available_source_ids and source_ids:
        source_ids = [sid for sid in source_ids if sid in available_source_ids]
        
    return source_ids if source_ids else None
