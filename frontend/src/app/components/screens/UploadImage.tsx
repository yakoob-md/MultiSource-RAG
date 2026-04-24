import React, { useState, useCallback } from 'react';
import { Upload, Image as ImageIcon, CheckCircle, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import { uploadImage, notifySidebarRefresh } from '../../api';

export const UploadImage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [context, setContext] = useState('');
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [result, setResult] = useState<{ image_id: string } | null>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('idle');
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setStatus('uploading');
    try {
      const res = await uploadImage(file, context);
      setResult(res);
      setStatus('success');
      notifySidebarRefresh();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload image');
      setStatus('error');
    }
  };

  const reset = () => {
    setFile(null);
    setContext('');
    setStatus('idle');
    setResult(null);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-white">Visual Intelligence</h1>
        <p className="text-zinc-400">Upload images or charts to be processed by our Vision model (LLaVA).</p>
      </div>

      <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 backdrop-blur-sm">
        {status === 'success' ? (
          <div className="flex flex-col items-center justify-center py-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-emerald-500" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-white">Image Queued Successfully</h2>
              <p className="text-zinc-400 max-w-sm">
                Your image "{file?.name}" has been added to the processing queue. 
                Run the vision captioner to generate descriptions.
              </p>
            </div>
            <div className="pt-4 flex gap-4">
              <button
                onClick={reset}
                className="px-6 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-medium transition-all"
              >
                Upload Another
              </button>
              <button
                onClick={() => window.location.hash = '#/sources'}
                className="px-6 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all flex items-center gap-2"
              >
                View Jobs <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="space-y-4">
              <label className="block text-sm font-medium text-zinc-300">Image File</label>
              <div 
                className={`relative border-2 border-dashed rounded-xl p-12 transition-all flex flex-col items-center justify-center gap-4 ${
                  file ? 'border-blue-500/50 bg-blue-500/5' : 'border-zinc-800 hover:border-zinc-700 bg-zinc-900/50'
                }`}
              >
                <input
                  type="file"
                  onChange={onFileChange}
                  accept="image/*"
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                {file ? (
                  <>
                    <ImageIcon className="w-12 h-12 text-blue-400" />
                    <div className="text-center">
                      <p className="text-white font-medium">{file.name}</p>
                      <p className="text-xs text-zinc-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center">
                      <Upload className="w-6 h-6 text-zinc-400" />
                    </div>
                    <div className="text-center">
                      <p className="text-white font-medium">Click or drag to upload</p>
                      <p className="text-xs text-zinc-500 mt-1">Supports JPG, PNG, WEBP, BMP</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <label className="block text-sm font-medium text-zinc-300">
                Additional Context (Optional)
              </label>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="Describe what this image is for better indexing..."
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 min-h-[100px] resize-none transition-all"
              />
            </div>

            {status === 'error' && (
              <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400 animate-in fade-in zoom-in-95 duration-300">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <p className="text-sm font-medium">{errorMessage}</p>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || status === 'uploading'}
              className={`w-full py-4 rounded-xl font-bold text-white transition-all flex items-center justify-center gap-2 ${
                !file || status === 'uploading'
                  ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-500/20 active:scale-[0.98]'
              }`}
            >
              {status === 'uploading' ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Queuing Image...
                </>
              ) : (
                <>
                  <ImageIcon className="w-5 h-5" />
                  Upload for Vision Analysis
                </>
              )}
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl space-y-3">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            VRAM Awareness
          </h3>
          <p className="text-sm text-zinc-400">
            Vision processing uses significant GPU memory. We queue images so you can process them 
            when the server is idle to avoid memory conflicts.
          </p>
        </div>
        <div className="p-6 bg-zinc-900/30 border border-zinc-800/50 rounded-2xl space-y-3">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-purple-500" />
            LLaVA Analysis
          </h3>
          <p className="text-sm text-zinc-400">
            Once processed, the generated captions become searchable chunks in your RAG database,
            allowing you to query the content of your images.
          </p>
        </div>
      </div>
    </div>
  );
};
