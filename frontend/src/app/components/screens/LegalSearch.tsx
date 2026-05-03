import { useState } from 'react';
import { Search, Loader2, Book, Scale, Shield, ChevronDown, ChevronUp, AlertCircle, FileText } from 'lucide-react';
import { queryLegal } from '../../api';
import { LegalQueryResponse, LegalCitation } from '../../types';

export function LegalSearch() {
  const [question, setQuestion] = useState('');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<LegalQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedAmendments, setExpandedAmendments] = useState<string[]>([]);

  const toggleAmendment = (idx: string) => {
    setExpandedAmendments(prev => 
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const filterParam = sourceFilter === 'all' ? undefined : sourceFilter;
      const res = await queryLegal(question, filterParam);
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to search corpus");
    } finally {
      setIsLoading(false);
    }
  };

  const getSourceBadge = (cit: LegalCitation) => {
    if (cit.source_type === 'judgment') {
      return <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 border border-purple-200 dark:border-purple-800 flex items-center gap-1"><Scale className="w-3 h-3" /> SC Judgment</span>;
    }
    const doc = cit.document.toLowerCase();
    if (doc.includes('ipc') || doc.includes('penal')) {
      return <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border border-red-200 dark:border-red-800 flex items-center gap-1"><Shield className="w-3 h-3" /> IPC</span>;
    }
    if (doc.includes('crpc') || doc.includes('procedure')) {
      return <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border border-blue-200 dark:border-blue-800 flex items-center gap-1"><Book className="w-3 h-3" /> CrPC</span>;
    }
    if (doc.includes('constitution')) {
      return <span className="px-2 py-1 text-xs font-medium rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800 flex items-center gap-1"><Book className="w-3 h-3" /> Constitution</span>;
    }
    return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400 border border-gray-200 dark:border-gray-700">{cit.document}</span>;
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="px-8 py-10 bg-white/5 backdrop-blur-md border-b border-white/10 drop-shadow-sm">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <Scale className="w-8 h-8 text-[#6366F1]" />
            <h1 className="text-3xl font-bold text-white">Indian Legal Assistant</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2 font-medium">
            <Shield className="w-4 h-4" /> Powered by IPC, CrPC, Constitution, and Supreme Court Judgments
          </p>
        </div>
      </div>

      <div className="flex-1 px-8 py-8 w-full max-w-4xl mx-auto">
        {/* Search Input */}
        <form onSubmit={handleSubmit} className="mb-10">
          <div className="relative mb-4">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Search className="h-6 w-6 text-gray-400" />
            </div>
            <input
              type="text"
              className="block w-full pl-12 pr-4 py-4 md:text-lg border-2 border-white/10 rounded-xl bg-white/5 backdrop-blur-md focus:bg-white/10 focus:border-[#6366F1] focus:ring-4 focus:ring-[#6366F1]/10 text-white placeholder-white/40 transition-all shadow-sm outline-none"
              placeholder="Ask a legal question... e.g. 'What is the punishment for murder?'"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isLoading}
            />
            <button 
              type="submit" 
              disabled={isLoading || !question.trim()}
              className="absolute inset-y-2 right-2 bg-[#6366F1] hover:bg-[#4F46E5] disabled:opacity-50 text-white px-6 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <span>Search</span>}
            </button>
          </div>
          
          <div className="flex items-center gap-6 px-2">
            <label className="flex items-center gap-2 cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-300">
              <input type="radio" value="all" checked={sourceFilter === 'all'} onChange={(e) => setSourceFilter(e.target.value)} className="text-[#6366F1] focus:ring-[#6366F1] w-4 h-4" />
              All Sources
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-300">
              <input type="radio" value="statute" checked={sourceFilter === 'statute'} onChange={(e) => setSourceFilter(e.target.value)} className="text-[#6366F1] focus:ring-[#6366F1] w-4 h-4" />
              Statutes Only
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-300">
              <input type="radio" value="judgment" checked={sourceFilter === 'judgment'} onChange={(e) => setSourceFilter(e.target.value)} className="text-[#6366F1] focus:ring-[#6366F1] w-4 h-4" />
              Judgments Only
            </label>
          </div>
        </form>

        {/* Loading State */}
        {isLoading && (
          <div className="py-20 flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
            <Loader2 className="w-10 h-10 animate-spin text-[#6366F1] mb-4" />
            <p className="text-lg font-medium animate-pulse">Searching legal corpus...</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-xl border border-red-200 dark:border-red-900/50 mb-8 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}

        {/* Results */}
        {!isLoading && result && (
          <div className="space-y-8 pb-12 animate-in fade-in slide-in-from-bottom-4 duration-500">
            
            {/* ANSWER */}
            <div className="p-6 md:p-8 bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 shadow-sm">
              <h2 className="text-sm font-bold tracking-wider text-gray-400 uppercase mb-4 flex items-center gap-2"><Scale className="w-4 h-4"/> Answer</h2>
              <div className="prose prose-blue dark:prose-invert max-w-none">
                <p className="text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
              </div>
            </div>

            {/* LEGAL BASIS */}
            {result.legal_basis && (
              <div className="p-6 md:p-8 bg-blue-500/5 backdrop-blur-md border border-blue-500/20 border-l-[4px] border-l-[#6366F1] rounded-r-2xl shadow-sm">
                 <h2 className="text-sm font-bold tracking-wider text-gray-400 uppercase mb-4 flex items-center gap-2"><FileText className="w-4 h-4"/> Legal Basis</h2>
                 <p className="font-serif text-gray-700 dark:text-gray-300 italic leading-relaxed whitespace-pre-wrap">
                   "{result.legal_basis}"
                 </p>
              </div>
            )}

            {/* CITATIONS */}
            {result.citations && result.citations.length > 0 && (
              <div className="space-y-4">
                <h2 className="text-sm font-bold tracking-wider text-gray-400 uppercase mb-4 pt-4 border-t border-gray-200 dark:border-gray-800">Primary Citations ({result.citations.length})</h2>
                
                {result.citations.map((cit, i) => (
                  <div key={i} className="p-5 bg-white/5 backdrop-blur-md rounded-xl border border-white/10 shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 mb-1">
                          {getSourceBadge(cit)}
                          <span className="text-xs text-gray-400">{cit.date || 'Active Statute'}</span>
                        </div>
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                          {cit.source_type === 'statute' 
                            ? `Section ${cit.section}: ${cit.title || cit.document}`
                            : `${cit.document}`}
                        </h3>
                        {cit.court && <p className="text-sm text-gray-500 flex items-center gap-1"><Scale className="w-3 h-3"/> {cit.court}</p>}
                      </div>
                      {cit.para && <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded text-xs font-medium border border-gray-200 dark:border-gray-700">Para {cit.para}</span>}
                    </div>

                    <div className="bg-gray-50 dark:bg-[#0F172A] rounded-lg p-4 font-mono text-sm text-gray-700 dark:text-gray-300 mb-2 border border-gray-200 dark:border-gray-800 leading-relaxed shadow-inner">
                      {cit.text_excerpt}
                    </div>

                    {cit.amendments && cit.amendments.length > 0 && (
                      <div className="mt-4 border-t border-gray-100 dark:border-gray-800 pt-3">
                        <button 
                          onClick={() => toggleAmendment(i.toString())}
                          className="flex items-center gap-1 text-sm font-medium text-[#6366F1] hover:text-[#4F46E5] transition-colors"
                        >
                          {expandedAmendments.includes(i.toString()) ? <ChevronUp className="w-4 h-4"/> : <ChevronDown className="w-4 h-4"/>}
                          Amendment History ({cit.amendments.length})
                        </button>
                        
                        {expandedAmendments.includes(i.toString()) && (
                          <ul className="mt-3 space-y-2">
                            {cit.amendments.map((amend, aIdx) => (
                              <li key={aIdx} className="text-xs text-gray-500 dark:text-gray-400 flex items-start gap-2 bg-gray-50 dark:bg-[#0F172A] p-2 rounded">
                                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1 flex-shrink-0" />
                                <span>{amend}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* Footer Disclaimer */}
      <div className="mt-auto border-t border-white/10 bg-white/5 backdrop-blur-md py-4 text-center">
        <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center justify-center gap-1">
          <AlertCircle className="w-3 h-3" />
          This system provides legal information only, not legal advice. Consult a qualified advocate for specific legal matters.
        </p>
      </div>
    </div>
  );
}
