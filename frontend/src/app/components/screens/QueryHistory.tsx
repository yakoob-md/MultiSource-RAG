import { Search, MessageSquare, Calendar, FileText, Globe, Youtube, ChevronRight, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { fetchHistory, BackendChatEntry } from '../../api';
import { loadChatHistory } from '../../data/history';
import type { ChatMessage } from '../../types';

export function QueryHistory() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Backend history entries (permanent, from MySQL)
  const [backendHistory, setBackendHistory] = useState<BackendChatEntry[]>([]);

  // Local history entries (from localStorage — fallback)
  const [localHistory, setLocalHistory] = useState<ChatMessage[]>([]);

  // ── Load backend history on mount ──────────────────────────────────────────
  useEffect(() => {
    setIsLoading(true);
    fetchHistory()
      .then(setBackendHistory)
      .catch(() => {
        // Backend unavailable — fall back to localStorage silently
        setLocalHistory(loadChatHistory());
      })
      .finally(() => setIsLoading(false));
  }, []);

  // ── Use backend history if available, else localStorage ───────────────────
  const useBackend = backendHistory.length > 0;

  const filteredBackend = backendHistory.filter(entry =>
    entry.question.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // For localStorage fallback
  const userMessages = localHistory.filter(m => m.role === 'user');
  const filteredLocal = userMessages.filter(q =>
    q.content.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const getLocalResponse = (queryId: string) => {
    const idx = localHistory.findIndex(m => m.id === queryId);
    return localHistory[idx + 1];
  };

  const sourceIcon = (type: string) =>
    type === 'pdf' ? FileText : type === 'web' || type === 'url' ? Globe : Youtube;

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto p-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-white mb-2">Query History</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Review your past questions and AI responses
          </p>
          {useBackend && (
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">
              ✓ Loaded from database — history persists across sessions
            </p>
          )}
        </div>

        {/* Search */}
        <div className="mb-8">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search queries..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 rounded-xl bg-white/5 backdrop-blur-md border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
            />
          </div>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading history...
          </div>
        )}

        {/* ── Backend History ───────────────────────────────────────────────── */}
        {useBackend && (
          <div className="space-y-4">
            {filteredBackend.map((entry) => {
              const isExpanded = selectedId === entry.id;
              const date = new Date(entry.createdAt);

              return (
                <div
                  key={entry.id}
                  className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden hover:shadow-lg transition-all"
                >
                  <button
                    onClick={() => setSelectedId(isExpanded ? null : entry.id)}
                    className="w-full p-6 text-left hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-start gap-4">
                      <div className="p-3 rounded-xl bg-[#6366F1]/10">
                        <MessageSquare className="w-5 h-5 text-[#6366F1]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white mb-2">
                          {entry.question}
                        </p>
                        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="w-4 h-4" />
                            <span>{date.toLocaleDateString()}</span>
                          </div>
                          <span>{date.toLocaleTimeString()}</span>
                          {entry.sourcesUsed?.length > 0 && (
                            <span>{entry.sourcesUsed.length} sources</span>
                          )}
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                      />
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-white/10 p-6 bg-white/5">
                      <h3 className="text-sm text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-3">
                        AI Response
                      </h3>
                      <p className="text-sm text-white/80 leading-relaxed whitespace-pre-line">
                        {entry.answer}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}

            {filteredBackend.length === 0 && !isLoading && (
              <div className="text-center py-16">
                <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400">
                  {searchQuery ? 'No queries found matching your search' : 'No query history yet'}
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── localStorage Fallback ─────────────────────────────────────────── */}
        {!useBackend && !isLoading && (
          <div className="space-y-4">
            {filteredLocal.map((query) => {
              const response = getLocalResponse(query.id);
              const isExpanded = selectedId === query.id;

              return (
                <div
                  key={query.id}
                  className="rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-lg transition-all"
                >
                  <button
                    onClick={() => setSelectedId(isExpanded ? null : query.id)}
                    className="w-full p-6 text-left hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-start gap-4">
                      <div className="p-3 rounded-xl bg-[#6366F1]/10">
                        <MessageSquare className="w-5 h-5 text-[#6366F1]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-gray-900 dark:text-[#F8FAFC] mb-2">{query.content}</p>
                        <div className="flex items-center gap-4 text-sm text-gray-500">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="w-4 h-4" />
                            <span>{query.timestamp.toLocaleDateString()}</span>
                          </div>
                          <span>{query.timestamp.toLocaleTimeString()}</span>
                          {response?.citations && (
                            <span>{response.citations.length} sources</span>
                          )}
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                      />
                    </div>
                  </button>

                  {isExpanded && response && (
                    <div className="border-t border-white/10 p-6 bg-white/5">
                      <h3 className="text-sm text-gray-600 dark:text-gray-400 uppercase tracking-wider mb-3">
                        AI Response
                      </h3>
                      <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-line mb-4">
                        {response.content}
                      </p>
                      {response.citations && response.citations.length > 0 && (
                        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-3">Sources</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {response.citations.map((citation, idx) => {
                              const Icon = sourceIcon(citation.sourceType);
                              return (
                                <div key={idx} className="p-4 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
                                  <div className="flex items-start gap-3">
                                    <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
                                      <Icon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-sm text-gray-900 dark:text-gray-100 truncate">{citation.sourceTitle}</span>
                                        <span className="text-xs text-[#6366F1] shrink-0">{citation.reference}</span>
                                      </div>
                                      <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">{citation.snippet}</p>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {filteredLocal.length === 0 && (
              <div className="text-center py-16">
                <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 dark:text-gray-400">
                  {searchQuery ? 'No queries found matching your search' : 'No query history yet'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
