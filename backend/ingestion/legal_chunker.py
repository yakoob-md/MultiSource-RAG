import re
from backend.ingestion.chunker import chunk_text

def chunk_statute(text: str) -> list[dict]:
    """
    Split statute text at section boundaries.
    Each section becomes one or more chunks.
    """
    # Regex for section headers: "Section 302." or "Sec 302." at start of line
    # Using MULTILINE so ^ matches start of lines
    section_pattern = re.compile(r"^(?:Section|Sec\.?)\s+(\d+[A-Z]?)\.", re.MULTILINE | re.IGNORECASE)
    
    matches = list(section_pattern.finditer(text))
    if not matches:
        # Fallback if no sections found
        return [{"text": t} for t in chunk_text(text)]

    result = []
    for i, match in enumerate(matches):
        section_number = match.group(1)
        start = match.start()
        end = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        section_full_text = text[start:end].strip()
        
        # Extract section_title: text after number and period, up to em-dash or newline
        # Example: "Section 302. Punishment for murder—Whoever..."
        title_line = section_full_text.split('\n')[0]
        # Skip the "Section 302. " part
        title_part = title_line[match.end() - match.start():].strip()
        section_title = re.split(r'[—\-]', title_part)[0].strip() if title_part else None

        # Split if exceeds length
        if len(section_full_text) > 1200:
            sub_chunks = chunk_text(section_full_text)
            for sc in sub_chunks:
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
    """
    Split judgments at paragraph boundaries with size-aware merging/splitting.
    """
    # 1. Detect boundaries: [1] through [999] or blank line separating 3+ sentence blocks
    # We'll use numbered paragraphs as the primary delimiter
    paragraphs = re.split(r'\n\s*\[(\d{1,3})\]\s*', text)
    
    # re.split with groups returns the split parts AND the groups
    # [intro, "1", p1, "2", p2, ...]
    blocks = []
    if len(paragraphs) > 1:
        intro = paragraphs[0].strip()
        if intro:
            blocks.append({"text": intro, "paragraph_number": 0})
        
        for i in range(1, len(paragraphs), 2):
            num = int(paragraphs[i])
            content = paragraphs[i+1].strip()
            if content:
                blocks.append({"text": f"[{num}] {content}", "paragraph_number": num})
    else:
        # No numbered paragraphs found, split by double newlines as fallback
        raw_blocks = [p.strip() for p in text.split('\n\n') if p.strip()]
        for i, b in enumerate(raw_blocks):
            blocks.append({"text": b, "paragraph_number": i + 1})

    # 2. Process blocks: merge < 200, split > 800
    final_chunks = []
    current_buffer = ""
    current_nums = []

    for block in blocks:
        text_block = block["text"]
        
        # If block is huge, split it first
        if len(text_block) > 800:
            # If we had a buffer, flush it first
            if current_buffer:
                final_chunks.append({
                    "text": current_buffer.strip(),
                    "paragraph_number": current_nums[0] if current_nums else None
                })
                current_buffer = ""
                current_nums = []

            sub_chunks = chunk_text(text_block)
            for sc in sub_chunks:
                final_chunks.append({
                    "text": sc,
                    "paragraph_number": block["paragraph_number"]
                })
            continue

        # Normal/Small block coordination
        if current_buffer:
            temp = current_buffer + "\n\n" + text_block
        else:
            temp = text_block
        
        if len(temp) < 200:
            current_buffer = temp
            current_nums.append(block["paragraph_number"])
        elif len(temp) > 800:
            # Over the limit if we add this one, flush buffer and start new
            if current_buffer:
                final_chunks.append({
                    "text": current_buffer.strip(),
                    "paragraph_number": current_nums[0] if current_nums else None
                })
            current_buffer = text_block
            current_nums = [block["paragraph_number"]]
        else:
            # Perfectly sized
            final_chunks.append({
                "text": temp.strip(),
                "paragraph_number": current_nums[0] if current_nums else block["paragraph_number"]
            })
            current_buffer = ""
            current_nums = []

    # Final flush
    if current_buffer:
        final_chunks.append({
            "text": current_buffer.strip(),
            "paragraph_number": current_nums[0] if current_nums else None
        })

    return final_chunks

def chunk_legal_document(text: str, doc_type: str) -> list[dict]:
    """
    Unified entry point for legal document chunking.
    """
    if doc_type in ['statute', 'constitution']:
        return chunk_statute(text)
    elif doc_type == 'judgment':
        return chunk_judgment(text)
    else:
        # Generic fallback
        return [{"text": t} for t in chunk_text(text)]
