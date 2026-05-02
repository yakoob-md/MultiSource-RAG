import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, X,
  ChevronLeft, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Send as SendIcon, X as XIcon, Sparkles, Clock, Lock
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

// ── Main Component ───────────────────────────────────────────────────────────

export function AskAI() {
  // ── Conversation state ────────────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const navigate = useNavigate();

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
  const [kbPage, setKbPage] = useState(1);
  const KB_ITEMS_PER_PAGE = 4;
  const [isUploadingSource, setIsUploadingSource] = useState(false);
  const sourceFileInputRef = useRef<HTMLInputElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 56, maxHeight: 200 });

  const loadConversation = useCallback(async (convId: string) => {
    setActiveConvId(convId);
    setMessages([]);
    setSelectedChunks([]);
    try {
      const data = await fetchConversationMessages(convId);
      const rebuilt: ChatMessage[] = [];
      for (const m of data.messages) {
        rebuilt.push({
          id: `user-${m.id}`,
          role: 'user',
          content: m.question,
          timestamp: new Date(m.createdAt),
        });
        rebuilt.push({
          id: `ai-${m.id}`,
          role: 'assistant',
          content: m.answer,
          timestamp: new Date(m.createdAt),
          retrievedChunks: m.sourcesUsed ? m.sourcesUsed.map((s: string) => ({
            id: s, 
            sourceId: s, 
            sourceName: s, 
            sourceType: 'pdf' as const, 
            text: 'Chunk loaded from history', 
            similarityScore: 1,
            language: 'EN' as const
          })) : [],
        });
      }
      setMessages(rebuilt);
    } catch {
      setError('Failed to load conversation');
    }
  }, []);

  // ── Effects ───────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchConversations().then(setConversations).catch(() => {});
    fetchSources().then(setSources).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);

  useEffect(() => {
    const handleLoadConv = (e: any) => {
        if (e.detail?.id) {
            loadConversation(e.detail.id);
        }
    };
    const handleOpenSources = () => setIsKbOpen(true);
    const handleOpenHistory = () => {
        // Since we removed the overlay, opening history now triggers the Command Palette
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }));
    };
    const handleNewChat = () => {
        setActiveConvId(null);
        setMessages([]);
        setSelectedChunks([]);
        setQuestion('');
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
  }, [loadConversation]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Direct upload logic
    if (file.type.startsWith('image/')) {
        setIsUploadingImage(true);
        setImagePreviewUrl(URL.createObjectURL(file));
        try {
            const res = await uploadImage(file);
            setActiveImageId(res.image_id);
        } catch (err: any) {
            setError(err.message || "Image upload failed");
            setImagePreviewUrl(null);
        } finally {
            setIsUploadingImage(false);
        }
    } else if (file.type === 'application/pdf') {
        setIsUploadingSource(true);
        try {
            await uploadPdf(file);
            const updated = await fetchSources();
            setSources(updated);
        } catch (err: any) {
            setError(err.message || "PDF upload failed");
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

    const history = messages.slice(-6).map(m => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const sourceFilter = selectedSourceIds.size > 0 ? Array.from(selectedSourceIds) : undefined;
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
        },
        (err) => { throw err; },
        activeImageId || undefined,
        true,
        llmProvider
      );

      removeImage();

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

  const sourceIcon = (type: string) =>
    type === 'pdf' ? FileText : type === 'web' ? Globe : Youtube;

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
                {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/5 flex flex-wrap gap-2">
                    {msg.retrievedChunks.map((chunk, i) => {
                      const Icon = sourceIcon(chunk.sourceType);
                      return (
                        <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/5 text-[10px] text-white/40">
                          <Icon className="w-3 h-3" />
                          <span className="truncate max-w-[100px]">{chunk.sourceName}</span>
                        </div>
                      );
                    })}
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
              <p className="text-sm leading-relaxed whitespace-pre-line font-medium text-white/90">
                {streamingAnswer}
                <span className="inline-block w-1 h-4 ml-1 bg-[#6366F1] animate-pulse align-middle" />
              </p>
            </div>
          )}
          <div ref={messagesEndRef} className="h-20" />
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
                  <button onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))} className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2">
                      <Clock className="w-3 h-3 text-[#6366F1]" /> History
                  </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Unified Input Bar */}
        <div className={cn(
            "w-full max-w-3xl mx-auto px-6 pb-12 transition-all duration-700",
            isInitial ? "translate-y-0" : "fixed bottom-0 left-1/2 -translate-x-1/2 translate-y-0 z-50 px-4"
        )}>
           <div className="relative group">
              {/* Image Preview inside bar */}
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

              <div className={cn(
                "backdrop-blur-2xl bg-white/[0.02] rounded-2xl border border-white/5 shadow-2xl transition-all",
                "focus-within:border-white/10 focus-within:bg-white/[0.04]"
              )}>
                <div className="p-2 pt-4">
                  <Textarea
                    ref={textareaRef}
                    value={question}
                    onChange={(e) => {
                      setQuestion(e.target.value);
                      adjustHeight();
                    }}
                    onKeyDown={(e) => {
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
                      <button 
                        type="button"
                        onClick={() => sourceFileInputRef.current?.click()}
                        className="p-2 text-white/20 hover:text-white transition-colors flex items-center gap-2"
                        title="Upload PDF or Image"
                      >
                        <Paperclip className="w-4 h-4" />
                        <span className="text-[10px] font-bold uppercase tracking-widest hidden sm:inline">Attach</span>
                      </button>
                      <input type="file" ref={sourceFileInputRef} onChange={handleFileChange} accept="image/*,application/pdf" className="hidden" />
                      
                      <div className="h-4 w-px bg-white/5 mx-2" />
                      
                      <select 
                        value={llmProvider}
                        onChange={(e) => setLlmProvider(e.target.value)}
                        className="bg-transparent border-none text-[10px] font-bold uppercase tracking-widest text-white/20 focus:outline-none cursor-pointer hover:text-[#6366F1] transition-colors"
                      >
                        <option value="groq">Default LLM</option>
                        <option value="huggingface">Legal AI</option>
                      </select>
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
                    <div className="px-8 py-6 border-b border-white/5 flex justify-between items-center bg-white/[0.01]">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-xl bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20">
                                <Database className="w-5 h-5 text-[#6366F1]" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold tracking-tight">Resource Manager</h2>
                                <p className="text-[10px] text-white/20 font-bold uppercase tracking-[0.2em]">Knowledge Bank Statistics</p>
                            </div>
                        </div>
                        <button onClick={() => setIsKbOpen(false)} className="p-2 rounded-xl hover:bg-white/5 text-white/20 hover:text-white transition-all">
                            <X className="w-5 h-5" />
                        </button>
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
                                    onClick={() => sourceFileInputRef.current?.click()}
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

                        {/* Recent Sources List */}
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold uppercase tracking-widest px-1">Recent Knowledge</h3>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                {sources.slice(0, 8).map(source => (
                                    <div key={source.id} className="flex items-center gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-all group">
                                        <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white/20 group-hover:text-[#6366F1] transition-colors">
                                            {source.type === 'pdf' ? <FileText className="w-5 h-5" /> : source.type === 'web' ? <Globe className="w-5 h-5" /> : <Youtube className="w-5 h-5" />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold truncate">{source.title}</p>
                                            <p className="text-[10px] text-white/20 font-medium uppercase tracking-tighter">{new Date(source.dateAdded).toLocaleDateString()}</p>
                                        </div>
                                        <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-white/5 text-white/20 uppercase tracking-widest">{source.status}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </motion.div>
            </div>
        )}
      </AnimatePresence>

    </div>
  );
}
