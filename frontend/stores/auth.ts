'use client';

import { create } from 'zustand';
import type { StoredUser } from '@/lib/auth';
import { clearAuth, getAccess, getRefresh, getUser, setTokens } from '@/lib/auth';
import { api } from '@/lib/api';
import type { TokenPair } from '@/lib/types';

type AuthState = {
  user: StoredUser | null;
  status: 'unknown' | 'signed-in' | 'signed-out';
  hydrate: () => void;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: 'unknown',
  hydrate: () => {
    const u = getUser();
    const a = getAccess();
    if (u && a) set({ user: u, status: 'signed-in' });
    else set({ user: null, status: 'signed-out' });
  },
  register: async (email, password, displayName) => {
    const pair = await api<TokenPair>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    setTokens(pair.access, pair.refresh, pair.user);
    set({ user: pair.user, status: 'signed-in' });
  },
  login: async (email, password) => {
    const pair = await api<TokenPair>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setTokens(pair.access, pair.refresh, pair.user);
    set({ user: pair.user, status: 'signed-in' });
  },
  logout: async () => {
    const refresh = getRefresh();
    if (refresh) {
      try {
        await api('/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh }),
        });
      } catch {
        /* idempotent */
      }
    }
    clearAuth();
    set({ user: null, status: 'signed-out' });
  },
}));
