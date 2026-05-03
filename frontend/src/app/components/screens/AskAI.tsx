import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, X,
  ChevronLeft, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Send as SendIcon, X as XIcon, Sparkles, Clock, Lock, History,
  Search, Zap, Gavel
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { streamQueryRag, fetchSources, fetchConversations, fetchConversationMessages, Conversation, uploadImage, uploadPdf, addWebsite, addYouTube } from '../../api';
import { cn } from '../ui/utils';
// import { CommandPalette } from '../CommandPalette';

// ── UI Components from rough.py ──────────────────────────────────────────────

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({
  minHeight,
  maxHeight,
}: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      if (reset) {
        textarea.style.height = `${minHeight}px`;
        return;
      }

      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(
        minHeight,
        Math.min(
          textarea.scrollHeight,
          maxHeight ?? Number.POSITIVE_INFINITY
        )
      );

      textarea.style.height = `${newHeight}px`;
    },
    [minHeight, maxHeight]
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = `${minHeight}px`;
    }
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  containerClassName?: string;
  showRing?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, showRing = true, ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false);

    return (
      <div className={cn("relative", containerClassName)}>
        <textarea
          className={cn(
            "flex min-h-[60px] w-full rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 text-sm",
            "transition-all duration-200 ease-in-out",
            "placeholder:text-white/20 text-white/90",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0",
            className
          )}
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />
        {showRing && isFocused && (
          <motion.span
            className="absolute inset-0 rounded-xl pointer-events-none ring-2 ring-offset-0 ring-violet-500/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}
      </div>
    )
  }
)
Textarea.displayName = "Textarea"

function TypingDots() {
  return (
    <div className="flex items-center ml-1">
      {[1, 2, 3].map((dot) => (
        <motion.div
          key={dot}
          className="w-1 h-1 bg-[#6366F1] rounded-full mx-0.5"
          initial={{ opacity: 0.3 }}
          animate={{
            opacity: [0.3, 0.9, 0.3],
            scale: [0.85, 1.1, 0.85]
          }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: dot * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

const sourceIcon = (type: string) => {
  switch (type) {
    case 'pdf': return FileText;
    case 'web':
    case 'url': return Globe;
    case 'youtube': return Youtube;
    case 'image': return ImageIcon;
    default: return FileText;
  }
};

// ── Citation Tooltip (Wikipedia-style hover preview) ─────────────────────────

interface CitationTooltipProps {
  chunk: RetrievedChunk;
  index: number;
}

function CitationTooltip({ chunk, index }: CitationTooltipProps) {
  const [show, setShow] = useState(false);
  const IconMap: Record<string, React.ElementType> = { pdf: FileText, web: Globe, youtube: Youtube, image: ImageIcon };
  const Icon = IconMap[chunk.sourceType] || FileText;
  const score = Math.round((chunk.similarityScore || 0) * 100);

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <button
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer",
          "bg-[#6366F1]/10 border border-[#6366F1]/20 text-[#6366F1] hover:bg-[#6366F1]/20"
        )}
      >
        <Icon className="w-3 h-3" />
        <span className="max-w-[120px] truncate">{chunk.sourceName || 'Source'}</span>
        {chunk.metadata?.page && <span className="opacity-60">p.{chunk.metadata.page}</span>}
        <span className="ml-1 opacity-40 font-mono">[{index + 1}]</span>
      </button>

      <AnimatePresence>
        {show && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-0 mb-2 z-[500] w-80 pointer-events-none"
          >
            <div className="bg-[#111114] border border-white/10 rounded-2xl p-4 shadow-2xl shadow-black/50 backdrop-blur-xl">
              {/* Header */}
              <div className="flex items-start gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-[#6366F1]/10 border border-[#6366F1]/20 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-[#6366F1]" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-white truncate">{chunk.sourceName}</p>
                  <p className="text-[10px] text-white/30 font-medium mt-0.5">
                    {chunk.sourceType.toUpperCase()}
                    {chunk.metadata?.page ? ` · Page ${chunk.metadata.page}` : ''}
                    {chunk.metadata?.timestamp ? ` · ${chunk.metadata.timestamp}` : ''}
                  </p>
                </div>
                <div className="ml-auto flex-shrink-0">
                  <span className="text-[9px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-1.5 py-0.5 rounded-md">{score}% match</span>
                </div>
              </div>

              {/* Snippet */}
              <div className="bg-white/[0.03] rounded-xl p-3 border border-white/5">
                <p className="text-[11px] text-white/60 leading-relaxed line-clamp-4">
                  {chunk.text || 'No preview available.'}
                </p>
              </div>

              {/* Footer */}
              {chunk.metadata?.url && (
                <p className="mt-2 text-[9px] text-[#6366F1] truncate">{chunk.metadata.url}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


// ── Main Component ───────────────────────────────────────────────────────────

export function AskAI() {
  const navigate = useNavigate();
  // ── Conversation state ────────────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const navigateTo = (path: string) => navigate(path);

  // ── Chat state ────────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [selectedChunks, setSelectedChunks] = useState<RetrievedChunk[]>([]);

  // ── Source selector & Provider ──────────────────────────────────────────────
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [llmProvider, setLlmProvider] = useState<string>('groq');

  // ── Image Upload state ─────────────────────────────────────────────────────
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Knowledge Base (Resources) state ───────────────────────────────────────
  const [isKbOpen, setIsKbOpen] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);
  const [sourceSearchQuery, setSourceSearchQuery] = useState('');
  const [isUploadingSource, setIsUploadingSource] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{ name: string, type: 'pdf' | 'image' } | null>(null);
  const sourceFileInputRef = useRef<HTMLInputElement>(null);

  // ── Unified Ingestion & Selection Preview ──
  const [isIngestionModalOpen, setIsIngestionModalOpen] = useState(false);
  const [isSelectedPreviewOpen, setIsSelectedPreviewOpen] = useState(false);
  const [ingestionMode, setIngestionMode] = useState<'options' | 'url' | 'youtube'>('options');
  const [urlInput, setUrlInput] = useState('');
  const [youtubeInput, setYoutubeInput] = useState('');
  const [isProcessingExternal, setIsProcessingExternal] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 56, maxHeight: 200 });
  
  // ── Mention Tagging state ──
  const [mentionQuery, setMentionQuery] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [taggedSourceIds, setTaggedSourceIds] = useState<Set<string>>(new Set());

  const filteredMentions = sources.filter(s => 
    selectedSourceIds.has(s.id) &&
    s.title.toLowerCase().includes(mentionQuery.toLowerCase())
  );

  const toggleSourceSelection = useCallback((sourceId: string) => {
    setSelectedSourceIds(prev => {
      const next = new Set(prev);
      if (next.has(sourceId)) next.delete(sourceId);
      else next.add(sourceId);
      return next;
    });
  }, []);


  // ── Effects ───────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchConversations().then(setConversations).catch(() => { });
    fetchSources().then(setSources).catch(() => { });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);
  const handleNewChat = useCallback(() => {
    setActiveConvId(null);
    setMessages([]);
    setQuestion('');
    setStreamingAnswer('');
    setError(null);
    setActiveImageId(null);
    setImagePreviewUrl(null);
    (window as any).currentConversationId = null;
    navigate('/app/ask');
  }, [navigate]);

  const loadConversation = useCallback(async (id: string) => {
    setActiveConvId(id);
    (window as any).currentConversationId = id;
    setMessages([]);
    setError(null);
    setSidebarOpen(false);
    try {
      const data = await fetchConversationMessages(id);
      const rebuilt: ChatMessage[] = [];
      for (const m of data.messages) {
        rebuilt.push({
          id: `u-${m.id}`,
          role: 'user',
          content: m.question,
          timestamp: new Date(m.createdAt),
        });
        
        // Rebuild citation/chunk structure from stored sourcesUsed
        const chunkRefs: RetrievedChunk[] = m.sourcesUsed
          ? m.sourcesUsed.map((sid: string) => ({
            id: sid,
            sourceId: sid,
            sourceName: 'Source', // Placeholder until hydrated
            sourceType: 'pdf',
            text: '',
            similarityScore: 1,
            language: 'EN'
          }))
          : [];

        rebuilt.push({
          id: `a-${m.id}`,
          role: 'assistant',
          content: m.answer,
          timestamp: new Date(m.createdAt),
          retrievedChunks: chunkRefs,
        });
      }
      setMessages(rebuilt);
    } catch {
      setError("Failed to load conversation");
    }
  }, []);

  const handleOpenSources = useCallback(() => setIsKbOpen(true), []);
  const handleOpenHistory = useCallback(() => setSidebarOpen(true), []);

  useEffect(() => {
    const handleLoadConv = (e: any) => {
      if (e.detail?.id) {
        loadConversation(e.detail.id);
      }
    };

    window.addEventListener('load-conversation', handleLoadConv);
    window.addEventListener('open-sources', handleOpenSources);
    window.addEventListener('open-history', handleOpenHistory);
    window.addEventListener('new-chat', handleNewChat);

    return () => {
      window.removeEventListener('load-conversation', handleLoadConv);
      window.removeEventListener('open-sources', handleOpenSources);
      window.removeEventListener('open-history', handleOpenHistory);
      window.removeEventListener('new-chat', handleNewChat);
    };
  }, [loadConversation, handleNewChat, handleOpenSources, handleOpenHistory]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so same file can be re-selected
    e.target.value = '';

    if (file.type.startsWith('image/')) {
      setIsUploadingImage(true);
      setImagePreviewUrl(URL.createObjectURL(file));
      try {
        const res = await uploadImage(file);
        setActiveImageId(res.image_id);
        setUploadedFile({ name: file.name, type: 'image' });
      } catch (err: any) {
        setError(err.message || "Image upload failed");
        setImagePreviewUrl(null);
      } finally {
        setIsUploadingImage(false);
      }
    } else if (file.type === 'application/pdf') {
      setIsUploadingSource(true);
      setUploadedFile({ name: file.name, type: 'pdf' });
      try {
        const newSource = await uploadPdf(file);
        // Immediately add to sources list so it's visible right away
        setSources(prev => [newSource, ...prev]);
        // Then do a full refresh to sync chunk counts etc.
        const updated = await fetchSources();
        setSources(updated);
      } catch (err: any) {
        setError(err.message || "PDF upload failed");
        setUploadedFile(null);
      } finally {
        setIsUploadingSource(false);
      }
    }
  };

  const removeImage = () => {
    setActiveImageId(null);
    setImagePreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const dismissUploadedFile = () => setUploadedFile(null);

  const handleMentionSelect = (source: KnowledgeSource) => {
    const words = question.split(' ');
    words[words.length - 1] = `@${source.title} `;
    setQuestion(words.join(' '));
    setTaggedSourceIds(prev => new Set(prev).add(source.id));
    setShowMentions(false);
    textareaRef.current?.focus();
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isThinking || isStreaming) return;

    setError(null);
    const currentQuestion = question;
    setQuestion('');
    adjustHeight(true);

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: currentQuestion,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);
    setIsStreaming(true);
    setStreamingAnswer('');

    // Pass last 12 messages (6 turns) for strong context
    const history = messages.slice(-12).map(m => ({
      role: m.role,
      content: m.content,
    }));

    try {
      // Merge tagged sources with general source filter
      const combinedSourceIds = new Set(selectedSourceIds);
      taggedSourceIds.forEach(id => combinedSourceIds.add(id));
      
      const sourceFilter = combinedSourceIds.size > 0 ? Array.from(combinedSourceIds) : undefined;
      let fullAnswer = '';
      let capturedChunks: RetrievedChunk[] = [];

      await streamQueryRag(
        currentQuestion,
        sourceFilter,
        history,
        (token) => {
          setIsThinking(false);
          fullAnswer += token;
          setStreamingAnswer(fullAnswer);
        },
        (meta) => {
          if (meta.retrievedChunks) {
            capturedChunks = meta.retrievedChunks;
            setSelectedChunks(capturedChunks);
          }
          // Sync conversationId on every new turn
          if (meta.conversationId) {
            setActiveConvId(meta.conversationId);
            (window as any).currentConversationId = meta.conversationId;
          }
          // Show which model is actually responding
          if ((meta as any).activeProvider) {
            setActiveModel((meta as any).activeProvider);
          }
        },
        (err) => { throw err; },
        activeImageId || undefined,
        true,
        llmProvider
      );

      removeImage();
      setTaggedSourceIds(new Set()); // Reset tags after query

      const aiMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: fullAnswer,
        timestamp: new Date(),
        retrievedChunks: capturedChunks,
      };

      setMessages(prev => [...prev, aiMsg]);
      setStreamingAnswer('');

      const updatedConvs = await fetchConversations();
      setConversations(updatedConvs);
      if (!activeConvId) {
        const newest = updatedConvs[0];
        if (newest) setActiveConvId(newest.id);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to get answer');
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
    }
  };


  const isInitial = messages.length === 0 && !isStreaming && !isThinking;

  // ── Resource Manager Visuals ──────────────────────────────────────────────
  const stats = {
    pdf: sources.filter(s => s.type === 'pdf').length,
    web: sources.filter(s => s.type === 'web').length,
    youtube: sources.filter(s => s.type === 'youtube').length,
    total: sources.length
  };

  return (
    <div className="h-full flex text-white relative overflow-hidden">
      {/* Main Container */}
      <div className="flex-1 flex flex-col relative z-10">

        {/* Chat History View */}
        <div className={cn(
          "flex-1 overflow-y-auto px-6 sm:px-12 py-8 space-y-8 no-scrollbar scroll-smooth transition-all duration-700",
          isInitial ? "opacity-0 translate-y-10 pointer-events-none" : "opacity-100 translate-y-0"
        )}>
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={cn(
                "max-w-[85%] rounded-3xl p-6 transition-all",
                msg.role === 'user'
                  ? "bg-[#6366F1] text-white shadow-xl shadow-[#6366F1]/10"
                  : "bg-white/[0.03] border border-white/5 backdrop-blur-xl"
              )}>
                <p className="text-sm leading-relaxed whitespace-pre-line font-medium">{msg.content}</p>

                {/* Rich Citation Panel — shown for assistant messages with sources */}
                {msg.role === 'assistant' && msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                  <div className="mt-5 pt-4 border-t border-white/5 space-y-2">
                    <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-white/20">Sources</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.retrievedChunks.map((chunk, i) => (
                        <CitationTooltip key={i} chunk={chunk} index={i} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isThinking && (
            <div className="flex items-center gap-3 text-white/40 p-4 rounded-2xl bg-white/5 w-fit">
              <Loader2 className="w-4 h-4 animate-spin text-[#6366F1]" />
              <span className="text-xs font-bold uppercase tracking-widest">Thinking...</span>
            </div>
          )}

          {isStreaming && streamingAnswer && (
            <div className="max-w-[85%] p-6 rounded-3xl bg-white/[0.03] border border-white/5 backdrop-blur-xl">
              <div className="flex items-center justify-between mb-2">
                 <span className="text-[10px] font-bold uppercase tracking-widest text-white/20">InteleX</span>
                 {activeModel && (
                   <span className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded-md bg-[#6366F1]/10 text-[#6366F1] border border-[#6366F1]/20">
                     Active: {activeModel === 'huggingface' ? 'Legal' : 'Groq'}
                   </span>
                 )}
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-line font-medium text-white/90">
                {streamingAnswer}
                <span className="inline-block w-1 h-4 ml-1 bg-[#6366F1] animate-pulse align-middle" />
              </p>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl p-4 bg-red-500/10 border border-red-500/20">
                <p className="text-sm text-red-400 font-medium">⚠️ {error}</p>
              </div>
            </div>
          )}

          {/* Bottom spacer — tall enough to clear the fixed input bar */}
          <div ref={messagesEndRef} className="h-56" />
        </div>

        {/* Initial Centered State */}
        <AnimatePresence>
          {isInitial && (
            <motion.div
              className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center space-y-12"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -50, scale: 0.95 }}
              transition={{ duration: 0.5 }}
            >
              <div className="space-y-4">
                <motion.div
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.5 }}
                >
                  <h1 className="text-4xl sm:text-5xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">
                    How can InteleX help today?
                  </h1>
                </motion.div>
                <p className="text-white/30 text-sm max-w-lg mx-auto font-medium">
                  Ask about your law cases, research papers, or legal documents.
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3">
                <button onClick={() => navigateTo("/app/legal")} className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2">
                  <Lock className="w-3 h-3 text-[#6366F1]" /> Legal AI
                </button>
                <button onClick={() => setIsKbOpen(true)} className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2">
                  <Database className="w-3 h-3 text-[#6366F1]" /> Sources
                </button>
                <button onClick={() => setSidebarOpen(true)} className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2">
                  <Clock className="w-3 h-3 text-[#6366F1]" /> History
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Unified Input Bar — fixed to bottom when chatting */}
        <div className={cn(
          "w-full max-w-3xl mx-auto transition-all duration-700",
          isInitial
            ? "px-6 pb-12"
            : "fixed bottom-0 left-1/2 -translate-x-1/2 z-50 px-4 pb-6 w-full max-w-3xl"
        )}>
          {/* Gradient fade behind input bar — prevents text bleed-through */}
          {!isInitial && (
            <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#0a0a0f] via-[#0a0a0f]/90 to-transparent pointer-events-none -z-10 rounded-t-2xl" />
          )}
          <div className="relative group">
            {/* Upload feedback chip — shown after PDF/image upload (like ChatGPT) */}
            <AnimatePresence>
              {(uploadedFile || isUploadingSource) && (
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                  className="absolute bottom-full mb-3 left-0"
                >
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#0a0a0f] border border-white/10 shadow-xl backdrop-blur-xl">
                    {isUploadingSource ? (
                      <Loader2 className="w-4 h-4 text-[#6366F1] animate-spin flex-shrink-0" />
                    ) : uploadedFile?.type === 'pdf' ? (
                      <FileText className="w-4 h-4 text-violet-400 flex-shrink-0" />
                    ) : (
                      <ImageIcon className="w-4 h-4 text-blue-400 flex-shrink-0" />
                    )}
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-white/90 max-w-[200px] truncate">
                        {isUploadingSource ? 'Uploading...' : uploadedFile?.name}
                      </span>
                      {!isUploadingSource && (
                        <span className="text-[9px] text-emerald-400 font-bold uppercase tracking-widest">✓ Added to knowledge base</span>
                      )}
                    </div>
                    {!isUploadingSource && (
                      <button
                        onClick={dismissUploadedFile}
                        className="ml-1 p-1 rounded-lg hover:bg-white/10 text-white/30 hover:text-white transition-all"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Image Preview above input bar */}
            <AnimatePresence>
              {imagePreviewUrl && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.9 }}
                  className="absolute bottom-full mb-4 left-0 p-2 bg-white/[0.03] border border-white/5 rounded-2xl backdrop-blur-2xl shadow-2xl"
                >
                  <div className="relative w-32 h-32 rounded-xl overflow-hidden border border-white/10">
                    <img src={imagePreviewUrl} alt="Preview" className="w-full h-full object-cover" />
                    <button onClick={removeImage} className="absolute top-1 right-1 p-1 bg-black/60 text-white rounded-full hover:bg-red-500 transition-colors">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Mention Suggestions */}
            <AnimatePresence>
              {showMentions && filteredMentions.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute bottom-full mb-2 left-0 w-64 bg-[#111114] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-[100]"
                >
                  <div className="p-2 border-b border-white/5 bg-white/5">
                    <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest px-2 py-1">Tag a Source</p>
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {filteredMentions.map((s, idx) => (
                      <button
                        key={s.id}
                        onClick={() => handleMentionSelect(s)}
                        className={cn(
                          "w-full px-4 py-2 text-left text-xs transition-colors hover:bg-[#6366F1]/20 flex items-center gap-2",
                          idx === mentionIndex ? "bg-[#6366F1]/10" : ""
                        )}
                      >
                        <FileText className="w-3 h-3 text-white/40" />
                        <span className="truncate">{s.title}</span>
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className={cn(
              "backdrop-blur-2xl bg-white/[0.02] rounded-2xl border border-white/5 shadow-2xl transition-all",
              "focus-within:border-white/10 focus-within:bg-white/[0.04]"
            )}>
              <div className="p-2 pt-4">
                <Textarea
                  ref={textareaRef}
                  value={question}
                  onChange={(e) => {
                    const val = e.target.value;
                    setQuestion(val);
                    adjustHeight();

                    // Detect @ mention
                    const lastWord = val.split(' ').pop() || '';
                    if (lastWord.startsWith('@')) {
                      setMentionQuery(lastWord.slice(1));
                      setShowMentions(true);
                      setMentionIndex(0);
                    } else {
                      setShowMentions(false);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (showMentions && filteredMentions.length > 0) {
                      if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        setMentionIndex(prev => (prev + 1) % filteredMentions.length);
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        setMentionIndex(prev => (prev - 1 + filteredMentions.length) % filteredMentions.length);
                      } else if (e.key === 'Enter' || e.key === 'Tab') {
                        e.preventDefault();
                        handleMentionSelect(filteredMentions[mentionIndex]);
                      } else if (e.key === 'Escape') {
                        setShowMentions(false);
                      }
                      return;
                    }

                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  placeholder="Ask InteleX a question..."
                  className="min-h-[56px] border-none bg-transparent focus:ring-0"
                  showRing={false}
                />
              </div>

              <div className="p-3 border-t border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    {selectedSourceIds.size > 0 && (
                      <button
                        onClick={() => setIsSelectedPreviewOpen(true)}
                        className="mr-2 flex items-center gap-2 px-2 py-1 rounded-lg bg-[#6366F1]/10 border border-[#6366F1]/20 hover:bg-[#6366F1]/20 transition-all"
                      >
                        <Database className="w-3 h-3 text-[#6366F1]" />
                        <span className="text-[9px] font-bold text-[#6366F1] uppercase">{selectedSourceIds.size} Selected</span>
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setIsIngestionModalOpen(true)}
                      disabled={isUploadingSource || isProcessingExternal}
                      className="p-2 text-white/20 hover:text-white transition-colors flex items-center gap-2 disabled:opacity-50"
                      title="Add Knowledge Source"
                    >
                      {isUploadingSource || isProcessingExternal ? (
                        <Loader2 className="w-4 h-4 animate-spin text-[#6366F1]" />
                      ) : (
                        <Plus className="w-4 h-4" />
                      )}
                      <span className="text-[10px] font-bold uppercase tracking-widest hidden sm:inline">
                        {isUploadingSource || isProcessingExternal ? 'Processing...' : 'Source'}
                      </span>
                    </button>
                    <input type="file" ref={sourceFileInputRef} onChange={handleFileChange} accept="image/*,application/pdf" className="hidden" />

                  <div className="h-4 w-px bg-white/5 mx-2" />

                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/5 hover:border-[#6366F1]/30 transition-all group">
                    {llmProvider === 'huggingface' ? (
                      <Lock className="w-3.5 h-3.5 text-[#6366F1]" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-[#6366F1]" />
                    )}
                    <select
                      value={llmProvider}
                      onChange={(e) => setLlmProvider(e.target.value)}
                      className="bg-transparent border-none text-[10px] font-bold uppercase tracking-widest text-white/40 focus:outline-none cursor-pointer group-hover:text-white transition-colors"
                    >
                      <option value="groq" className="bg-[#0A0A0B]">General Intelligence (Groq)</option>
                      <option value="huggingface" className="bg-[#0A0A0B]">Legal Intelligence (Fine-tuned)</option>
                    </select>
                  </div>
                </div>

                <button
                  onClick={() => handleSubmit()}
                  disabled={!question.trim() || isThinking || isStreaming}
                  className={cn(
                    "p-2 rounded-xl transition-all",
                    question.trim() ? "bg-[#6366F1] text-white shadow-lg shadow-[#6366F1]/20" : "bg-white/5 text-white/10"
                  )}
                >
                  <SendIcon className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>


      {/* Resource Manager Visual Modal */}
      <AnimatePresence>
        {isKbOpen && (
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0A0A0B] border border-white/10 w-full max-w-5xl rounded-3xl overflow-hidden flex flex-col max-h-[85vh] shadow-2xl relative"
            >
              <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-50">
                <div className="absolute -top-[20%] -left-[10%] w-[70%] h-[70%] rounded-full bg-[#6366F1]/10 blur-[120px]" />
                <div className="absolute top-[20%] -right-[10%] w-[50%] h-[50%] rounded-full bg-violet-500/5 blur-[100px]" />
                <div className="absolute -bottom-[10%] left-[20%] w-[60%] h-[60%] rounded-full bg-blue-500/5 blur-[110px]" />
              </div>

              <div className="px-8 py-6 border-b border-white/5 flex flex-col sm:flex-row justify-between items-start sm:items-center bg-white/[0.01] relative z-10 gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20 shadow-inner">
                    <Database className="w-6 h-6 text-[#6366F1]" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight">Resource Manager</h2>
                    <p className="text-[10px] text-white/20 font-bold uppercase tracking-[0.2em]">Knowledge Bank Intelligence</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <div className="relative flex-1 sm:w-64 group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20 group-focus-within:text-[#6366F1] transition-colors" />
                    <input
                      type="text"
                      placeholder="Search documents..."
                      value={sourceSearchQuery}
                      onChange={(e) => setSourceSearchQuery(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 focus:ring-1 focus:ring-[#6366F1]/20 transition-all"
                    />
                  </div>
                  <button onClick={() => setIsKbOpen(false)} className="p-2.5 rounded-xl hover:bg-white/5 text-white/20 hover:text-white transition-all">
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-8 space-y-8 no-scrollbar">
                {/* Statistics Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                  {[
                    { label: 'Total Sources', value: stats.total, icon: Database, color: 'text-[#6366F1]' },
                    { label: 'PDF Documents', value: stats.pdf, icon: FileText, color: 'text-violet-400' },
                    { label: 'Web Pages', value: stats.web, icon: Globe, color: 'text-blue-400' },
                    { label: 'YouTube Links', value: stats.youtube, icon: Youtube, color: 'text-red-400' },
                  ].map((s, i) => (
                    <div key={i} className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
                      <div className="flex items-center justify-between">
                        <s.icon className={cn("w-4 h-4", s.color)} />
                        <span className="text-2xl font-bold">{s.value}</span>
                      </div>
                      <p className="text-[10px] font-bold uppercase tracking-widest text-white/20">{s.label}</p>
                    </div>
                  ))}
                </div>

                {/* Visual Graph / Distribution */}
                <div className="p-8 rounded-3xl bg-white/[0.01] border border-white/5 space-y-6">
                  <div className="flex justify-between items-end">
                    <div className="space-y-1">
                      <h3 className="text-sm font-bold uppercase tracking-widest">Storage Distribution</h3>
                      <p className="text-[10px] text-white/20 font-medium">Visual representation of your knowledge base composition</p>
                    </div>
                    <button
                      onClick={() => setIsIngestionModalOpen(true)}
                      className="px-6 py-2 bg-[#6366F1] hover:bg-[#4F46E5] text-white text-[10px] font-bold uppercase tracking-widest rounded-xl transition-all shadow-lg shadow-[#6366F1]/20"
                    >
                      Upload New Source
                    </button>
                  </div>

                  <div className="h-4 w-full bg-white/5 rounded-full overflow-hidden flex">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(stats.pdf / stats.total) * 100 || 0}%` }}
                      className="h-full bg-violet-400"
                      title="PDFs"
                    />
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(stats.web / stats.total) * 100 || 0}%` }}
                      className="h-full bg-blue-400"
                      title="Web"
                    />
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(stats.youtube / stats.total) * 100 || 0}%` }}
                      className="h-full bg-red-400"
                      title="YouTube"
                    />
                  </div>

                  <div className="flex flex-wrap gap-6 pt-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-violet-400" />
                      <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">PDF Documents</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-blue-400" />
                      <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Web Scraping</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-red-400" />
                      <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">YouTube Transcripts</span>
                    </div>
                  </div>
                </div>

                {/* All Knowledge Sources */}
                <div className="space-y-4 relative z-10">
                  <div className="flex items-center justify-between px-1">
                    <h3 className="text-sm font-bold uppercase tracking-widest">
                      {sourceSearchQuery ? `Search Results: "${sourceSearchQuery}"` : "All Knowledge Sources"}
                    </h3>
                    <span className="text-[10px] text-white/30 font-bold uppercase tracking-widest">
                      {sources.filter(s => s.title.toLowerCase().includes(sourceSearchQuery.toLowerCase())).length} matches
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {(() => {
                      const filtered = sources.filter(s => s.title.toLowerCase().includes(sourceSearchQuery.toLowerCase()));
                      const displaySources = showAllSources || sourceSearchQuery ? filtered : filtered.slice(0, 8);

                      if (displaySources.length === 0) {
                        return (
                          <div className="col-span-full py-12 text-center border border-dashed border-white/10 rounded-3xl bg-white/[0.01]">
                            <p className="text-white/20 text-xs font-bold uppercase tracking-widest">No matching documents found</p>
                          </div>
                        );
                      }

                      return displaySources.map(source => (
                        <div key={source.id} className="flex items-center gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-all group">
                          <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white/20 group-hover:text-[#6366F1] transition-colors flex-shrink-0">
                            {(() => {
                              const IconComp = sourceIcon(source.type);
                              return <IconComp className="w-5 h-5" />;
                            })()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold truncate">{source.title}</p>
                            <p className="text-[10px] text-white/20 font-medium uppercase tracking-tighter">
                              {source.dateAdded ? new Date(source.dateAdded).toLocaleDateString() : 'Unknown Date'}
                              {(source.chunkCount ?? 0) > 0 && <span className="ml-2 text-[#6366F1]/50">{source.chunkCount} chunks</span>}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => toggleSourceSelection(source.id)}
                              className={cn(
                                "px-3 py-1 rounded-lg text-[9px] font-bold uppercase tracking-widest transition-all",
                                selectedSourceIds.has(source.id)
                                  ? "bg-[#6366F1] text-white shadow-lg shadow-[#6366F1]/20"
                                  : "bg-white/5 text-white/20 hover:bg-white/10"
                              )}
                            >
                              {selectedSourceIds.has(source.id) ? "✓ Selected" : "Select"}
                            </button>
                          </div>
                        </div>
                      ));
                    })()}
                  </div>
                  {sources.length > 8 && !sourceSearchQuery && (
                    <button
                      onClick={() => setShowAllSources(prev => !prev)}
                      className="w-full py-3 text-[10px] font-bold uppercase tracking-widest text-white/30 hover:text-[#6366F1] transition-colors border border-white/5 rounded-xl hover:border-[#6366F1]/30"
                    >
                      {showAllSources ? `↑ Show Less` : `↓ Show All ${sources.length} Sources`}
                    </button>
                  )}
                </div>

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* History Sidebar Overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md"
            />
            <motion.div
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              className="fixed top-0 left-0 bottom-0 w-85 z-[101] bg-[#0A0A0B]/95 backdrop-blur-2xl border-r border-white/10 p-8 flex flex-col shadow-2xl overflow-hidden"
            >
              {/* Beams Background for Sidebar */}
              <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-40">
                <div className="absolute -top-[10%] -right-[20%] w-[80%] h-[40%] rounded-full bg-[#6366F1]/10 blur-[80px]" />
                <div className="absolute bottom-[20%] -left-[20%] w-[60%] h-[50%] rounded-full bg-violet-500/5 blur-[90px]" />
              </div>

              <div className="flex items-center justify-between mb-10 relative z-10">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/10 flex items-center justify-center">
                    <History className="w-5 h-5 text-[#6366F1]" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">Intelligence</h2>
                    <p className="text-[9px] text-white/20 font-bold uppercase tracking-[0.2em]">Conversation History</p>
                  </div>
                </div>
                <button onClick={() => setSidebarOpen(false)} className="p-2 hover:bg-white/5 rounded-xl text-white/20 hover:text-white transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <button
                onClick={() => { handleNewChat(); setSidebarOpen(false); }}
                className="w-full py-3 px-4 mb-8 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-2xl flex items-center justify-center gap-3 transition-all shadow-lg shadow-[#6366F1]/20 group relative z-10"
              >
                <Plus className="w-4 h-4" />
                <span className="text-[11px] font-bold uppercase tracking-widest">New Intelligence Case</span>
              </button>

              <div className="flex-1 overflow-y-auto space-y-3 no-scrollbar pr-2">
                {conversations.length === 0 ? (
                  <div className="py-10 text-center space-y-2">
                    <p className="text-white/20 text-xs font-bold uppercase tracking-widest">No chats yet</p>
                    <button onClick={handleNewChat} className="text-[10px] text-[#6366F1] font-bold underline">Start your first one</button>
                  </div>
                ) : (
                  conversations.map(conv => (
                      <button
                        key={conv.id}
                        onClick={() => {
                          if (conv.conv_type === 'legal') {
                            navigate(`/app/legal?id=${conv.id}`);
                          } else {
                            loadConversation(conv.id);
                          }
                          setSidebarOpen(false);
                        }}
                      className={cn(
                        "w-full flex items-center gap-4 p-4 rounded-2xl transition-all border text-left group relative",
                        activeConvId === conv.id
                          ? "bg-[#6366F1]/10 border-[#6366F1]/30 text-white"
                          : "bg-white/[0.02] border-white/5 text-white/40 hover:bg-white/[0.04] hover:border-white/10"
                      )}
                    >
                      <div className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center border transition-colors",
                        activeConvId === conv.id 
                          ? "bg-[#6366F1]/20 border-[#6366F1]/40 text-[#6366F1]" 
                          : "bg-white/5 border-white/10 text-white/20 group-hover:text-white/60"
                      )}>
                        {conv.conv_type === 'legal' ? (
                          <Gavel className="w-4 h-4" />
                        ) : (
                          <MessageSquare className="w-4 h-4" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold truncate group-hover:text-white transition-colors">{conv.title}</p>
                        <p className="text-[9px] font-medium text-white/20 uppercase tracking-tighter mt-0.5">
                          {conv.conv_type === 'legal' ? 'Legal Case' : 'General Intelligence'}
                          {conv.updated_at && ` · ${new Date(conv.updated_at).toLocaleDateString()}`}
                        </p>
                      </div>
                    </button>
                  ))
                )}
              </div>

              <div className="pt-6 border-t border-white/5 mt-auto">
                <button
                  onClick={handleNewChat}
                  className="w-full py-4 bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 rounded-2xl text-[10px] font-bold uppercase tracking-[0.2em] transition-all"
                >
                  + New Conversation
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Unified Ingestion Modal */}
      <AnimatePresence>
        {isIngestionModalOpen && (
          <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="bg-[#0A0A0B] border border-white/10 w-full max-w-md rounded-3xl overflow-hidden p-8 shadow-2xl relative"
            >
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="text-xl font-bold">Add Intelligence</h2>
                  <p className="text-[10px] text-white/20 font-bold uppercase tracking-widest mt-1">Select source origin</p>
                </div>
                <button onClick={() => { setIsIngestionModalOpen(false); setIngestionMode('options'); }} className="p-2 hover:bg-white/5 rounded-xl text-white/20 hover:text-white transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {ingestionMode === 'options' ? (
                <div className="grid grid-cols-1 gap-3">
                  <button
                    onClick={() => { sourceFileInputRef.current?.click(); setIsIngestionModalOpen(false); }}
                    className="flex items-center gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] hover:border-[#6366F1]/30 transition-all group text-left"
                  >
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center text-violet-400 group-hover:scale-110 transition-transform">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold">Local Intelligence</p>
                      <p className="text-[10px] text-white/30 font-medium">Upload PDF or Image files</p>
                    </div>
                  </button>

                  <button
                    onClick={() => setIngestionMode('url')}
                    className="flex items-center gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] hover:border-blue-500/30 transition-all group text-left"
                  >
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400 group-hover:scale-110 transition-transform">
                      <Globe className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold">Web Scraping</p>
                      <p className="text-[10px] text-white/30 font-medium">Ingest content from any URL</p>
                    </div>
                  </button>

                  <button
                    onClick={() => setIngestionMode('youtube')}
                    className="flex items-center gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] hover:border-red-500/30 transition-all group text-left"
                  >
                    <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center text-red-400 group-hover:scale-110 transition-transform">
                      <Youtube className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold">Video Analytics</p>
                      <p className="text-[10px] text-white/30 font-medium">Process YouTube transcripts</p>
                    </div>
                  </button>
                </div>
              ) : ingestionMode === 'url' ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-white/40">Enter Web URL</label>
                    <div className="relative">
                      <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                      <input
                        type="url"
                        placeholder="https://example.com/article"
                        value={urlInput}
                        onChange={(e) => setUrlInput(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 focus:ring-1 focus:ring-[#6366F1]/20 transition-all"
                        autoFocus
                      />
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={() => setIngestionMode('options')} className="flex-1 py-3 bg-white/5 hover:bg-white/10 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all">Back</button>
                    <button
                      onClick={async () => {
                        if (!urlInput) return;
                        setIsProcessingExternal(true);
                        setIsIngestionModalOpen(false);
                        try {
                          await addWebsite(urlInput);
                          setUrlInput('');
                          const updated = await fetchSources();
                          setSources(updated);
                        } catch (e) {
                          setError("Failed to ingest URL");
                        } finally {
                          setIsProcessingExternal(false);
                          setIngestionMode('options');
                        }
                      }}
                      className="flex-2 py-3 bg-[#6366F1] hover:bg-[#4F46E5] rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all"
                    >
                      Process URL
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-white/40">YouTube Video Link</label>
                    <div className="relative">
                      <Youtube className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                      <input
                        type="url"
                        placeholder="https://youtube.com/watch?v=..."
                        value={youtubeInput}
                        onChange={(e) => setYoutubeInput(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 focus:ring-1 focus:ring-[#6366F1]/20 transition-all"
                        autoFocus
                      />
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={() => setIngestionMode('options')} className="flex-1 py-3 bg-white/5 hover:bg-white/10 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all">Back</button>
                    <button
                      onClick={async () => {
                        if (!youtubeInput) return;
                        setIsProcessingExternal(true);
                        setIsIngestionModalOpen(false);
                        try {
                          await addYouTube(youtubeInput);
                          setYoutubeInput('');
                          const updated = await fetchSources();
                          setSources(updated);
                        } catch (e) {
                          setError("Failed to ingest YouTube video");
                        } finally {
                          setIsProcessingExternal(false);
                          setIngestionMode('options');
                        }
                      }}
                      className="flex-2 py-3 bg-red-600 hover:bg-red-700 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all"
                    >
                      Process Video
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Selected Sources Preview Modal */}
      <AnimatePresence>
        {isSelectedPreviewOpen && (
          <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="bg-[#0A0A0B] border border-white/10 w-full max-w-lg rounded-3xl overflow-hidden p-8 shadow-2xl relative flex flex-col max-h-[60vh]"
            >
              <div className="flex items-center justify-between mb-8 shrink-0">
                <div>
                  <h2 className="text-xl font-bold">Active Intelligence Context</h2>
                  <p className="text-[10px] text-white/20 font-bold uppercase tracking-widest mt-1">Reviewing {selectedSourceIds.size} selected sources</p>
                </div>
                <button onClick={() => setIsSelectedPreviewOpen(false)} className="p-2 hover:bg-white/5 rounded-xl text-white/20 hover:text-white transition-all">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 no-scrollbar pr-2">
                {Array.from(selectedSourceIds).map(id => {
                  const source = sources.find(s => s.id === id);
                  if (!source) return null;
                  const Icon = sourceIcon(source.type);
                  return (
                    <div key={id} className="flex items-center justify-between p-4 rounded-2xl bg-white/[0.02] border border-white/5 group hover:border-[#6366F1]/30 transition-all">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-white/30">
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-bold truncate max-w-[240px]">{source.title}</p>
                          <p className="text-[9px] text-white/20 uppercase tracking-widest">{source.type}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => toggleSourceSelection(id)}
                        className="p-2 rounded-lg bg-red-500/10 text-red-500 opacity-0 group-hover:opacity-100 transition-all hover:bg-red-500 hover:text-white"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>

              <div className="mt-8 pt-6 border-t border-white/5 flex gap-3 shrink-0">
                <button onClick={() => setSelectedSourceIds(new Set())} className="flex-1 py-3 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all">Clear All</button>
                <button onClick={() => setIsSelectedPreviewOpen(false)} className="flex-1 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all shadow-lg shadow-[#6366F1]/20">Confirm Context</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
