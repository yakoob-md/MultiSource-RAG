// frontend/src/app/components/screens/AskAI.tsx
import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Send, RotateCcw, Loader2, FileText, Globe, Youtube,
  Plus, MessageSquare, Trash2, Edit2, Check, X,
  ChevronLeft, ChevronRight
} from 'lucide-react';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { streamQueryRag, fetchSources, fetchConversations, fetchConversationMessages, createConversation, deleteConversation, renameConversation, Conversation } from '../../api';

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

  // ── Source selector ───────────────────────────────────────────────────────
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());

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
        });
      }
      setMessages(rebuilt);
    } catch {
      setError('Failed to load conversation');
    }
  }, []);

  // ── New chat ──────────────────────────────────────────────────────────────
  const handleNewChat = async () => {
    const conv = await createConversation('New Chat');
    setConversations(prev => [conv, ...prev]);
    setActiveConvId(conv.id);
    setMessages([]);
    setSelectedChunks([]);
    setError(null);
  };

  // ── Delete conversation ───────────────────────────────────────────────────
  const handleDeleteConv = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteConversation(convId);
    setConversations(prev => prev.filter(c => c.id !== convId));
    if (activeConvId === convId) {
      setActiveConvId(null);
      setMessages([]);
    }
  };

  // ── Rename conversation ───────────────────────────────────────────────────
  const handleRenameConv = async (convId: string) => {
    if (!editTitle.trim()) return;
    await renameConversation(convId, editTitle);
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, title: editTitle } : c
    ));
    setEditingConvId(null);
  };

  // ── Submit question ───────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isThinking || isStreaming) return;

    setError(null);
    let convId = activeConvId;

    // Auto-create conversation if none active
    if (!convId) {
      const conv = await createConversation(question.slice(0, 50));
      convId = conv.id;
      setActiveConvId(convId);
      setConversations(prev => [conv, ...prev]);
    }

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    const currentQuestion = question;
    setQuestion('');
    setIsThinking(true);
    setIsStreaming(true);
    setStreamingAnswer('');

    // Build history from current messages
    const history = messages.slice(-6).map(m => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const sourceFilter = selectedSourceIds.size > 0
        ? Array.from(selectedSourceIds) : undefined;

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
          capturedChunks = meta.retrievedChunks || [];
          setSelectedChunks(capturedChunks);
        },
        (err) => { throw err; }
      );

      const aiMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: fullAnswer,
        timestamp: new Date(),
        retrievedChunks: capturedChunks,
      };

      setMessages(prev => [...prev, aiMsg]);
      setStreamingAnswer('');

      // Update conversation title from first message
      if (messages.length === 0) {
        const newTitle = currentQuestion.slice(0, 60);
        await renameConversation(convId, newTitle);
        setConversations(prev => prev.map(c =>
          c.id === convId ? { ...c, title: newTitle, updated_at: new Date().toISOString() } : c
        ));
      } else {
        // Just bump updated_at in UI
        setConversations(prev => prev.map(c =>
          c.id === convId ? { ...c, updated_at: new Date().toISOString() } : c
        ));
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
    <div className="h-full flex bg-white dark:bg-[#0F172A]">
      {/* ── Conversation Sidebar ───────────────────────────────────────── */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-200 overflow-hidden flex-shrink-0 border-r border-gray-200 dark:border-gray-800 flex flex-col`}>
        <div className="p-3 border-b border-gray-200 dark:border-gray-800">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-[#6366F1] text-white hover:bg-[#4F46E5] transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
          {conversations.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-8 px-4">
              No conversations yet. Start a new chat!
            </p>
          )}
          {conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all ${
                activeConvId === conv.id
                  ? 'bg-[#6366F1]/10 border border-[#6366F1]/30'
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
                <span className="flex-1 text-xs text-gray-700 dark:text-gray-300 truncate">
                  {conv.title}
                </span>
              )}

              <div className="hidden group-hover:flex items-center gap-1 flex-shrink-0">
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
        className="absolute left-0 top-1/2 -translate-y-1/2 z-20 p-1.5 rounded-r-lg bg-gray-100 dark:bg-gray-800 border border-l-0 border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        style={{ left: sidebarOpen ? '256px' : '0px' }}
      >
        {sidebarOpen ? <ChevronLeft className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
      </button>

      {/* ── Main Chat Area ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
              {activeConvId
                ? conversations.find(c => c.id === activeConvId)?.title || 'Chat'
                : 'Ask AI'}
            </h1>
            <p className="text-xs text-gray-500">
              {selectedSourceIds.size > 0
                ? `${selectedSourceIds.size} sources selected`
                : `All ${sources.length} sources`}
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {messages.length === 0 && !isThinking && (
            <div className="h-full flex flex-col items-center justify-center text-center py-20">
              <div className="w-16 h-16 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-[#6366F1]" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                {activeConvId ? 'Continue the conversation' : 'Start a new conversation'}
              </h2>
              <p className="text-sm text-gray-500 max-w-sm">
                Ask anything about your uploaded documents, websites, or YouTube videos.
              </p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'user' ? (
                <div className="max-w-2xl px-5 py-3 rounded-2xl bg-[#6366F1] text-white shadow-sm">
                  <p className="text-sm leading-relaxed">{msg.content}</p>
                </div>
              ) : (
                <div className="max-w-4xl w-full p-5 rounded-2xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
                  <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line">
                    {msg.content}
                  </p>
                  {msg.retrievedChunks && msg.retrievedChunks.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                      <p className="text-xs font-semibold text-gray-400 uppercase mb-2">Sources Used</p>
                      <div className="flex flex-wrap gap-2">
                        {[...new Map(msg.retrievedChunks.map(c => [c.sourceId, c])).values()].map(chunk => {
                          const Icon = sourceIcon(chunk.sourceType);
                          return (
                            <span key={chunk.sourceId}
                              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-400">
                              <Icon className="w-3 h-3" />
                              {chunk.sourceName}
                            </span>
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
            <div className="flex items-center gap-3 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin text-[#6366F1]" />
              <span className="text-sm">Thinking...</span>
            </div>
          )}

          {isStreaming && streamingAnswer && (
            <div className="max-w-4xl w-full p-5 rounded-2xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line">
                {streamingAnswer}
                <span className="inline-block w-0.5 h-4 ml-1 bg-[#6366F1] animate-pulse align-middle" />
              </p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-600">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="relative">
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="Ask a question..."
                rows={3}
                className="w-full px-5 py-4 pr-24 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] resize-none shadow-sm"
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              <div className="absolute bottom-3 right-3 flex gap-2">
                <button type="button" onClick={() => setQuestion('')}
                  className="p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400">
                  <RotateCcw className="w-4 h-4" />
                </button>
                <button type="submit"
                  disabled={!question.trim() || isThinking || isStreaming}
                  className="p-2 rounded-xl bg-[#6366F1] text-white hover:bg-[#4F46E5] disabled:opacity-40 disabled:cursor-not-allowed">
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-400 text-center mt-2">
              Press Enter to send · Shift+Enter for new line
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}