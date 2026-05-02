import { KnowledgeSource, RetrievedChunk, Citation, Language, LegalQueryResponse, ImageJob } from './types';

const DEFAULT_API_BASE = 'http://127.0.0.1:8000';
const API_BASE = (import.meta as any).env?.VITE_API_URL || DEFAULT_API_BASE;

// ── Types ────────────────────────────────────────────────────────────────────

type BackendSource = {
  id: string;
  type: 'pdf' | 'url' | 'youtube' | 'statute' | 'judgment' | 'constitution';
  title: string;
  origin?: string;
  language?: string;
  status?: KnowledgeSource['status'];
  chunkCount?: number;
  createdAt?: string;
  dateAdded?: string;
  doc_type?: string;   // For legal sources
  court?: string;      // For legal sources
  judgment_date?: string; // For legal sources
};

export interface QueryResponse {
  answer: string;
  sources: Citation[];
  retrievedChunks: RetrievedChunk[];
  conversationId?: string; // Added for Phase 1
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  question: string;
  answer: string;
  sourcesUsed: string[];
  createdAt: string;
}

// ── Helper: Normalization ───────────────────────────────────────────────────

function normalizeSource(raw: BackendSource): KnowledgeSource {
  // Map "url" → "web" for frontend type consistency
  let type: KnowledgeSource['type'] =
    raw.type === 'url' ? 'web' :
      (raw.type as KnowledgeSource['type']);

  // If it's a legal type from Prompt 4, we might want to map it to 'pdf' 
  // or keep it if types.ts supports it. Assuming pdf for now if not 'web'/'youtube'.
  if (['statute', 'judgment', 'constitution'].includes(raw.type)) {
    type = 'pdf';
  }

  const language = ((raw.language || 'en').toUpperCase()) as Language;
  const dateRaw = raw.createdAt || raw.dateAdded;
  const dateAdded = dateRaw ? new Date(dateRaw) : new Date();

  const metadata: KnowledgeSource['metadata'] = {};
  if (raw.origin) {
    if (type === 'web' || type === 'youtube') metadata.url = raw.origin;
    if (raw.origin.match(/[?&]v=([^&]+)/)) {
      const match = raw.origin.match(/[?&]v=([^&]+)/);
      if (match) metadata.videoId = match[1];
    }
  }

  // Add legal metadata if present
  if (raw.doc_type) metadata.docType = raw.doc_type;
  if (raw.court) metadata.court = raw.court;
  if (raw.judgment_date) metadata.judgmentDate = raw.judgment_date;

  return {
    id: String(raw.id),
    type: type || 'pdf',
    title: raw.title,
    language,
    status: raw.status || 'completed',
    chunkCount: raw.chunkCount ?? 0,
    dateAdded,
    metadata,
  };
}

// ── Sources API ──────────────────────────────────────────────────────────────

export async function fetchSources(): Promise<KnowledgeSource[]> {
  const res = await fetch(`${API_BASE}/sources`);
  if (!res.ok) throw new Error(`Failed to fetch sources: ${res.statusText}`);
  const data = await res.json();
  const raw: BackendSource[] = Array.isArray(data) ? data : (data.sources ?? []);
  return raw.map(normalizeSource);
}

export async function fetchLegalSources(): Promise<KnowledgeSource[]> {
  const res = await fetch(`${API_BASE}/legal/legal-sources`);
  if (!res.ok) throw new Error(`Failed to fetch legal sources: ${res.statusText}`);
  const data = await res.json();
  const raw: BackendSource[] = data.sources ?? [];
  return raw.map(normalizeSource);
}

export async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sources/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Delete failed with status ${res.status}`);
  }
}

// ── Ingestion API ────────────────────────────────────────────────────────────

export async function uploadPdf(file: File): Promise<KnowledgeSource> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/upload-pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error(await res.text() || 'PDF Upload failed');
  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: 'pdf',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    createdAt: new Date().toISOString(),
  });
}

export async function uploadLegal(file: File, docType: string = "judgment"): Promise<KnowledgeSource> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/legal/upload-legal?doc_type=${docType}`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error(await res.text() || 'Legal Upload failed');
  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: data.doc_type as any || 'pdf',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    createdAt: new Date().toISOString(),
    doc_type: data.doc_type
  });
}

export async function addWebsite(url: string, language: Language = 'EN'): Promise<KnowledgeSource> {
  const res = await fetch(`${API_BASE}/add-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, language: language.toLowerCase() }),
  });
  if (!res.ok) throw new Error(await res.text() || 'URL Ingestion failed');
  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: 'url',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    origin: url,
  });
}

export async function addYouTube(url: string, language: Language = 'EN'): Promise<KnowledgeSource> {
  const res = await fetch(`${API_BASE}/add-youtube`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, language: language.toLowerCase() }),
  });
  if (!res.ok) throw new Error(await res.text() || 'YouTube Ingestion failed');
  const data = await res.json();
  return normalizeSource({
    id: data.source_id,
    type: 'youtube',
    title: data.title,
    chunkCount: data.chunk_count,
    status: 'completed',
    origin: url,
  });
}

// ── Image API ────────────────────────────────────────────────────────────────

export async function uploadImage(file: File, context: string = ""): Promise<{ image_id: string, status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('context', context);

  const res = await fetch(`${API_BASE}/images/upload-image`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error(await res.text() || 'Image Upload failed');
  return await res.json();
}

export async function fetchImageJobs(): Promise<ImageJob[]> {
  const res = await fetch(`${API_BASE}/images/image-jobs`);
  if (!res.ok) throw new Error(`Failed to fetch image jobs: ${res.statusText}`);
  const data = await res.json();
  return data.jobs ?? [];
}

export async function fetchPendingImageCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/images/image-jobs/pending-count`);
  if (!res.ok) throw new Error(`Failed to fetch pending count: ${res.statusText}`);
  const data = await res.json();
  return data.count ?? 0;
}

// ── Query API ───────────────────────────────────────────────────────────────

export async function queryRag(
  question: string, 
  sourceIds?: string[], 
  imageId?: string, 
  includeRecentImages?: boolean
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      source_ids: sourceIds && sourceIds.length > 0 ? sourceIds : null,
      conversation_id: (window as any).currentConversationId || null,
      image_id: imageId || null,
      include_recent_images: includeRecentImages || false,
    }),
  });

  if (!res.ok) throw new Error(await res.text() || 'Query failed');
  const data = await res.json();

  return {
    answer: data.answer,
    conversationId: data.conversationId, // Added for Phase 1
    sources: (data.citations || []).map((c: any) => ({
      sourceTitle: c.sourceTitle || c.source_title || '',
      sourceType: c.sourceType === 'url' ? 'web' : (c.sourceType || 'pdf'),
      reference: c.reference || '',
      snippet: c.snippet || '',
    })),
    retrievedChunks: (data.retrievedChunks || []).map((c: any) => ({
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
        ipcSections: c.metadata?.ipc_sections || c.ipc_sections || [],
      },
    })),
  };
}

// frontend/src/app/api.ts — streamQueryRag FIXED

export async function streamQueryRag(
  question: string,
  sourceIds: string[] | undefined,
  history: Array<{ role: string; content: string }>,
  onToken: (token: string) => void,
  onMeta: (meta: { chatId: string; citations: Citation[]; retrievedChunks: RetrievedChunk[] }) => void,
  onError: (err: Error) => void,
  imageId?: string,
  includeRecentImages?: boolean
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        source_ids: sourceIds && sourceIds.length > 0 ? sourceIds : null,
        history,
        conversation_id: (window as any).currentConversationId || null,
        image_id: imageId || null,
        include_recent_images: includeRecentImages || false,
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    if (!res.body) throw new Error('No response body');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const parsed = JSON.parse(jsonStr);

          if (parsed.error) {
            onError(new Error(parsed.error));
            return;
          }

          // Token event
          if (parsed.type === 'token' || (parsed.token !== undefined && parsed.token !== '')) {
            onToken(parsed.type === 'token' ? parsed.content : parsed.token);
          }

          // Meta event (sent at start by backend)
          if (parsed.type === 'meta') {
            const citations = (parsed.citations || []).map((c: any) => ({
              sourceTitle: c.sourceTitle || c.source_title || '',
              sourceType: (c.sourceType === 'url' ? 'web' : c.sourceType || 'pdf') as any,
              reference: c.reference || '',
              snippet: c.snippet || '',
            }));
            const retrievedChunks = (parsed.retrievedChunks || []).map((c: any, i: number) => ({
              id: c.chunkId || String(i),
              sourceId: c.sourceId || '',
              sourceName: c.sourceTitle || '',
              sourceType: (c.sourceType === 'url' ? 'web' : c.sourceType || 'pdf') as any,
              text: c.text || '',
              similarityScore: c.score || 0,
              metadata: { page: c.pageNumber, timestamp: c.timestampS, url: c.urlRef }
            }));
            onMeta({ chatId: parsed.chatId || '', citations, retrievedChunks });
          }

          // Done event — stream.py sends citations + retrievedChunks here
          if (parsed.done) {
            const rawCitations = parsed.citations || [];
            const rawChunks = parsed.retrievedChunks || [];

            const citations: Citation[] = rawCitations.map((c: any) => ({
              sourceTitle: c.source_title || c.sourceTitle || '',
              sourceType: (c.source_type === 'url' ? 'web' : c.source_type || 'pdf') as any,
              reference: c.reference || '',
              snippet: c.snippet || '',
            }));

            const retrievedChunks: RetrievedChunk[] = rawChunks.map((c: any, i: number) => ({
              id: c.chunkId || c.chunk_id || String(i),
              sourceId: c.sourceId || c.source_id || '',
              sourceName: c.sourceTitle || c.source_title || '',
              sourceType: (c.sourceType === 'url' ? 'web' : c.sourceType || 'pdf') as any,
              language: ((c.language || 'en').toUpperCase()) as Language,
              text: c.text || c.chunk_text || '',
              similarityScore: typeof c.score === 'number' ? c.score : 0,
              metadata: {
                page: c.pageNumber ?? c.page_number,
                timestamp: c.timestampS != null
                  ? `${Math.floor(c.timestampS / 60)}:${String(c.timestampS % 60).padStart(2, '0')}`
                  : undefined,
                url: c.urlRef || c.url_ref,
              },
            }));

            onMeta({ chatId: parsed.chatId || '', citations, retrievedChunks });
            return;
          }
        } catch {
          // Partial JSON — skip
        }
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

// ── History API ─────────────────────────────────────────────────────────────

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

export async function clearHistory(): Promise<void> {
  const res = await fetch(`${API_BASE}/history`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to clear history');
}

// ── Events ──────────────────────────────────────────────────────────────────

export function notifySidebarRefresh() {
  window.dispatchEvent(new CustomEvent('sources-updated'));
}

export async function queryLegal(question: string, sourceFilter?: string, modelType: "finetuned" | "base" = "finetuned"): Promise<LegalQueryResponse> {
  const res = await fetch(`${API_BASE}/legal-query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      question, 
      source_filter: sourceFilter || null, 
      language: "en",
      model_type: modelType 
    })
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to query legal search: ${text}`);
  }
  return res.json();
}

// ── Conversations API ────────────────────────────────────────────────────────

export async function createConversation(title = 'New Chat'): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/conversations`);
  if (!res.ok) throw new Error('Failed to fetch conversations');
  const data = await res.json();
  return data.conversations ?? [];
}

export async function fetchConversationMessages(convId: string): Promise<{
  conversation: { id: string; title: string };
  messages: ConversationMessage[];
}> {
  const res = await fetch(`${API_BASE}/conversations/${convId}/messages`);
  if (!res.ok) throw new Error('Failed to fetch messages');
  return res.json();
}

export async function renameConversation(convId: string, title: string): Promise<void> {
  await fetch(`${API_BASE}/conversations/${convId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(convId: string): Promise<void> {
  await fetch(`${API_BASE}/conversations/${convId}`, { method: 'DELETE' });
}
