import { Link } from 'react-router';
import { LiquidCursor } from '../LiquidCursor';
import { ArrowRight, Hexagon, Shield, Zap } from 'lucide-react';

export function Landing() {
  return (
    <div className="relative min-h-screen bg-black overflow-hidden flex flex-col items-center justify-center font-sans">
      {/* Dynamic Cursor Background */}
      <LiquidCursor />

      {/* Grid Pattern Overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Subtle Glows */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#6366F1]/10 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-[#8B5CF6]/10 blur-[80px] rounded-full pointer-events-none" />

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center text-center px-4 max-w-4xl w-full">
        {/* Title */}
        <h1 className="text-7xl md:text-8xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 tracking-tight mb-6 animate-in slide-in-from-bottom-8 fade-in duration-700 delay-100">
          InteleX
        </h1>

        {/* Subtitle */}
        <p className="text-xl md:text-2xl text-gray-400 font-light mb-12 max-w-2xl mx-auto leading-relaxed animate-in slide-in-from-bottom-8 fade-in duration-700 delay-200">
          Advanced Multi-Modal Legal Intelligence. <br className="hidden md:block"/>
          Powered by Hybrid RAG and GPU-Optimized Vision.
        </p>

        {/* Launch Button */}
        <div className="animate-in slide-in-from-bottom-8 fade-in duration-700 delay-300">
          <Link
            to="/app"
            className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 bg-white text-black rounded-full font-bold text-lg overflow-hidden transition-transform hover:scale-105 active:scale-95"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-[#6366F1] via-[#8B5CF6] to-[#D946EF] opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <span className="relative z-10 group-hover:text-white transition-colors duration-300 flex items-center gap-2">
              Launch System <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </span>
          </Link>
        </div>

      </div>
    </div>
  );
}
