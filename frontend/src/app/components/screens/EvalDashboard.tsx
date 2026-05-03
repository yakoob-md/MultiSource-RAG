import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  BarChart3, 
  Play, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Search, 
  ShieldCheck, 
  Zap, 
  Target, 
  ChevronRight,
  Database,
  ArrowLeft
} from 'lucide-react';
import { useNavigate } from 'react-router';
import { startEvaluation, getEvaluationStatus } from '../../api';

interface EvalResult {
  summary: {
    faithfulness: number;
    answer_relevancy: number;
    context_precision: number;
    overall: number;
  };
  per_question: Array<{
    question: string;
    source_title: string;
    answer_preview: string;
    faithfulness: number;
    answer_relevancy: number;
    context_precision: number;
    avg_score: number;
    error?: string;
  }>;
  n_evaluated: number;
}

export function EvalDashboard() {
  const navigate = useNavigate();
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [progress, setProgress] = useState({ current: 0, total: 15, message: '' });
  const [result, setResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nQuestions, setNQuestions] = useState(15);

  // Poll for status if a job is running
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (status === 'running' && jobId) {
      interval = setInterval(async () => {
        try {
          const data = await getEvaluationStatus(jobId);
          if (data.status === 'running' || data.status === 'queued') {
            setProgress(data.progress);
          } else if (data.status === 'done') {
            setResult(data.result);
            setStatus('done');
            clearInterval(interval);
          } else if (data.status === 'error') {
            setError(data.error);
            setStatus('error');
            clearInterval(interval);
          }
        } catch (err: any) {
          setError(err.message);
          setStatus('error');
          clearInterval(interval);
        }
      }, 2000);
    }

    return () => clearInterval(interval);
  }, [status, jobId]);

  const handleStart = async () => {
    setError(null);
    setResult(null);
    setStatus('running');
    try {
      const id = await startEvaluation(nQuestions);
      setJobId(id);
    } catch (err: any) {
      setError(err.message);
      setStatus('error');
    }
  };

  const ScoreCard = ({ title, score, icon: Icon, color }: any) => {
    const percentage = Math.round(score * 100);
    return (
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white/[0.03] border border-white/5 rounded-3xl p-6 relative overflow-hidden group hover:border-white/10 transition-all"
      >
        <div className={`absolute top-0 right-0 w-32 h-32 bg-${color}-500/5 blur-[50px] -mr-16 -mt-16 group-hover:bg-${color}-500/10 transition-all`} />
        
        <div className="flex items-start justify-between mb-4">
          <div className={`p-3 rounded-2xl bg-${color}-500/10 border border-${color}-500/20`}>
            <Icon className={`w-5 h-5 text-${color}-400`} />
          </div>
          <div className="text-right">
            <span className="text-3xl font-bold text-white/90">{percentage}%</span>
            <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mt-1">Efficiency Score</p>
          </div>
        </div>
        
        <h3 className="text-sm font-bold text-white/80 mb-2">{title}</h3>
        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${percentage}%` }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            className={`h-full bg-${color}-500 shadow-[0_0_10px_rgba(0,0,0,0.5)]`}
          />
        </div>
      </motion.div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#0A0A0B] relative overflow-hidden p-8 overflow-y-auto no-scrollbar">
      {/* Background Decor */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#6366F1]/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-purple-500/5 blur-[100px] rounded-full" />
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 mb-12 relative z-10">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate(-1)}
            className="p-3 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all group"
          >
            <ArrowLeft className="w-5 h-5 text-white/40 group-hover:text-white" />
          </button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white/90">System Evaluation</h1>
            <p className="text-xs font-bold uppercase tracking-[0.3em] text-white/20">RAGAS Framework Metrics</p>
          </div>
        </div>

        {status === 'idle' && (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 px-4 py-2 rounded-2xl bg-white/5 border border-white/10">
              <span className="text-[10px] font-bold uppercase text-white/40">Sample Size:</span>
              <input 
                type="number" 
                value={nQuestions} 
                onChange={(e) => setNQuestions(parseInt(e.target.value))}
                min="5" max="30"
                className="bg-transparent border-none text-xs font-bold text-[#6366F1] focus:ring-0 w-12"
              />
            </div>
            <button 
              onClick={handleStart}
              className="px-8 py-4 rounded-2xl bg-[#6366F1] text-white text-xs font-bold uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-xl shadow-[#6366F1]/20 flex items-center gap-3"
            >
              <Play className="w-4 h-4" /> Start Audit
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="relative z-10 space-y-12">
        {status === 'running' && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-w-3xl mx-auto py-20 text-center space-y-8"
          >
            <div className="relative inline-block">
              <div className="absolute inset-0 bg-[#6366F1]/20 blur-3xl rounded-full animate-pulse" />
              <Loader2 className="w-20 h-20 text-[#6366F1] animate-spin relative" />
            </div>
            
            <div className="space-y-4">
              <h2 className="text-2xl font-bold text-white/90">{progress.message || 'Initializing Judge LLM...'}</h2>
              <p className="text-white/40 text-sm">Evaluating system performance across {progress.total} benchmarks.</p>
              
              <div className="max-w-md mx-auto mt-8">
                <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest text-white/20 mb-2">
                  <span>Progress</span>
                  <span>{Math.round((progress.current / progress.total) * 100)}%</span>
                </div>
                <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${(progress.current / progress.total) * 100}%` }}
                    className="h-full bg-gradient-to-r from-[#6366F1] to-purple-500 shadow-[0_0_20px_rgba(99,102,241,0.5)]"
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {status === 'done' && result && (
          <div className="space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Top Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <ScoreCard 
                title="Faithfulness" 
                score={result.summary.faithfulness} 
                icon={ShieldCheck} 
                color="green" 
              />
              <ScoreCard 
                title="Answer Relevance" 
                score={result.summary.answer_relevancy} 
                icon={Target} 
                color="blue" 
              />
              <ScoreCard 
                title="Context Precision" 
                score={result.summary.context_precision} 
                icon={Search} 
                color="purple" 
              />
              <div className="bg-[#6366F1] rounded-3xl p-6 flex flex-col justify-between shadow-2xl shadow-[#6366F1]/20 relative overflow-hidden group">
                <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
                <Zap className="w-8 h-8 text-white/40 mb-4" />
                <div>
                  <span className="text-4xl font-bold text-white">{Math.round(result.summary.overall * 100)}%</span>
                  <p className="text-[10px] font-bold text-white/50 uppercase tracking-[0.2em] mt-1">Overall Robustness</p>
                </div>
              </div>
            </div>

            {/* Per Question Breakdown */}
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white/90">Detailed Audit Trail</h2>
                <div className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] font-bold text-white/40 uppercase">
                  {result.n_evaluated} Benchmarks Evaluated
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4">
                {result.per_question.map((q, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className="group bg-white/[0.02] border border-white/5 rounded-2xl p-6 hover:bg-white/[0.04] hover:border-white/10 transition-all"
                  >
                    <div className="flex flex-col lg:flex-row gap-6">
                      <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-[#6366F1] bg-[#6366F1]/10 px-2 py-0.5 rounded-full">TEST {idx + 1}</span>
                          <span className="text-[10px] font-bold text-white/20 uppercase tracking-widest truncate max-w-[200px]">
                            <Database className="w-3 h-3 inline mr-1 opacity-50" /> {q.source_title}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-white/90">Q: {q.question}</h4>
                        <p className="text-xs text-white/40 leading-relaxed italic line-clamp-2">
                          "A: {q.answer_preview}"
                        </p>
                      </div>

                      <div className="flex items-center gap-8 px-6 border-l border-white/5">
                        <div className="text-center">
                          <div className="text-lg font-bold text-green-400">{Math.round(q.faithfulness * 100)}%</div>
                          <div className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">Faithful</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-bold text-blue-400">{Math.round(q.answer_relevancy * 100)}%</div>
                          <div className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">Relevant</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-bold text-purple-400">{Math.round(q.context_precision * 100)}%</div>
                          <div className="text-[8px] font-bold text-white/20 uppercase tracking-widest mt-1">Precise</div>
                        </div>
                        <div className="ml-4 p-3 rounded-full bg-white/5 group-hover:bg-[#6366F1]/20 group-hover:text-[#6366F1] transition-all">
                          <ChevronRight className="w-4 h-4" />
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        )}

        {status === 'idle' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 py-20">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-green-500/10 border border-green-500/20 flex items-center justify-center mx-auto mb-6">
                <ShieldCheck className="w-8 h-8 text-green-400" />
              </div>
              <h3 className="text-lg font-bold text-white/90">Zero Hallucination Audit</h3>
              <p className="text-xs text-white/30 leading-relaxed">Scientifically measure Faithfulness to ensure AI answers are 100% grounded in your documents.</p>
            </div>
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mx-auto mb-6">
                <Target className="w-8 h-8 text-blue-400" />
              </div>
              <h3 className="text-lg font-bold text-white/90">Answer Relevancy</h3>
              <p className="text-xs text-white/30 leading-relaxed">Verify that AI responses actually solve the user's problem with high semantic alignment.</p>
            </div>
            <div className="text-center space-y-4">
              <div className="w-16 h-16 rounded-3xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto mb-6">
                <Search className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-lg font-bold text-white/90">Context Precision</h3>
              <p className="text-xs text-white/30 leading-relaxed">Evaluate the retrieval engine's ability to pick the "needle in the haystack" from your knowledge base.</p>
            </div>
          </div>
        )}

        {error && (
          <div className="max-w-md mx-auto p-6 rounded-3xl bg-red-500/10 border border-red-500/20 flex items-center gap-4 text-red-400 animate-bounce">
            <AlertCircle className="w-6 h-6 flex-shrink-0" />
            <p className="text-sm font-medium">Audit Failed: {error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
