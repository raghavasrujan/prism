'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { useThemeStore } from '@/stores/theme';

function ThemeSync() {
  const { theme } = useThemeStore();
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={qc}>
      <ThemeSync />
      {children}
      <Toaster
        position="top-right"
        toastOptions={{ duration: 3000 }}
        theme="system"
      />
    </QueryClientProvider>
  );
}
