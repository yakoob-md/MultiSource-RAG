import { Outlet } from 'react-router';
import { CommandPalette } from './CommandPalette';
import { BeamsBackground } from './ui/BeamsBackground';

export function MainLayout() {
  return (
    <BeamsBackground className="h-screen w-screen overflow-hidden relative">
      {/* Global Background Beams */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-[#6366F1]/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-violet-600/5 blur-[120px]" />
        <div className="absolute top-[20%] left-[30%] w-[40%] h-[40%] rounded-full bg-blue-600/5 blur-[120px] opacity-20" />
      </div>

      <CommandPalette />
      <div className="h-full w-full overflow-hidden relative z-10">
        <Outlet />
      </div>
    </BeamsBackground>
  );
}
