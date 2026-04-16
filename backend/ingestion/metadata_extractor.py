import re
import json
import logging
from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

def parse_with_regex(text: str) -> dict:
    """Fallback Regex parsing if LLM fails or is unavailable."""
    metadata = {
        "case_name": None,
        "court": None,
        "date": None,
        "ipc_sections": [],
        "citation": None,
        "petitioner": None,
        "respondent": None
    }

    court_match = re.search(r"(IN THE SUPREME COURT OF INDIA|HIGH COURT OF [A-Z\s]+|DISTRICT COURT OF [A-Z\s]+)", text, re.IGNORECASE)
    if court_match: metadata["court"] = court_match.group(0).strip()

    date_match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", text, re.IGNORECASE)
    if date_match: metadata["date"] = date_match.group(0).strip()

    ipc_matches = re.findall(r"(?:Section|IPC|u/s)\s+(\d+[A-Z]?)", text, re.IGNORECASE)
    if ipc_matches: metadata["ipc_sections"] = list(set([f"Section {m}" for m in ipc_matches]))

    top_text = text[:3000]
    case_patterns = [r"(.+)\s+vs\.?\s+(.+)", r"(.+)\s+v\.\s+(.+)"]
    for pattern in case_patterns:
        case_match = re.search(pattern, top_text, re.IGNORECASE)
        if case_match:
            p_raw = case_match.group(1).strip().split('\n')[-1]
            r_raw = case_match.group(2).strip().split('\n')[0]
            metadata["petitioner"] = re.sub(r"^(Petitioner|Appellant|Plaintiff):\s*", "", p_raw, flags=re.IGNORECASE).strip()
            metadata["respondent"] = re.sub(r"^(Respondent|Defendant):\s*", "", r_raw, flags=re.IGNORECASE).strip()
            metadata["case_name"] = f"{metadata['petitioner']} vs {metadata['respondent']}"
            break

    cit_match = re.search(r"(\(\d{4}\)\s+\d+\s+SCC\s+\d+|AIR\s+\d{4}\s+SC\s+\d+)", text, re.IGNORECASE)
    if cit_match: metadata["citation"] = cit_match.group(0).strip()

    return metadata

def extract_metadata(text: str, doc_type: str) -> dict:
    """
    Extract legal metadata using Groq JSON Mode LLM processing,
    falling back to Regex if LLM fails.
    """
    head_text = text[:8000] # Provide enough context to find headers
    
    system_prompt = '''You are a strict legal data extractor. Extract exactly these fields from the document text:
    case_name (string or null), court (string or null), date (string or null), 
    ipc_sections (array of strings like ["Section 302", "Section 120B"] or empty []), 
    citation (string or null), petitioner (string or null), respondent (string or null).
    Output valid JSON only. Do not wrap in markdown blocks.'''

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document context:\n{head_text}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=1024,
            temperature=0.0
        )
        data = json.loads(response.choices[0].message.content)
        
        # Merge defaults to guarantee all schema fields exist safely
        default_schema = {
            "case_name": None, "court": None, "date": None, 
            "ipc_sections": [], "citation": None, 
            "petitioner": None, "respondent": None
        }
        for k in default_schema.keys():
            if k in data and data[k] is not None:
                default_schema[k] = data[k]
                
        logger.info("[MetadataExtractor] Successfully extracted metadata via LLM.")
        return default_schema

    except Exception as e:
        logger.warning(f"[MetadataExtractor] LLM extraction failed ({e}). Falling back to Regex parsing.")
        return parse_with_regex(text)
