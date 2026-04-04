import { FileText, Globe, Youtube, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { KnowledgeSource } from '../types';

interface SourceCardProps {
  source: KnowledgeSource;
  compact?: boolean;
}

const languageColors = {
  EN: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  HI: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
  TE: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  ES: 'bg-green-500/10 text-green-600 dark:text-green-400',
  FR: 'bg-pink-500/10 text-pink-600 dark:text-pink-400',
  DE: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
};

const statusIcons = {
  pending: Loader2,
  processing: Loader2,
  completed: CheckCircle,
  failed: AlertCircle,
};

const statusColors = {
  pending: 'text-gray-400',
  processing: 'text-blue-500 animate-spin',
  completed: 'text-green-500',
  failed: 'text-red-500',
};

export function SourceCard({ source, compact = false }: SourceCardProps) {
  const Icon = source.type === 'pdf' ? FileText : source.type === 'web' ? Globe : Youtube;
  const StatusIcon = statusIcons[source.status];

  if (compact) {
    return (
      <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] dark:hover:border-[#6366F1] transition-colors group cursor-pointer">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 group-hover:border-[#6366F1] transition-colors">
            <Icon className="w-3.5 h-3.5 text-gray-600 dark:text-gray-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-1">
              <h4 className="text-xs text-gray-900 dark:text-gray-100 truncate">
                {source.title}
              </h4>
              <StatusIcon className={`w-3 h-3 flex-shrink-0 ${statusColors[source.status]}`} />
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`px-1.5 py-0.5 rounded text-[10px] ${languageColors[source.language]}`}>
                {source.language}
              </span>
              {source.chunkCount !== undefined && source.chunkCount > 0 && (
                <span className="text-[10px] text-gray-500 dark:text-gray-400">
                  {source.chunkCount} chunks
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700 hover:border-[#6366F1] dark:hover:border-[#6366F1] hover:shadow-lg transition-all group cursor-pointer">
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 group-hover:border-[#6366F1] transition-colors">
          <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 mb-2">
            <h3 className="text-gray-900 dark:text-[#F8FAFC] truncate">
              {source.title}
            </h3>
            <StatusIcon className={`w-4 h-4 flex-shrink-0 ${statusColors[source.status]}`} />
          </div>
          
          <div className="flex items-center gap-2 mb-3">
            <span className={`px-2 py-1 rounded-md text-xs ${languageColors[source.language]}`}>
              {source.language}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">
              {source.status}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            {source.chunkCount !== undefined && source.chunkCount > 0 && (
              <span>{source.chunkCount} chunks</span>
            )}
            {source.metadata?.pageCount && (
              <span>{source.metadata.pageCount} pages</span>
            )}
            {source.metadata?.domain && (
              <span className="truncate">{source.metadata.domain}</span>
            )}
            {source.metadata?.duration && (
              <span>{source.metadata.duration}</span>
            )}
          </div>

          {source.lastProcessed && (
            <div className="text-xs text-gray-400 dark:text-gray-500 mt-2">
              Processed {source.lastProcessed.toLocaleDateString()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
