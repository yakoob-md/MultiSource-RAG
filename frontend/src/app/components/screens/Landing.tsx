import { Link } from 'react-router';
import { LiquidCursor } from '../LiquidCursor';
import { ArrowRight, Hexagon, Shield, Zap } from 'lucide-react';
import { cn } from '../ui/utils';

export function Landing() {
  return (
    <div className="relative min-h-screen bg-[#fafafa] overflow-hidden flex flex-col items-center justify-center font-sans">
      {/* Aurora Background Wrapper */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className={cn(
          `
          [--white-gradient:repeating-linear-gradient(100deg,var(--white)_0%,var(--white)_7%,var(--transparent)_10%,var(--transparent)_12%,var(--white)_16%)]
          [--dark-gradient:repeating-linear-gradient(100deg,var(--black)_0%,var(--black)_7%,var(--transparent)_10%,var(--transparent)_12%,var(--black)_16%)]
          [--aurora:repeating-linear-gradient(100deg,var(--blue-500)_10%,var(--indigo-300)_15%,var(--blue-300)_20%,var(--violet-200)_25%,var(--blue-400)_30%)]
          [background-image:var(--white-gradient),var(--aurora)]
          [background-size:300%,_200%]
          [background-position:50%_50%,50%_50%]
          filter blur-[10px] invert dark:invert-0
          after:content-[""] after:absolute after:inset-0 after:[background-image:var(--white-gradient),var(--aurora)] 
          after:[background-size:200%,_100%] 
          after:animate-aurora after:[background-attachment:fixed] after:mix-blend-difference
          pointer-events-none
          absolute -inset-[10px] opacity-40 will-change-transform
          [mask-image:radial-gradient(ellipse_at_100%_0%,black_10%,var(--transparent)_70%)]`
        )}></div>
      </div>

      {/* Dynamic Cursor Background */}
      <LiquidCursor />

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center text-center px-4 max-w-4xl w-full">
        {/* Title */}
        <h1 className="text-7xl md:text-8xl font-black text-black tracking-tight mb-6 animate-in slide-in-from-bottom-8 fade-in duration-700 delay-100">
          InteleX
        </h1>

        {/* Subtitle */}
        <p className="text-xl md:text-2xl text-black/40 font-light mb-12 max-w-2xl mx-auto leading-relaxed animate-in slide-in-from-bottom-8 fade-in duration-700 delay-200">
          Advanced Multi-Modal Legal Intelligence. <br className="hidden md:block"/>
          Powered by Hybrid RAG and GPU-Optimized Vision.
        </p>

        {/* Launch Button */}
        <div className="animate-in slide-in-from-bottom-8 fade-in duration-700 delay-300">
          <Link
            to="/app"
            className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 bg-black text-white rounded-full font-bold text-lg overflow-hidden transition-transform hover:scale-105 active:scale-95 shadow-2xl shadow-black/20"
          >
            <span className="relative z-10 flex items-center gap-2">
              Launch System <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}

