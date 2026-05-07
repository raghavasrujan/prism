'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';
import { AuthBackground } from '@/components/auth/auth-background';
import { Logo } from '@/components/layout/logo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuthStore();
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      await register(email.trim().toLowerCase(), password, displayName.trim() || undefined);
      router.replace('/app');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create account');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthBackground tagline="Start your AI journey">
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
          Sign up
        </h1>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-ink">Display name</label>
            <Input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
            />
          </div>
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
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </div>

          {error && (
            <div className="rounded-md border border-danger/25 bg-danger/8 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          <Button type="submit" disabled={busy} size="lg" className="mt-1 w-full">
            {busy ? 'Creating account…' : 'Create your account'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-soft">
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-ink hover:text-primary">
            Log in
          </Link>
        </p>
      </motion.div>
    </AuthBackground>
  );
}
