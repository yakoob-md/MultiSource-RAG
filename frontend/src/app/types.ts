export type SourceType = 'pdf' | 'web' | 'youtube' | 'image';
export type Language = 'EN' | 'HI' | 'TE' | 'ES' | 'FR' | 'DE';
export type IngestionStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface KnowledgeSource {
  id: string;
  type: SourceType;
  title: string;
  language: Language;
  status: IngestionStatus;
  chunkCount?: number;
  dateAdded: Date;
  lastProcessed?: Date;
  metadata?: {
    pageCount?: number;
    url?: string;
    domain?: string;
    videoId?: string;
    thumbnail?: string;
    duration?: string;
    docType?: string;
    court?: string;
    judgmentDate?: string;
  };
}

export interface RetrievedChunk {
  id: string;
  sourceId: string;
  sourceName: string;
  sourceType: SourceType;
  language: Language;
  text: string;
  similarityScore: number;
  metadata?: {
    page?: number;
    timestamp?: string;
    url?: string;
    ipcSections?: string[];
  };
}

export interface Citation {
  sourceTitle: string;
  sourceType: SourceType;
  reference: string;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  retrievedChunks?: RetrievedChunk[];
}

export interface LegalCitation {
  document: string;
  section?: string;
  title?: string;
  text_excerpt: string;
  amendments?: string[];
  source_type: "statute" | "judgment";
  court?: string;
  date?: string;
  para?: string;
}

export interface LegalQueryResponse {
  answer: string;
  legal_basis: string;
  citations: LegalCitation[];
  retrieved_chunks: any[];
}

export interface ImageJob {
  id: string;
  image_path: string;
  status: IngestionStatus;
  caption?: string;
  error_message?: string;
  created_at: string;
}
