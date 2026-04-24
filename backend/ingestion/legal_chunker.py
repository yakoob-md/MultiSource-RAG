import re
from backend.ingestion.chunker import chunk_text

def chunk_statute(text: str) -> list[dict]:
    """
    Split statute/constitution text at section boundaries.
    """
    # Regex for section boundary at start of line
    section_pattern = re.compile(r"^(?:Section|Sec\.?)\s+(\d+[A-Z]?)\.\s*(.*?)(?:—|\n|$)", re.MULTILINE | re.IGNORECASE)
    
    # Find all boundaries to split the text
    matches = list(section_pattern.finditer(text))
    
    if not matches:
        # Fallback to standard chunking if no sections found
        return [{"text": c} for c in chunk_text(text)]

    chunks = []
    for i, match in enumerate(matches):
        section_number = match.group(1)
        section_title = match.group(2).strip()
        
        # Start of current section is the start of the match
        # End of current section is the start of the next match or end of text
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        
        section_body = text[start:end].strip()
        
        if len(section_body) > 1200:
            # Split further if too large
            sub_chunks = chunk_text(section_body)
            for sc in sub_chunks:
                chunks.append({
                    "text": sc,
                    "section_number": section_number,
                    "section_title": section_title
                })
        else:
            chunks.append({
                "text": section_body,
                "section_number": section_number,
                "section_title": section_title
            })
            
    return chunks

def chunk_judgment(text: str) -> list[dict]:
    """
    Split judgment text at paragraph boundaries and manage chunk sizes (200-800 chars).
    """
    # Boundary: [1]...[999] or blank line separating blocks
    # We'll split by [n] patterns first
    para_pattern = re.compile(r"\[(\d+)\]")
    
    # Also split by double newlines if they seem to separate sentence blocks
    # For simplicity, we'll split by paragraphs and then handle size
    raw_paras = []
    
    last_pos = 0
    for match in para_pattern.finditer(text):
        if match.start() > last_pos:
            block = text[last_pos:match.start()].strip()
            if block:
                # If block has multiple newlines, split it further
                sub_blocks = [b.strip() for b in re.split(r'\n\s*\n', block) if b.strip()]
                raw_paras.extend(sub_blocks)
        
        # Current paragraph marker starts here
        last_pos = match.start()
    
    # Add the remaining text
    if last_pos < len(text):
        block = text[last_pos:].strip()
        if block:
            sub_blocks = [b.strip() for b in re.split(r'\n\s*\n', block) if b.strip()]
            raw_paras.extend(sub_blocks)

    if not raw_paras:
        return [{"text": c} for c in chunk_text(text)]

    # Merge/Split logic
    processed_chunks = []
    current_buffer = ""
    para_count = 0
    
    for para in raw_paras:
        # 1. If buffer + para is too large (> 800), close buffer first
        if current_buffer and (len(current_buffer) + len(para) > 800):
            processed_chunks.append({
                "text": current_buffer.strip(),
                "paragraph_number": para_count
            })
            current_buffer = ""

        # 2. Add para to buffer
        if current_buffer:
            current_buffer += "\n\n" + para
        else:
            current_buffer = para
            para_count += 1 # Rough tracking of paragraph sequence

        # 3. If current buffer is already too large (> 800), split it
        if len(current_buffer) > 800:
            sub_chunks = chunk_text(current_buffer)
            # Add all but the last one (which might be < 200)
            for sc in sub_chunks[:-1]:
                processed_chunks.append({
                    "text": sc,
                    "paragraph_number": para_count
                })
            current_buffer = sub_chunks[-1]

    # Final buffer handling
    if current_buffer:
        if len(current_buffer) < 200 and processed_chunks:
            # Merge with previous if too short
            processed_chunks[-1]["text"] += "\n\n" + current_buffer
        else:
            processed_chunks.append({
                "text": current_buffer.strip(),
                "paragraph_number": para_count
            })

    return processed_chunks

def chunk_legal_document(text: str, doc_type: str) -> list[dict]:
    """
    Dispatcher for legal document chunking.
    """
    if doc_type in ['statute', 'constitution']:
        return chunk_statute(text)
    elif doc_type == 'judgment':
        return chunk_judgment(text)
    else:
        # Default fallback
        return [{"text": c} for c in chunk_text(text)]
