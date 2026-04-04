import { useEffect, useState, useCallback } from 'react';
import { Search, Filter, FileText, Globe, Youtube, MoreVertical, Trash2, RefreshCw, Eye, Loader2, AlertCircle } from 'lucide-react';
import { SourceCard } from '../SourceCard';
import { SourceType, Language, KnowledgeSource } from '../../types';
import { fetchSources, deleteSource } from '../../api';

export function KnowledgeSources() {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<SourceType | 'all'>('all');
  const [filterLanguage, setFilterLanguage] = useState<Language | 'all'>('all');
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSources = useCallback(() => {
    setIsLoading(true);
    setError(null);
    fetchSources()
      .then((data) => setSources(data))
      .catch((err: any) => setError(err?.message || 'Failed to load sources.'))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const handleDelete = async (sourceId: string) => {
    try {
      await deleteSource(sourceId);
      setSources(prev => prev.filter(s => s.id !== sourceId));
    } catch (err: any) {
      setError(err?.message || 'Failed to delete source.');
    }
  };

  const filteredSources = sources.filter(source => {
    const matchesSearch = source.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || source.type === filterType;
    const matchesLanguage = filterLanguage === 'all' || source.language === filterLanguage;
    return matchesSearch && matchesType && matchesLanguage;
  });

  const groupedSources = {
    pdf: filteredSources.filter(s => s.type === 'pdf'),
    web: filteredSources.filter(s => s.type === 'web'),
    youtube: filteredSources.filter(s => s.type === 'youtube'),
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-3xl text-gray-900 dark:text-[#F8FAFC] mb-2">Knowledge Sources</h1>
            <p className="text-gray-600 dark:text-gray-400">
              Manage and organize your ingested sources
            </p>
          </div>
          <button
            onClick={loadSources}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300 hover:border-[#6366F1] transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Search and Filters */}
        <div className="mb-8 flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search sources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
            />
          </div>

          <div className="flex gap-3">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as SourceType | 'all')}
              className="px-4 py-3 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
            >
              <option value="all">All Types</option>
              <option value="pdf">PDF</option>
              <option value="web">Web</option>
              <option value="youtube">YouTube</option>
            </select>

            <select
              value={filterLanguage}
              onChange={(e) => setFilterLanguage(e.target.value as Language | 'all')}
              className="px-4 py-3 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
            >
              <option value="all">All Languages</option>
              <option value="EN">English</option>
              <option value="HI">Hindi</option>
              <option value="TE">Telugu</option>
            </select>
          </div>
        </div>

        {/* Feedback */}
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 mb-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading sources...
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-700 dark:text-red-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Sources by Type */}
        <div className="space-y-8">
          {groupedSources.pdf.length > 0 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                <h2 className="text-xl text-gray-900 dark:text-[#F8FAFC]">PDF Documents</h2>
                <span className="px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm text-gray-600 dark:text-gray-400">
                  {groupedSources.pdf.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {groupedSources.pdf.map(source => (
                  <div key={source.id} className="relative group">
                    <SourceCard source={source} />
                    <SourceActions sourceId={source.id} onDelete={handleDelete} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {groupedSources.web.length > 0 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <Globe className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                <h2 className="text-xl text-gray-900 dark:text-[#F8FAFC]">Web Pages</h2>
                <span className="px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm text-gray-600 dark:text-gray-400">
                  {groupedSources.web.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {groupedSources.web.map(source => (
                  <div key={source.id} className="relative group">
                    <SourceCard source={source} />
                    <SourceActions sourceId={source.id} onDelete={handleDelete} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {groupedSources.youtube.length > 0 && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <Youtube className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                <h2 className="text-xl text-gray-900 dark:text-[#F8FAFC]">YouTube Videos</h2>
                <span className="px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm text-gray-600 dark:text-gray-400">
                  {groupedSources.youtube.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {groupedSources.youtube.map(source => (
                  <div key={source.id} className="relative group">
                    <SourceCard source={source} />
                    <SourceActions sourceId={source.id} onDelete={handleDelete} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {filteredSources.length === 0 && !isLoading && (
            <div className="text-center py-16">
              <Filter className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 dark:text-gray-400">
                {sources.length === 0
                  ? 'No sources ingested yet. Upload a PDF, add a website, or ingest a YouTube video to get started.'
                  : 'No sources found matching your filters.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceActions({ sourceId, onDelete }: { sourceId: string; onDelete: (id: string) => Promise<void> }) {
  const [showMenu, setShowMenu] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this source? All associated chunks will be removed.')) return;
    setShowMenu(false);
    setIsDeleting(true);
    try {
      await onDelete(sourceId);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="absolute top-5 right-5">
      {isDeleting ? (
        <div className="p-2 rounded-lg bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
          <Loader2 className="w-4 h-4 text-gray-600 dark:text-gray-400 animate-spin" />
        </div>
      ) : (
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-2 rounded-lg bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 opacity-0 group-hover:opacity-100 transition-opacity hover:border-[#6366F1]"
        >
          <MoreVertical className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        </button>
      )}

      {showMenu && !isDeleting && (
        <>
          {/* Backdrop to close menu */}
          <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 mt-2 w-48 py-2 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 shadow-xl z-20">
            <button
              onClick={handleDelete}
              className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-3"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}
