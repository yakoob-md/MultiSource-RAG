import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, X,
  ChevronLeft, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Send as SendIcon, X as XIcon, Sparkles, Clock, Lock, History,
  Search, Zap, Gavel, Scale, Shield, ChevronUp, ChevronDown
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

const Textarea = React.forwardRef<HTMLTextAreaElement, any>(
  ({ className, containerClassName, showRing = true, ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false);
    return (
      <div className={cn("relative", containerClassName)}>
        <textarea
          className={cn(
            "flex min-h-[60px] w-full rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3 text-sm transition-all duration-200 ease-in-out placeholder:text-white/20 text-white/90 focus-visible:outline-none focus-visible:ring-0",
            className
          )}
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />
      </div>
    );
  }
);

// ── Legal Citation Card ───────────────────────────────────────────────────────

function LegalCitationCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const [show, setShow] = useState(false);
  const score = Math.round((chunk.similarityScore || 0) * 100);

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4 shadow-sm hover:border-[#6366F1]/30 transition-all group">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20">
             <Scale className="w-3.5 h-3.5 text-[#6366F1]" />
          </div>
          <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{chunk.sourceName}</span>
        </div>
        <span className="text-[9px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-1.5 py-0.5 rounded-md">{score}% match</span>
      </div>
      <p className="text-xs text-white/60 leading-relaxed line-clamp-3 italic">
        "{chunk.text}"
      </p>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function LegalAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [llmProvider, setLlmProvider] = useState<string>('huggingface'); // Default to Legal
  const [legalFilter, setLegalFilter] = useState<string | null>(null);

  const [isKbOpen, setIsKbOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 56, maxHeight: 200 });
  const navigate = useNavigate();

  useEffect(() => {
    fetchSources().then(setSources).catch(() => {});
    fetchConversations().then(setConversations).catch(() => {});
  }, []);

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
    setIsThinking(true);
    setIsStreaming(true);
    setStreamingAnswer('');

    // Chat memory
    const history = messages.slice(-6).map(m => ({ role: m.role, content: m.content }));

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
          if (meta.retrievedChunks) capturedChunks = meta.retrievedChunks;
          if (meta.conversationId) {
            setActiveConvId(meta.conversationId);
            (window as any).currentConversationId = meta.conversationId;
          }
        },
        (err) => { throw err; },
        undefined,
        false,
        llmProvider,
        true, // isLegalMode = true
        legalFilter
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
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10">
             <Scale className="w-4 h-4 text-[#6366F1]" />
             <select 
               value={llmProvider} 
               onChange={(e) => setLlmProvider(e.target.value)}
               className="bg-transparent border-none text-xs font-bold uppercase tracking-widest text-white/60 focus:outline-none cursor-pointer"
             >
               <option value="huggingface" className="bg-[#0A0A0B]">Kaggle Fine-Tuned</option>
               <option value="groq" className="bg-[#0A0A0B]">Groq 70B (Base)</option>
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

        {isThinking && (
          <div className="flex items-center gap-3 text-white/40 p-4 rounded-2xl bg-white/5 w-fit">
            <Loader2 className="w-4 h-4 animate-spin text-[#6366F1]" />
            <span className="text-xs font-bold uppercase tracking-widest">Counsel is reviewing files...</span>
          </div>
        )}

        {isStreaming && streamingAnswer && (
          <div className="max-w-[85%] p-6 rounded-3xl bg-white/[0.03] border border-white/5 backdrop-blur-xl">
             <div className="flex items-center gap-2 mb-2">
                 <span className="text-[10px] font-bold uppercase tracking-widest text-white/20">Legal AI</span>
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
            <div className="backdrop-blur-2xl bg-white/[0.02] rounded-2xl border border-white/5 shadow-2xl transition-all focus-within:border-[#6366F1]/30">
              <div className="p-2 pt-4">
                <Textarea 
                  ref={textareaRef}
                  value={question}
                  onChange={(e: any) => { setQuestion(e.target.value); adjustHeight(); }}
                  onKeyDown={(e: any) => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }}
                  placeholder="Query Indian Laws, SC Judgments, or Constitutional Articles..."
                  className="min-h-[56px] border-none bg-transparent focus:ring-0"
                />
              </div>
              <div className="p-3 border-t border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                   <button 
                     onClick={() => setIsKbOpen(true)}
                     className="p-2 text-white/20 hover:text-white transition-all flex items-center gap-2"
                   >
                     <Database className="w-4 h-4" />
                     <span className="text-[10px] font-bold uppercase tracking-widest">{selectedSourceIds.size || 'No'} Sources</span>
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
    </div>
  );
}
