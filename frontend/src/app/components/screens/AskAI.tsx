import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, RotateCcw, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, Edit2, Check, X,
  ChevronLeft, ChevronRight, ExternalLink, Paperclip, Image as ImageIcon,
  Database, Upload, Link as LinkIcon, Video
} from 'lucide-react';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { streamQueryRag, fetchSources, fetchConversations, fetchConversationMessages, createConversation, deleteConversation, renameConversation, Conversation, uploadImage, uploadPdf, addWebsite, addYouTube } from '../../api';

export function AskAI() {
  // ── Conversation state ────────────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

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
  const [uploadUrlInput, setUploadUrlInput] = useState('');
  const [uploadType, setUploadType] = useState<'url' | 'youtube'>('url');
  const sourceFileInputRef = useRef<HTMLInputElement>(null);
  const [postUploadPrompt, setPostUploadPrompt] = useState<{source: KnowledgeSource} | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Load conversations on mount ───────────────────────────────────────────
  useEffect(() => {
    fetchConversations().then(setConversations).catch(() => {});
    fetchSources().then(setSources).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);

  // ── Load messages when switching conversations ────────────────────────────
  const loadConversation = useCallback(async (convId: string) => {
    setActiveConvId(convId);
    setMessages([]);
    setSelectedChunks([]);
    try {
      const data = await fetchConversationMessages(convId);
      // Reconstruct ChatMessage[] from backend data
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
            id: s, sourceId: s, sourceName: s, sourceType: 'pdf', text: 'Chunk loaded from history', similarityScore: 1
          })) : [], // Basic hydration of sources for history
        });
      }
      setMessages(rebuilt);
      // Set current chunks to the last message's chunks if available
      const lastMsg = data.messages[data.messages.length - 1];
      // Note: we might need to update the API to return more chunk info in history if we want them to show up on reload
    } catch {
      setError('Failed to load conversation');
    }
  }, []);

  // ── New chat ──────────────────────────────────────────────────────────────
  const handleNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setSelectedChunks([]);
    setQuestion('');
    setError(null);
  };

  // ── Delete conversation ───────────────────────────────────────────────────
  const handleDeleteConv = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConvId === convId) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  // ── Rename conversation ───────────────────────────────────────────────────
  const handleRenameConv = async (convId: string) => {
    if (!editTitle.trim()) return;
    try {
      await renameConversation(convId, editTitle);
      setConversations(prev => prev.map(c =>
        c.id === convId ? { ...c, title: editTitle } : c
      ));
      setEditingConvId(null);
    } catch (err) {
      console.error('Rename failed:', err);
    }
  };

  // ── Image Upload logic ────────────────────────────────────────────────────
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

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
  };

  const removeImage = () => {
    setActiveImageId(null);
    setImagePreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Knowledge Base Upload & Selection logic ────────────────────────────────
  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds(prev => {
      const next = new Set(prev);
      if (next.has(sourceId)) next.delete(sourceId);
      else next.add(sourceId);
      return next;
    });
  };

  const handleSourceFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingSource(true);
    try {
      const src = await uploadPdf(file);
      setSources(prev => [src, ...prev]);
      setPostUploadPrompt({ source: src });
      setIsKbOpen(false); // Close KB to show the prompt
    } catch (err: any) {
      setError(err.message || "PDF Upload failed");
    } finally {
      setIsUploadingSource(false);
      if (sourceFileInputRef.current) sourceFileInputRef.current.value = '';
    }
  };

  const handleUrlUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadUrlInput.trim()) return;
    setIsUploadingSource(true);
    try {
      let src: KnowledgeSource;
      if (uploadType === 'youtube' || uploadUrlInput.includes('youtube.com') || uploadUrlInput.includes('youtu.be')) {
        src = await addYouTube(uploadUrlInput);
      } else {
        src = await addWebsite(uploadUrlInput);
      }
      setSources(prev => [src, ...prev]);
      setUploadUrlInput('');
      setPostUploadPrompt({ source: src });
      setIsKbOpen(false);
    } catch (err: any) {
      setError(err.message || "URL/YouTube Upload failed");
    } finally {
      setIsUploadingSource(false);
    }
  };

  const startChatWithSource = async (sourceId: string) => {
    // 1. Clear current chat and select ONLY this source
    setMessages([]);
    setSelectedChunks([]);
    setActiveConvId(null);
    setSelectedSourceIds(new Set([sourceId]));
    setPostUploadPrompt(null);
    
    // 2. Create new chat immediately
    try {
      const conv = await createConversation(`Chat about new resource`);
      setActiveConvId(conv.id);
      setConversations(prev => [conv, ...prev]);
    } catch (err) {
      console.error("Failed to create conversation auto", err);
    }
  };

  // ── Submit question ───────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isThinking || isStreaming) return;

    setError(null);
    const currentQuestion = question;
    setQuestion('');
    
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

    // Build history from current messages (last 6 turns)
    const history = messages.slice(-6).map(m => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const sourceFilter = selectedSourceIds.size > 0
        ? Array.from(selectedSourceIds) : undefined;

      let fullAnswer = '';
      let capturedChunks: RetrievedChunk[] = [];
      let serverConvId = activeConvId;

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
          if (meta.chatId) {
             // Use meta to identify the conversation if needed, 
             // but our backend returns it at the end usually or in meta
          }
        },
        (err) => { throw err; },
        activeImageId || undefined, // imageId
        true,                      // includeImages (Phase 2 default)
        llmProvider
      );

      // Reset image state after sending
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

      // Refresh conversations list to show new chat or updated order
      const updatedConvs = await fetchConversations();
      setConversations(updatedConvs);
      
      // If this was a new chat, the backend auto-created a conversation
      // We should ideally find the newest one if activeConvId was null
      if (!activeConvId) {
          const newest = updatedConvs[0];
          if (newest) setActiveConvId(newest.id);
      }

    } catch (err: any) {
      setError(err?.message || 'Failed to get answer');
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err?.message || 'Something went wrong'}`,
        timestamp: new Date(),
      }]);
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
    }
  };

  const sourceIcon = (type: string) =>
    type === 'pdf' ? FileText : type === 'web' ? Globe : Youtube;

  return (
    <div className="h-full flex bg-white dark:bg-[#0F172A] relative overflow-hidden">
      {/* ── Conversation Sidebar ───────────────────────────────────────── */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 overflow-hidden flex-shrink-0 border-r border-gray-200 dark:border-gray-800 flex flex-col bg-gray-50/50 dark:bg-[#0F172A]`}>
        <div className="p-4 border-b border-gray-200 dark:border-gray-800">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#6366F1] text-white hover:bg-[#4F46E5] transition-all text-sm font-semibold shadow-lg shadow-[#6366F1]/20"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-3 px-3 space-y-1">
          {conversations.length === 0 && (
            <div className="text-center py-10 px-4">
               <MessageSquare className="w-8 h-8 text-gray-300 dark:text-gray-700 mx-auto mb-2" />
               <p className="text-xs text-gray-400">No conversations yet</p>
            </div>
          )}
          {conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              className={`group relative flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer transition-all ${
                activeConvId === conv.id
                  ? 'bg-white dark:bg-[#1E293B] shadow-sm border border-gray-200 dark:border-gray-700'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-800/50'
              }`}
            >
              <MessageSquare className={`w-4 h-4 flex-shrink-0 ${
                activeConvId === conv.id ? 'text-[#6366F1]' : 'text-gray-400'
              }`} />

              {editingConvId === conv.id ? (
                <input
                  autoFocus
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleRenameConv(conv.id);
                    if (e.key === 'Escape') setEditingConvId(null);
                  }}
                  onClick={e => e.stopPropagation()}
                  className="flex-1 bg-transparent text-xs text-gray-900 dark:text-gray-100 outline-none border-b border-[#6366F1]"
                />
              ) : (
                <span className="flex-1 text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
                  {conv.title}
                </span>
              )}

              <div className={`flex items-center gap-1 flex-shrink-0 transition-opacity ${editingConvId === conv.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                {editingConvId === conv.id ? (
                  <>
                    <button onClick={e => { e.stopPropagation(); handleRenameConv(conv.id); }}
                      className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/20">
                      <Check className="w-3 h-3 text-green-500" />
                    </button>
                    <button onClick={e => { e.stopPropagation(); setEditingConvId(null); }}
                      className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/20">
                      <X className="w-3 h-3 text-red-500" />
                    </button>
                  </>
                ) : (
                  <>
                    <button onClick={e => {
                      e.stopPropagation();
                      setEditingConvId(conv.id);
                      setEditTitle(conv.title);
                    }} className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700">
                      <Edit2 className="w-3 h-3 text-gray-400" />
                    </button>
                    <button onClick={e => handleDeleteConv(conv.id, e)}
                      className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/20">
                      <Trash2 className="w-3 h-3 text-red-400" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Sidebar toggle button ──────────────────────────────────────── */}
      <button
        onClick={() => setSidebarOpen(o => !o)}
        className="absolute top-1/2 -translate-y-1/2 z-20 p-1.5 rounded-r-xl bg-white dark:bg-gray-800 border border-l-0 border-gray-200 dark:border-gray-700 shadow-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
        style={{ left: sidebarOpen ? '256px' : '0px' }}
      >
        {sidebarOpen ? <ChevronLeft className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>

      {/* ── Main Chat Area ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-8 py-5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center gap-4">
             <div className="p-2 rounded-xl bg-[#6366F1]/10 text-[#6366F1]">
                <MessageSquare className="w-5 h-5" />
             </div>
             <div>
                <h1 className="text-lg font-bold text-gray-900 dark:text-white">
                  {activeConvId
                    ? conversations.find(c => c.id === activeConvId)?.title || 'Chat'
                    : 'New Conversation'}
                </h1>
                <p className="text-[10px] uppercase tracking-wider font-bold text-gray-400">
                  {selectedSourceIds.size > 0
                    ? `${selectedSourceIds.size} Focus Sources`
                    : `Global RAG Search`}
                </p>
             </div>
          </div>
          <button 
            onClick={() => setIsKbOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm font-bold text-gray-700 dark:text-gray-300 transition-colors shadow-sm border border-gray-200 dark:border-gray-700"
          >
            <Database className="w-4 h-4 text-[#6366F1]" />
            Knowledge Base
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-8 space-y-8 scroll-smooth">
          {messages.length === 0 && !isThinking && (
            <div className="h-full flex flex-col items-center justify-center text-center py-20 animate-in fade-in zoom-in duration-500">
              <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-[#6366F1] to-[#818CF8] flex items-center justify-center mb-6 shadow-xl shadow-[#6366F1]/20">
                <Send className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-3">How can InteleX assist you?</h2>
              <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                Ask questions about your uploaded documents, websites, or YouTube videos. InteleX provides citations for every answer.
              </p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-4 duration-300`}>
              {msg.role === 'user' ? (
                <div className="max-w-[70%] px-6 py-4 rounded-3xl bg-[#6366F1] text-white shadow-lg shadow-[#6366F1]/10">
                  <p className="text-sm leading-relaxed font-medium">{msg.content}</p>
                </div>
              ) : (
                <div className="max-w-[85%] w-full p-6 rounded-3xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 shadow-sm">
                  <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line font-medium">
                    {msg.content}
                  </p>
                  {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                    <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
                      <div className="flex items-center gap-2 mb-4">
                         <div className="w-1 h-4 bg-[#6366F1] rounded-full" />
                         <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Supporting Evidence</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {[...new Map(msg.retrievedChunks.map(c => [c.sourceId, c])).values()].map(chunk => {
                          const Icon = sourceIcon(chunk.sourceType);
                          return (
                            <button key={chunk.sourceId}
                              onClick={() => setSelectedChunks(msg.retrievedChunks || [])}
                              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-[11px] font-semibold text-gray-600 dark:text-gray-300 shadow-sm hover:border-[#6366F1] hover:text-[#6366F1] transition-colors">
                              <Icon className="w-3.5 h-3.5" />
                              <span className="truncate max-w-[200px]">{chunk.sourceName}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {isThinking && (
            <div className="flex items-center gap-3 text-gray-400 p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/30 w-fit animate-pulse">
              <Loader2 className="w-5 h-5 animate-spin text-[#6366F1]" />
              <span className="text-sm font-medium">Processing request...</span>
            </div>
          )}

          {isStreaming && streamingAnswer && (
            <div className="max-w-[85%] w-full p-6 rounded-3xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 shadow-sm animate-in fade-in duration-300">
              <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line font-medium">
                {streamingAnswer}
                <span className="inline-block w-1.5 h-4 ml-1 bg-[#6366F1] animate-pulse align-middle" />
              </p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-sm text-red-600 font-medium flex items-center gap-3">
              <X className="w-4 h-4" />
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-8 bg-white dark:bg-[#0F172A] border-t border-gray-200 dark:border-gray-800">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative">
            
            {/* Image Preview */}
            {imagePreviewUrl && (
              <div className="mb-4 relative w-32 h-32 rounded-2xl overflow-hidden border-2 border-[#6366F1] shadow-lg group">
                <img src={imagePreviewUrl} alt="Upload preview" className="w-full h-full object-cover" />
                {isUploadingImage ? (
                  <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-white" />
                  </div>
                ) : (
                  <button 
                    type="button"
                    onClick={removeImage}
                    className="absolute top-1 right-1 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            )}

            <div className="flex justify-between items-center mb-3 px-2">
               <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                  <span>Model:</span>
                  <select 
                     value={llmProvider}
                     onChange={(e) => setLlmProvider(e.target.value)}
                     className="bg-transparent border-none text-[#6366F1] font-bold focus:outline-none cursor-pointer"
                  >
                     <option value="groq">Llama-3 (Groq - Fast)</option>
                     <option value="huggingface">Legal Model (HF API)</option>
                  </select>
               </div>
            </div>

            <div className="relative group">
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                accept="image/*" 
                className="hidden" 
              />
              
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="Message InteleX..."
                rows={1}
                className="w-full px-6 py-5 pl-14 pr-24 rounded-3xl bg-gray-50 dark:bg-[#1E293B] border border-transparent dark:border-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:bg-white dark:focus:bg-[#1E293B] transition-all resize-none shadow-inner min-h-[64px] max-h-48 overflow-y-auto"
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              
              <button 
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="absolute left-4 bottom-3 p-3 rounded-2xl hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 transition-colors"
              >
                <Paperclip className="w-5 h-5" />
              </button>

              <div className="absolute right-3 bottom-3 flex gap-2">
                <button type="button" onClick={() => {setQuestion(''); removeImage();}}
                  className="p-3 rounded-2xl hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 transition-colors">
                  <RotateCcw className="w-5 h-5" />
                </button>
                <button type="submit"
                  disabled={!question.trim() || isThinking || isStreaming || isUploadingImage}
                  className="p-3 rounded-2xl bg-[#6366F1] text-white hover:bg-[#4F46E5] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-[#6366F1]/20">
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
            <p className="text-[10px] text-gray-400 text-center mt-3 font-medium uppercase tracking-widest">
              Enter to send · Shift+Enter for new line
            </p>
          </form>
        </div>
      </div>

      {/* ── Context Sidebar (Right) ────────────────────────────────────── */}
      <div className="w-80 flex flex-col bg-gray-50/50 dark:bg-[#0F172A] border-l border-gray-200 dark:border-gray-800 overflow-hidden">
         <div className="p-6 border-b border-gray-200 dark:border-gray-800">
            <h2 className="text-sm font-bold text-gray-900 dark:text-white mb-1">Retrieved Context</h2>
            <p className="text-[10px] text-gray-400 uppercase tracking-widest font-bold">Evidence from Sources</p>
         </div>
         
         <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {selectedChunks.length === 0 ? (
               <div className="h-40 flex flex-col items-center justify-center text-center opacity-40">
                  <FileText className="w-8 h-8 mb-2" />
                  <p className="text-xs">No citations yet</p>
               </div>
            ) : (
               selectedChunks.map((chunk, i) => {
                  const Icon = sourceIcon(chunk.sourceType);
                  return (
                     <div key={i} className="p-4 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 shadow-sm hover:border-[#6366F1] transition-all group relative">
                        <div className="flex items-center gap-2 mb-3 pr-6">
                           <Icon className="w-3.5 h-3.5 text-[#6366F1] flex-shrink-0" />
                           <span className="text-[10px] font-bold text-gray-900 dark:text-white truncate flex-1" title={chunk.sourceName}>{chunk.sourceName}</span>
                           <span className="text-[9px] font-black text-[#6366F1] flex-shrink-0">{(chunk.similarityScore * 100).toFixed(0)}%</span>
                        </div>
                        
                        {(chunk.sourceType === 'web' || chunk.sourceType === 'youtube') && chunk.metadata?.url && (
                           <a href={chunk.metadata.url} target="_blank" rel="noopener noreferrer" 
                              className="absolute top-4 right-4 p-1 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-500 hover:text-[#6366F1] transition-colors">
                              <ExternalLink className="w-3 h-3" />
                           </a>
                        )}

                        <p className="text-[11px] text-gray-600 dark:text-gray-400 leading-relaxed italic line-clamp-4 group-hover:line-clamp-none transition-all">
                           "{chunk.text}"
                        </p>
                        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center">
                           <span className="text-[9px] font-bold text-gray-400 uppercase">
                              {chunk.metadata?.page ? `Page ${chunk.metadata.page}` : chunk.metadata?.timestamp ? `@ ${chunk.metadata.timestamp}` : 'Document Chunk'}
                           </span>
                        </div>
                     </div>
                  );
               })
            )}
         </div>
      </div>

      {/* ── Knowledge Base Modal ─────────────────────────────────────────── */}
      {isKbOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#0F172A] w-full max-w-4xl rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] border border-gray-200 dark:border-gray-800">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-[#1E293B]">
              <div className="flex items-center gap-3">
                <Database className="w-6 h-6 text-[#6366F1]" />
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">Resource Manager</h2>
              </div>
              <button onClick={() => setIsKbOpen(false)} className="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Upload Section (Left) */}
              <div className="md:col-span-1 space-y-6">
                <div className="p-5 bg-gray-50 dark:bg-[#1E293B] rounded-2xl border border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Upload className="w-4 h-4 text-[#6366F1]" /> Upload File
                  </h3>
                  <input type="file" ref={sourceFileInputRef} onChange={handleSourceFileUpload} accept=".pdf,.txt,.docx" className="hidden" />
                  <button 
                    onClick={() => sourceFileInputRef.current?.click()}
                    disabled={isUploadingSource}
                    className="w-full py-3 px-4 bg-white dark:bg-[#0F172A] border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl hover:border-[#6366F1] dark:hover:border-[#6366F1] transition-colors flex flex-col items-center justify-center gap-2 text-gray-500 disabled:opacity-50"
                  >
                    {isUploadingSource ? <Loader2 className="w-6 h-6 animate-spin text-[#6366F1]" /> : <FileText className="w-6 h-6" />}
                    <span className="text-sm font-medium">{isUploadingSource ? "Processing..." : "Select Document"}</span>
                  </button>
                </div>

                <div className="p-5 bg-gray-50 dark:bg-[#1E293B] rounded-2xl border border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-4 flex items-center gap-2">
                    <LinkIcon className="w-4 h-4 text-emerald-500" /> Web & Video
                  </h3>
                  <form onSubmit={handleUrlUpload} className="space-y-3">
                    <select 
                      value={uploadType} 
                      onChange={(e) => setUploadType(e.target.value as any)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-[#0F172A] border border-gray-300 dark:border-gray-600 text-sm focus:ring-2 focus:ring-[#6366F1] outline-none"
                    >
                      <option value="url">Website URL</option>
                      <option value="youtube">YouTube Video</option>
                    </select>
                    <input 
                      type="url" 
                      placeholder="Paste link here..." 
                      value={uploadUrlInput}
                      onChange={(e) => setUploadUrlInput(e.target.value)}
                      className="w-full p-2 rounded-lg bg-white dark:bg-[#0F172A] border border-gray-300 dark:border-gray-600 text-sm focus:ring-2 focus:ring-[#6366F1] outline-none"
                    />
                    <button 
                      type="submit" 
                      disabled={!uploadUrlInput.trim() || isUploadingSource}
                      className="w-full py-2 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
                    >
                      {isUploadingSource ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                      Add Link
                    </button>
                  </form>
                </div>
              </div>

              {/* Resources List (Right) */}
              <div className="md:col-span-2 flex flex-col h-full min-h-[400px]">
                <div className="flex justify-between items-end mb-4">
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">Your Resources</h3>
                  <span className="text-sm text-gray-500 font-medium">
                    {selectedSourceIds.size > 0 ? `${selectedSourceIds.size} selected for RAG` : 'Global RAG (All selected by default)'}
                  </span>
                </div>
                
                {sources.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-gray-400 p-8 border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-2xl">
                    <Database className="w-12 h-12 mb-3 opacity-20" />
                    <p>No resources uploaded yet.</p>
                  </div>
                ) : (
                  <div className="flex-1 space-y-3">
                    {sources.slice((kbPage - 1) * KB_ITEMS_PER_PAGE, kbPage * KB_ITEMS_PER_PAGE).map(src => (
                      <div 
                        key={src.id} 
                        onClick={() => toggleSourceSelection(src.id)}
                        className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex items-center justify-between ${
                          selectedSourceIds.has(src.id) 
                            ? 'border-[#6366F1] bg-[#6366F1]/5' 
                            : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1E293B] hover:border-gray-300 dark:hover:border-gray-600'
                        }`}
                      >
                        <div className="flex items-center gap-3 overflow-hidden">
                          <div className={`p-2 rounded-lg flex-shrink-0 ${
                            src.type === 'pdf' || src.type === 'judgment' ? 'bg-red-100 text-red-600' : 
                            src.type === 'youtube' ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'
                          }`}>
                            {src.type === 'youtube' ? <Youtube className="w-5 h-5" /> : 
                             src.type === 'url' ? <Globe className="w-5 h-5" /> : <FileText className="w-5 h-5" />}
                          </div>
                          <div className="truncate">
                            <h4 className="font-semibold text-gray-900 dark:text-white truncate" title={src.title || src.id}>
                              {src.title || src.id}
                            </h4>
                            <div className="flex gap-2 text-xs text-gray-500 font-medium mt-1">
                              <span className="uppercase tracking-wider px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">{src.type}</span>
                              <span>{src.chunkCount} chunks</span>
                            </div>
                          </div>
                        </div>
                        <div className={`w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${
                          selectedSourceIds.has(src.id) ? 'bg-[#6366F1] border-[#6366F1]' : 'border-gray-300 dark:border-gray-600'
                        }`}>
                          {selectedSourceIds.has(src.id) && <Check className="w-3 h-3 text-white" />}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Pagination */}
                {sources.length > KB_ITEMS_PER_PAGE && (
                  <div className="flex justify-between items-center mt-6 pt-4 border-t border-gray-200 dark:border-gray-800">
                    <button 
                      disabled={kbPage === 1} 
                      onClick={() => setKbPage(p => p - 1)}
                      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <span className="text-sm font-medium text-gray-500">
                      Page {kbPage} of {Math.ceil(sources.length / KB_ITEMS_PER_PAGE)}
                    </span>
                    <button 
                      disabled={kbPage >= Math.ceil(sources.length / KB_ITEMS_PER_PAGE)} 
                      onClick={() => setKbPage(p => p + 1)}
                      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
            
            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#1E293B] flex justify-between items-center">
              <p className="text-xs text-gray-500">
                Tip: Leave all unselected to search across your entire knowledge base.
              </p>
              <button 
                onClick={() => setIsKbOpen(false)}
                className="px-6 py-2 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl font-medium transition-colors shadow-lg shadow-[#6366F1]/20"
              >
                Apply Selection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Post-Upload Action Prompt ────────────────────────────────────── */}
      {postUploadPrompt && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in zoom-in-95 duration-200">
          <div className="bg-white dark:bg-[#1E293B] w-full max-w-md rounded-3xl shadow-2xl p-8 border border-gray-200 dark:border-gray-700 text-center">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 text-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
              <Check className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Resource Processed!</h2>
            <p className="text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
              "{postUploadPrompt.source.title || postUploadPrompt.source.id}" has been chunked and embedded successfully.
            </p>
            <div className="space-y-3">
              <button 
                onClick={() => startChatWithSource(postUploadPrompt.source.id)}
                className="w-full py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl font-bold transition-all shadow-lg shadow-[#6366F1]/20 flex items-center justify-center gap-2"
              >
                <MessageSquare className="w-5 h-5" />
                Start Chatting with this Resource
              </button>
              <button 
                onClick={() => setPostUploadPrompt(null)}
                className="w-full py-3 bg-gray-100 dark:bg-[#0F172A] hover:bg-gray-200 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-xl font-bold transition-colors"
              >
                No, just save it to Knowledge Base
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
