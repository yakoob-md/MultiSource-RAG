import { useState } from 'react';
import { Globe, Link as LinkIcon, CheckCircle, Loader2, Eye, Database } from 'lucide-react';
import { addWebsite, notifySidebarRefresh } from '../../api';
import type { Language, KnowledgeSource } from '../../types';

interface WebsitePreview {
  url: string;
  title: string;
  domain: string;
  description?: string;
  status: 'fetching' | 'ready' | 'processing' | 'completed';
  result?: KnowledgeSource;
}

export function AddWebsite() {
  const [url, setUrl] = useState('');
  const [preview, setPreview] = useState<WebsitePreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetchPreview = async () => {
    if (!url.trim()) return;
    setError(null);
    setIsLoading(true);
    try {
      const parsed = new URL(url);
      const domain = parsed.hostname;
      setPreview({
        url,
        title: url,
        domain,
        description: 'Click "Ingest to Knowledge Base" to fetch and process the content from this URL.',
        status: 'ready',
      });
    } catch {
      setError('Please enter a valid URL (including https://).');
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngest = async (language: Language = 'EN') => {
    if (!preview) return;
    setPreview({ ...preview, status: 'processing' });
    setError(null);
    try {
      const result = await addWebsite(preview.url, language);
      setPreview(prev => prev ? { ...prev, status: 'completed', result, title: result.title } : null);
      // ✅ Notify sidebar to refresh source list
      notifySidebarRefresh();
    } catch (err: any) {
      const msg = err?.message || 'Failed to ingest website.';
      setError(msg);
      setPreview(prev => prev ? { ...prev, status: 'ready' } : null);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-white mb-2">Add Website</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Add web pages to your knowledge base
          </p>
        </div>

        {/* URL Input */}
        <div className="mb-8">
          <label className="block text-sm text-gray-700 dark:text-gray-300 mb-3">
            Website URL
          </label>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <LinkIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="url"
                placeholder="https://example.com/article"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleFetchPreview()}
                className="w-full pl-12 pr-4 py-3 rounded-xl bg-white/5 backdrop-blur-md border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
              />
            </div>
            <button
              onClick={handleFetchPreview}
              disabled={!url.trim() || isLoading}
              className="px-6 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isLoading ? (
                <><Loader2 className="w-5 h-5 animate-spin" /><span>Fetching...</span></>
              ) : (
                <><Eye className="w-5 h-5" /><span>Preview</span></>
              )}
            </button>
          </div>
        </div>

        {/* Website Preview */}
        {preview && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10">
              <div className="flex items-start gap-4 mb-4">
                <div className="p-3 rounded-xl bg-green-500/10">
                  <Globe className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl text-white mb-1">
                    {preview.result?.title || preview.title}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{preview.domain}</p>
                </div>
              </div>

              {preview.description && (
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                  {preview.description}
                </p>
              )}

              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1 mr-4">
                    {preview.url}
                  </div>
                  {preview.status === 'ready' && (
                    <button
                      onClick={() => handleIngest('EN')}
                      className="px-4 py-2 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-lg text-sm transition-colors flex items-center gap-2"
                    >
                      <Database className="w-4 h-4" />
                      <span>Ingest to Knowledge Base</span>
                    </button>
                  )}
                  {preview.status === 'processing' && (
                    <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Processing...</span>
                    </div>
                  )}
                  {preview.status === 'completed' && (
                    <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                      <CheckCircle className="w-4 h-4" />
                      <span>Successfully added!</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {(preview.status === 'processing' || preview.status === 'completed') && (
              <div className="p-6 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-4">Processing Details</h3>
                <div className="space-y-3">
                  <ProcessingStep label="Fetching content" completed={true} />
                  <ProcessingStep label="Extracting text" completed={preview.status === 'completed'} active={preview.status === 'processing'} />
                  <ProcessingStep label="Creating embeddings" completed={preview.status === 'completed'} />
                  <ProcessingStep label="Storing in vector database" completed={preview.status === 'completed'} />
                </div>

                {preview.status === 'completed' && preview.result && (
                  <div className="mt-6 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
                    <div className="flex items-start gap-3">
                      <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm text-green-900 dark:text-green-100 mb-1">
                          Website successfully ingested: <strong>{preview.result.title}</strong>
                        </p>
                        <p className="text-xs text-green-700 dark:text-green-300">
                          {preview.result.chunkCount} chunks created • Language: {preview.result.language} • Ready for querying
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {!preview && !isLoading && (
          <div className="p-6 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10">
            <h3 className="text-sm text-gray-900 dark:text-[#F8FAFC] mb-3">How it works</h3>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Enter the URL of a web page you want to add to your knowledge base</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Click "Preview" then "Ingest" to process and add it</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Most public websites work — Wikipedia, news articles, documentation, etc.</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>The content will be chunked and embedded for semantic search</span></li>
            </ul>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

function ProcessingStep({ label, completed, active }: { label: string; completed?: boolean; active?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-5 h-5 rounded-full flex items-center justify-center ${completed ? 'bg-green-500' : active ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-700'
        }`}>
        {completed ? <CheckCircle className="w-3 h-3 text-white" /> : active ? <Loader2 className="w-3 h-3 text-white animate-spin" /> : null}
      </div>
      <span className={`text-sm ${completed ? 'text-gray-900 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
        {label}
      </span>
    </div>
  );
}
