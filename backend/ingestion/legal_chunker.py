import json
import uuid
import re
from pathlib import Path

def create_statute_chunks(doc: dict) -> list[dict]:
    source = doc.get("source", "unknown")
    if source.lower() == "ipc_1860":
        statute_name = "IPC 1860"
    elif source.lower() == "crpc_1973":
        statute_name = "CrPC 1973"
    elif "constitution" in source.lower():
        statute_name = "Constitution of India"
    else:
        statute_name = doc.get("full_title", source)

    chunks = []
    
    for section in doc.get("content", []):
        sec_id = section.get("section_id", "")
        title = section.get("title", "")
        text = section.get("text", "")
        sub_sections = section.get("sub_sections", [])
        explanations = section.get("explanations", [])
        exceptions = section.get("exceptions", [])
        amendments = section.get("amendments", [])
        chapter = section.get("chapter", "")
        
        prefix = f"<SECTION {sec_id}, {statute_name} — {title}>\n"
        
        body = text if text else ""
        if sub_sections:
            body += "\n" + "\n".join(sub_sections)
        if explanations:
            body += "\n" + "\n".join(explanations)
        if exceptions:
            body += "\n" + "\n".join(exceptions)
            
        full_text = prefix + body
        
        metadata = {
            "source": source,
            "doc_type": doc.get("doc_type", "statute"),
            "section_id": sec_id,
            "title": title,
            "chapter": chapter,
            "has_explanation": bool(explanations),
            "has_exception": bool(exceptions),
            "amendments": amendments
        }
        
        if len(full_text) > 1000:
            lines = body.split("\n")
            current_buffer = ""
            for line in lines:
                if len(current_buffer) + len(line) + 1 > 800 and current_buffer:
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "text": prefix + current_buffer.strip(),
                        "metadata": metadata
                    })
                    current_buffer = line
                else:
                    if current_buffer:
                        current_buffer += "\n" + line
                    else:
                        current_buffer = line
            if current_buffer:
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "text": prefix + current_buffer.strip(),
                    "metadata": metadata
                })
        else:
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "text": full_text.strip(),
                "metadata": metadata
            })
            
    return chunks


def create_judgment_chunks(doc: dict) -> list[dict]:
    source = doc.get("source", "unknown")
    meta = doc.get("metadata", {})
    case_name = meta.get("case_name", "")
    court = meta.get("court", "")
    date = meta.get("date", "")
    
    cited_sections = doc.get("cited_sections", [])
    cited_cases = doc.get("cited_cases", [])
    paragraphs = doc.get("paragraphs", [])
    
    chunks = []
    
    for i in range(0, len(paragraphs), 3):
        group = paragraphs[i:i+3]
        if not group:
            continue
            
        start_para = group[0].get("para_num", "?")
        end_para = group[-1].get("para_num", "?")
        if start_para == end_para:
            para_range = f"{start_para}"
        else:
            para_range = f"{start_para}-{end_para}"
            
        prefix = f"<JUDGMENT: {case_name}, {court}, {date}, para {para_range}>\n"
        
        texts = []
        for p in group:
            texts.append(f"[Para {p.get('para_num', '?')}] {p.get('text', '')}")
            
        body = "\n".join(texts)
        full_text = prefix + body
        
        metadata = {
            "source": source,
            "doc_type": "judgment",
            "case_name": case_name,
            "court": court,
            "date": date,
            "para_range": para_range,
            "cited_sections": cited_sections,
            "cited_cases": cited_cases
        }
        
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "text": full_text,
            "metadata": metadata
        })
        
    return chunks


def chunk_all_documents(processed_dir: Path) -> list[dict]:
    all_chunks = []
    
    stats_statutes = 0
    stats_judgments = 0
    
    for json_file in processed_dir.rglob("*.json"):
        if json_file.name == "all_chunks.jsonl":
            continue
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                doc = json.load(f)
                
            doc_type = doc.get("doc_type")
            if doc_type in ['statute', 'constitution']:
                chunks = create_statute_chunks(doc)
                stats_statutes += len(chunks)
            elif doc_type == 'judgment':
                chunks = create_judgment_chunks(doc)
                stats_judgments += len(chunks)
            else:
                continue
                
            print(f"Chunking {json_file.name} → {len(chunks)} chunks")
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
            
    print(f"Total chunks: {len(all_chunks)}  |  Statutes: {stats_statutes}  |  Judgments: {stats_judgments}")
    return all_chunks


if __name__ == "__main__":
    processed_dir = Path("data/legal_processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    chunks = chunk_all_documents(processed_dir)
    
    out_file = processed_dir / "all_chunks.jsonl"
    with open(out_file, 'w', encoding='utf-8') as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
