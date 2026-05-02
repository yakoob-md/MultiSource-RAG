import { Outlet } from 'react-router';
import { Sidebar } from './Sidebar';
import { CommandPalette } from './CommandPalette';

export function MainLayout() {
  return (
    <div className="h-screen w-screen bg-[#F8FAFC] dark:bg-[#0A0A0B] transition-colors overflow-hidden">
      <CommandPalette />
      <div className="flex h-full">
        <Sidebar />
        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
