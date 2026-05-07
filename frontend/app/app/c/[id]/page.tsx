'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { Share, Check, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { MessageList, MessageAction, contentText, imageAttachmentIds } from '@/components/chat/message-list';
import { ChatComposer } from '@/components/chat/chat-composer';
import { ConversationUsageBadge } from '@/components/chat/conversation-usage-badge';
import { useChatStream } from '@/hooks/use-chat-stream';
import { useAuthStore } from '@/stores/auth';
import { PageHamburger } from '@/components/layout/page-hamburger';
import { Logo } from '@/components/layout/logo';
import type { Conversation, ConversationUsage, CustomTool, McpServer, Message, ProviderModel } from '@/lib/types';

export default function ChatPage() {
  const params = useParams<{ id: string }>();
  const convId = params.id;
  const qc = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const titleGenRef = useRef(false); // prevent double title-gen in strict mode
  const pendingHandled = useRef(false); // prevent double auto-send in strict mode

  const conversation = useQuery<Conversation>({
    queryKey: ['conversation', convId],
    queryFn: () => api(`/conversations/${convId}`),
  });
  const messages = useQuery<Message[]>({
    queryKey: ['messages', convId],
    queryFn: () => api(`/conversations/${convId}/messages`),
  });
  const usage = useQuery<ConversationUsage>({
    queryKey: ['conversation-usage', convId],
    queryFn: () => api(`/conversations/${convId}/usage`),
  });
  const models = useQuery<ProviderModel[]>({
    queryKey: ['models'],
    queryFn: () => api('/models'),
  });
  const allTools = useQuery<CustomTool[]>({
    queryKey: ['tools'],
    queryFn: () => api('/tools'),
  });
  const allMcp = useQuery<McpServer[]>({
    queryKey: ['mcp'],
    queryFn: () => api('/mcp'),
  });
  const activeAllTools = (allTools.data || []).filter((t) => t.is_active);
  const activeAllMcp = (allMcp.data || []).filter((s) => s.is_active);

  const { streaming, streamText, send, cancel, lastUsage } = useChatStream();

  // ── scroll to bottom on new content ──────────────────────────────
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.data, streamText]);

  // ── auto-send pending message seeded by /app/new ──────────────────
  useEffect(() => {
    if (pendingHandled.current) return;
    const raw = sessionStorage.getItem('__pending_msg');
    if (!raw) return;
    try {
      const { convId: pendingId, text, attachmentIds } = JSON.parse(raw) as {
        convId: string;
        text: string;
        attachmentIds?: string[];
      };
      if (pendingId === convId) {
        pendingHandled.current = true;
        sessionStorage.removeItem('__pending_msg');
        optimisticSend.mutate({ text, attachmentIds: attachmentIds ?? [] });
      }
    } catch {
      sessionStorage.removeItem('__pending_msg');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convId]);

  // ── refetch after streaming + auto-generate title ─────────────────
  useEffect(() => {
    if (streaming || !lastUsage) return;
    qc.invalidateQueries({ queryKey: ['messages', convId] });
    qc.invalidateQueries({ queryKey: ['conversation-usage', convId] });
    qc.invalidateQueries({ queryKey: ['conversation', convId] });

    const conv = qc.getQueryData<Conversation>(['conversation', convId]);
    const isUntitled = !conv?.title || ['', 'Untitled', 'New conversation'].includes(conv.title);
    if (isUntitled && !titleGenRef.current) {
      titleGenRef.current = true;
      api<{ title: string }>(`/conversations/${convId}/generate-title`, { method: 'POST' })
        .then(({ title }) => {
          if (title && title !== 'New conversation' && title !== 'Untitled') {
            qc.setQueryData<Conversation>(['conversation', convId], (old) => (old ? { ...old, title } : old));
            qc.invalidateQueries({ queryKey: ['conversations'] });
          }
        })
        .catch(() => undefined)
        .finally(() => {
          titleGenRef.current = false;
        });
    }
  }, [streaming, lastUsage, qc, convId]);

  // ── optimistic usage badge ────────────────────────────────────────
  const liveUsage: ConversationUsage | undefined = (() => {
    const base = usage.data;
    if (!lastUsage) return base;
    if (!base)
      return {
        input_tokens: lastUsage.input_tokens,
        output_tokens: lastUsage.output_tokens,
        cost_usd: lastUsage.cost_usd,
        message_count: 1,
        by_model: [],
      };
    if (usage.isFetching)
      return {
        ...base,
        input_tokens: base.input_tokens + lastUsage.input_tokens,
        output_tokens: base.output_tokens + lastUsage.output_tokens,
        cost_usd: base.cost_usd + lastUsage.cost_usd,
        message_count: base.message_count + 1,
      };
    return base;
  })();

  const optimisticSend = useMutation({
    mutationFn: async ({ text, attachmentIds }: { text: string; attachmentIds: string[] }) => {
      const optimisticId = `optimistic-${Date.now()}`;
      // Parent should be the current active leaf so the optimistic bubble sits
      // on the active branch and is picked up by computeBranchView. Null when
      // this is the first message of a brand-new chat.
      const parentId = conversation.data?.active_leaf_message_id ?? null;
      const optimistic: Message = {
        id: optimisticId,
        conversation_id: convId,
        request_id: optimisticId,
        parent_message_id: parentId,
        role: 'user',
        content: [{ type: 'text', text }],
        tool_calls: null,
        tool_call_id: null,
        tool_name: null,
        provider_snapshot: null,
        input_tokens: null,
        output_tokens: null,
        cost_usd: null,
        latency_ms: null,
        finish_reason: null,
        created_at: new Date().toISOString(),
      };
      qc.setQueryData<Message[]>(['messages', convId], (prev = []) => [...prev, optimistic]);
      // Point active_leaf at the optimistic user msg so the branch view walks
      // through it during streaming.
      qc.setQueryData<Conversation>(['conversation', convId], (prev) =>
        prev ? { ...prev, active_leaf_message_id: optimisticId } : prev,
      );
      await send(convId, text, undefined, attachmentIds);
    },
  });

  // ── switch model for this conversation ────────────────────────────
  const switchModel = useMutation({
    mutationFn: (newModelId: string) =>
      api<Conversation>(`/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ provider_model_id: newModelId }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(['conversation', convId], data);
    },
  });

  // ── toggle a tool on/off for this conversation ────────────────────
  const toggleTool = useMutation({
    mutationFn: async (toolId: string) => {
      const current = conversation.data?.tool_ids ?? [];
      const next = current.includes(toolId) ? current.filter((id) => id !== toolId) : [...current, toolId];
      return api<Conversation>(`/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ tool_ids: next }),
      });
    },
    onSuccess: (data) => {
      qc.setQueryData(['conversation', convId], data);
    },
  });

  // ── toggle an MCP server on/off for this conversation ─────────────
  const toggleMcp = useMutation({
    mutationFn: async (mcpId: string) => {
      const current = conversation.data?.mcp_server_ids ?? [];
      const next = current.includes(mcpId) ? current.filter((id) => id !== mcpId) : [...current, mcpId];
      return api<Conversation>(`/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ mcp_server_ids: next }),
      });
    },
    onSuccess: (data) => {
      qc.setQueryData(['conversation', convId], data);
    },
  });

  const activeModels = (models.data || []).filter((m) => m.is_active);
  const currentModelId = conversation.data?.provider_model_id;
  const currentToolIds = new Set(conversation.data?.tool_ids ?? []);
  const currentMcpIds = new Set(conversation.data?.mcp_server_ids ?? []);
  const title = conversation.data?.title || 'New conversation';

  // Resend from a given parent message — powers both instant "Regenerate"
  // and inline "edit & resubmit". Nothing here touches the composer.
  const branchSend = useMutation({
    mutationFn: async ({
      text,
      parentMessageId,
      attachmentIds,
    }: {
      text: string;
      parentMessageId: string | null;
      attachmentIds: string[];
    }) => {
      const optimisticId = `optimistic-${Date.now()}`;
      const optimistic: Message = {
        id: optimisticId,
        conversation_id: convId,
        request_id: optimisticId,
        parent_message_id: parentMessageId,
        role: 'user',
        content: [{ type: 'text', text }],
        tool_calls: null,
        tool_call_id: null,
        tool_name: null,
        provider_snapshot: null,
        input_tokens: null,
        output_tokens: null,
        cost_usd: null,
        latency_ms: null,
        finish_reason: null,
        created_at: new Date().toISOString(),
      };
      qc.setQueryData<Message[]>(['messages', convId], (prev = []) => [...prev, optimistic]);
      // Flip the active branch immediately so the message list re-renders on
      // the newly-edited path instead of the old chain while streaming.
      qc.setQueryData<Conversation>(['conversation', convId], (prev) =>
        prev ? { ...prev, active_leaf_message_id: optimisticId } : prev,
      );
      await send(convId, text, parentMessageId ?? undefined, attachmentIds);
    },
  });

  function handleMessageAction(action: MessageAction) {
    const allMessages = messages.data ?? [];

    if (action.type === 'edit-submit') {
      branchSend.mutate({
        text: action.text,
        parentMessageId: action.message.parent_message_id,
        attachmentIds: imageAttachmentIds(action.message),
      });
    }

    if (action.type === 'branch') {
      // Assistant message: find its parent user message and resend that text
      // (and any attached images) immediately — no composer step, no retyping.
      let parentId: string | null = null;
      let text = '';
      let attachmentIds: string[] = [];

      if (action.message.role === 'assistant') {
        const parentUserMsg = allMessages.find((m) => m.id === action.message.parent_message_id);
        if (parentUserMsg) {
          text = contentText(parentUserMsg);
          parentId = parentUserMsg.parent_message_id;
          attachmentIds = imageAttachmentIds(parentUserMsg);
        }
      } else {
        text = contentText(action.message);
        parentId = action.message.parent_message_id;
        attachmentIds = imageAttachmentIds(action.message);
      }
      if (text || attachmentIds.length > 0) branchSend.mutate({ text, parentMessageId: parentId, attachmentIds });
    }

    if (action.type === 'delete') {
      qc.setQueryData<Message[]>(['messages', convId], (prev) => (prev ?? []).filter((m) => m.id !== action.message.id));
      api(`/conversations/${convId}/messages/${action.message.id}`, { method: 'DELETE' })
        .then(() => qc.invalidateQueries({ queryKey: ['messages', convId] }))
        .catch(() => {
          toast.error('Could not delete message');
          qc.invalidateQueries({ queryKey: ['messages', convId] });
        });
    }

    if (action.type === 'switch-branch') {
      const leafId = action.leafMessageId;
      // Point the conversation cache at the requested leaf right away so
      // the message list reflects the flip without waiting on the server.
      qc.setQueryData<Conversation>(['conversation', convId], (prev) =>
        prev ? { ...prev, active_leaf_message_id: leafId } : prev,
      );
      api(`/conversations/${convId}/switch-branch?leaf_message_id=${encodeURIComponent(leafId)}`, {
        method: 'POST',
      })
        .then(() => qc.invalidateQueries({ queryKey: ['conversation', convId] }))
        .catch(() => {
          toast.error('Could not switch branch');
          qc.invalidateQueries({ queryKey: ['conversation', convId] });
        });
    }
  }

  const { user } = useAuthStore();

  // ── share ─────────────────────────────────────────────────────────
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const shareMutation = useMutation({
    mutationFn: () =>
      api<{ slug: string; url_path: string }>(`/conversations/${convId}/share`, { method: 'POST' }),
    onSuccess: (data) => {
      const full = `${window.location.origin}${data.url_path}`;
      setShareUrl(full);
      navigator.clipboard.writeText(full).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        toast.success('Share link copied to clipboard');
      }).catch(() => {
        toast.success(`Share link: ${full}`);
      });
    },
    onError: (err: Error) => toast.error(err.message || 'Could not create share link'),
  });

  // ── rename ────────────────────────────────────────────────────────
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingTitle) titleInputRef.current?.select();
  }, [editingTitle]);

  const renameMutation = useMutation({
    mutationFn: (nextTitle: string) =>
      api<Conversation>(`/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: nextTitle }),
      }),
    onSuccess: (data) => {
      qc.setQueryData<Conversation>(['conversation', convId], () => data);
      qc.invalidateQueries({ queryKey: ['conversations'] });
      setEditingTitle(false);
      toast.success('Chat renamed');
    },
    onError: (err: Error) => toast.error(err.message || 'Could not rename chat'),
  });

  function startRename() {
    setTitleDraft(title === 'New conversation' ? '' : title);
    setEditingTitle(true);
  }

  function commitRename() {
    const next = titleDraft.trim();
    if (!next || next === title) {
      setEditingTitle(false);
      return;
    }
    renameMutation.mutate(next);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-canvas">
      {/* Navbar */}
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-hairline bg-canvas px-4 sm:px-5">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <PageHamburger />
          <a href="/app">
            <Logo size={20} wordmarkClassName="hidden sm:inline" />
          </a>
          {title && (
            <>
              <span className="hidden text-base text-muted-soft sm:inline">/</span>
              {editingTitle ? (
                <input
                  ref={titleInputRef}
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      commitRename();
                    } else if (e.key === 'Escape') {
                      e.preventDefault();
                      setEditingTitle(false);
                    }
                  }}
                  autoFocus
                  disabled={renameMutation.isPending}
                  className="h-7 min-w-0 flex-shrink rounded-md border border-hairline bg-surface-card px-2 text-sm text-ink outline-none transition-colors duration-160 ease-out focus:border-primary/60 focus-visible:outline-none"
                  aria-label="Rename chat"
                />
              ) : (
                <button
                  type="button"
                  onClick={startRename}
                  title="Rename chat"
                  className="group/title flex min-w-0 flex-shrink items-center gap-1.5 rounded-md px-1 py-0.5 transition-colors duration-160 ease-out hover:bg-surface-card"
                >
                  <span className="min-w-0 truncate text-sm text-body group-hover/title:text-ink">
                    {title}
                  </span>
                  <Pencil
                    size={12}
                    className="shrink-0 text-muted-soft opacity-0 transition-opacity duration-160 ease-out group-hover/title:opacity-100"
                  />
                </button>
              )}
            </>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <span className="hidden lg:inline-block">
            <ConversationUsageBadge usage={liveUsage} streaming={streaming} />
          </span>
          <button
            onClick={() => shareMutation.mutate()}
            disabled={shareMutation.isPending}
            className="hidden h-8 items-center gap-1.5 rounded-md border border-hairline bg-canvas px-2.5 text-[13px] text-body transition-colors duration-160 ease-out hover:bg-surface-card hover:text-ink disabled:opacity-50 sm:flex"
          >
            {copied ? <Check size={13} className="text-green-600" /> : <Share size={13} />}
            {shareMutation.isPending ? 'Sharing…' : copied ? 'Copied!' : 'Share'}
          </button>
          <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-active text-xs font-semibold text-white">
            {user?.display_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
        </div>
      </div>

      {/* Message list */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="pb-4 pt-8">
          {messages.isPending ? (
            <div className="px-4 text-center text-sm text-muted-soft">Loading…</div>
          ) : (messages.data?.length ?? 0) === 0 && !streaming ? (
            <div className="mt-16 px-4 text-center text-sm text-muted-soft">Start the conversation below</div>
          ) : (
            <MessageList
              messages={messages.data || []}
              streaming={streaming}
              streamText={streamText}
              activeLeafId={conversation.data?.active_leaf_message_id}
              onAction={handleMessageAction}
            />
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="flex-none border-t border-hairline bg-canvas/95 backdrop-blur-md">
        <div className="mx-auto w-full max-w-[760px] px-3 pb-3 pt-2.5 sm:px-5">
          <ChatComposer
            onSend={(t, attachmentIds) => optimisticSend.mutate({ text: t, attachmentIds })}
            onCancel={cancel}
            streaming={streaming}
            activeTools={activeAllTools.filter((t) => currentToolIds.has(t.id))}
            availableTools={activeAllTools}
            onToggleTool={(toolId) => toggleTool.mutate(toolId)}
            activeMcp={activeAllMcp.filter((s) => currentMcpIds.has(s.id))}
            availableMcp={activeAllMcp}
            onToggleMcp={(mcpId) => toggleMcp.mutate(mcpId)}
            models={activeModels}
            modelId={currentModelId}
            onModelChange={(id) => switchModel.mutate(id)}
          />
          <div className="mt-2 text-center text-[11px] text-muted-soft">AI can make mistakes. Read about our privacy.</div>
        </div>
      </div>
    </div>
  );
}
