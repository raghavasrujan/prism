'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { AuthGuard } from '@/components/auth-guard';
import { Sidebar } from '@/components/layout/sidebar';
import { SidebarContext } from '@/components/layout/sidebar-context';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const mql = window.matchMedia('(min-width: 1024px)');
    const update = () => setIsDesktop(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!isDesktop) setSidebarOpen(false);
  }, [pathname, isDesktop]);

  const closeSidebar = useCallback(() => {
    if (!isDesktop) setSidebarOpen(false);
  }, [isDesktop]);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);

  const effectiveOpen = isDesktop ? true : sidebarOpen;

  return (
    <AuthGuard>
      <SidebarContext.Provider value={{ open: effectiveOpen, openSidebar, closeSidebar }}>
        <div className="flex h-dvh w-full overflow-hidden bg-canvas">
          <Sidebar open={effectiveOpen} onClose={closeSidebar} />
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden">{children}</main>
        </div>
      </SidebarContext.Provider>
    </AuthGuard>
  );
}
