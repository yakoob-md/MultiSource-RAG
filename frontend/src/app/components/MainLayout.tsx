import { Outlet } from 'react-router';
import { Sidebar } from './Sidebar';

export function MainLayout() {
  return (
    <div className="h-screen w-screen bg-[#F8FAFC] dark:bg-[#0F172A] transition-colors">
      <div className="flex h-full">
        <Sidebar />
        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
