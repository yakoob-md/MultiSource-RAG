import { KnowledgeSource, RetrievedChunk, Citation, Language } from './types';

const DEFAULT_API_BASE = 'http://127.0.0.1:8000';
const API_BASE = (import.meta as any).env?.VITE_API_URL || DEFAULT_API_BASE;

// ── Raw shape returned by backend /sources ────────────────────────────────────
type BackendSource = {
  id: string;
  type: 'pdf' | 'url' | 'youtube';   // backend sends "url" not "web"
  title: string;
  origin?: string;
  language?: string;                  // backend sends lowercase "en"
  status?: KnowledgeSource['status'];
  chunkCount?: number;
  createdAt?: string;                 // backend sends "createdAt" not "dateAdded"
  dateAdded?: string;
};

// ── Normalize one backend source into a KnowledgeSource ──────────────────────
function normalizeSource(raw: BackendSource): KnowledgeSource {
  // Map "url" → "web" for frontend type system
  const type: KnowledgeSource['type'] =
    raw.type === 'url' ? 'web' : raw.type;

  // Map lowercase language "en" → "EN"
  const language = ((raw.language || 'en').toUpperCase()) as Language;

  // Accept either createdAt (backend) or dateAdded (legacy)
  const dateRaw = raw.createdAt || raw.dateAdded;
  const dateAdded = dateRaw ? new Date(dateRaw) : new Date();

  // Build metadata from origin field
  const metadata: KnowledgeSource['metadata'] = {};
  if (raw.origin) {
    if (type === 'web') metadata.url = raw.origin;
    if (type === 'youtube') {
      metadata.url = raw.origin;
      const match = raw.origin.match(/[?&]v=([^&]+)/);
      if (match) metadata.videoId = match[1];
    }
  }

  return {
    id: String(raw.id),
    type,
    title: raw.title,
    language,
    status: raw.status || 'completed',
    chunkCount: raw.chunkCount ?? 0,
    dateAdded,
    metadata,
  };
}

// ── GET /sources ──────────────────────────────────────────────────────────────
export async function fetchSources(): Promise<KnowledgeSource[]> {
  const res = await fetch(`${API_BASE}/sources`);
  if (!res.ok) throw new Error(`Failed to fetch sources: ${res.statusText}`);

  const data = await res.json();

  // Backend returns { sources: [...] }
  const raw: BackendSource[] = Array.isArray(data) ? data : (data.sources ?? []);
  return raw.map(normalizeSource);
}

// ── POST /query ───────────────────────────────────────────────────────────────
export interface QueryResponse {
  answer: string;
  sources: Citation[];
  retrievedChunks: RetrievedChunk[];
}

export async function queryRag(
  question: string,
  sourceIds?: string[]
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      source_ids: sourceIds && sourceIds.length > 0 ? sourceIds : null,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Query failed with status ${res.status}`);
  }

  const data = await res.json();

  // ── Map citations from backend shape to frontend Citation type ────────────
  const sources: Citation[] = (data.citations || []).map((c: any) => ({
    sourceTitle: c.sourceTitle || c.source_title || '',
    sourceType: c.sourceType === 'url' ? 'web' : (c.sourceType || 'pdf'),
    reference: c.reference || '',
    snippet: c.snippet || '',
  }));

  // ── Map retrievedChunks from backend shape to frontend RetrievedChunk ─────
  const retrievedChunks: RetrievedChunk[] = (data.retrievedChunks || []).map((c: any) => ({
    id: c.chunkId || c.id || '',
    sourceId: c.sourceId || '',
    sourceName: c.sourceTitle || c.sourceName || '',
    sourceType: c.sourceType === 'url' ? 'web' : (c.sourceType || 'pdf'),
    language: ((c.language || 'en').toUpperCase()) as Language,
    text: c.text || '',
    similarityScore: c.score ?? c.similarityScore ?? 0,
    metadata: {
      page: c.pageNumber ?? c.metadata?.page,
      timestamp: c.timestampS != null
        ? `${Math.floor(c.timestampS / 60)}:${String(c.timestampS % 60).padStart(2, '0')}`
        : c.metadata?.timestamp,
      url: c.urlRef || c.metadata?.url,
    },
  }));

  return {
    answer: data.answer as string,
    sources,
    retrievedChunks,
  };
}

// ── POST /upload-pdf ──────────────────────────────────────────────────────────
export async function uploadPdf(file: File): Promise<KnowledgeSource> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/upload-pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Upload failed with status ${res.status}`);
  }

  const data = await res.json();

  // Backend returns {message, source_id, title, chunk_count}
  // Normalize into a KnowledgeSource shape
  return normalizeSource({
    id: data.source_id,
    type: 'pdf',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    createdAt: new Date().toISOString(),
  });
}

// ── POST /add-url ─────────────────────────────────────────────────────────────
export async function addWebsite(
  url: string,
  language: Language = 'EN'
): Promise<KnowledgeSource> {
  const res = await fetch(`${API_BASE}/add-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, language: language.toLowerCase() }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Add URL failed with status ${res.status}`);
  }

  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: 'url',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    createdAt: new Date().toISOString(),
    origin: url,
  });
}

// ── POST /add-youtube ─────────────────────────────────────────────────────────
export async function addYouTube(
  url: string,
  language: Language = 'EN'
): Promise<KnowledgeSource> {
  const res = await fetch(`${API_BASE}/add-youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, language: language.toLowerCase() }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Add YouTube failed with status ${res.status}`);
  }

  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: 'youtube',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    createdAt: new Date().toISOString(),
    origin: url,
  });
}

// ── DELETE /sources/{id} ──────────────────────────────────────────────────────
export async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sources/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Delete failed with status ${res.status}`);
  }
}

// ── GET /history ──────────────────────────────────────────────────────────────
export interface BackendChatEntry {
  id: string;
  question: string;
  answer: string;
  sourcesUsed: string[];
  createdAt: string;
}

export async function fetchHistory(): Promise<BackendChatEntry[]> {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error(`Failed to fetch history: ${res.statusText}`);
  const data = await res.json();
  return data.history ?? [];
}

// ── DELETE /history ───────────────────────────────────────────────────────────
export async function clearHistory(): Promise<void> {
  const res = await fetch(`${API_BASE}/history`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear history');
}

// ── Sidebar refresh event ─────────────────────────────────────────────────────
// Call this after any upload to tell the Sidebar to refresh its source list
export function notifySidebarRefresh() {
  window.dispatchEvent(new CustomEvent('sources-updated'));
}