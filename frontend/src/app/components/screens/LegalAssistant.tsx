import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
  Send, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, X,
  ChevronLeft, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Send as SendIcon, X as XIcon, Sparkles, Clock, Lock, History,
  Search, Zap, Gavel, Scale, Shield, ChevronUp, ChevronDown, Brain
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { streamQueryRag, fetchSources, fetchConversations, fetchConversationMessages, Conversation, uploadImage, uploadPdf } from '../../api';
import { cn } from '../ui/utils';

// ── Shared UI Utilities ──────────────────────────────────────────────────────

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({ minHeight, maxHeight }: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const adjustHeight = useCallback((reset?: boolean) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    if (reset) {
      textarea.style.height = `${minHeight}px`;
      return;
    }
    textarea.style.height = `${minHeight}px`;
    const newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY));
    textarea.style.height = `${newHeight}px`;
  }, [minHeight, maxHeight]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) textarea.style.height = `${minHeight}px`;
  }, [minHeight]);

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
            "flex min-h-[60px] w-full rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 text-sm transition-all duration-200 ease-in-out placeholder:text-white/20 text-white/90 focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0",
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
    );
  }
);
Textarea.displayName = "Textarea";

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

// ── Legal Citation Card (Enhanced with Tooltip) ───────────────────────────────
function LegalCitationCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const score = Math.round((chunk.similarityScore || 0) * 100);

  return (
    <div 
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 shadow-sm hover:border-[#6366F1]/30 transition-all group h-full">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20">
               <Scale className="w-3.5 h-3.5 text-[#6366F1]" />
            </div>
            <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest truncate max-w-[100px]">{chunk.sourceName}</span>
          </div>
          <span className="text-[9px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-1.5 py-0.5 rounded-md">{score}% match</span>
        </div>
        <p className="text-xs text-white/60 leading-relaxed line-clamp-3 italic">
          "{chunk.text}"
        </p>
      </div>

      <AnimatePresence>
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="absolute bottom-full left-0 mb-3 z-[100] w-[320px] pointer-events-none"
          >
            <div className="bg-[#111114] border border-white/10 rounded-2xl p-5 shadow-2xl shadow-black/50 backdrop-blur-xl">
               <div className="flex items-center gap-3 mb-3">
                 <Shield className="w-4 h-4 text-[#6366F1]" />
                 <span className="text-[10px] font-bold text-white uppercase tracking-widest">Statutory Context</span>
               </div>
               <div className="space-y-3">
                 <p className="text-xs text-white/80 leading-relaxed max-h-[200px] overflow-y-auto pr-2 custom-scrollbar">
                   {chunk.text}
                 </p>
                 <div className="flex items-center gap-2 pt-2 border-t border-white/5">
                   <LinkIcon className="w-3 h-3 text-[#6366F1]" />
                   <span className="text-[9px] text-[#6366F1] font-bold uppercase tracking-tight">Verified Reference ID: {chunk.id.slice(0,8)}</span>
                 </div>
               </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function LegalAssistant() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  
  // ── Persisted LLM Provider state ──
  const [llmProvider, setLlmProvider] = useState<string>(() => {
    return localStorage.getItem('legal-llm-provider') || 'huggingface';
  });
  const [agenticMode, setAgenticMode] = useState<boolean>(() => localStorage.getItem('legal-agentic-mode') === 'true');
  const [agentStatus, setAgentStatus] = useState<string[]>([]);

  const [legalFilter, setLegalFilter] = useState<string | null>(null);

  const [isKbOpen, setIsKbOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeModel, setActiveModel] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 56, maxHeight: 200 });

  // ── Mention Tagging state ──
  const [mentionQuery, setMentionQuery] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [taggedSourceIds, setTaggedSourceIds] = useState<Set<string>>(new Set());

  const filteredMentions = useMemo(() => {
    if (!mentionQuery) {
      // Show legal sources first when in legal mode, then recent sources
      const legalSources = sources.filter(s => 
        s.metadata?.docType && selectedSourceIds.has(s.id)
      );
      const recentSources = sources
        .filter(s => selectedSourceIds.has(s.id) && !s.metadata?.docType)
        .sort((a, b) => b.dateAdded.getTime() - a.dateAdded.getTime())
        .slice(0, 5);
      return [...legalSources, ...recentSources];
    }
    
    const query = mentionQuery.toLowerCase();
    return sources.filter(s => 
      selectedSourceIds.has(s.id) && (
        s.title.toLowerCase().includes(query) ||
        s.metadata?.docType?.includes(query) ||
        s.metadata?.court?.toLowerCase().includes(query)
      )
    );
  }, [mentionQuery, sources, selectedSourceIds]);

  const handleMentionSelect = (source: KnowledgeSource) => {
    const words = question.split(' ');
    words[words.length - 1] = `@${source.title} `;
    setQuestion(words.join(' '));
    setTaggedSourceIds(prev => new Set(prev).add(source.id));
    setShowMentions(false);
    textareaRef.current?.focus();
  };
  const handleNewChat = useCallback(() => {
    setMessages([]);
    setQuestion('');
    setStreamingAnswer('');
    setError(null);
    setActiveConvId(null);
    (window as any).currentConversationId = null;
    navigate('/app/legal');
  }, [navigate]);

  const handleOpenSources = useCallback(() => setIsKbOpen(true), []);
  const handleOpenHistory = useCallback(() => setSidebarOpen(true), []);

  const loadConversation = useCallback(async (convId: string) => {
    setActiveConvId(convId);
    (window as any).currentConversationId = convId;
    setMessages([]);
    setError(null);
    setSidebarOpen(false);
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
        
        // Build readability-enhanced chunks for legal display
        const chunkRefs: RetrievedChunk[] = m.sourcesUsed
          ? m.sourcesUsed.map((sid: string) => {
            const found = sources.find(s => s.id === sid);
            return {
              id: sid,
              sourceId: sid,
              sourceName: found?.title || 'Legal Source',
              sourceType: (found?.type as any) || 'pdf',
              text: '',
              similarityScore: 1,
              language: 'EN' as const
            };
          })
          : [];

        rebuilt.push({
          id: `ai-${m.id}`,
          role: 'assistant',
          content: m.answer,
          timestamp: new Date(m.createdAt),
          retrievedChunks: chunkRefs,
        });
      }
      setMessages(rebuilt);
    } catch {
      setError('Failed to load legal conversation');
    }
  }, [sources]);

  useEffect(() => {
    fetchSources().then(setSources).catch(() => {});
    fetchConversations().then(setConversations).catch(() => {});
    
    // Check for ID in URL
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (id) {
      loadConversation(id);
      // Clean URL after loading
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('legal-llm-provider', llmProvider);
  }, [llmProvider]);

  useEffect(() => {
    localStorage.setItem('legal-agentic-mode', String(agenticMode));
  }, [agenticMode]);

  useEffect(() => {
    const handleLoadConv = (e: any) => {
      if (e.detail?.id) loadConversation(e.detail.id);
    };
    const handleNewChatEv = () => handleNewChat();
    const handleOpenHistEv = () => handleOpenHistory();
    const handleOpenSourcesEv = () => handleOpenSources();
    
    window.addEventListener('load-conversation', handleLoadConv);
    window.addEventListener('new-chat', handleNewChatEv);
    window.addEventListener('open-history', handleOpenHistEv);
    window.addEventListener('open-sources', handleOpenSourcesEv);
    return () => {
      window.removeEventListener('load-conversation', handleLoadConv);
      window.removeEventListener('new-chat', handleNewChatEv);
      window.removeEventListener('open-history', handleOpenHistEv);
      window.removeEventListener('open-sources', handleOpenSourcesEv);
    };
  }, [loadConversation, handleNewChat, handleOpenHistory, handleOpenSources]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isThinking || isStreaming) return;

    const currentQuestion = question;
    setQuestion('');
    adjustHeight(true);
    setError(null);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: currentQuestion,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setAgentStatus([]);
    setIsThinking(true);
    setIsStreaming(true);
    setStreamingAnswer('');

    // Chat memory
    const history = messages.slice(-6).map(m => ({ role: m.role, content: m.content }));

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
          if (meta.retrievedChunks) capturedChunks = meta.retrievedChunks;
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
        undefined,
        false,
        llmProvider,
        true, // isLegalMode = true
        legalFilter,
        agenticMode,
        (status) => {
          setAgentStatus(prev => {
            if (prev.includes(status.message)) return prev;
            return [...prev, status.message];
          });
        }
      );

      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: fullAnswer,
        timestamp: new Date(),
        retrievedChunks: capturedChunks,
      };

      setMessages(prev => [...prev, aiMsg]);
      setStreamingAnswer('');
      setTaggedSourceIds(new Set()); // Reset tags
      fetchConversations().then(setConversations);
    } catch (err: any) {
      setError(err.message || "Legal search failed");
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
    }
  };

  const isInitial = messages.length === 0 && !isStreaming && !isThinking;

  return (
    <div className="h-full flex flex-col bg-[#0A0A0B] relative overflow-hidden">
      {/* Background Decor */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-[#6366F1]/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-purple-500/5 blur-[100px] rounded-full" />
      </div>

      {/* Header */}
      <div className="px-8 py-6 border-b border-white/10 flex items-center justify-between backdrop-blur-xl relative z-10">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20">
            <Gavel className="w-6 h-6 text-[#6366F1]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Legal Specialist AI</h1>
            <p className="text-[10px] text-white/30 font-bold uppercase tracking-[0.2em]">InteleX Constitutional Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button onClick={() => setSidebarOpen(true)} className="p-2.5 rounded-xl bg-white/5 border border-white/10 text-white/40 hover:text-white transition-all flex items-center gap-2">
             <History className="w-4 h-4" />
             <span className="text-[10px] font-bold uppercase tracking-widest hidden sm:inline">History</span>
          </button>

          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10">
             <Scale className="w-4 h-4 text-[#6366F1]" />
             <select 
               value={llmProvider} 
               onChange={(e) => setLlmProvider(e.target.value)}
               className="bg-transparent border-none text-xs font-bold uppercase tracking-widest text-white/60 focus:outline-none cursor-pointer"
             >
               <option value="huggingface" className="bg-[#0A0A0B]">Kaggle Fine-Tuned</option>
               <option value="groq" className="bg-[#0A0A0B]">Groq 8B (High Speed)</option>
             </select>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-8 no-scrollbar relative z-10">
        {isInitial && (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-8">
             <motion.div 
               initial={{ scale: 0.9, opacity: 0 }}
               animate={{ scale: 1, opacity: 1 }}
               className="space-y-4"
             >
                <h2 className="text-4xl font-bold text-white/90">How can I assist your legal research?</h2>
                <p className="text-sm text-white/30 max-w-md mx-auto">Analyze IPC, CrPC, Constitution, and Supreme Court Judgments with persistent conversational context.</p>
             </motion.div>
             <div className="flex gap-4">
                <button onClick={() => setIsKbOpen(true)} className="px-6 py-3 rounded-2xl bg-[#6366F1]/10 border border-[#6366F1]/20 text-xs font-bold uppercase tracking-widest text-[#6366F1] hover:bg-[#6366F1]/20 transition-all flex items-center gap-2">
                   <Database className="w-4 h-4" /> Select Sources
                </button>
             </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={cn(
              "max-w-[85%] rounded-3xl p-6 transition-all",
              msg.role === 'user' 
                ? "bg-[#6366F1] text-white shadow-xl shadow-[#6366F1]/10" 
                : "bg-white/[0.03] border border-white/5 backdrop-blur-xl"
            )}>
              <div className="flex items-center gap-2 mb-2">
                 <span className="text-[10px] font-bold uppercase tracking-widest text-white/20">{msg.role === 'user' ? 'Counsel' : 'Legal AI'}</span>
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap font-medium">{msg.content}</p>
              
              {msg.role === 'assistant' && msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                <div className="mt-6 pt-6 border-t border-white/5">
                   <p className="text-[10px] font-bold uppercase tracking-widest text-white/20 mb-4">Legal Basis & Citations</p>
                   <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                     {msg.retrievedChunks.slice(0, 4).map((chunk, ci) => (
                       <LegalCitationCard key={ci} chunk={chunk} index={ci} />
                     ))}
                   </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Agent Status Display */}
        {(isThinking || isStreaming) && agentStatus.length > 0 && (
          <div className="mb-4 p-4 rounded-2xl bg-purple-500/5 border border-purple-500/10 animate-in fade-in slide-in-from-bottom-2 duration-500 w-fit">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400">Legal Research Pipeline</span>
            </div>
            <div className="space-y-2">
              {agentStatus.map((status, idx) => (
                <div key={idx} className="flex items-start gap-2 text-[11px] text-white/50 font-mono">
                  <span className="text-purple-500/50">›</span>
                  <span>{status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {isThinking && (
          <div className="flex items-center gap-3 text-white/40 p-4 rounded-2xl bg-white/5 w-fit">
            <Loader2 className="w-4 h-4 animate-spin text-[#6366F1]" />
            <span className="text-xs font-bold uppercase tracking-widest">Counsel is reviewing files...</span>
          </div>
        )}

        {isStreaming && streamingAnswer && (
          <div className="max-w-[85%] p-6 rounded-3xl bg-[#6366F1]/5 border border-[#6366F1]/10 backdrop-blur-xl">
             <div className="flex items-center justify-between mb-2">
                 <span className="text-[10px] font-bold uppercase tracking-widest text-[#6366F1]/60">InteleX</span>
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

        <div ref={messagesEndRef} className="h-40" />
      </div>

      {/* Input Section */}
      <div className="px-6 pb-8 pt-4 relative z-20">
        <div className="max-w-4xl mx-auto">
          <div className="relative group">
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
                    <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest px-2 py-1">Tag Legal Source</p>
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

            <div className="backdrop-blur-2xl bg-white/[0.02] rounded-2xl border border-white/5 shadow-2xl transition-all focus-within:border-[#6366F1]/30">
              <div className="p-2 pt-4">
                <Textarea 
                  ref={textareaRef}
                  value={question}
                  onChange={(e: any) => { 
                    const val = e.target.value;
                    setQuestion(val); 
                    adjustHeight(); 
                    
                    const lastWord = val.split(' ').pop() || '';
                    if (lastWord.startsWith('@')) {
                      setMentionQuery(lastWord.slice(1));
                      setShowMentions(true);
                      setMentionIndex(0);
                    } else {
                      setShowMentions(false);
                    }
                  }}
                  onKeyDown={(e: any) => { 
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

                    if(e.key === 'Enter' && !e.shiftKey) { 
                      e.preventDefault(); 
                      handleSubmit(); 
                    } 
                  }}
                  placeholder="Query Indian Laws, SC Judgments, or Constitutional Articles..."
                  className="min-h-[56px] border-none bg-transparent focus:ring-0"
                />
              </div>
              <div className="p-3 border-t border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                   <button 
                     onClick={() => setIsKbOpen(true)}
                     className="p-2 text-white/20 hover:text-white transition-all flex items-center gap-2"
                     title="Select Knowledge Sources"
                   >
                     <Database className="w-4 h-4" />
                     <span className="text-[10px] font-bold uppercase tracking-widest">{selectedSourceIds.size || 'No'} Sources</span>
                   </button>
                   
                   <div className="h-4 w-px bg-white/5 mx-2" />
                   
                   <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/5 hover:border-[#6366F1]/30 transition-all group">
                    {llmProvider === 'huggingface' ? (
                      <Scale className="w-3.5 h-3.5 text-[#6366F1]" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-[#6366F1]" />
                    )}
                    <select
                      value={llmProvider}
                      onChange={(e) => {
                        const val = e.target.value;
                        setLlmProvider(val);
                        localStorage.setItem('legal-llm-provider', val);
                      }}
                      className="bg-transparent border-none text-[10px] font-bold uppercase tracking-widest text-white/40 focus:outline-none cursor-pointer group-hover:text-white transition-colors"
                      title="Select LLM Provider"
                    >
                      <option value="huggingface" className="bg-[#0A0A0B]">Legal Model (Fine-tuned)</option>
                      <option value="groq" className="bg-[#0A0A0B]">General Model (Groq)</option>
                    </select>
                  </div>
                   
                    <div className="h-4 w-px bg-white/5 mx-2" />
                    
                    {/* Deep Research Toggle */}
                    <button
                      onClick={() => setAgenticMode(!agenticMode)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest border transition-all ${
                        agenticMode 
                          ? 'bg-purple-500/10 text-purple-400 border-purple-500/30 shadow-[0_0_10px_rgba(168,85,247,0.1)]' 
                          : 'bg-white/5 text-white/40 border-white/10 hover:bg-white/10'
                      }`}
                      title="Enable Agentic Multi-Stage Reasoning"
                    >
                      <Brain className={`w-3.5 h-3.5 ${agenticMode ? 'animate-pulse' : ''}`} />
                      <span>Deep Research</span>
                    </button>
                    
                    <div className="h-4 w-px bg-white/5 mx-2" />
                   
                   <div className="flex items-center gap-3">
                      {['statute', 'judgment'].map(f => (
                        <button 
                          key={f}
                          onClick={() => setLegalFilter(legalFilter === f ? null : f)}
                          className={cn(
                            "px-3 py-1 rounded-lg text-[9px] font-bold uppercase tracking-widest border transition-all",
                            legalFilter === f 
                              ? "bg-[#6366F1]/20 border-[#6366F1]/40 text-[#6366F1]" 
                              : "bg-white/5 border-white/10 text-white/20 hover:text-white/60"
                          )}
                        >
                          {f}s
                        </button>
                      ))}
                   </div>
                </div>

                <button 
                  onClick={() => handleSubmit()}
                  disabled={!question.trim() || isThinking || isStreaming}
                  className={cn(
                    "p-2 rounded-xl transition-all",
                    question.trim() ? "bg-[#6366F1] text-white" : "bg-white/5 text-white/10"
                  )}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Simple Source Modal (Simplified for this version) */}
      <AnimatePresence>
        {isKbOpen && (
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <motion.div className="bg-[#111114] border border-white/10 w-full max-w-2xl rounded-3xl p-8 space-y-6">
               <div className="flex justify-between items-center">
                  <h2 className="text-xl font-bold flex items-center gap-3"><Database className="w-5 h-5 text-[#6366F1]"/> Knowledge Library</h2>
                  <button onClick={() => setIsKbOpen(false)}><X className="w-6 h-6"/></button>
               </div>
               <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                 {sources.map(s => (
                   <div 
                    key={s.id} 
                    onClick={() => {
                      const next = new Set(selectedSourceIds);
                      if(next.has(s.id)) next.delete(s.id);
                      else next.add(s.id);
                      setSelectedSourceIds(next);
                    }}
                    className={cn(
                      "p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between",
                      selectedSourceIds.has(s.id) ? "bg-[#6366F1]/10 border-[#6366F1]/40" : "bg-white/5 border-white/5 hover:bg-white/10"
                    )}
                   >
                     <div className="flex items-center gap-3">
                        <FileText className="w-4 h-4 text-white/40" />
                        <span className="text-sm font-medium">{s.title}</span>
                     </div>
                     {selectedSourceIds.has(s.id) && <div className="w-2 h-2 rounded-full bg-[#6366F1]" />}
                   </div>
                 ))}
               </div>
               <button onClick={() => setIsKbOpen(false)} className="w-full py-4 bg-[#6366F1] text-white rounded-2xl font-bold uppercase tracking-widest text-xs">Confirm Selection</button>
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
                <span className="text-[11px] font-bold uppercase tracking-widest">New Legal Session</span>
              </button>

              <div className="flex-1 overflow-y-auto space-y-3 no-scrollbar pr-2">
                {conversations.length === 0 ? (
                  <div className="py-10 text-center space-y-2">
                    <p className="text-white/20 text-xs font-bold uppercase tracking-widest">No cases yet</p>
                  </div>
                ) : (
                  conversations.map(conv => (
                    <button
                      key={conv.id}
                      onClick={() => {
                        if (conv.conv_type === 'general' || !conv.conv_type) {
                          navigate(`/app/ask?id=${conv.id}`);
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
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
