import { useState } from 'react';
import { Upload, FileText, CheckCircle, Loader2, X, AlertCircle } from 'lucide-react';
import { uploadPdf, notifySidebarRefresh } from '../../api';

interface UploadedFile {
  name: string;
  size: number;
  pages?: number;
  language?: string;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
}

export function UploadPDF() {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.type === 'application/pdf'
    );
    processFiles(droppedFiles);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(Array.from(e.target.files));
    }
  };

  const processFiles = (fileList: File[]) => {
    fileList.forEach(file => {
      const uploadedFile: UploadedFile = {
        name: file.name,
        size: file.size,
        status: 'uploading',
        progress: 0,
      };

      setFiles(prev => [...prev, uploadedFile]);

      uploadPdf(file)
        .then((source) => {
          setFiles(prev => prev.map(f =>
            f.name === file.name
              ? {
                ...f,
                status: 'completed',
                progress: 100,
                pages: source.metadata?.pageCount,
                language: source.language,
              }
              : f
          ));
          // ✅ Notify sidebar to refresh source list
          notifySidebarRefresh();
        })
        .catch(() => {
          setFiles(prev => prev.map(f =>
            f.name === file.name
              ? { ...f, status: 'failed', progress: 0 }
              : f
          ));
        });
    });
  };

  const removeFile = (fileName: string) => {
    setFiles(prev => prev.filter(f => f.name !== fileName));
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl text-gray-900 dark:text-[#F8FAFC] mb-2">Upload PDF</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Upload PDF documents to add them to your knowledge base
          </p>
        </div>

        {/* Drop Zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-12 transition-all ${dragActive
            ? 'border-[#6366F1] bg-[#6366F1]/5'
            : 'border-gray-300 dark:border-gray-700 hover:border-[#6366F1] hover:bg-gray-50 dark:hover:bg-gray-800/50'
            }`}
        >
          <input
            type="file"
            id="file-upload"
            multiple
            accept=".pdf"
            onChange={handleFileInput}
            className="hidden"
          />

          <div className="text-center">
            <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-[#6366F1]/10 flex items-center justify-center">
              <Upload className="w-8 h-8 text-[#6366F1]" />
            </div>
            <h3 className="text-xl text-gray-900 dark:text-[#F8FAFC] mb-2">
              Drop your PDF files here
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              or click to browse from your computer
            </p>
            <label
              htmlFor="file-upload"
              className="inline-block px-6 py-3 bg-[#6366F1] hover:bg-[#4F46E5] text-white rounded-xl cursor-pointer transition-colors"
            >
              Select Files
            </label>
            <p className="text-sm text-gray-500 dark:text-gray-500 mt-4">
              Supports: PDF files up to 50MB
            </p>
          </div>
        </div>

        {/* Uploaded Files */}
        {files.length > 0 && (
          <div className="mt-8 space-y-4">
            <h2 className="text-xl text-gray-900 dark:text-[#F8FAFC] mb-4">
              Uploaded Files ({files.length})
            </h2>

            {files.map((file) => (
              <div
                key={file.name}
                className="p-5 rounded-xl bg-white dark:bg-[#1E293B] border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-gray-100 dark:bg-gray-800">
                    <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-sm text-gray-900 dark:text-[#F8FAFC] mb-1">
                          {file.name}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                          {file.pages && ` • ${file.pages} pages`}
                          {file.language && ` • ${file.language}`}
                        </p>
                      </div>
                      <button
                        onClick={() => removeFile(file.name)}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
                      >
                        <X className="w-4 h-4 text-gray-500" />
                      </button>
                    </div>

                    {file.status !== 'completed' && file.status !== 'failed' && (
                      <div className="mb-2">
                        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#6366F1] transition-all duration-300"
                            style={{ width: `${file.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-xs">
                      {file.status === 'uploading' && (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin text-[#6366F1]" />
                          <span className="text-[#6366F1]">Uploading and processing...</span>
                        </>
                      )}
                      {file.status === 'processing' && (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
                          <span className="text-blue-500">Processing and extracting text...</span>
                        </>
                      )}
                      {file.status === 'completed' && (
                        <>
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          <span className="text-green-500">Completed — sidebar updated</span>
                        </>
                      )}
                      {file.status === 'failed' && (
                        <>
                          <AlertCircle className="w-3 h-3 text-red-500" />
                          <span className="text-red-500">Failed to upload</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
