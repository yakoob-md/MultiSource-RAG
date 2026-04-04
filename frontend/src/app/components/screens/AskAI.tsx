import { useEffect, useRef, useState } from 'react';
import {
  Send, RotateCcw, Loader2, FileText, Globe, Youtube,
  CheckSquare, Square, ChevronDown, ChevronUp, Filter
} from 'lucide-react';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { queryRag, fetchSources } from '../../api';
import { loadChatHistory, saveChatHistory } from '../../data/history';

export function AskAI() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadChatHistory());
  const [question, setQuestion] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedChunks, setSelectedChunks] = useState<RetrievedChunk[]>(() => {
    const history = loadChatHistory();
    const last = history[history.length - 1];
    return last?.retrievedChunks || [];
  });

  // Source selector state
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [showSourceFilter, setShowSourceFilter] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  useEffect(() => {
    if (messages.length > 0) {
      saveChatHistory(messages);
    }
  }, [messages]);

  // Load available sources for the selector
  useEffect(() => {
    setSourcesLoading(true);
    fetchSources()
      .then(setSources)
      .catch(() => { })
      .finally(() => setSourcesLoading(false));
  }, []);

  const toggleSource = (id: string) => {
    setSelectedSourceIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedSourceIds.size === sources.length) {
      setSelectedSourceIds(new Set());
    } else {
      setSelectedSourceIds(new Set(sources.map(s => s.id)));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isThinking) return;

    setError(null);

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setQuestion('');
    setIsThinking(true);

    try {
      const sourceFilter = selectedSourceIds.size > 0 ? Array.from(selectedSourceIds) : undefined;
      const response = await queryRag(userMessage.content, sourceFilter);

      const aiMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        citations: response.sources,
        retrievedChunks: response.retrievedChunks,
      };

      setMessages(prev => [...prev, aiMessage]);
      setSelectedChunks(response.retrievedChunks);
    } catch (err: any) {
      const message = err?.message || 'Failed to get answer from server.';
      setError(message);

      const errorMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: `Sorry, something went wrong.\n\nDetails: ${message}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsThinking(false);
    }
  };

  const sourceIcon = (type: string) =>
    type === 'pdf' ? FileText : type === 'web' ? Globe : Youtube;

  return (
    <div className="h-full flex">
      {/* Center Panel - Chat */}
      <div className="flex-1 flex flex-col border-r border-gray-200 dark:border-gray-800 min-w-0">
        {/* Header */}
        <div className="px-8 py-6 border-b border-gray-200 dark:border-gray-800">
          <h1 className="text-2xl text-gray-900 dark:text-[#F8FAFC] mb-1">Ask AI</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {selectedSourceIds.size > 0
              ? `Searching ${selectedSourceIds.size} selected source${selectedSourceIds.size > 1 ? 's' : ''}`
              : `Searching all ${sources.length} source${sources.length !== 1 ? 's' : ''}`}
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-20 text-gray-500 dark:text-gray-400">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center">
                <Send className="w-8 h-8 text-[#6366F1]" />
              </div>
              <p className="text-lg mb-1">Ask a question</p>
              <p className="text-sm">
                {sources.length === 0
                  ? 'Upload a PDF, website, or YouTube video first, then ask questions here.'
                  : 'Use the source filter on the right to narrow your search.'}
              </p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id}>
              {message.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="max-w-2xl px-5 py-3 rounded-2xl bg-[#6366F1] text-white">
                    <p className="text-sm leading-relaxed">{message.content}</p>
                  </div>
                </div>
              ) : (
                <div className="max-w-4xl">
                  <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line mb-4">
                      {message.content}
                    </p>

                    {/* Citations */}
                    {message.citations && message.citations.length > 0 && (
                      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                        <h4 className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Sources Used</h4>
                        <div className="space-y-2">
                          {message.citations.map((citation, idx) => {
                            const Icon = sourceIcon(citation.sourceType);
                            return (
                              <div key={idx} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] transition-colors">
                                <div className="flex items-start gap-3">
                                  <div className="p-1.5 rounded bg-white dark:bg-gray-800">
                                    <Icon className="w-3.5 h-3.5 text-gray-600 dark:text-gray-400" />
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs text-gray-900 dark:text-gray-100 truncate">{citation.sourceTitle}</span>
                                      {citation.reference && (
                                        <span className="text-xs text-[#6366F1] shrink-0">{citation.reference}</span>
                                      )}
                                    </div>
                                    <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                                      {citation.snippet}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {isThinking && (
            <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin text-[#6366F1]" />
              <span className="text-sm">Searching sources and generating answer...</span>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-800">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="relative">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question across your knowledge sources..."
                rows={3}
                className="w-full px-5 py-4 pr-28 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent resize-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              <div className="absolute bottom-4 right-4 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setQuestion('')}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  title="Clear"
                >
                  <RotateCcw className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                </button>
                <button
                  type="submit"
                  disabled={!question.trim() || isThinking}
                  className="px-4 py-2 rounded-lg bg-[#6366F1] hover:bg-[#4F46E5] text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <span className="text-sm">Ask</span>
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Right Panel - Source Selector + Retrieved Context */}
      <div className="w-96 flex flex-col bg-gray-50 dark:bg-[#0F172A] shrink-0">

        {/* Source Filter Section */}
        <div className="border-b border-gray-200 dark:border-gray-800">
          <button
            onClick={() => setShowSourceFilter(!showSourceFilter)}
            className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-[#6366F1]" />
              <span className="text-sm font-medium text-gray-900 dark:text-[#F8FAFC]">Source Filter</span>
              {selectedSourceIds.size > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-[#6366F1] text-white text-xs">
                  {selectedSourceIds.size}
                </span>
              )}
            </div>
            {showSourceFilter ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
          </button>

          {showSourceFilter && (
            <div className="px-6 pb-4 space-y-1 max-h-60 overflow-y-auto">
              {sourcesLoading && (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Loading sources...
                </div>
              )}

              {!sourcesLoading && sources.length === 0 && (
                <p className="text-xs text-gray-400 py-2">No sources uploaded yet.</p>
              )}

              {!sourcesLoading && sources.length > 0 && (
                <>
                  {/* Select All */}
                  <button
                    onClick={toggleAll}
                    className="w-full flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors text-left"
                  >
                    {selectedSourceIds.size === sources.length ? (
                      <CheckSquare className="w-4 h-4 text-[#6366F1] shrink-0" />
                    ) : (
                      <Square className="w-4 h-4 text-gray-400 shrink-0" />
                    )}
                    <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                      {selectedSourceIds.size === sources.length ? 'Deselect All' : 'Select All'}
                    </span>
                  </button>

                  <div className="border-t border-gray-200 dark:border-gray-700 my-1" />

                  {sources.map(source => {
                    const Icon = sourceIcon(source.type);
                    const isSelected = selectedSourceIds.has(source.id);
                    return (
                      <button
                        key={source.id}
                        onClick={() => toggleSource(source.id)}
                        className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg transition-colors text-left ${isSelected
                            ? 'bg-[#6366F1]/10 hover:bg-[#6366F1]/15'
                            : 'hover:bg-gray-200 dark:hover:bg-gray-800'
                          }`}
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-[#6366F1] shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 text-gray-400 shrink-0" />
                        )}
                        <Icon className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400 shrink-0" />
                        <span className="text-xs text-gray-700 dark:text-gray-300 truncate flex-1">
                          {source.title}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${source.language === 'EN' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' :
                            source.language === 'HI' ? 'bg-orange-500/10 text-orange-600 dark:text-orange-400' :
                              'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                          }`}>
                          {source.language}
                        </span>
                      </button>
                    );
                  })}
                </>
              )}

              {selectedSourceIds.size > 0 && (
                <button
                  onClick={() => setSelectedSourceIds(new Set())}
                  className="w-full text-xs text-center text-[#6366F1] hover:underline py-1"
                >
                  Clear selection (search all)
                </button>
              )}
            </div>
          )}
        </div>

        {/* Retrieved Context */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
          <h2 className="text-sm font-medium text-gray-900 dark:text-[#F8FAFC]">Retrieved Context</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {selectedChunks.length} chunk{selectedChunks.length !== 1 ? 's' : ''} retrieved
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {selectedChunks.length === 0 && (
            <p className="text-xs text-gray-400 text-center pt-4">
              Ask a question to see relevant context here.
            </p>
          )}
          {selectedChunks.map((chunk) => {
            const Icon = sourceIcon(chunk.sourceType);
            return (
              <div
                key={chunk.id}
                className="p-4 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon className="w-4 h-4 text-gray-600 dark:text-gray-400 shrink-0" />
                    <span className="text-xs text-gray-900 dark:text-gray-100 truncate">
                      {chunk.sourceName}
                    </span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] shrink-0 ml-2 ${chunk.language === 'EN' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' :
                      chunk.language === 'HI' ? 'bg-orange-500/10 text-orange-600 dark:text-orange-400' :
                        'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                    }`}>
                    {chunk.language}
                  </span>
                </div>

                <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed mb-3 line-clamp-4">
                  {chunk.text}
                </p>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500 dark:text-gray-400">
                    {chunk.metadata?.page && `Page ${chunk.metadata.page}`}
                    {chunk.metadata?.timestamp && `@ ${chunk.metadata.timestamp}`}
                  </span>
                  <div className="flex items-center gap-1">
                    <div className="w-12 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#6366F1]"
                        style={{ width: `${chunk.similarityScore * 100}%` }}
                      />
                    </div>
                    <span className="text-[#6366F1] ml-1">
                      {(chunk.similarityScore * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
