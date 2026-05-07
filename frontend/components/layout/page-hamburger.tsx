'use client';
import { Menu } from 'lucide-react';
import { useSidebar } from './sidebar-context';

/** Hamburger button for the mobile drawer. Auto-hidden at >=1024px via lg:hidden. */
export function PageHamburger() {
  const { openSidebar } = useSidebar();
  return (
    <button
      type="button"
      aria-label="Open sidebar"
      onClick={openSidebar}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-hairline bg-canvas text-ink transition-colors duration-120 ease-out hover:bg-surface-card lg:hidden"
    >
      <Menu size={18} />
    </button>
  );
}
