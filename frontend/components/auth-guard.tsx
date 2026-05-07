'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';

/** Redirects to /login when not signed in, otherwise renders children. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (status === 'signed-out') router.replace('/login');
  }, [status, router]);

  if (status !== 'signed-in') {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-canvas text-sm text-muted-soft">
        Loading…
      </div>
    );
  }
  return <>{children}</>;
}
