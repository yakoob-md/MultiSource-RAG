import { useState } from 'react';
import { Youtube, CheckCircle, Loader2, Eye, Database, Clock, FileText } from 'lucide-react';
import { addYouTube, notifySidebarRefresh } from '../../api';
import type { Language, KnowledgeSource } from '../../types';

interface VideoPreview {
  url: string;
  videoId: string;
  title: string;
  channel: string;
  duration: string;
  thumbnail: string;
  transcriptAvailable: boolean;
  status: 'fetching' | 'ready' | 'processing' | 'completed';
  result?: KnowledgeSource;
}

export function AddYouTube() {
  const [url, setUrl] = useState('');
  const [preview, setPreview] = useState<VideoPreview | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetchPreview = async () => {
    if (!url.trim()) return;
    setError(null);
    setIsLoading(true);
    try {
      const urlObj = new URL(url);
      const videoId =
        urlObj.searchParams.get('v') ||
        (urlObj.hostname === 'youtu.be' ? urlObj.pathname.slice(1) : '') ||
        urlObj.pathname.split('/').pop() ||
        '';

      if (!videoId) throw new Error('Could not extract a video ID from this URL. Please paste a valid YouTube link.');

      setPreview({
        url,
        videoId,
        title: 'YouTube Video',
        channel: urlObj.hostname,
        duration: '--:--',
        thumbnail: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
        transcriptAvailable: true,
        status: 'ready',
      });
    } catch (err: any) {
      setError(err?.message || 'Please enter a valid YouTube URL.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngest = async (language: Language = 'EN') => {
    if (!preview) return;
    setPreview({ ...preview, status: 'processing' });
    setError(null);
    try {
      const result = await addYouTube(preview.url, language);
      setPreview(prev => prev ? { ...prev, status: 'completed', result, title: result.title } : null);
      // ✅ Notify sidebar to refresh source list
      notifySidebarRefresh();
    } catch (err: any) {
      const msg = err?.message || 'Failed to ingest YouTube video.';
      setError(msg);
      setPreview(prev => prev ? { ...prev, status: 'ready' } : null);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-gray-900 dark:text-[#F8FAFC] mb-2">Add YouTube Video</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Add YouTube video transcripts to your knowledge base
          </p>
        </div>

        {/* URL Input */}
        <div className="mb-8">
          <label className="block text-sm text-gray-700 dark:text-gray-300 mb-3">YouTube URL</label>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Youtube className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-red-500" />
              <input
                type="url"
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleFetchPreview()}
                className="w-full pl-12 pr-4 py-3 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-[#F8FAFC] placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#6366F1] focus:border-transparent"
              />
            </div>
            <button
              onClick={handleFetchPreview}
              disabled={!url.trim() || isLoading}
              className="px-6 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isLoading
                ? <><Loader2 className="w-5 h-5 animate-spin" /><span>Fetching...</span></>
                : <><Eye className="w-5 h-5" /><span>Preview</span></>}
            </button>
          </div>
        </div>

        {/* Video Preview */}
        {preview && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
              <div className="flex gap-6 mb-4">
                <div className="w-48 h-28 rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-800 flex-shrink-0 relative">
                  <img
                    src={preview.thumbnail}
                    alt={preview.title}
                    className="w-full h-full object-cover"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                    <Youtube className="w-12 h-12 text-white opacity-80" />
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <h2 className="text-xl text-gray-900 dark:text-[#F8FAFC] mb-2">
                    {preview.result?.title || preview.title}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Video ID: {preview.videoId}</p>
                  <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-4 h-4" /><span>{preview.duration}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <FileText className="w-4 h-4" />
                      {preview.transcriptAvailable
                        ? <span className="text-green-600 dark:text-green-400">Transcript available</span>
                        : <span className="text-red-600 dark:text-red-400">No transcript</span>}
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1 mr-4">
                    {preview.url}
                  </div>
                  {preview.status === 'ready' && preview.transcriptAvailable && (
                    <button
                      onClick={() => handleIngest('EN')}
                      className="px-4 py-2 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-lg text-sm transition-colors flex items-center gap-2"
                    >
                      <Database className="w-4 h-4" /><span>Ingest Transcript</span>
                    </button>
                  )}
                  {preview.status === 'processing' && (
                    <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                      <Loader2 className="w-4 h-4 animate-spin" /><span>Processing transcript...</span>
                    </div>
                  )}
                  {preview.status === 'completed' && (
                    <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                      <CheckCircle className="w-4 h-4" /><span>Successfully added!</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {(preview.status === 'processing' || preview.status === 'completed') && (
              <div className="p-6 rounded-2xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700">
                <h3 className="text-lg text-gray-900 dark:text-[#F8FAFC] mb-4">Processing Details</h3>
                <div className="space-y-3">
                  <ProcessingStep label="Fetching transcript" completed={true} />
                  <ProcessingStep label="Parsing timestamps" completed={preview.status === 'completed'} active={preview.status === 'processing'} />
                  <ProcessingStep label="Creating embeddings" completed={preview.status === 'completed'} />
                  <ProcessingStep label="Storing in vector database" completed={preview.status === 'completed'} />
                </div>

                {preview.status === 'completed' && preview.result && (
                  <div className="mt-6 p-4 rounded-xl bg-green-500/10 border border-green-500/20">
                    <div className="flex items-start gap-3">
                      <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm text-green-900 dark:text-green-100 mb-1">
                          Video transcript successfully ingested
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
          <div className="p-6 rounded-2xl bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
            <h3 className="text-sm text-gray-900 dark:text-[#F8FAFC] mb-3">How it works</h3>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Enter a YouTube video URL to extract its transcript</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Videos with English, Hindi, or Telugu captions are supported</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Click "Ingest" to process the transcript and add it to your knowledge base</span></li>
              <li className="flex items-start gap-2"><span className="text-[#6366F1] mt-1">•</span><span>Timestamps are preserved for accurate source citations</span></li>
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
