import { useEffect, useRef, useState } from 'react';
import {
  Send, RotateCcw, Loader2, FileText, Globe, Youtube,
  CheckSquare, Square, ChevronDown, ChevronUp, Filter, RotateCcw as RotateIcon
} from 'lucide-react';
import { ChatMessage, RetrievedChunk, KnowledgeSource } from '../../types';
import { queryRag, streamQueryRag, fetchSources } from '../../api';
import { loadChatHistory, saveChatHistory } from '../../data/history';

export function AskAI() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadChatHistory());
  const [question, setQuestion] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingAnswer, setStreamingAnswer] = useState<string>('');
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
  }, [messages, isThinking, streamingAnswer]);

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

    if (!question.trim() || isThinking || isStreaming) return;

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
    setIsStreaming(true);
    setStreamingAnswer('');

    try {
      const sourceFilter = selectedSourceIds.size > 0 ? Array.from(selectedSourceIds) : undefined;

      let fullAnswer = '';
      let capturedCitations: any[] = [];
      let capturedChunks: any[] = [];

      await streamQueryRag(
        userMessage.content,
        sourceFilter,
        messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
        (token) => {
          setIsThinking(false);
          fullAnswer += token;
          setStreamingAnswer(fullAnswer);
        },
        (meta) => {
          // meta contains chatId, citations, retrievedChunks
          capturedCitations = meta.citations || [];
          capturedChunks = meta.retrievedChunks || [];
          setSelectedChunks(capturedChunks);
        },
        (err) => {
          throw err;
        }
      );

      // Once done, add the final message
      const aiMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: fullAnswer,
        timestamp: new Date(),
        citations: capturedCitations,
        retrievedChunks: capturedChunks,
      };

      setMessages(prev => [...prev, aiMessage]);
      setStreamingAnswer('');
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
      setIsStreaming(false);
      setIsThinking(false);
    }
  };

  const sourceIcon = (type: string) =>
    type === 'pdf' ? FileText : type === 'web' ? Globe : Youtube;

  return (
    <div className="h-full flex">
      {/* Center Panel - Chat */}
      <div className="flex-1 flex flex-col border-r border-gray-200 dark:border-gray-800 min-w-0 bg-white dark:bg-[#0F172A]">
        {/* Header */}
        <div className="px-8 py-6 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-[#F8FAFC] mb-1">Ask AI</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {selectedSourceIds.size > 0
                ? `Searching ${selectedSourceIds.size} selected source${selectedSourceIds.size > 1 ? 's' : ''}`
                : `Searching all ${sources.length} source${sources.length !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-20 text-gray-500 dark:text-gray-400">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center">
                <Send className="w-8 h-8 text-[#6366F1]" />
              </div>
              <p className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">Ask a question</p>
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
                  <div className="max-w-2xl px-5 py-3 rounded-2xl bg-[#6366F1] text-white shadow-sm">
                    <p className="text-sm leading-relaxed">{message.content}</p>
                  </div>
                </div>
              ) : (
                <div className="max-w-4xl">
                  <div className="p-6 rounded-2xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 shadow-sm">
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line mb-4">
                      {message.content}
                    </p>

                    {/* Citations */}
                    {message.citations && message.citations.length > 0 && (
                      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">Sources Used</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {message.citations.map((citation, idx) => {
                            const Icon = sourceIcon(citation.sourceType);
                            return (
                              <div key={idx} className="p-3 rounded-xl bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] transition-all group">
                                <div className="flex items-start gap-3">
                                  <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 group-hover:bg-[#6366F1]/10 transition-colors">
                                    <Icon className="w-4 h-4 text-gray-600 dark:text-gray-400 group-hover:text-[#6366F1]" />
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">{citation.sourceTitle}</span>
                                      {citation.reference && (
                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#6366F1]/10 text-[#6366F1] font-medium">{citation.reference}</span>
                                      )}
                                    </div>
                                    <p className="text-[11px] text-gray-600 dark:text-gray-400 line-clamp-2 italic">
                                      "{citation.snippet}"
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
            <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800">
                <Loader2 className="w-5 h-5 animate-spin text-[#6366F1]" />
              </div>
              <span className="text-sm font-medium">Thinking...</span>
            </div>
          )}

          {isStreaming && streamingAnswer !== '' && (
            <div className="max-w-4xl animate-in fade-in duration-300">
              <div className="p-6 rounded-2xl bg-gray-50 dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line">
                  {streamingAnswer}
                  <span className="inline-block w-1.5 h-4 ml-1 bg-[#6366F1] animate-pulse align-middle" />
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-700 dark:text-red-300 animate-in shake duration-500">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-800">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="relative group">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question across your knowledge sources..."
                rows={3}
                className="w-full px-6 py-5 pr-28 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent resize-none transition-all shadow-sm group-hover:border-gray-400 dark:group-hover:border-gray-600"
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
                  className="p-2.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
                  title="Clear"
                >
                  <RotateCcw className="w-5 h-5" />
                </button>
                <button
                  type="submit"
                  disabled={!question.trim() || isThinking || isStreaming}
                  className="p-2.5 rounded-xl bg-[#6366F1] hover:bg-[#4F46E5] text-white transition-all shadow-lg shadow-[#6366F1]/20 disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed group/btn"
                >
                  <Send className="w-5 h-5 group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
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
            className="w-full flex items-center justify-between px-6 py-5 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-[#6366F1]/10">
                <Filter className="w-4 h-4 text-[#6366F1]" />
              </div>
              <div>
                <span className="block text-sm font-semibold text-gray-900 dark:text-[#F8FAFC]">Source Filter</span>
                <span className="text-[10px] text-gray-500">
                  {selectedSourceIds.size > 0 ? `${selectedSourceIds.size} Selected` : 'Searching all'}
                </span>
              </div>
            </div>
            {showSourceFilter ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
          </button>

          {showSourceFilter && (
            <div className="px-6 pb-6 space-y-1 max-h-[40vh] overflow-y-auto animate-in fade-in slide-in-from-top-2 duration-200">
              {sourcesLoading && (
                <div className="flex items-center gap-3 text-sm text-gray-400 py-4 justify-center">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Scanning...</span>
                </div>
              )}

              {!sourcesLoading && sources.length === 0 && (
                <p className="text-xs text-gray-400 py-4 text-center">No sources available.</p>
              )}

              {!sourcesLoading && sources.length > 0 && (
                <>
                  <button
                    onClick={toggleAll}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white dark:hover:bg-gray-800 transition-all text-left mb-2 border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
                  >
                    {selectedSourceIds.size === sources.length ? (
                      <CheckSquare className="w-4 h-4 text-[#6366F1]" />
                    ) : (
                      <Square className="w-4 h-4 text-gray-400" />
                    )}
                    <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                      {selectedSourceIds.size === sources.length ? 'Deselect All' : 'Select All'}
                    </span>
                  </button>

                  <div className="space-y-1">
                    {sources.map(source => {
                      const Icon = sourceIcon(source.type);
                      const isSelected = selectedSourceIds.has(source.id);
                      return (
                        <button
                          key={source.id}
                          onClick={() => toggleSource(source.id)}
                          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all border ${isSelected
                              ? 'bg-white dark:bg-[#1E293B] border-[#6366F1] shadow-sm'
                              : 'bg-transparent border-transparent hover:bg-white dark:hover:bg-gray-800 hover:border-gray-200 dark:hover:border-gray-700'
                            }`}
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-[#6366F1]" />
                          ) : (
                            <Square className="w-4 h-4 text-gray-400" />
                          )}
                          <div className={`p-1.5 rounded-lg ${isSelected ? 'bg-[#6366F1]/10 text-[#6366F1]' : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}`}>
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                          <span className={`text-xs truncate flex-1 ${isSelected ? 'font-medium text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'}`}>
                            {source.title}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Retrieved Context */}
        <div className="px-6 py-5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1E293B]/30">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 dark:text-[#F8FAFC]">Retrieved Context</h2>
            <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-[10px] font-medium text-gray-600 dark:text-gray-400">
              {selectedChunks.length} Chunks
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {selectedChunks.length === 0 && (
            <div className="flex flex-col items-center justify-center h-40 text-center">
              <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-3">
                <FileText className="w-5 h-5 text-gray-400" />
              </div>
              <p className="text-[11px] text-gray-400 max-w-[150px]">
                Ask questions to see the relevant knowledge chunks here.
              </p>
            </div>
          )}
          {selectedChunks.map((chunk) => {
            const Icon = sourceIcon(chunk.sourceType);
            return (
              <div
                key={chunk.id}
                className="p-5 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] transition-all shadow-sm flex flex-col gap-3 group"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 rounded bg-gray-50 dark:bg-gray-800">
                      <Icon className="w-3.5 h-3.5 text-gray-600 dark:text-gray-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-gray-900 dark:text-gray-100 truncate">
                      {chunk.sourceName}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <div className="flex items-center gap-1">
                      <div className="w-12 h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#6366F1]"
                          style={{ width: `${chunk.similarityScore * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-bold text-[#6366F1]">
                        {(chunk.similarityScore * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>

                <p className="text-[11px] text-gray-700 dark:text-gray-300 leading-relaxed line-clamp-6">
                  {chunk.text}
                </p>

                <div className="pt-2 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
                  <span className="text-[9px] font-medium text-gray-400 uppercase tracking-tighter">
                    {chunk.metadata?.page ? `Page ${chunk.metadata.page}` : chunk.metadata?.timestamp ? `@ ${chunk.metadata.timestamp}` : 'Source Segment'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
