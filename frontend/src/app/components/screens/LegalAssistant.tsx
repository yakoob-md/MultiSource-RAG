import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, X,
  ChevronLeft, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Sparkles, Clock, Lock, History,
  Search, Zap, Gavel, Scale, Shield, ChevronUp, ChevronDown, Brain, FileDown,
  CheckCircle2, Activity, ChevronRight
} from 'lucide-react';
import { cn } from '../ui/utils';
import { AuroraBackground } from '../ui/AuroraBackground';
import { 
  fetchSources, streamQueryRag, fetchConversationMessages, fetchConversations, 
  Conversation, uploadImage, uploadPdf, addWebsite, addYouTube, exportToPDF 
} from '../../api';
import { ChatMessage, RetrievedChunk, KnowledgeSource, Language } from '../../types';

// ── Shared UI Utilities ──────────────────────────────────────────────────────

const useAutoResizeTextarea = ({ minHeight, maxHeight }: { minHeight: number, maxHeight: number }) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const adjustHeight = () => {
    const node = textareaRef.current;
    if (node) {
      node.style.height = 'auto';
      node.style.height = `${Math.min(Math.max(node.scrollHeight, minHeight), maxHeight)}px`;
    }
  };
  return { textareaRef, adjustHeight };
};

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  containerClassName?: string;
  showRing?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, showRing = true, ...props }, ref) => {
    return (
      <div className={cn("relative flex flex-col w-full", containerClassName)}>
        <textarea
          ref={ref}
          className={cn(
            "flex min-h-[56px] w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm ring-offset-background placeholder:text-white/20 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition-all no-scrollbar",
            showRing && "focus-visible:ring-1 focus-visible:ring-[#6366F1]/50 focus-visible:border-[#6366F1]/50",
            className
          )}
          {...props}
        />
      </div>
    );
  }
);
Textarea.displayName = "Textarea";

function sourceIcon(type: string) {
  switch (type) {
    case 'pdf': return FileText;
    case 'web': return Globe;
    case 'youtube': return Youtube;
    default: return FileText;
  }
}

function LegalCitationCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const score = Math.round((chunk.similarityScore || 0) * 100);

  return (
    <div 
      className="relative group p-4 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-[#6366F1]/30 transition-all"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-[#6366F1]/10 flex items-center justify-center">
            <FileText className="w-3.5 h-3.5 text-[#6366F1]" />
          </div>
          <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest truncate max-w-[100px]">{chunk.sourceName}</span>
        </div>
        <span className="text-[9px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-1.5 py-0.5 rounded-md">{score}% match</span>
      </div>
      <p className="text-xs text-white/60 leading-relaxed line-clamp-3 italic">
        "{chunk.text}"
      </p>

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
  const [currentStep, setCurrentStep] = useState(0);

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

  // ── Source Management state ──
  const [isIngestionModalOpen, setIsIngestionModalOpen] = useState(false);
  const [isSelectedPreviewOpen, setIsSelectedPreviewOpen] = useState(false);
  const [sourceSearchQuery, setSourceSearchQuery] = useState('');
  const [ingestionMode, setIngestionMode] = useState<'options' | 'url' | 'youtube'>('options');
  const [urlInput, setUrlInput] = useState('');
  const [youtubeInput, setYoutubeInput] = useState('');
  const [isProcessingExternal, setIsProcessingExternal] = useState(false);
  const sourceFileInputRef = useRef<HTMLInputElement>(null);

  // ── Research Intelligence state ──
  const [activeChunks, setActiveChunks] = useState<RetrievedChunk[]>([]);
  const [showIntelligence, setShowIntelligence] = useState(false);
  const [embeddingActivity, setEmbeddingActivity] = useState(false);

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
    return sources.filter(s => 
      s.title.toLowerCase().includes(mentionQuery.toLowerCase())
    ).slice(0, 8);
  }, [sources, mentionQuery, selectedSourceIds]);

  useEffect(() => {
    fetchSources().then(setSources).catch(console.error);
    fetchConversations().then(list => {
      setConversations(list.filter(c => c.conv_type === 'legal' || !c.conv_type));
    });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer, isThinking]);

  const loadConversation = async (convId: string) => {
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
          retrievedChunks: chunkRefs
        });
      }
      setMessages(rebuilt);
    } catch (err) {
      setError("Failed to load conversation history");
    }
  };

  const handleNewChat = () => {
    setActiveConvId(null);
    (window as any).currentConversationId = null;
    setMessages([]);
    setStreamingAnswer('');
    setError(null);
  };

  const handleExport = async () => {
    if (!messages.length) return;
    const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
    if (!lastAssistantMessage) {
        setError("No research content to export");
        return;
    }

    try {
      // Export formatting according to api.ts signature
      await exportToPDF(
        "Legal Research Memorandum", 
        lastAssistantMessage.content,
        lastAssistantMessage.retrievedChunks || []
      );
    } catch (err) {
      setError("Failed to export memorandum");
    }
  };

  const handleSubmit = async (overrideText?: string) => {
    const text = overrideText || question;
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setQuestion('');
    setIsThinking(true);
    setIsStreaming(true);
    setStreamingAnswer('');
    setAgentStatus(['Initializing Research Agent...']);
    setCurrentStep(0);
    setActiveChunks([]);

    const history = messages.slice(-6).map(m => ({ role: m.role, content: m.content }));

    try {
      // Merge tagged sources with general source filter
      const combinedSourceIds = new Set(selectedSourceIds);
      taggedSourceIds.forEach(id => combinedSourceIds.add(id));
      const sourceFilter = combinedSourceIds.size > 0 ? Array.from(combinedSourceIds) : undefined;
      
      let fullAnswer = '';
      let capturedChunks: RetrievedChunk[] = [];

      await streamQueryRag(
        text,
        sourceFilter,
        history,
        (token) => {
          setIsThinking(false);
          fullAnswer += token;
          setStreamingAnswer(fullAnswer);
          setCurrentStep(4); // Synthesis step
        },
        (meta) => {
          if (meta.retrievedChunks) {
            capturedChunks = meta.retrievedChunks;
            setActiveChunks(meta.retrievedChunks);
          }
          if (meta.conversationId) {
            setActiveConvId(meta.conversationId);
            (window as any).currentConversationId = meta.conversationId;
          }
          // Show which model is actually responding
          if ((meta as any).activeProvider) {
            setActiveModel((meta as any).activeProvider);
          }
          setEmbeddingActivity(true);
          setTimeout(() => setEmbeddingActivity(false), 2000);
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
          
          // Map backend stages to UI steps (0-4)
          // Status contains stage (0-4 from agent_workflow status_log indices)
          if (status.stage !== undefined) {
             if (status.message.includes("Planner")) setCurrentStep(1);
             if (status.message.includes("Searcher")) setCurrentStep(2);
             if (status.message.includes("Validator")) setCurrentStep(3);
             if (status.message.includes("Synthesizer")) setCurrentStep(4);
          }
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
      setIsStreaming(false);
      setStreamingAnswer('');
      setTaggedSourceIds(new Set()); // Reset tags after submission

    } catch (err: any) {
      setError(err.message || "Pipeline execution failed");
      setIsThinking(false);
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showMentions && filteredMentions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex(prev => (prev + 1) % filteredMentions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex(prev => (prev - 1 + filteredMentions.length) % filteredMentions.length);
      } else if (e.key === 'Enter') {
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
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const lastAtPos = value.lastIndexOf('@');
    
    if (lastAtPos !== -1 && lastAtPos >= value.lastIndexOf(' ')) {
      const query = value.substring(lastAtPos + 1);
      setMentionQuery(query);
      setShowMentions(true);
      setMentionIndex(0);
    } else {
      setShowMentions(false);
    }
    adjustHeight();
  };

  const handleMentionSelect = (source: KnowledgeSource) => {
    const lastAtPos = question.lastIndexOf('@');
    const newText = question.substring(0, lastAtPos); // Remove the @query
    setQuestion(newText); // Remove the @ part from text, keep it as a tag
    setTaggedSourceIds(prev => new Set(prev).add(source.id));
    setShowMentions(false);
    setMentionQuery('');
    textareaRef.current?.focus();
  };

  const isInitial = messages.length === 0 && !isThinking && !isStreaming;

  return (
    <AuroraBackground className="h-full w-full">
      <div className="h-full flex bg-transparent relative overflow-hidden">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 relative h-full">

        {/* Header */}
        <div className="px-8 py-6 border-b border-white/10 flex items-center justify-between backdrop-blur-xl relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20">
              <Gavel className="w-6 h-6 text-[#6366F1]" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Legal Assistant</h1>
              <p className="text-[10px] text-white/20 font-bold uppercase tracking-[0.2em] mt-0.5">Statutory Intelligence Workbench</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
             <button
              onClick={() => setShowIntelligence(!showIntelligence)}
              className={cn(
                "p-3 rounded-xl border transition-all flex items-center gap-2",
                showIntelligence 
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-500" 
                  : "bg-white/5 border-white/10 text-white/40 hover:text-white hover:bg-white/10"
              )}
              title="Toggle Research Intelligence"
            >
              <Activity className="w-5 h-5" />
              <span className="text-[10px] font-bold uppercase tracking-widest hidden sm:inline">Intelligence</span>
            </button>
             <button
              onClick={handleExport}
              disabled={messages.length === 0}
              className={cn(
                "p-3 rounded-xl border transition-all flex items-center gap-2",
                messages.length > 0 
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-500 hover:bg-emerald-500/20" 
                  : "bg-white/5 border-white/10 text-white/20 cursor-not-allowed"
              )}
              title="Export Memorandum"
            >
              <FileDown className="w-5 h-5" />
              <span className="text-[10px] font-bold uppercase tracking-widest hidden sm:inline">Export</span>
            </button>
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-3 rounded-xl bg-white/5 border border-white/10 text-white/40 hover:text-white hover:bg-white/10 transition-all group"
            >
              <History className="w-5 h-5 group-hover:rotate-[-12deg] transition-transform" />
            </button>
            <button
              onClick={() => setIsKbOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-[#6366F1]/10 text-[#6366F1] border border-[#6366F1]/20 flex items-center gap-2 hover:bg-[#6366F1]/20 transition-all"
            >
              <Database className="w-4 h-4" />
              <span className="text-[11px] font-bold uppercase tracking-widest">Knowledge Base</span>
            </button>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto py-10 no-scrollbar relative z-10">
          <div className="max-w-3xl mx-auto px-8 space-y-8">
          {isInitial ? (
            <div className="h-full flex flex-col items-center justify-center max-w-2xl mx-auto text-center space-y-8">
              <div className="w-20 h-20 rounded-[2.5rem] bg-[#6366F1]/10 flex items-center justify-center border border-[#6366F1]/20 animate-pulse">
                <Scale className="w-10 h-10 text-[#6366F1]" />
              </div>
              <div className="space-y-4">
                <h2 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-white to-white/40">
                  How can InteleX assist your legal research today?
                </h2>
                <p className="text-sm text-white/30 leading-relaxed max-w-lg mx-auto">
                  Analyze statutes, cross-reference precedents, and generate memoranda with verified citations and grounding.
                </p>
              </div>
              
              <div className="grid grid-cols-2 gap-4 w-full pt-4">
                {[
                  { title: "Statutory Analysis", desc: "Interpret Section 438 CrPC conditions", icon: Shield },
                  { title: "Case Precedents", desc: "Recent SC rulings on anticipatory bail", icon: Gavel }
                ].map((item, idx) => (
                  <button 
                    key={idx}
                    onClick={() => setQuestion(item.desc)}
                    className="p-6 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-[#6366F1]/30 hover:bg-[#6366F1]/5 transition-all group text-left space-y-3"
                  >
                    <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-white/20 group-hover:text-[#6366F1] group-hover:bg-[#6366F1]/10 transition-all">
                      <item.icon className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white/80">{item.title}</p>
                      <p className="text-[10px] text-white/20 mt-1 leading-relaxed">{item.desc}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <div key={msg.id} className={cn("flex", msg.role === 'user' ? "justify-end" : "justify-start")}>
                  <div className={cn(
                    "max-w-[85%] p-6 rounded-[2rem] relative group transition-all",
                    msg.role === 'user' 
                      ? "bg-[#6366F1] text-white rounded-tr-none shadow-xl shadow-[#6366F1]/20" 
                      : "bg-white/[0.03] border border-white/10 rounded-tl-none backdrop-blur-xl"
                  )}>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    
                    {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                      <div className="mt-6 pt-6 border-t border-white/5 space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                          <LinkIcon className="w-3.5 h-3.5 text-[#6366F1]" />
                          <span className="text-[10px] font-bold text-white/30 uppercase tracking-[0.2em]">Verified Evidence Chunks</span>
                        </div>
                        <div className="grid grid-cols-1 gap-3">
                          {msg.retrievedChunks.slice(0, 4).map((chunk, ci) => (
                            <LegalCitationCard key={ci} chunk={chunk} index={ci} />
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div className="absolute -bottom-6 left-2 opacity-0 group-hover:opacity-100 transition-all flex items-center gap-4">
                       <span className="text-[9px] font-bold text-white/20 uppercase tracking-widest">{new Date(msg.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                </div>
              ))}
              {isThinking && (
                <div className="flex justify-start">
                  <div className="bg-white/[0.03] border border-white/10 p-6 rounded-[2rem] rounded-tl-none backdrop-blur-xl space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-[#6366F1] animate-bounce" />
                      <div className="w-2 h-2 rounded-full bg-[#6366F1] animate-bounce [animation-delay:-0.15s]" />
                      <div className="w-2 h-2 rounded-full bg-[#6366F1] animate-bounce [animation-delay:-0.3s]" />
                    </div>
                    <div className="space-y-2">
                      {agentStatus.map((status, idx) => (
                        <motion.div 
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          key={idx} 
                          className="flex items-center gap-2"
                        >
                          <Zap className="w-3 h-3 text-[#6366F1]" />
                          <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">{status}</span>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              {isStreaming && streamingAnswer && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] p-6 bg-white/[0.03] border border-white/10 rounded-[2rem] rounded-tl-none backdrop-blur-xl">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{streamingAnswer}</p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
          </div>
        </div>

        {/* Input Section */}
        <div className="px-6 pb-8 pt-4 relative z-20">
          <div className="max-w-3xl mx-auto">
            <div className="relative group">
              {/* Mentions UI */}
              <AnimatePresence>
                {showMentions && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute bottom-full left-0 w-full mb-4 bg-[#111114] border border-white/10 rounded-2xl p-2 shadow-2xl backdrop-blur-2xl z-50 overflow-hidden"
                  >
                    <div className="p-3 border-b border-white/5 flex items-center justify-between">
                       <span className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Available Sources</span>
                       <span className="text-[10px] text-[#6366F1] font-mono">@{mentionQuery}</span>
                    </div>
                    <div className="max-h-[280px] overflow-y-auto no-scrollbar">
                      {filteredMentions.map((s, idx) => (
                        <button
                          key={s.id}
                          onClick={() => handleMentionSelect(s)}
                          className={cn(
                            "w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left",
                            idx === mentionIndex ? "bg-[#6366F1]/10 text-white" : "text-white/40 hover:bg-white/5"
                          )}
                        >
                          <div className={cn(
                            "w-8 h-8 rounded-lg flex items-center justify-center border transition-colors",
                            idx === mentionIndex ? "bg-[#6366F1]/20 border-[#6366F1]/40 text-[#6366F1]" : "bg-white/5 border-white/10"
                          )}>
                            <FileText className="w-4 h-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                             <p className="text-xs font-bold truncate">{s.title}</p>
                             <p className="text-[9px] uppercase tracking-widest opacity-50">{s.type}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="backdrop-blur-2xl bg-white/[0.02] border border-white/10 rounded-[2.5rem] shadow-2xl shadow-black/50 transition-all group-focus-within:border-[#6366F1]/50 group-focus-within:bg-white/[0.04]">
                <div className="p-2 pt-4">
                  <textarea
                    ref={textareaRef}
                    value={question}
                    onChange={(e) => {
                      setQuestion(e.target.value);
                      handleTextareaChange(e);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about Sections, IPC, CrPC..."
                    className="w-full bg-transparent border-none resize-none px-6 py-2 text-sm text-white/90 focus:ring-0 placeholder:text-white/20 min-h-[50px] no-scrollbar"
                  />
                </div>
                
                {/* Active Tags */}
                {taggedSourceIds.size > 0 && (
                  <div className="px-6 pb-2 flex flex-wrap gap-2">
                    {Array.from(taggedSourceIds).map(sid => {
                      const s = sources.find(src => src.id === sid);
                      if (!s) return null;
                      return (
                        <div key={sid} className="flex items-center gap-2 pl-2 pr-1 py-1 rounded-lg bg-[#6366F1]/20 border border-[#6366F1]/30 text-[#6366F1]">
                          <span className="text-[10px] font-bold truncate max-w-[120px]">@{s.title}</span>
                          <button onClick={() => {
                            const next = new Set(taggedSourceIds);
                            next.delete(sid);
                            setTaggedSourceIds(next);
                          }} className="p-0.5 hover:bg-[#6366F1]/20 rounded transition-all">
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="p-3 border-t border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button className="p-2.5 rounded-xl bg-white/5 text-white/40 hover:bg-white/10 hover:text-[#6366F1] transition-all">
                      <Paperclip className="w-4 h-4" />
                    </button>
                    <div className="w-[1px] h-4 bg-white/10 mx-1" />
                    <div className="flex items-center bg-white/5 rounded-xl p-1">
                      {['statute', 'judgment'].map(f => (
                        <button 
                          key={f}
                          onClick={() => setLegalFilter(legalFilter === f ? null : f)}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-[9px] font-bold uppercase tracking-widest transition-all",
                            legalFilter === f ? "bg-[#6366F1] text-white" : "text-white/20 hover:text-white"
                          )}
                        >
                          {f}s
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/5">
                      <Zap className={cn("w-3.5 h-3.5 transition-colors", agenticMode ? "text-amber-500" : "text-white/20")} />
                      <span className="text-[9px] font-bold text-white/40 uppercase tracking-widest">Deep Research</span>
                      <button 
                        onClick={() => {
                          const next = !agenticMode;
                          setAgenticMode(next);
                          localStorage.setItem('legal-agentic-mode', String(next));
                        }}
                        className={cn(
                          "w-8 h-4 rounded-full relative transition-all duration-300",
                          agenticMode ? "bg-[#6366F1]" : "bg-white/10"
                        )}
                      >
                        <motion.div 
                          animate={{ x: agenticMode ? 18 : 2 }}
                          className="absolute top-1 w-2 h-2 rounded-full bg-white shadow-sm"
                        />
                      </button>
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
      </div>
      </div>

      {/* Research Intelligence Sidebar (Visual Proof) */}
      <AnimatePresence>
        {showIntelligence && (
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            className="w-[380px] border-l border-white/10 bg-black/20 backdrop-blur-3xl flex flex-col relative z-30 hidden lg:flex"
          >
            {/* Sidebar Header */}
            <div className="p-6 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                  <Activity className="w-4 h-4 text-emerald-500" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Research Intelligence</h3>
                  <p className="text-[9px] text-white/30 font-bold uppercase tracking-widest">Real-time Pipeline Audit</p>
                </div>
              </div>
              <button 
                onClick={() => setShowIntelligence(false)}
                className="p-1.5 hover:bg-white/5 rounded-lg text-white/20 transition-all"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-8 no-scrollbar">
              {/* 1. Pipeline Status */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Intelligence Flow</span>
                </div>
                <div className="space-y-3">
                  {['Query Decomposition', 'Vector Semantic Search', 'Cross-Encoder Reranking', 'Synthesis Guardrails'].map((step, idx) => {
                    const stepNum = idx + 1;
                    const isActive = (isThinking || isStreaming) && currentStep === stepNum;
                    const isDone = (isThinking || isStreaming) && currentStep > stepNum;
                    return (
                      <div key={step} className="flex items-center gap-3">
                        <div className={cn(
                          "w-1.5 h-1.5 rounded-full transition-all duration-500",
                          isActive ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] scale-150" : "bg-white/10",
                          isDone ? "bg-emerald-500/40" : ""
                        )} />
                        <span className={cn(
                          "text-[11px] font-medium transition-colors",
                          isActive ? "text-white" : "text-white/20",
                          isDone ? "text-emerald-500/60" : ""
                        )}>{step}</span>
                        {isDone && <CheckCircle2 className="w-3 h-3 text-emerald-500/40 ml-auto" />}
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* 2. Vector Embedding Matrix (Creative Visualization) */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <Database className="w-3.5 h-3.5 text-blue-500" />
                  <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Vector Embedding Matrix</span>
                </div>
                <div className="h-32 rounded-2xl bg-white/[0.02] border border-white/5 overflow-hidden relative group p-1">
                  {/* Real-time reactive grid */}
                  <div className="absolute inset-0 grid grid-cols-12 gap-[2px] p-2">
                    {Array.from({ length: 96 }).map((_, i) => {
                      const isActive = (isThinking || isStreaming || embeddingActivity);
                      return (
                        <motion.div 
                          key={i}
                          animate={{ 
                            opacity: isActive ? [0.1, 0.8, 0.1] : 0.15,
                            scale: isActive ? [1, 1.2, 1] : 1,
                            backgroundColor: isActive ? ['#3b82f6', '#6366f1', '#a855f7'] : '#ffffff'
                          }}
                          transition={{ 
                            duration: isActive ? 0.8 + (Math.random() * 1) : 3, 
                            repeat: Infinity, 
                            delay: i * 0.01 
                          }}
                          className="w-full h-full rounded-[1px] bg-white/20"
                        />
                      );
                    })}
                  </div>
                  
                  {/* Overlay Labels */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                    <div className="flex items-center gap-2 bg-black/60 px-4 py-1.5 rounded-full backdrop-blur-xl border border-white/10 shadow-2xl">
                      <div className={cn(
                        "w-1.5 h-1.5 rounded-full",
                        (isThinking || isStreaming) ? "bg-blue-500 animate-pulse" : "bg-emerald-500"
                      )} />
                      <p className="text-[10px] font-mono text-white font-bold uppercase tracking-[0.2em]">
                        {isThinking ? 'TOKENIZING...' : isStreaming ? 'MAPPING VECTORS...' : 'DIM: 1024 | STEADY'}
                      </p>
                    </div>
                    {(isThinking || isStreaming) && (
                      <motion.p 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-[8px] font-bold text-[#6366F1] uppercase tracking-[0.4em] animate-pulse"
                      >
                        Calculating Semantic Proximity
                      </motion.p>
                    )}
                  </div>

                  {/* Scanning Effect */}
                  {(isThinking || isStreaming) && (
                    <motion.div 
                      animate={{ top: ['-100%', '200%'] }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      className="absolute left-0 right-0 h-10 bg-gradient-to-b from-transparent via-[#6366F1]/20 to-transparent pointer-events-none"
                    />
                  )}
                </div>
                <div className="mt-3 flex items-center justify-between px-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[8px] font-bold text-white/20 uppercase tracking-widest">Latent Space:</span>
                    <span className="text-[8px] font-mono text-blue-400 font-bold tracking-tighter">e5-multilingual-v3</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[8px] font-bold text-white/20 uppercase tracking-widest">Compute:</span>
                    <span className="text-[8px] font-mono text-amber-500 font-bold tracking-tighter">FP16 CUDA</span>
                  </div>
                </div>
              </section>

              {/* 3. Retrieved Chunks List */}
              <section className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <LinkIcon className="w-3.5 h-3.5 text-purple-500" />
                    <span className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Retrieved Evidence</span>
                  </div>
                  <span className="text-[9px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-2 py-0.5 rounded-full">{activeChunks.length} Chunks</span>
                </div>
                
                <div className="space-y-4">
                  {activeChunks.length === 0 ? (
                    <div className="py-10 text-center border border-dashed border-white/5 rounded-2xl">
                      <p className="text-[10px] text-white/20 font-bold uppercase tracking-widest">Awaiting Analysis</p>
                    </div>
                  ) : (
                    activeChunks.map((chunk, idx) => (
                      <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        key={idx} 
                        className="p-4 rounded-2xl bg-white/[0.03] border border-white/5 hover:border-[#6366F1]/30 transition-all group"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[9px] font-bold text-[#6366F1] uppercase truncate max-w-[150px]">{chunk.sourceName}</span>
                          <span className="text-[8px] font-mono text-white/30">SCORE: {Math.round((chunk.similarityScore || 0) * 100)}%</span>
                        </div>
                        <p className="text-[11px] text-white/60 leading-relaxed line-clamp-4 italic mb-3">
                          "{chunk.text}"
                        </p>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                            <motion.div 
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.round((chunk.similarityScore || 0) * 100)}%` }}
                              className="h-full bg-emerald-500/50"
                            />
                          </div>
                          <span className="text-[8px] font-bold text-emerald-500 uppercase">Relevant</span>
                        </div>
                      </motion.div>
                    ))
                  )}
                </div>
              </section>
            </div>

            {/* Sidebar Footer */}
            <div className="p-6 border-t border-white/10 bg-black/20">
               <div className="flex items-center gap-3 p-3 rounded-xl bg-[#6366F1]/5 border border-[#6366F1]/10">
                  <Shield className="w-4 h-4 text-[#6366F1]" />
                  <p className="text-[10px] text-white/40 font-medium leading-tight">All evidence is verified against the local knowledge base to prevent hallucinations.</p>
               </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Source Selection Modal (KB) */}
      <AnimatePresence>
        {isKbOpen && (
          <div className="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="bg-[#111114] border border-white/10 w-full max-w-2xl rounded-3xl overflow-hidden p-8 shadow-2xl flex flex-col max-h-[85vh]"
            >
               <div className="flex items-center justify-between mb-8">
                  <div>
                    <h2 className="text-2xl font-bold">Constitutional Library</h2>
                    <p className="text-[10px] text-white/20 font-bold uppercase tracking-[0.2em] mt-1">Select evidence for legal analysis</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => setIsIngestionModalOpen(true)}
                      className="p-3 rounded-xl bg-[#6366F1]/10 text-[#6366F1] border border-[#6366F1]/20 hover:bg-[#6366F1]/20 transition-all"
                      title="Add New Source"
                    >
                      <Plus className="w-5 h-5" />
                    </button>
                    <button onClick={() => setIsKbOpen(false)} className="p-2 hover:bg-white/5 rounded-xl text-white/20 hover:text-white transition-all">
                      <X className="w-6 h-6" />
                    </button>
                  </div>
               </div>

               {/* Search Bar */}
               <div className="relative mb-6">
                 <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                 <input 
                   type="text" 
                   placeholder="Search statutes, precedents, or case files..."
                   value={sourceSearchQuery}
                   onChange={(e) => setSourceSearchQuery(e.target.value)}
                   className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 transition-all"
                 />
               </div>

               <div className="flex-1 overflow-y-auto space-y-3 no-scrollbar pr-2 mb-8">
                  {sources
                    .filter(s => s.title.toLowerCase().includes(sourceSearchQuery.toLowerCase()))
                    .map(source => (
                    <button
                      key={source.id}
                      onClick={() => {
                        const next = new Set(selectedSourceIds);
                        if (next.has(source.id)) next.delete(source.id);
                        else next.add(source.id);
                        setSelectedSourceIds(next);
                      }}
                      className={cn(
                        "w-full flex items-center justify-between p-4 rounded-2xl transition-all border text-left group",
                        selectedSourceIds.has(source.id)
                          ? "bg-[#6366F1]/10 border-[#6366F1]/30"
                          : "bg-white/[0.02] border-white/5 hover:border-white/20"
                      )}
                    >
                      <div className="flex items-center gap-4">
                        <div className={cn(
                          "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
                          selectedSourceIds.has(source.id) ? "bg-[#6366F1]/20 text-[#6366F1]" : "bg-white/5 text-white/20"
                        )}>
                          {source.type === 'pdf' ? <FileText className="w-5 h-5" /> : <Globe className="w-5 h-5" />}
                        </div>
                        <div>
                          <p className="text-xs font-bold">{source.title}</p>
                          <p className="text-[9px] text-white/20 uppercase tracking-widest mt-0.5">{source.metadata?.court || 'General Statutes'}</p>
                        </div>
                      </div>
                      {selectedSourceIds.has(source.id) && <CheckCircle2 className="w-5 h-5 text-[#6366F1]" />}
                    </button>
                  ))}
               </div>
               <div className="flex items-center gap-3">
                 <button 
                   onClick={() => setIsSelectedPreviewOpen(true)}
                   className="flex-1 py-4 bg-white/5 text-white/40 hover:text-white rounded-2xl font-bold uppercase tracking-widest text-xs transition-all"
                 >
                   Manage Selected ({selectedSourceIds.size})
                 </button>
                 <button onClick={() => setIsKbOpen(false)} className="flex-[2] py-4 bg-[#6366F1] text-white rounded-2xl font-bold uppercase tracking-widest text-xs shadow-lg shadow-[#6366F1]/20">Confirm Context</button>
               </div>
            </motion.div>
          </div>
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
                  <h2 className="text-xl font-bold">Add Legal Intel</h2>
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
                      <p className="text-xs font-bold">Local Files</p>
                      <p className="text-[10px] text-white/30 font-medium">Upload PDF or Image evidence</p>
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
                      <p className="text-xs font-bold">Web Laws</p>
                      <p className="text-[10px] text-white/30 font-medium">Ingest content from any URL</p>
                    </div>
                  </button>

                  <button
                    onClick={() => setIngestionMode('youtube')}
                    className="flex items-center gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-red-500/30 transition-all group text-left"
                  >
                    <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center text-red-400 group-hover:scale-110 transition-transform">
                      <Youtube className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold">Video Transcripts</p>
                      <p className="text-[10px] text-white/30 font-medium">Process YouTube court proceedings</p>
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
                        placeholder="https://example.com/legal-text"
                        value={urlInput}
                        onChange={(e) => setUrlInput(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 transition-all"
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
                      className="flex-[2] py-3 bg-[#6366F1] hover:bg-[#4F46E5] rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all"
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
                        className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-4 text-xs focus:outline-none focus:border-[#6366F1]/50 transition-all"
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
                      className="flex-[2] py-3 bg-red-600 hover:bg-red-700 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all"
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
                  <h2 className="text-xl font-bold">Active Context</h2>
                  <p className="text-[10px] text-white/20 font-bold uppercase tracking-widest mt-1">Reviewing {selectedSourceIds.size} active sources</p>
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
                        onClick={() => {
                          const next = new Set(selectedSourceIds);
                          next.delete(id);
                          setSelectedSourceIds(next);
                        }}
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
                <button onClick={() => setIsSelectedPreviewOpen(false)} className="flex-1 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all shadow-lg shadow-[#6366F1]/20">Confirm Selection</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <input 
        type="file" 
        ref={sourceFileInputRef} 
        className="hidden" 
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            const newSource = await uploadPdf(file);
            setSources(prev => [newSource, ...prev]);
            setSelectedSourceIds(prev => new Set(prev).add(newSource.id));
          } catch (e) {
            setError("Upload failed");
          }
        }}
      />
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
              className="fixed top-0 left-0 bottom-0 w-80 z-[101] bg-[#0A0A0B]/95 backdrop-blur-2xl border-r border-white/10 p-8 flex flex-col shadow-2xl overflow-hidden"
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

              <div className="flex-1 overflow-y-auto space-y-3 no-scrollbar pr-2 relative z-10">
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
    </AuroraBackground>
  );
}
