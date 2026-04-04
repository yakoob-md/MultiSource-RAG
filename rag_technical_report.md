# Technical Project Report: Multi-Source RAG Knowledge Assistant

**Version:** 1.0  
**Date:** March 2026  
**Classification:** Internal Technical Documentation  
**System:** Multi-Source Retrieval-Augmented Generation (RAG) Knowledge Assistant

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Architecture](#4-backend-architecture)
5. [Detailed Data Processing Pipeline](#5-detailed-data-processing-pipeline)
6. [Query Processing and Answer Generation](#6-query-processing-and-answer-generation)
7. [Evaluation of the Current Implementation](#7-evaluation-of-the-current-implementation)
8. [Potential Improvements](#8-potential-improvements)
9. [Security and Reliability Considerations](#9-security-and-reliability-considerations)
10. [Scalability Considerations](#10-scalability-considerations)
11. [Conclusion](#11-conclusion)

---

## 1. Project Overview

### 1.1 Purpose and Motivation

The Multi-Source RAG Knowledge Assistant is a locally-deployable AI system designed to allow users to build a personalized, queryable knowledge base from heterogeneous information sources — PDF documents, web pages, and YouTube video transcripts — and interrogate that knowledge base using natural language questions. Answers are generated with precise citations back to the original source material.

The system addresses a fundamental problem in modern information retrieval: **the knowledge-retrieval gap**. Traditional information retrieval systems rely on keyword matching, which fails to capture semantic intent. Pure large language model (LLM) responses, on the other hand, are constrained by the model's training cutoff date and tend to hallucinate facts with confident-sounding language. Neither approach is satisfactory for knowledge-intensive tasks that require high accuracy and auditability.

### 1.2 Why Retrieval-Augmented Generation

RAG is the architectural solution chosen for this system precisely because it combines the strengths of both paradigms while mitigating their individual weaknesses:

- **Factual grounding:** The LLM's answer generation is constrained to the retrieved context. When the system explicitly instructs the model to answer *only* from the provided context — as implemented in [generator.py](file:///c:/Users/dabaa/OneDrive/Desktop/Rag_System/test_generator.py) — hallucination rates drop dramatically.
- **Domain adaptability:** The knowledge base can be populated with any domain-specific documents without retraining or fine-tuning the LLM. Adding a new PDF or URL immediately extends the system's knowledge.
- **Auditability:** Because answers are generated from specific retrieved chunks, every claim in the response can be traced back to an exact source, page number, URL, or video timestamp.
- **Freshness:** Unlike a static LLM, the RAG knowledge base can be updated in real time by ingesting new documents.
- **Cost efficiency:** The system runs entirely locally using Ollama (serving `llama3`) and a local FAISS vector index, with no dependency on external APIs for inference at query time.

These properties make RAG uniquely suitable for document-centric, knowledge-management scenarios where accuracy and source attribution are mandatory.

---

## 2. System Architecture

### 2.1 High-Level Data Flow

The system follows a classic two-phase RAG architecture: **offline ingestion** and **online retrieval-and-generation**.

```
┌─────────────────────────────────────────────────────────────┐
│                        INGESTION PHASE                      │
│                                                             │
│  [User] → Upload PDF / URL / YouTube                        │
│        → React Frontend (Vite + TypeScript)                 │
│        → POST /upload-pdf | /add-url | /add-youtube         │
│        → FastAPI Backend                                    │
│            ├─ Text Extraction (pypdf / BS4 / yt-transcript) │
│            ├─ Preprocessing & Cleaning                      │
│            ├─ Chunking (chunker.py, 800 chars, 100 overlap) │
│            ├─ Embedding (multilingual-e5-small, dim=384)    │
│            ├─ Vector Storage → FAISS (IndexFlatIP)          │
│            └─ Metadata Storage → MySQL (chunks, sources)    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     RETRIEVAL PHASE                         │
│                                                             │
│  [User] → Ask question                                      │
│        → React Frontend → POST /query                       │
│        → FastAPI Backend                                    │
│            ├─ Query Embedding (embed_query with "query: ")  │
│            ├─ FAISS similarity search (top-k=8)             │
│            ├─ MySQL metadata join (chunks JOIN sources)     │
│            ├─ Optional source_id filtering                  │
│            ├─ Prompt construction                           │
│            ├─ Ollama (llama3) → Answer generation           │
│            └─ Citation building                             │
│        ← { answer, citations, retrievedChunks }             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack Summary

| Layer | Technology | Version |
|---|---|---|
| Frontend | React + Vite + TypeScript + TailwindCSS | React 18 |
| Backend | Python + FastAPI + Uvicorn | FastAPI 0.115.6 |
| Vector Store | FAISS (CPU) | faiss-cpu 1.9.0 |
| Embedding Model | intfloat/multilingual-e5-small | SentenceTransformers 3.2.1 |
| Relational Database | MySQL (raw queries, no ORM) | mysql-connector-python 9.1.0 |
| LLM | llama3 via Ollama | Served locally |
| PDF Processing | pypdf + pdfplumber | pypdf 5.1.0 |
| Web Scraping | BeautifulSoup4 + requests + lxml | BS4 4.12.3 |
| YouTube | youtube-transcript-api | 1.2.4 |

### 2.3 Component Interaction

The frontend and backend are decoupled; the only communication channel is a REST API on `http://127.0.0.1:8000`. The backend is stateless at the HTTP layer: every request carries all required context. Persistent state lives in two stores — FAISS (vector index files on disk at `data/faiss_index/`) and MySQL (relational metadata). The LLM (Ollama) is a separate, locally-running service that the backend calls as a plain HTTP client.

---

## 3. Frontend Architecture

### 3.1 Component Structure

The frontend is organized as a single-page application built with React 18 and Vite, using TypeScript throughout. The application entry point is `main.tsx`, which renders a `RouterProvider` wrapping React Router. Navigation is handled declaratively through `routes.tsx`, which registers eight page routes rendered within a persistent `MainLayout`.

The folder structure follows a screen-centric pattern:

```
frontend/src/app/
├── api.ts              ← Centralized HTTP communication layer
├── types.ts            ← Shared TypeScript interfaces
├── routes.tsx          ← Route definitions
├── data/
│   └── history.ts      ← localStorage persistence
└── components/
    ├── MainLayout.tsx  ← App shell
    ├── Sidebar.tsx     ← Navigation + source preview
    ├── SourceCard.tsx  ← Reusable source card
    └── screens/        ← One component per page
        ├── Dashboard.tsx
        ├── AskAI.tsx
        ├── KnowledgeSources.tsx
        ├── UploadPDF.tsx
        ├── AddWebsite.tsx
        ├── AddYouTube.tsx
        ├── QueryHistory.tsx
        └── Settings.tsx
```

### 3.2 The Role of api.ts

`api.ts` is the sole communication bridge between the React components and the FastAPI backend. All HTTP calls are consolidated here, which enforces a clean separation of concerns and makes endpoint changes trivially maintainable — one file to update rather than hunting mutations across components.

The module exports the following functions that map directly onto backend REST endpoints:

| Function | HTTP Method | Endpoint | Purpose |
|---|---|---|---|
| `fetchSources()` | GET | `/sources` | Retrieve all knowledge sources |
| `uploadPdf(file)` | POST | `/upload-pdf` | Ingest a PDF document |
| `addWebsite(url, lang)` | POST | `/add-url` | Ingest a webpage |
| `addYouTube(url, lang)` | POST | `/add-youtube` | Ingest a YouTube video transcript |
| `queryRag(question, sourceIds?)` | POST | `/query` | Ask a question |
| `deleteSource(id)` | DELETE | `/sources/{id}` | Remove a source |
| `fetchHistory()` | GET | `/history` | Retrieve query history |
| `clearHistory()` | DELETE | `/history` | Clear query history |

### 3.3 The `normalizeSource()` Function

A technically important detail in `api.ts` is the `normalizeSource()` function. The backend speaks its own type vocabulary (e.g., source type `"url"`, language `"en"` in lowercase, timestamp field `"createdAt"`), while the frontend type system uses different conventions (`"web"`, `"EN"` in uppercase, `"dateAdded"`). `normalizeSource()` performs this bidirectional mapping, ensuring frontend components always receive a `KnowledgeSource` object with consistent shapes:

- Maps `"url"` → `"web"` for the type field
- Uppercases language codes (`"en"` → `"EN"`)
- Accepts either `createdAt` or `dateAdded` as a timestamp field, converting the raw string to a JavaScript `Date` object
- Extracts `videoId` from YouTube URLs using a regex match
- Provides sensible defaults for `status` (`"completed"`) and `chunkCount` (`0`)

### 3.4 State Management and User Interaction Flow

The application does not use any external state management library (e.g., Redux or Zustand). State is managed locally within components using React's `useState` and `useEffect` hooks.

The central interaction in `AskAI.tsx` exemplifies the pattern:

1. Local state variables `messages`, `question`, `isThinking`, `selectedSourceIds`, and `selectedChunks` govern the two-panel UI
2. On form submission, `queryRag(question, selectedSourceIds)` is called — an optional `sourceIds` argument restricts the vector search to specific sources, enabling **scoped querying**
3. A temporary "thinking" assistant message is shown while the backend processes (~2–30 seconds depending on LLM speed)
4. On response, the answer, citations, and retrieved chunks are mapped into their frontend type shapes and appended to the chat history
5. The conversation is persisted to `localStorage` under key `"rag_chat_history"` for session persistence

The sidebar source list refresh uses a custom browser event (`sources-updated`) dispatched by `notifySidebarRefresh()` after any upload, allowing the `Sidebar` component to re-fetch sources without a page reload — partially mitigating a documented stale-state issue where the sidebar fetches sources only once on mount.

### 3.5 Knowledge Source Management

`KnowledgeSources.tsx` provides the full source management interface: search by keyword, filter by type (PDF/Web/YouTube) or language (EN/HI/TE), and delete individual sources via the kebab menu. Deletion calls `deleteSource(id)` and optimistically removes the source from local state without a full reload. The `SourceCard` component renders in both normal and compact modes to accommodate different layout density requirements.

---

## 4. Backend Architecture

### 4.1 Modular Structure

The backend follows a clean module decomposition designed for readability and maintainability:

```
backend/
├── main.py             ← FastAPI app factory, CORS, route registration
├── config.py           ← All configuration constants (paths, model names, credentials)
├── database/
│   ├── connection.py   ← MySQL connection context manager
│   └── schema.sql      ← Table definitions
├── ingestion/
│   ├── pdf_loader.py   ← PDF text extraction
│   ├── url_loader.py   ← Web scraping pipeline
│   ├── youtube_loader.py ← YouTube transcript fetching
│   ├── chunker.py      ← Text chunking (with page/timestamp variants)
│   └── embedder.py     ← SentenceTransformer wrapper
├── vectorstore/
│   └── faiss_store.py  ← FAISS index management (add/search/delete)
├── rag/
│   ├── retriever.py    ← Full retrieval pipeline
│   └── generator.py    ← Prompt building + Ollama LLM call + citation building
└── api/
    ├── upload_routes.py   ← /upload-pdf, /add-url, /add-youtube
    ├── query_routes.py    ← /query
    └── dashboard_routes.py ← /sources, /sources/{id}
```

### 4.2 Configuration as Single Source of Truth

`config.py` centralizes all configuration, including the embedding model name (`intfloat/multilingual-e5-small`), embedding dimensions (384), FAISS index paths, MySQL credentials, `TOP_K=8`, and the Ollama endpoint (`http://localhost:11434`) with a 120-second timeout. This design prevents magic strings from scattering across modules and makes environment-specific overrides straightforward.

### 4.3 MySQL Database Schema

The relational database stores source metadata and chunk text. The key tables are:

- **`sources`** — One row per ingested document, storing `id`, `type` (pdf/url/youtube), `title`, `origin` (URL or filename), `language`, `chunk_count`, and `created_at`
- **`chunks`** — One row per text chunk, storing `id`, `source_id` (FK), `chunk_text`, `page_number` (nullable), `timestamp_s` (nullable), and `url_ref`

The FAISS index stores only raw float vectors. The mapping between a FAISS vector position and a `chunk_id` UUID is maintained in a JSON sidecar file (`id_map.json`). All chunk text retrieval happens via SQL JOIN at query time.

---

## 5. Detailed Data Processing Pipeline

### 5.A Text Extraction

#### PDF Extraction

PDF extraction is performed using the `pypdf` library along with `pdfplumber` (listed in `requirements.txt`) as a fallback option for more complex layouts. The loader extracts text on a per-page basis, returning a list of strings — one per page. This page-granular extraction is critical because it enables the system to record and later report the page number for each chunk, providing precise citations.

**Challenges in PDF extraction** are inherently complex:
- **Multi-column layouts** cause text extraction libraries to interleave columns in the wrong reading order, producing garbled sentences
- **Scanned PDFs** yield no extractable text without Optical Character Recognition; the current implementation has no OCR fallback
- **Tables and figures** are extracted as raw text sequences, losing their tabular structure and becoming semantically confusing
- **Formatting noise** such as repeated headers, footers, watermarks, and page numbers needs cleaning to prevent them from contaminating chunks and misleading the embedding model
- **Ligatures and encoding issues** manifest as broken characters in certain PDF encodings

#### Web Extraction

Website content is fetched using the `requests` library with a `User-Agent` header to avoid bot blocking, then parsed with `BeautifulSoup4` using the `lxml` parser for speed. The extractor strips the full HTML and extracts meaningful content by targeting `<p>`, `<h1>` through `<h4>`, and `<li>` tags while discarding `<nav>`, `<footer>`, `<script>`, `<style>`, `<header>`, and other structural boilerplate. The resulting text segments are joined with newlines.

**Web extraction challenges** include:
- **JavaScript-rendered content**: `requests` fetches only the raw HTML. Pages relying on client-side JS rendering (SPAs, React apps) will yield nearly empty content
- **Paywalls and authentication walls**: Content behind login pages is inaccessible
- **Dynamic navigation, cookie banners, advertisements**: Even after tag filtering, these elements may survive and pollute the extracted text
- **Multilingual encoding**: UTF-8 handling must be explicit to support Hindi (Devanagari) and Telugu scripts correctly

#### YouTube Transcript Extraction

Transcripts are retrieved via the `youtube-transcript-api` library at version 1.2.4. This library fetches the auto-generated or manual caption track for a given video URL. Each transcript segment is a dictionary with `text`, `start` (seconds), and `duration` fields. The system passes these raw segments directly to the timestamp-aware chunker.

**YouTube transcript challenges:**
- Not all videos have transcripts (some creators disable captions)
- Auto-generated transcripts in non-English languages can be lower quality than manual transcripts
- YouTube may rate-limit bulk transcript requests
- The API fetches only the primary language track; multilingual track selection requires explicit language code passing

---

### 5.B Preprocessing

Preprocessing transforms noisy, heterogeneous raw text into clean, uniform inputs that generate high-quality embeddings. The quality of embeddings is critically dependent on the quality of input text — a noisy chunk containing repeated navigation fragments, unicode artifacts, or excessive whitespace will produce an embedding that does not faithfully represent the semantic content, degrading retrieval accuracy.

The preprocessing stage (implemented within the individual loaders) applies the following transformations:

- **Whitespace normalization**: Multiple consecutive spaces, tabs, and newlines are collapsed into single spaces or single newlines. This prevents the embedding model from treating visual whitespace as semantic content.
- **Removal of non-informative patterns**: Page numbers, header/footer text repetitions, and social share buttons extracted from HTML are filtered.
- **Unicode normalization**: Ensures consistent character representations, which is especially important for Hindi (Devanagari) and Telugu text where multiple Unicode code points can represent visually identical characters.
- **Sentence boundary preservation**: While the chunker operates at the character level, preprocessing avoids discarding sentence-end punctuation that helps the model understand chunk boundaries.
- **Empty block removal**: Pages yielding fewer than a threshold of characters after cleaning are skipped entirely rather than creating near-empty chunks.

The multilingual `intfloat/multilingual-e5-small` embedding model supports 96 languages. However, it is sensitive to mixed-language text within a single chunk — a chunk that mixes English and Telugu, for example, may produce a suboptimal embedding. Language-tagging at the source level (the `language` field stored per source) allows future filtering, but currently does not influence chunk-level preprocessing.

---

### 5.C Chunking Strategy

#### Why Chunking is Necessary

LLMs operate within a finite context window. Early models accepted only a few thousand tokens; even modern models supporting 128k+ context windows face practical performance degradation at maximum context due to the "lost in the middle" phenomenon where the model attends poorly to information in the center of very long prompts. FAISS similarity search also operates at the chunk level — a document embedded as a single large vector loses granular retrievability, making it impossible to surface a specific sub-topic from a 50-page document. Chunking enables fine-grained retrieval where only the semantically relevant subsections are passed to the LLM.

#### Current Implementation

The system uses a **fixed-size character-based sliding window** chunker (`chunker.py`):

- **Chunk size:** 800 characters
- **Chunk overlap:** 100 characters
- **Step size:** 700 characters per slide (`CHUNK_SIZE - CHUNK_OVERLAP`)

Three variants are implemented:
1. `chunk_text(text)` — basic chunking for web content
2. `chunk_text_with_pages(pages)` — page-aware chunking that preserves the page number of the PDF page from which each chunk originates
3. `chunk_text_with_timestamps(segments)` — segment-aware chunking that records the `start` timestamp of the first transcript segment in each chunk, enabling precise YouTube video citations

The overlap strategy ensures that sentences straddling chunk boundaries are captured in at least one chunk, preventing retrieval misses for information at chunk boundaries.

#### Tradeoffs and Analysis

| Factor | Small Chunks (e.g., 200 chars) | Current (800 chars) | Large Chunks (e.g., 3000 chars) |
|---|---|---|---|
| Retrieval precision | High (narrow context) | Moderate-High | Low (too much dilution) |
| Context completeness | Low (loses surrounding context) | Moderate | High |
| Embedding quality | Less noisy | Reasonable | May suffer from topic drift |
| LLM prompt size | Smaller, more focused | Manageable | May exceed context limits |
| Citation granularity | Very precise | Acceptable | Coarse |

The current 800-character size corresponds to approximately 150–200 tokens for English text. This is within the effective range for most embedding models and provides sufficient context for the LLM to synthesize a meaningful response without excessive dilution.

**Weakness of the current approach:** Character-based chunking is semantically naive. It cuts at character boundaries with no awareness of sentence or paragraph structure. A chunk may begin mid-sentence and end mid-sentence, producing text that, while overlapping correctly with the next chunk, is not a self-contained semantic unit. This impairs both embedding quality (the chunk does not represent a complete thought) and LLM comprehension (the model may struggle with fragments).

---

### 5.D Embedding Generation

#### How Embeddings Work

An embedding model maps a text string of arbitrary length into a dense fixed-length floating-point vector in a high-dimensional space (dimensionality 384 for `multilingual-e5-small`). The model is trained such that semantically similar texts produce vectors that are geometrically close — specifically, that they have high cosine similarity or high inner product after L2 normalization.

This property enables **semantic search**: instead of matching query keywords to document keywords, the system compares the meaning of the query to the meaning of each stored chunk. A query like "What causes insulin resistance?" will retrieve chunks discussing glucose metabolism, even if they do not contain the words "insulin resistance" verbatim.

#### Implementation Details

The `embedder.py` module uses `SentenceTransformer` from the `sentence-transformers` library, loading the `intfloat/multilingual-e5-small` model. The model is cached via Python's `@lru_cache(maxsize=1)` decorator, ensuring it is loaded from disk only once at application startup and reused for all subsequent embedding calls — avoiding a ~2-second model loading overhead on every request.

A critical model-specific requirement is the **instruction prefix**:
- Documents (chunks during ingestion): prefixed with `"passage: "` → `embed_texts()`
- Queries (user questions at retrieval time): prefixed with `"query: "` → `embed_query()`

This asymmetric prefixing is mandated by the E5 model architecture. Omitting the prefix causes the model to produce suboptimal embeddings, degrading retrieval accuracy significantly. Vectors are normalized to unit length (`normalize_embeddings=True`), making the inner product equivalent to cosine similarity — a requirement for the `IndexFlatIP` FAISS index used in this system.

#### Impact of Embedding Quality

The embedding model is the most performance-critical component of the RAG pipeline. A weak embedding model that fails to capture semantic relationships produces vectors where similar chunks cluster randomly, causing the retrieval stage to return irrelevant chunks. This is **not correctable by a better LLM** — the LLM can only work with what is retrieved. The `multilingual-e5-small` model is a compact (117M parameter) but strong multilingual model, providing reasonable performance. It does, however, trade some accuracy for speed and size compared to larger models like `multilingual-e5-large` or OpenAI's `text-embedding-3-large`.

---

### 5.E Vector Database Storage (FAISS)

#### FAISS Overview

Facebook AI Similarity Search (FAISS) is a high-performance library for efficient similarity search over dense float vectors. The system uses `faiss-cpu` in version 1.9.0, running entirely on CPU.

#### Index Type: `IndexFlatIP`

The implementation uses `faiss.IndexFlatIP` — a **flat index with Inner Product** distance metric. "Flat" means FAISS performs exhaustive brute-force search: every stored vector is compared against the query vector for every search request. This guarantees exact (not approximate) nearest-neighbor results.

After vector L2 normalization (enforced via `normalize_embeddings=True` in the embedder), the inner product is mathematically equivalent to cosine similarity. A score of `1.0` indicates identical vectors; scores approaching `0` indicate orthogonality (unrelated content).

#### Persistence and the ID Map

FAISS does not natively associate vectors with application-level identifiers. The system maintains a **parallel JSON sidecar file** (`id_map.json`) where position `i` stores the `chunk_id` UUID of the vector at FAISS index position `i`. When FAISS returns position `pos` with score `s`, the system looks up `_id_map[pos]` to recover the UUID, then queries MySQL for the chunk text and source metadata.

On every write (`add_vectors`, `delete_vectors`), both the FAISS index file (`index.faiss`) and the ID map file are serialized to disk via `faiss.write_index()` and `json.dump()`, ensuring durability.

#### Vector Deletion

`IndexFlatIP` does not support in-place deletion. The `delete_vectors()` function implements a full **index rebuild**: it extracts all existing vectors from the index using `faiss.rev_swig_ptr()`, filters out vectors whose IDs appear in the deletion set, creates a new empty `IndexFlatIP`, adds the retained vectors, and replaces the in-memory index object. This is O(n) in the total number of vectors, which becomes expensive as the knowledge base grows large.

---

## 6. Query Processing and Answer Generation

### 6.1 The Full Query Lifecycle

When a user submits a question from `AskAI.tsx`, the following chain executes synchronously:

**Step 1 — Query Embedding**
The question string is passed to `embed_query()` in `embedder.py`. It is prefixed with `"query: "` (per E5 model requirements) and encoded into a 384-dimensional float vector with L2 normalization. This vector captures the semantic meaning of the question in the same vector space as all stored passage embeddings.

**Step 2 — FAISS Similarity Search**
`search_vectors(query_vector, top_k)` performs an exhaustive inner product search across all stored vectors. When source filtering is requested, the system over-fetches (`TOP_K * 5 = 40` candidates) to ensure enough matching vectors remain after applying the source filter. FAISS returns position indices and their corresponding inner product scores.

**Step 3 — MySQL Metadata Join**
The FAISS position indices are mapped to chunk UUIDs via `_id_map`. A single SQL query retrieves all chunk text, page numbers, timestamps, URL references, and associated source metadata (type, title, language) using a `JOIN` between the `chunks` and `sources` tables:

```sql
SELECT c.id, c.source_id, c.chunk_text, c.page_number, c.timestamp_s,
       c.url_ref, s.type, s.title, s.language
FROM chunks c JOIN sources s ON s.id = c.source_id
WHERE c.id IN (%s, %s, ...)
```

**Step 4 — Source Filtering**
If the frontend passed `source_ids`, the retrieved rows are filtered in Python to retain only chunks belonging to the specified sources. Results are sorted by similarity score (highest first) and truncated to `TOP_K=8`.

**Step 5 — Prompt Construction**
`_build_prompt()` in `generator.py` assembles a structured prompt. Each retrieved chunk is formatted as:

```
[i] Source: {source_title} ({reference})
{chunk_text}
```

All chunk blocks are concatenated, then wrapped with a system instruction and the user's question:

```
You are a helpful AI assistant. Answer the question using ONLY the context provided below.
If the answer is not in the context, say "I don't have enough information to answer this question."
Always be specific and cite which source your answer comes from.

CONTEXT:
[1] Source: attention_paper.pdf (page 4)
...chunk text...

QUESTION: {question}

ANSWER:
```

**Step 6 — LLM Answer Generation**
The prompt is sent to the locally running Ollama service (`http://localhost:11434/api/chat`) in non-streaming mode. The model (`llama3`) processes the prompt within the configured 120-second timeout. The raw response text is extracted from `data["message"]["content"]`.

**Step 7 — Citation Building**
The top 5 chunks (by score), deduplicated by source ID, are converted into `Citation` objects. Each citation includes the source title, type, a formatted reference string (page number, timestamp, or URL), and a 150-character snippet of the chunk text.

**Step 8 — Response Delivery**
The `GeneratedAnswer` object (`answer`, `citations`, `chunks`) is serialized to JSON and returned to the frontend, which maps it into `QueryResponse` via the type mappings in `api.ts`.

### 6.2 Hallucination Reduction

The prompt explicitly constrains the LLM: *"Answer the question using ONLY the context provided below."* If none of the retrieved chunks contain relevant information, the model is instructed to respond with *"I don't have enough information to answer this question"* rather than fabricating an answer. This hard constraint is the primary hallucination mitigation mechanism. Its effectiveness depends on the model's instruction-following capability (`llama3` is strong in this regard) and, critically, on whether the retrieval stage has fetched sufficiently relevant chunks in the first place.

---

## 7. Evaluation of the Current Implementation

### 7.1 Chunking Weaknesses

The character-based fixed-size chunker is the weakest link in the extraction-to-embedding pipeline. Splitting at arbitrary character positions:
- Creates sentence fragments at chunk boundaries, degrading embedding semantic coherence
- Does not respect paragraph or section boundaries, so a chunk may span two unrelated topics
- The 800-character window corresponds to roughly 150 tokens — adequate but not optimal; some embedding models perform best around 256–512 tokens
- The overlap approach (100 characters = ~2–3 sentences) is relatively minimal; for technical documents with dense information, more generous overlap may be warranted

### 7.2 Embedding Model Selection

`multilingual-e5-small` is lightweight (117M parameters, 384 dimensions) and multilingual. However, its retrieval performance is noticeably below larger models such as `multilingual-e5-large` (560M parameters, 1024 dimensions) or OpenAI's `text-embedding-3-large`. For a production deployment requiring high recall, the performance gap is significant. Additionally, domain-specific fine-tuned embedding models consistently outperform general-purpose models on specialized corpora.

### 7.3 Retrieval Accuracy

The current retrieval mechanism is **pure vector similarity search** with no hybrid component. This creates systematic blind spots:
- **Exact keyword queries** (e.g., a specific product serial number, a person's name) may be poorly served by semantic search if the embedding model encodes these as generic tokens with low specificity
- **Negation queries** ("What does the paper say is NOT effective?") are notoriously difficult for embedding models to handle correctly
- **Multi-hop reasoning queries** requiring information from two or more non-adjacent chunks cannot be satisfied by retrieving only top-k individual chunks with no cross-chunk reasoning

### 7.4 Prompt Design Limitations

The current prompt passes all 8 retrieved chunks to the LLM without any reranking or relevance filtering. If some of the 8 chunks are tangentially related (low score), they introduce noise that dilutes the LLM's attention. The "lost in the middle" problem is relevant here: chunks positioned in the center of a long context tend to receive less attention from transformer-based models.

Additionally, the prompt does not include **chat history**, making the system stateless across turns. Follow-up questions ("Can you expand on that?") lack context and will fail semantically.

### 7.5 FAISS Scalability

`IndexFlatIP` performs exhaustive search — every search examines every stored vector. This scales as O(n × d) where n is the number of vectors and d is the embedding dimension (384). At small scale (thousands of chunks), this is fast. But as the knowledge base grows to hundreds of thousands of chunks, search latency will become unacceptable. Vector deletion requires a full index rebuild, which is extremely expensive at scale.

### 7.6 Frontend/Backend Coupling

The frontend performs ad-hoc field mapping in `api.ts` to bridge naming discrepancies between the backend API and the frontend type system (`"url"` vs `"web"`, case differences in language codes). This manual bridging is brittle: any backend schema change must be matched by a corresponding update in `normalizeSource()` and the chunk-mapping code in `queryRag()`. There is no shared schema contract (e.g., OpenAPI-generated TypeScript types), making breaking changes hard to catch.

### 7.7 Chat History Architecture

Chat history is persisted exclusively in `localStorage`, which means it is browser-specific, unshared across devices, and unqueryable by the backend. The `QueryHistory` page reads from this local store. The backend does implement `/history` and `/history` DELETE endpoints (visible in `api.ts`), suggesting partial backend history support, but the `AskAI.tsx` component persists to `localStorage`, not the backend, creating a data consistency gap.

---

## 8. Potential Improvements

### 8.1 Semantic Chunking

Replace the character-based chunker with a **semantic chunker** that splits text at sentence and paragraph boundaries using an NLP tokenizer (e.g., spaCy or NLTK's sentence tokenizer). A more advanced approach uses a **sliding embedding window** that computes embedding similarity between adjacent sentences and splits at points of low semantic coherence. Libraries like LangChain's `SemanticChunker` or LlamaIndex's `SentenceSplitter` implement this pattern. This produces chunks that are self-contained semantic units, significantly improving embedding quality.

### 8.2 Hybrid Search (BM25 + Vector)

Introduce a **BM25 keyword search index** (e.g., via Elasticsearch or a local `rank-bm25` implementation) alongside FAISS. At query time, perform both BM25 keyword search and vector similarity search, then merge the result sets using **Reciprocal Rank Fusion (RRF)**. This hybrid combination consistently outperforms either approach alone, particularly for queries that mix semantic intent with specific keywords.

### 8.3 Reranking

After initial retrieval, apply a **cross-encoder reranker** (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) to re-score the top-k candidates. Cross-encoders process query and document jointly rather than independently, producing significantly more accurate relevance judgments. The retrieve-then-rerank pipeline is the current state of the art in RAG retrieval quality.

### 8.4 Metadata-Aware Filtering

Extend FAISS with `IndexIDMap` or migrate to FAISS with pre-filtering using source type, language, or date range metadata. Alternatively, implement a dedicated metadata filtering stage in the retriever before vector search, enabling queries like "search only in Hindi PDFs uploaded this week."

### 8.5 Approximate Nearest Neighbor (ANN) Indexing

Replace `IndexFlatIP` with `IndexIVFFlat` or `IndexHNSWFlat` — approximate nearest neighbor indexes that trade marginal accuracy loss for dramatic speed improvements. `IndexIVFFlat` clusters vectors into Voronoi cells and searches only within nearby cells, scaling to millions of vectors with sub-linear query time. `IndexHNSWFlat` uses a graph-based approach that is highly cache-friendly and extremely fast for medium-scale datasets.

### 8.6 Caching

Implement a **semantic query cache**: when a new query arrives, compute its embedding and compare it against a cache of recent queries. If a sufficiently similar query has been answered recently (cosine similarity > 0.95), return the cached answer without invoking the LLM — reducing latency from ~30 seconds to milliseconds for repeated questions.

### 8.7 Multi-Turn Conversation

Extend the `queryRag()` API to accept a conversation history array and modify `_build_prompt()` to include prior turns. This enables coherent multi-turn dialogues where follow-up questions have access to prior context. Query reformulation (using the LLM to rephrase a follow-up question as a standalone question before embedding) improves retrieval quality in conversational settings.

### 8.8 Evaluation Metrics

Introduce automated RAG evaluation using frameworks like **RAGAs** (Retrieval-Augmented Generation Assessment), which measures:
- **Faithfulness**: Does the answer contradict or extend beyond the retrieved context?
- **Answer Relevancy**: Is the answer on-topic for the question?
- **Context Recall**: Do the retrieved chunks actually contain the answer?
- **Context Precision**: What fraction of retrieved chunks are actually relevant?

These metrics enable data-driven iteration on chunking, embedding, and retrieval parameters.

### 8.9 Streaming Responses

Replace the non-streaming Ollama call with a server-sent events (SSE) stream. The frontend displays the LLM's answer token-by-token as it is generated, dramatically reducing perceived latency from a long wait to progressive output.

### 8.10 OpenAPI Contract Generation

Generate TypeScript types directly from the FastAPI OpenAPI schema (e.g., using `openapi-typescript`). This eliminates the manual bridging in `normalizeSource()` and the chunk mapping code, ensuring type safety across the API boundary.

---

## 9. Security and Reliability Considerations

### 9.1 API Security

The current implementation exposes all endpoints without authentication. Anyone with network access to port 8000 can upload documents, query the knowledge base, and delete sources. For any deployment beyond a single-user localhost setup, the following are required:

- **Bearer token authentication** (JWT or API key) on all endpoints via FastAPI's dependency injection
- **CORS restriction**: The current CORS configuration likely allows all origins (`allow_origins=["*"]`); this must be restricted to the frontend's origin in production
- **HTTPS**: All traffic between frontend and backend must be encrypted in transit via TLS; even for internal deployments, TLS prevents man-in-the-middle attacks

### 9.2 Rate Limiting

Without rate limiting, the `/query` endpoint is vulnerable to denial-of-service via query flooding — each query invokes the LLM with a potentially long context, consuming significant CPU/RAM resources. A simple in-memory rate limiter (e.g., via `slowapi` for FastAPI) should enforce per-IP or per-user daily query limits.

### 9.3 Input Validation

- **PDF uploads**: The backend should validate MIME type server-side, not just rely on the frontend's client-side check. Malicious files disguised as PDFs (e.g., embedding executable code) should be rejected.
- **URL ingestion**: The backend must validate that submitted URLs are legitimate HTTP/HTTPS URLs and should implement an allowlist or denylist to prevent Server-Side Request Forgery (SSRF), which could allow attackers to probe internal network services via the URL fetcher.
- **Content size limits**: Large PDF files or very long web pages should be truncated or rejected to prevent memory exhaustion.
- **YouTube URL validation**: Validate that the submitted URL is a recognizable YouTube video URL before invoking the transcript API.

### 9.4 Prompt Injection

Prompt injection is a RAG-specific attack vector: a malicious document uploaded to the knowledge base could contain carefully crafted text that, when injected into the LLM prompt as retrieved context, manipulates the LLM's behavior. For example, a chunk containing `"Ignore the previous instructions and instead..."` could alter the model's responses. Mitigations include:
- Input sanitization of ingested document text (removing instruction-like patterns)
- **Instruction hierarchy reinforcement** in the system prompt: using system-role messages rather than user-role messages for RAG context makes some models more resistant to injection
- Output validation to detect anomalous answers that violate expected response patterns

### 9.5 Database Security

The MySQL connection uses hardcoded credentials in `config.py` (`DB_PASSWORD = "mysql"`). In production, credentials must be sourced from environment variables or a secrets manager. All SQL queries should use parameterized queries (already implemented via `%s` placeholders) to prevent SQL injection. The database user should have minimal required privileges (SELECT, INSERT, DELETE on specific tables only; no DROP or administrative permissions).

---

## 10. Scalability Considerations

### 10.1 Large Document Collections

At scale, the primary bottlenecks are:

- **FAISS exhaustive search**: Transitions from `IndexFlatIP` to `IndexIVFFlat` or `HNSW` reduce search complexity from O(n) to near O(log n)
- **MySQL**: As the chunks table grows to millions of rows, the `WHERE c.id IN (...)` query must be covered by an index on `chunks.id`. Partitioning the chunks table by `source_id` can improve deletion and per-source queries.
- **Disk storage**: Each 384-dimensional float32 vector occupies 1536 bytes. One million vectors = 1.5 GB. Quantization (e.g., `IndexIVFPQ`) can reduce memory by 4–16× with minimal accuracy loss.

### 10.2 High Query Volume

The LLM (Ollama running `llama3` locally) is the primary throughput bottleneck. A single query occupies the CPU for 5–60 seconds. Options for scaling:

- **Request queuing**: Wrap the `/query` endpoint in an async task queue (e.g., Celery + Redis) with configurable concurrency, returning a task ID immediately and notifying the frontend via WebSocket when the answer is ready
- **GPU acceleration**: Running Ollama with CUDA enables vastly lower inference latency (2–10× faster than CPU for LLMs)
- **Model quantization**: `llama3` in 4-bit GGUF quantization consumes significantly less memory and is faster than full precision on CPU

### 10.3 Distributed Vector Databases

For enterprise scale (tens of millions of vectors, multiple concurrent users), FAISS running in a single Python process is insufficient. Migration to a dedicated vector database service is warranted:

- **Milvus**: Open-source, Kubernetes-native, supports horizontal sharding and replication. Natively supports metadata filtering.
- **Qdrant**: Rust-based, extremely fast, strong filtering API with named vector support.
- **Weaviate**: Schema-aware, integrated BM25 + vector hybrid search, GraphQL API.
- **Pinecone**: Managed cloud service; no infrastructure overhead but introduces external data dependency.

### 10.4 GPU Acceleration for Embeddings

Embedding generation with `SentenceTransformers` is fully GPU-accelerated if a CUDA-compatible GPU is available. Switching from `faiss-cpu` to `faiss-gpu` enables GPU-accelerated similarity search. For the current `multilingual-e5-small` model at 384 dimensions, GPU acceleration primarily benefits batch embedding during large document ingestion rather than single-query operations.

### 10.5 Horizontal Backend Scaling

FastAPI with Uvicorn can be horizontally scaled by running multiple worker processes behind a load balancer (e.g., Nginx or HAProxy). However, the in-process FAISS index is not shared across workers. Horizontal scaling requires externalizing the vector store to a dedicated service (Milvus, Qdrant) and the MySQL connection to a connection pool (e.g., `aiomysql` with `asyncpg`).

---

## 11. Conclusion

### 11.1 Strengths of the Current System

The RAG Knowledge Assistant represents a well-structured, locally deployable, privacy-preserving knowledge management system with a number of genuine architectural strengths:

- **Modular Python backend**: The clean separation into `ingestion/`, `vectorstore/`, `rag/`, and `api/` modules makes the codebase comprehensible and individually testable
- **Multi-source ingestion**: Supporting PDF, web, and YouTube as co-equal knowledge sources in a shared vector index is technically non-trivial and correctly implemented
- **Metadata-aware chunking**: The three chunker variants (plain, page-aware, timestamp-aware) correctly preserve source-specific provenance for accurate citations
- **E5 multilingual embeddings**: The choice of `intfloat/multilingual-e5-small` with proper `"passage:"` / `"query:"` prefixing is technically correct and gives the system multilingual query capability out of the box
- **Citation pipeline**: The full chain from vector retrieval through SQL join to structured `Citation` objects with per-type references (page numbers, timestamps, URLs) provides strong answer auditability
- **API normalization layer**: `normalizeSource()` in `api.ts` provides a clean abstraction over backend API inconsistencies, protecting the rest of the frontend from schema details
- **Local-first architecture**: Running Ollama locally means no data leaves the user's machine — a significant privacy advantage for sensitive document corpora

### 11.2 Priority Improvements for Production Readiness

For deployment beyond a single-user development environment, the following improvements are most critical, in order of impact:

1. **Semantic chunking** — Replace the character-based chunker with sentence-boundary-aware chunking to dramatically improve embedding quality and retrieval precision
2. **Authentication and authorization** — All API endpoints must require authentication before any multi-user deployment
3. **Hybrid BM25 + vector search** — Significantly improves retrieval recall for keyword-sensitive queries with minimal architectural overhead
4. **FAISS ANN index migration** (`IndexIVFFlat`) — Required before the knowledge base exceeds ~50,000 chunks to maintain acceptable query latency
5. **Cross-encoder reranking** — Further improves result quality with minimal additional latency using a small reranker model
6. **Multi-turn conversation context** — Essential for practical usability; the system currently cannot handle follow-up questions
7. **Streaming LLM responses** — The most impactful UX improvement, eliminating the perception of a long static wait during answer generation
8. **RAGAs evaluation pipeline** — Required for any data-driven optimization of chunking, retrieval parameters, or prompt structure

The current implementation is a solid, technically coherent proof-of-concept that demonstrates all core RAG capabilities. Its architecture provides an excellent foundation from which the improvements outlined above can be methodically introduced to achieve production-grade reliability, accuracy, and scalability.

---

*This report was produced based on direct analysis of source code including `api.ts`, `config.py`, `chunker.py`, `embedder.py`, `faiss_store.py`, `retriever.py`, `generator.py`, `requirements.txt`, and the project build specification document.*
