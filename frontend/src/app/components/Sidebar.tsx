import { Link, useLocation } from 'react-router';
import {
  LayoutDashboard, MessageSquare, Database, FileText,
  Globe, Youtube, History, Settings as SettingsIcon, Plus, Sun, Moon,
  Gavel, Image as ImageIcon
} from 'lucide-react';
import { useTheme } from './ThemeProvider';
import { SourceCard } from './SourceCard';
import { useEffect, useState } from 'react';
import { KnowledgeSource } from '../types';
import { fetchSources } from '../api';

const navigation = [
  { name: 'Dashboard', path: '/app', icon: LayoutDashboard },
  { name: 'Ask AI', path: '/app/ask', icon: MessageSquare },
  { name: 'Legal AI', path: '/app/legal', icon: Gavel },
  { name: 'Vision / Image', path: '/app/upload-image', icon: ImageIcon },
  { name: 'Knowledge Sources', path: '/app/sources', icon: Database },
  { name: 'Upload PDF', path: '/app/upload-pdf', icon: FileText },
  { name: 'Add Website', path: '/app/add-website', icon: Globe },
  { name: 'Add YouTube', path: '/app/add-youtube', icon: Youtube },
  { name: 'Query History', path: '/app/history', icon: History },
  { name: 'Settings', path: '/app/settings', icon: SettingsIcon },
];

export function Sidebar() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);

  // ── Load sources + refresh when any upload completes ─────────────────────
  const loadSources = () => {
    fetchSources()
      .then(setSources)
      .catch(() => { });
  };

  useEffect(() => {
    loadSources();

    // Listen for the custom event fired by notifySidebarRefresh() in api.ts
    window.addEventListener('sources-updated', loadSources);
    return () => window.removeEventListener('sources-updated', loadSources);
  }, []);

  const pdfSources = sources.filter(s => s.type === 'pdf');
  const webSources = sources.filter(s => s.type === 'web');
  const youtubeSources = sources.filter(s => s.type === 'youtube');

  return (
    <div className="w-80 h-full bg-white dark:bg-[#1E293B] border-r border-gray-200 dark:border-gray-800 flex flex-col transition-colors">

      {/* Header */}
      <div className="p-6 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#4F46E5] flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-gray-900 dark:text-[#F8FAFC] tracking-tight font-black">InteleX</h1>
              <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider font-bold">Intelligence</p>
            </div>
          </div>
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {theme === 'light'
              ? <Moon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              : <Sun className="w-4 h-4 text-gray-400" />}
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3 py-4 space-y-1 border-b border-gray-200 dark:border-gray-800">
        {navigation.map((item) => {
          const isActive = item.path === '/app'
            ? location.pathname === '/app' || location.pathname === '/app/'
            : location.pathname.startsWith(item.path);

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${isActive
                  ? 'bg-[#6366F1] text-white shadow-sm'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Sources Preview */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-4">
          {pdfSources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 px-2 mb-2">
                <FileText className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                <h3 className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  PDF Documents ({pdfSources.length})
                </h3>
              </div>
              <div className="space-y-2">
                {pdfSources.slice(0, 2).map(source => (
                  <SourceCard key={source.id} source={source} compact />
                ))}
              </div>
            </div>
          )}

          {webSources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 px-2 mb-2">
                <Globe className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                <h3 className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Web Pages ({webSources.length})
                </h3>
              </div>
              <div className="space-y-2">
                {webSources.slice(0, 2).map(source => (
                  <SourceCard key={source.id} source={source} compact />
                ))}
              </div>
            </div>
          )}

          {youtubeSources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 px-2 mb-2">
                <Youtube className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                <h3 className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  YouTube Videos ({youtubeSources.length})
                </h3>
              </div>
              <div className="space-y-2">
                {youtubeSources.slice(0, 2).map(source => (
                  <SourceCard key={source.id} source={source} compact />
                ))}
              </div>
            </div>
          )}

          {sources.length === 0 && (
            <p className="text-xs text-gray-400 text-center px-2 py-4">
              No sources yet. Upload a PDF, website, or YouTube video.
            </p>
          )}
        </div>
      </div>

      {/* New Source Button */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        <Link
          to="/app/sources"
          className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">New Source</span>
        </Link>
      </div>
    </div>
  );
}
