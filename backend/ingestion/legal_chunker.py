import re
from backend.ingestion.chunker import chunk_text

def chunk_statute(text: str) -> list[dict]:
    # Regex for section headers
    pattern = re.compile(r"^(Section|Sec\.?)\s+(\d+[A-Z]?)\.", re.MULTILINE | re.IGNORECASE)
    matches = list(pattern.finditer(text))
    
    if not matches:
        return [{"text": t, "section_number": None, "section_title": None} for t in chunk_text(text)]
        
    result = []
    
    for i, match in enumerate(matches):
        section_number = match.group(2)
        start_idx = match.start()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        section_full_text = text[start_idx:end_idx].strip()
        
        # Extract title from the first line
        title_line = section_full_text.split("\n")[0]
        title_line = title_line[match.end() - match.start():].strip() # strip Section X.
        
        title_splits = re.split(r'[—\-]', title_line, maxsplit=1)
        section_title = title_splits[0].strip() if title_splits else None
        
        if len(section_full_text) > 1200:
            chunks = chunk_text(section_full_text)
            for sc in chunks:
                result.append({
                    "text": sc,
                    "section_number": section_number,
                    "section_title": section_title
                })
        else:
            result.append({
                "text": section_full_text,
                "section_number": section_number,
                "section_title": section_title
            })
            
    return result

def chunk_judgment(text: str) -> list[dict]:
    # Split paragraphs by [1], [2], etc.
    parts = re.split(r'\n\s*\[(\d{1,3})\]\s*', text)
    
    blocks = []
    if len(parts) > 1:
        if parts[0].strip():
            blocks.append({"text": parts[0].strip(), "num": 0})
            
        for i in range(1, len(parts), 2):
            num = int(parts[i])
            content = parts[i+1].strip()
            if content:
                blocks.append({"text": f"[{num}] {content}", "num": num})
    else:
        # Fallback to blank lines
        raw_blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        for i, b in enumerate(raw_blocks):
            blocks.append({"text": b, "num": i+1})
            
    final_chunks = []
    current_buffer = ""
    current_num = None
    
    for block in blocks:
        block_text = block["text"]
        b_num = block["num"]
        
        # 1. Block > 800
        if len(block_text) > 800:
            if current_buffer:
                final_chunks.append({"text": current_buffer, "paragraph_number": current_num})
                current_buffer = ""
                current_num = None
            
            sub_chunks = chunk_text(block_text)
            for sc in sub_chunks:
                final_chunks.append({"text": sc, "paragraph_number": b_num})
            continue

        temp = (current_buffer + "\n\n" + block_text).strip() if current_buffer else block_text
        
        # 2. Block < 200
        if len(temp) < 200:
            current_buffer = temp
            if current_num is None:
                current_num = b_num
        
        # 3. Block 200-800
        elif 200 <= len(temp) <= 800:
            final_chunks.append({"text": temp, "paragraph_number": current_num if current_num is not None else b_num})
            current_buffer = ""
            current_num = None
            
        # 4. Merging pushes it > 800
        else:
            final_chunks.append({"text": current_buffer, "paragraph_number": current_num})
            current_buffer = block_text
            current_num = b_num
            if len(current_buffer) >= 200:
                final_chunks.append({"text": current_buffer, "paragraph_number": current_num})
                current_buffer = ""
                current_num = None
                
    if current_buffer:
        final_chunks.append({"text": current_buffer, "paragraph_number": current_num})
        
    return final_chunks

def chunk_legal_document(text: str, doc_type: str) -> list[dict]:
    if doc_type in ['statute', 'constitution']:
        return chunk_statute(text)
    elif doc_type == 'judgment':
        return chunk_judgment(text)
    
    return [{"text": t} for t in chunk_text(text)]
