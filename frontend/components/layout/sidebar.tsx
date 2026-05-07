'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BadgeCheck,
  Cog,
  LineChart,
  LogOut,
  MoreHorizontal,
  PenSquare,
  Server,
  Trash2,
  Wrench,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { GooeyInput } from '@/components/ui/gooey-input';
import type { Conversation } from '@/lib/types';

function groupConversations(convs: Conversation[]) {
  const now = new Date();
  const todayStart = new Date(now);
  todayStart.setHours(0, 0, 0, 0);
  const DAY = 86_400_000;
  const buckets: Record<string, Conversation[]> = {
    Today: [],
    Yesterday: [],
    'Last 7 days': [],
    'Last 30 days': [],
    Older: [],
  };
  for (const c of convs) {
    const updated = new Date(c.updated_at);
    const diff = (todayStart.getTime() - updated.getTime()) / DAY;
    if (updated >= todayStart) buckets.Today.push(c);
    else if (diff < 2) buckets.Yesterday.push(c);
    else if (diff < 7) buckets['Last 7 days'].push(c);
    else if (diff < 30) buckets['Last 30 days'].push(c);
    else buckets.Older.push(c);
  }
  return Object.entries(buckets).filter(([, items]) => items.length > 0);
}

const PROFILE_LINKS = [
  { href: '/app/settings/models', label: 'Models', icon: BadgeCheck },
  { href: '/app/settings/tools', label: 'Tools', icon: Wrench },
  { href: '/app/settings/mcp', label: 'MCP Servers', icon: Server },
  { href: '/app/analytics', label: 'Analytics', icon: LineChart },
  { href: '/app/settings/account', label: 'Settings', icon: Cog },
];

export function Sidebar({ open = true, onClose }: { open?: boolean; onClose?: () => void } = {}) {
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const { user, logout } = useAuthStore();
  const [search, setSearch] = useState('');

  const conversations = useQuery<Conversation[]>({
    queryKey: ['conversations'],
    queryFn: () => api('/conversations'),
    refetchInterval: 8_000,
  });

  const groups = useMemo(() => {
    const all = conversations.data || [];
    const q = search.toLowerCase().trim();
    const filtered = q ? all.filter((c) => (c.title || 'Untitled').toLowerCase().includes(q)) : all;
    return groupConversations(filtered);
  }, [conversations.data, search]);

  async function deleteConversation(e: React.MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    qc.setQueryData<Conversation[]>(['conversations'], (prev) => (prev ?? []).filter((c) => c.id !== id));
    if (pathname === `/app/c/${id}`) router.push('/app/new');
    api(`/conversations/${id}`, { method: 'DELETE' }).catch(() => {
      qc.invalidateQueries({ queryKey: ['conversations'] });
    });
  }

  const initials = (user?.display_name || user?.email || 'U')[0].toUpperCase();

  return (
    <>
      <div
        className="app-sidebar-backdrop fixed inset-0 z-[55] bg-ink/40"
        data-open={open ? 'true' : 'false'}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="app-sidebar fixed left-0 top-0 z-[60] flex h-dvh w-[272px] min-w-[272px] flex-col border-r border-hairline bg-surface-soft lg:z-10"
        data-open={open ? 'true' : 'false'}
      >
        {/* New chat */}
        <div className="p-3 pb-2">
          <Link
            href="/app/new"
            onClick={onClose}
            className={cn(
              'flex h-10 w-full items-center justify-center gap-2 rounded-md border border-hairline bg-canvas',
              'text-sm font-medium text-ink shadow-card',
              'transition-[transform,background-color,border-color] duration-160 ease-out',
              'hover:bg-surface-card hover:border-muted-soft/40 active:scale-[0.98]',
            )}
          >
            <PenSquare size={14} />
            <span>New chat</span>
          </Link>
        </div>

        {/* Nav */}
        <div className="space-y-0.5 px-2 pb-2">
          <GooeyInput
            placeholder="Search chats…"
            collapsedLabel="Search chats"
            value={search}
            onValueChange={setSearch}
            collapsedWidth={228}
            expandedWidth={188}
            expandedOffset={40}
            surfaceClass="bg-surface-card text-muted shadow-card ring-1 ring-hairline/60"
            classNames={{
              trigger: 'justify-start',
              collapsedLabel: 'text-muted',
              input: 'text-ink placeholder:text-muted-soft',
            }}
            className="w-full"
          />

          <Link
            href="/app/settings/account"
            onClick={onClose}
            className={cn(
              'flex h-9 items-center gap-2.5 rounded-md px-3 text-sm transition-colors duration-120 ease-out',
              pathname?.startsWith('/app/settings')
                ? 'bg-surface-card text-ink'
                : 'text-body hover:bg-surface-card hover:text-ink',
            )}
          >
            <Cog size={15} />
            <span>Settings</span>
          </Link>
        </div>

        <div className="mx-3 h-px bg-hairline" />

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {groups.length === 0 && !conversations.isPending && (
            <div className="mt-6 text-center text-xs text-muted-soft">No conversations yet</div>
          )}
          {groups.map(([label, items]) => (
            <div key={label}>
              <div className="mb-0.5 mt-3 px-3 text-[11px] font-medium uppercase tracking-wider text-muted-soft first:mt-1">
                {label}
              </div>
              {items.map((conv) => {
                const active = pathname === `/app/c/${conv.id}`;
                return (
                  <Link
                    key={conv.id}
                    href={`/app/c/${conv.id}`}
                    onClick={onClose}
                    className={cn(
                      'group/item relative flex h-8 items-center rounded-md px-3 text-sm transition-colors duration-120 ease-out',
                      active ? 'bg-surface-card text-ink' : 'text-body hover:bg-surface-card hover:text-ink',
                    )}
                  >
                    <span className="block truncate pr-6">{conv.title || 'Untitled'}</span>
                    <button
                      onClick={(e) => deleteConversation(e, conv.id)}
                      title="Delete"
                      className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center p-0.5 text-muted-soft opacity-0 transition-opacity duration-120 ease-out hover:text-danger group-hover/item:opacity-100"
                    >
                      <Trash2 size={12} />
                    </button>
                  </Link>
                );
              })}
            </div>
          ))}
        </div>

        {/* Profile */}
        <div className="border-t border-hairline p-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex w-full items-center gap-2.5 rounded-md p-2 transition-colors duration-120 ease-out hover:bg-surface-card">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-active text-[12px] font-semibold text-white">
                  {initials}
                </span>
                <span className="min-w-0 flex-1 truncate text-left text-sm text-body">
                  {user?.display_name || user?.email}
                </span>
                <MoreHorizontal size={15} className="shrink-0 text-muted-soft" />
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                side="top"
                align="start"
                sideOffset={8}
                style={{ transformOrigin: 'var(--radix-dropdown-menu-content-transform-origin)' }}
                className={cn(
                  'z-50 w-[220px] rounded-lg border border-hairline bg-canvas p-1 shadow-popover',
                  'data-[state=open]:animate-in data-[state=closed]:animate-out',
                  'data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
                  'data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95',
                  'duration-160 ease-out',
                )}
              >
                {PROFILE_LINKS.map(({ href, label, icon: Icon }) => (
                  <DropdownMenu.Item key={href} asChild>
                    <Link
                      href={href}
                      className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm text-body outline-none transition-colors duration-120 ease-out hover:bg-surface-card hover:text-ink data-[highlighted]:bg-surface-card data-[highlighted]:text-ink"
                    >
                      <Icon size={14} />
                      {label}
                    </Link>
                  </DropdownMenu.Item>
                ))}
                <DropdownMenu.Separator className="my-1 h-px bg-hairline" />
                <DropdownMenu.Item
                  onSelect={() => logout()}
                  className="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted outline-none transition-colors duration-120 ease-out hover:bg-surface-card hover:text-ink data-[highlighted]:bg-surface-card data-[highlighted]:text-ink"
                >
                  <LogOut size={14} />
                  Sign out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </aside>
    </>
  );
}
