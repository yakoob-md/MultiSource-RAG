import { Outlet } from 'react-router';
import { CommandPalette } from './CommandPalette';
import { BeamsBackground } from './ui/BeamsBackground';

export function MainLayout() {
  return (
    <BeamsBackground className="h-screen w-screen overflow-hidden">
      <CommandPalette />
      <div className="h-full w-full overflow-hidden">
        <Outlet />
      </div>
    </BeamsBackground>
  );
}
