'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { AuthBackground } from '@/components/auth/auth-background';
import { Logo } from '@/components/layout/logo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

export default function LoginPage() {
  const router = useRouter();
  const { login, status, hydrate } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);
  useEffect(() => {
    if (status === 'signed-in') router.replace('/app');
  }, [status, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim().toLowerCase(), password);
      router.replace('/app');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthBackground tagline="Many models refracted through one lens">
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: EASE_OUT }}
        className="w-full max-w-[400px] rounded-2xl border border-hairline-soft/10 bg-canvas p-7 shadow-popover-dark sm:p-9"
      >
        <div className="mb-7 flex justify-center">
          <Logo size={26} wordmarkClassName="text-xl" />
        </div>

        <h1 className="mb-7 text-center font-serif text-[clamp(26px,6vw,32px)] font-medium tracking-tight text-ink">
          Log in
        </h1>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink">Email</label>
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Your email address"
              autoComplete="email"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink">Password</label>
            <Input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete="current-password"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-body">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 accent-primary"
              />
              Remember me
            </label>
            <button type="button" className="text-sm font-medium text-ink transition-opacity duration-120 hover:opacity-70">
              Forgot password?
            </button>
          </div>

          {error && (
            <div className="rounded-md border border-danger/25 bg-danger/8 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          <Button type="submit" disabled={busy} size="lg" className="mt-1 w-full">
            {busy ? 'Signing in…' : 'Log in'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-soft">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="font-semibold text-ink hover:text-primary">
            Sign up
          </Link>
        </p>
      </motion.div>
    </AuthBackground>
  );
}
