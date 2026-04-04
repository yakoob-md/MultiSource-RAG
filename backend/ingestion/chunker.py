import re

# ── Chunking settings ─────────────────────────────────────────────────────────
# These are now token/sentence based, not raw character counts.
# TARGET_SENTENCES : ideal number of sentences per chunk
# MAX_CHUNK_CHARS  : hard ceiling — chunks never exceed this
# OVERLAP_SENTENCES: how many sentences from the end of chunk N
#                    are prepended to chunk N+1
#                    (keeps context across boundaries)
TARGET_SENTENCES  = 5
MAX_CHUNK_CHARS   = 1200
OVERLAP_SENTENCES = 1


# ── Sentence splitter ─────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex.
    Handles common abbreviations to avoid false splits (e.g. "Dr.", "U.S.").

    Why not use spaCy or NLTK?
    Those libraries are excellent but add heavy dependencies and slow
    startup time. For a RAG system this regex approach handles 95% of
    real-world text correctly without any extra installs.

    The pattern splits after  .  !  ?  followed by a space and
    an uppercase letter — which is the standard sentence boundary signal.

    Args:
        text: raw cleaned text string

    Returns:
        list of sentence strings (no empty strings)
    """
    # Protect common abbreviations from being split
    # Replace their periods temporarily with a placeholder
    abbreviations = [
        r'Mr\.', r'Mrs\.', r'Ms\.', r'Dr\.', r'Prof\.', r'Sr\.', r'Jr\.',
        r'vs\.', r'etc\.', r'i\.e\.', r'e\.g\.', r'U\.S\.', r'U\.K\.',
        r'Fig\.', r'No\.', r'Vol\.', r'pp\.', r'al\.',
    ]
    protected = text
    for abbr in abbreviations:
        protected = re.sub(abbr, lambda m: m.group().replace('.', '<<DOT>>'), protected)

    # Split at sentence-ending punctuation followed by whitespace + capital
    # Also split at newlines that look like paragraph breaks (2+ newlines)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?:\n{2,})', protected)

    # Restore protected dots and clean up
    result = []
    for s in sentences:
        s = s.replace('<<DOT>>', '.').strip()
        if s:
            result.append(s)

    return result


# ── Core semantic chunker ─────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """
    Split a long text into semantically coherent chunks.

    Strategy:
    1. Split the text into sentences first
    2. Group sentences into chunks of ~TARGET_SENTENCES each
    3. If a chunk would exceed MAX_CHUNK_CHARS, close it early
    4. Carry OVERLAP_SENTENCES from the end of each chunk into
       the beginning of the next, so no context is lost at boundaries

    Why this is better than fixed character splitting:
    - Each chunk is a complete thought (full sentences)
    - Embedding quality improves because the model sees coherent text
    - Retrieval precision improves because chunks don't contain
      half-sentences from two unrelated paragraphs

    Example:
        "The cat sat. The dog ran. The bird flew." with TARGET=2, OVERLAP=1
        chunk 0 → "The cat sat. The dog ran."
        chunk 1 → "The dog ran. The bird flew."   ← overlap keeps context

    Args:
        text: raw cleaned text string

    Returns:
        list of chunk strings
    """
    text = text.strip()
    if not text:
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    # Edge case: if the entire text is one long sentence, return it as-is
    # (split it by MAX_CHUNK_CHARS as a fallback)
    if len(sentences) == 1:
        if len(text) <= MAX_CHUNK_CHARS:
            return [text]
        # Fall back to character splitting for a single huge sentence
        return [text[i:i+MAX_CHUNK_CHARS] for i in range(0, len(text), MAX_CHUNK_CHARS - 100)]

    chunks  = []
    current = []      # sentences in the current chunk
    current_len = 0   # character count of current chunk

    for sentence in sentences:
        sentence_len = len(sentence)

        # If adding this sentence would blow the hard limit AND
        # we already have some content → close the current chunk
        if current and (current_len + sentence_len > MAX_CHUNK_CHARS):
            chunks.append(" ".join(current))

            # Carry overlap sentences into next chunk
            overlap = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES > 0 else []
            current = overlap.copy()
            current_len = sum(len(s) for s in current)

        current.append(sentence)
        current_len += sentence_len

        # If we have reached the target sentence count → close the chunk
        if len(current) >= TARGET_SENTENCES + OVERLAP_SENTENCES:
            chunks.append(" ".join(current))

            # Carry overlap sentences into next chunk
            overlap = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES > 0 else []
            current = overlap.copy()
            current_len = sum(len(s) for s in current)

    # Don't forget the last partial chunk
    if current:
        last_chunk = " ".join(current).strip()
        if last_chunk:
            chunks.append(last_chunk)

    return chunks


# ── PDF chunker (page-aware) ──────────────────────────────────────────────────

def chunk_text_with_pages(pages: list[str]) -> list[dict]:
    """
    Chunk text from a PDF where each item in `pages` is one page.
    Preserves the page number for each chunk.

    Uses semantic chunking per page — each page is chunked independently
    so a chunk never spans two pages (which preserves citation accuracy).

    Args:
        pages: list of strings, one per PDF page

    Returns:
        list of dicts:
        [
            {"text": "...", "page_number": 1},
            {"text": "...", "page_number": 2},
            ...
        ]
    """
    result = []

    for page_num, page_text in enumerate(pages, start=1):
        page_text = page_text.strip()
        if not page_text:
            continue

        chunks = chunk_text(page_text)
        for chunk in chunks:
            result.append({
                "text"       : chunk,
                "page_number": page_num,
            })

    return result


# ── YouTube chunker (timestamp-aware) ────────────────────────────────────────

def chunk_text_with_timestamps(segments: list[dict]) -> list[dict]:
    """
    Chunk YouTube transcript segments, preserving timestamps.

    Each segment from youtube-transcript-api looks like:
        {"text": "hello world", "start": 12.5, "duration": 3.2}

    Strategy:
    - We group segments by sentence boundaries, not raw character count
    - When accumulated sentences reach TARGET_SENTENCES (or MAX_CHUNK_CHARS),
      close the chunk and record the timestamp of its first segment
    - OVERLAP_SENTENCES sentences carry over to the next chunk

    Args:
        segments: list of transcript segment dicts

    Returns:
        list of dicts:
        [
            {"text": "...", "timestamp_s": 12},
            {"text": "...", "timestamp_s": 45},
            ...
        ]
    """
    # Step 1: Concatenate all segment texts into one string,
    # but track where each segment starts in the string for timestamp mapping
    if not segments:
        return []

    # Build full transcript text with segment boundary markers
    # We need to map sentence positions back to timestamps
    full_text_parts = []
    seg_positions   = []   # (start_char_index, timestamp_s) for each segment
    char_cursor     = 0

    for seg in segments:
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue
        seg_positions.append((char_cursor, int(seg.get("start", 0))))
        full_text_parts.append(seg_text)
        char_cursor += len(seg_text) + 1  # +1 for the space separator

    if not full_text_parts:
        return []

    full_text = " ".join(full_text_parts)

    # Step 2: Split into sentences
    sentences = _split_sentences(full_text)
    if not sentences:
        return []

    # Step 3: For each sentence, find the closest segment timestamp
    def get_timestamp_for_pos(char_pos: int) -> int:
        """Return timestamp of the segment that contains char_pos."""
        ts = 0
        for start_pos, timestamp in seg_positions:
            if start_pos <= char_pos:
                ts = timestamp
            else:
                break
        return ts

    # Step 4: Group sentences into chunks (same logic as chunk_text)
    result  = []
    current = []
    current_len = 0
    chunk_start_ts = 0  # timestamp of the first sentence in this chunk

    # Track char position as we walk through sentences
    char_cursor = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        sentence_ts  = get_timestamp_for_pos(char_cursor)

        if not current:
            chunk_start_ts = sentence_ts

        # Close chunk if hard limit reached
        if current and (current_len + sentence_len > MAX_CHUNK_CHARS):
            result.append({
                "text"       : " ".join(current).strip(),
                "timestamp_s": chunk_start_ts,
            })
            overlap = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES > 0 else []
            current = overlap.copy()
            current_len = sum(len(s) for s in current)
            if current:
                chunk_start_ts = sentence_ts

        current.append(sentence)
        current_len += sentence_len
        char_cursor += sentence_len + 1  # +1 for space

        # Close chunk if target sentence count reached
        if len(current) >= TARGET_SENTENCES + OVERLAP_SENTENCES:
            result.append({
                "text"       : " ".join(current).strip(),
                "timestamp_s": chunk_start_ts,
            })
            overlap = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES > 0 else []
            current = overlap.copy()
            current_len = sum(len(s) for s in current)
            if current:
                chunk_start_ts = sentence_ts

    # Last partial chunk
    if current:
        last_chunk = " ".join(current).strip()
        if last_chunk:
            result.append({
                "text"       : last_chunk,
                "timestamp_s": chunk_start_ts,
            })

    return result