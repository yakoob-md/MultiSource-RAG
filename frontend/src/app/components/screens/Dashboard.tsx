import { useEffect, useState } from 'react';
import { FileText, Globe, Youtube, Database, Languages, Activity, BarChart3, ChevronRight } from 'lucide-react';
import { KnowledgeSource } from '../../types';
import { fetchSources, fetchPendingImageCount } from '../../api';
import { ImageIcon } from 'lucide-react';
import { useNavigate } from 'react-router';

export function Dashboard() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingImages, setPendingImages] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchSources()
      .then((data) => {
        if (!cancelled) {
          setSources(data);
        }
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load sources.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    fetchPendingImageCount()
      .then(count => {
        if (!cancelled) setPendingImages(count);
      })
      .catch(() => { });

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = {
    totalSources: sources.length,
    pdfs: sources.filter(s => s.type === 'pdf').length,
    webPages: sources.filter(s => s.type === 'web').length,
    videos: sources.filter(s => s.type === 'youtube').length,
    languages: new Set(sources.map(s => s.language)).size,
    totalChunks: sources.reduce((sum, s) => sum + (s.chunkCount || 0), 0),
  };

  const recentActivity = [...sources]
    .sort((a, b) => b.dateAdded.getTime() - a.dateAdded.getTime())
    .slice(0, 5);

  const languageDistribution = [
    { lang: 'EN', count: sources.filter(s => s.language === 'EN').length, color: 'bg-blue-500' },
    { lang: 'HI', count: sources.filter(s => s.language === 'HI').length, color: 'bg-orange-500' },
    { lang: 'TE', count: sources.filter(s => s.language === 'TE').length, color: 'bg-purple-500' },
  ].filter(l => l.count > 0);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-gray-900 dark:text-[#F8FAFC] mb-2">Dashboard</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Monitor your knowledge base and system performance
          </p>
          {isLoading && (
            <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
              Loading statistics...
            </p>
          )}
          {error && (
            <p className="text-xs text-red-500 mt-2">
              {error}
            </p>
          )}
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {/* Total Sources */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-blue-500/10">
                <Database className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.totalSources}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Sources</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Across all types
            </p>
          </div>

          {/* PDF Documents */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-purple-500/10">
                <FileText className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.pdfs}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">PDF Documents</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Research papers & docs
            </p>
          </div>

          {/* Web Pages */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-green-500/10">
                <Globe className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.webPages}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">Web Pages</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Indexed websites
            </p>
          </div>

          {/* YouTube Videos */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-red-500/10">
                <Youtube className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.videos}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">YouTube Videos</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Transcribed content
            </p>
          </div>

          {/* Languages */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-orange-500/10">
                <Languages className="w-6 h-6 text-orange-600 dark:text-orange-400" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.languages}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">Languages</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Detected languages
            </p>
          </div>

          {/* Total Chunks */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-[#6366F1]/10">
                <Activity className="w-6 h-6 text-[#6366F1]" />
              </div>
              <span className="text-2xl text-gray-900 dark:text-[#F8FAFC]">
                {stats.totalChunks}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Chunks</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Stored embeddings
            </p>
          </div>

          {/* Vision Queue */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-indigo-500/10">
                <ImageIcon className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              </div>
              <span className={`text-2xl font-bold ${pendingImages > 0 ? 'text-amber-500' : 'text-gray-900 dark:text-[#F8FAFC]'}`}>
                {pendingImages}
              </span>
            </div>
            <h3 className="text-sm text-gray-600 dark:text-gray-400 mb-1">Vision Queue</h3>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              {pendingImages === 0 ? 'All images processed' : 'Pending LLaVA analysis'}
            </p>
          </div>

          {/* System Audit */}
          <div 
            onClick={() => navigate('/app/evaluate')}
            className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:border-[#6366F1]/50 hover:shadow-xl transition-all cursor-pointer group"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 rounded-xl bg-[#6366F1]/10 group-hover:bg-[#6366F1]/20 transition-all">
                <BarChart3 className="w-6 h-6 text-[#6366F1]" />
              </div>
              <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-[#6366F1] transition-all" />
            </div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-[#F8FAFC] mb-1">System Audit</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Run RAGAS performance benchmarks
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Language Distribution */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-6">Language Distribution</h3>
            <div className="space-y-4">
              {languageDistribution.map(({ lang, count, color }) => (
                <div key={lang}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-700 dark:text-gray-300">{lang}</span>
                    <span className="text-sm text-gray-600 dark:text-gray-400">{count} sources</span>
                  </div>
                  <div className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${color} transition-all duration-500`}
                      style={{ width: `${(count / stats.totalSources) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-6">Recent Activity</h3>
            <div className="space-y-4">
              {recentActivity.map((source) => {
                const Icon = source.type === 'pdf' ? FileText : source.type === 'web' ? Globe : Youtube;
                return (
                  <div key={source.id} className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800">
                      <Icon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 dark:text-gray-100 truncate">{source.title}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Added {source.dateAdded.toLocaleDateString()}
                      </p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${
                      source.language === 'EN' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' :
                      source.language === 'HI' ? 'bg-orange-500/10 text-orange-600 dark:text-orange-400' :
                      'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                    }`}>
                      {source.language}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
