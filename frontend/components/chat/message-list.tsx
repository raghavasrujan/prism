'use client';

import { motion } from 'framer-motion';
import { ChevronDown, ChevronLeft, ChevronRight, Clock, Copy, GitBranch, PenLine, Sparkle, Terminal, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { TypingAnimation } from '@/components/ui/typing-animation';
import type { Message } from '@/lib/types';
import { MessageAttachmentImage } from './message-attachment-image';
import { MessageUsageChip } from './message-usage-chip';

export type MessageAction =
  | { type: 'branch'; message: Message }
  | { type: 'delete'; message: Message }
  | { type: 'edit-submit'; message: Message; text: string }
  | { type: 'switch-branch'; leafMessageId: string };

type Props = {
  messages: Message[];
  streaming: boolean;
  streamText: string;
  activeLeafId?: string | null;
  onAction?: (action: MessageAction) => void;
};

export function contentText(msg: Message): string {
  return msg.content.map((p) => (p.type === 'text' ? p.text : '')).join('');
}

/** Extracts attachment ids from `attachment://{id}` image_url parts. */
export function imageAttachmentIds(msg: Message): string[] {
  return msg.content
    .filter((p): p is Extract<Message['content'][number], { type: 'image_url' }> => p.type === 'image_url')
    .map((p) => p.image_url.url)
    .filter((url) => url.startsWith('attachment://'))
    .map((url) => url.slice('attachment://'.length));
}

// ── Message grouping ─────────────────────────────────────────────────────────
// Groups messages into: user | ai-turn (thinking+tool calls) | assistant response

type Group =
  | { kind: 'user'; message: Message }
  | { kind: 'ai-turn'; thinkingMsg: Message | null; toolMessages: Message[]; latencyMs: number }
  | { kind: 'response'; message: Message };

function groupMessages(messages: Message[]): Group[] {
  const groups: Group[] = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    if (msg.role === 'user') {
      groups.push({ kind: 'user', message: msg });
      i++;
      continue;
    }
    if (msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0) {
      const thinking = msg;
      const toolMessages: Message[] = [];
      i++;
      while (i < messages.length && messages[i].role === 'tool') {
        toolMessages.push(messages[i]);
        i++;
      }
      groups.push({ kind: 'ai-turn', thinkingMsg: thinking, toolMessages, latencyMs: thinking.latency_ms ?? 0 });
      continue;
    }
    if (msg.role === 'tool') {
      const toolMessages: Message[] = [msg];
      i++;
      while (i < messages.length && messages[i].role === 'tool') {
        toolMessages.push(messages[i]);
        i++;
      }
      groups.push({ kind: 'ai-turn', thinkingMsg: null, toolMessages, latencyMs: 0 });
      continue;
    }
    groups.push({ kind: 'response', message: msg });
    i++;
  }
  return groups;
}

const rowMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.28, ease: [0.23, 1, 0.32, 1] as const },
};

// ── Branch computation ──────────────────────────────────────────────────────
// Given the flat list of every message in the conversation plus the current
// `active_leaf_message_id`, work out which chain of messages we should render
// and, for each user message that has been re-edited, how many siblings exist
// so we can offer the "< N/M >" navigator.

export type SiblingInfo = {
  siblingLeafIds: string[]; // one leaf id per sibling, ordered by created_at
  index: number; // 0-based index of the current message within siblingLeafIds
  total: number; // === siblingLeafIds.length
};

function computeBranchView(
  messages: Message[],
  activeLeafId: string | null | undefined,
): { activeMessages: Message[]; siblingByUserMsgId: Map<string, SiblingInfo> } {
  if (messages.length === 0) {
    return { activeMessages: [], siblingByUserMsgId: new Map() };
  }

  const byId = new Map(messages.map((m) => [m.id, m]));
  const childrenByParent = new Map<string | null, Message[]>();
  for (const m of messages) {
    const arr = childrenByParent.get(m.parent_message_id) ?? [];
    arr.push(m);
    childrenByParent.set(m.parent_message_id, arr);
  }
  for (const arr of childrenByParent.values()) {
    arr.sort((a, b) => a.created_at.localeCompare(b.created_at));
  }

  // Follow "latest child" from a node down to a leaf.
  function walkToLeaf(startId: string): string {
    let node = startId;
    while (true) {
      const kids = childrenByParent.get(node);
      if (!kids || kids.length === 0) return node;
      node = kids[kids.length - 1].id;
    }
  }

  // Determine effective leaf: honor `activeLeafId` when valid; otherwise
  // fall back to the newest tail node.
  let leafId: string | null = null;
  if (activeLeafId && byId.has(activeLeafId)) {
    leafId = activeLeafId;
  } else {
    const sorted = [...messages].sort((a, b) => a.created_at.localeCompare(b.created_at));
    leafId = sorted[sorted.length - 1].id;
  }

  // Walk up parent chain to build the active path (root → leaf).
  const activeIds = new Set<string>();
  const activePath: Message[] = [];
  let cursor: string | null = leafId;
  while (cursor) {
    const node = byId.get(cursor);
    if (!node) break;
    activeIds.add(cursor);
    activePath.push(node);
    cursor = node.parent_message_id;
  }
  activePath.reverse();

  // Sibling info: for every user message on the active path, look up its
  // siblings sharing the same parent. Skip when only one sibling.
  const siblingByUserMsgId = new Map<string, SiblingInfo>();
  for (const m of activePath) {
    if (m.role !== 'user') continue;
    const siblings = (childrenByParent.get(m.parent_message_id) ?? []).filter(
      (s) => s.role === 'user',
    );
    if (siblings.length <= 1) continue;
    const idx = siblings.findIndex((s) => s.id === m.id);
    const leafIds = siblings.map((s) => walkToLeaf(s.id));
    siblingByUserMsgId.set(m.id, {
      siblingLeafIds: leafIds,
      index: idx < 0 ? 0 : idx,
      total: siblings.length,
    });
  }

  return { activeMessages: activePath, siblingByUserMsgId };
}

// ── Branch selector control ─────────────────────────────────────────────────

function BranchSwitcher({
  info,
  onSelect,
}: {
  info: SiblingInfo;
  onSelect: (leafId: string) => void;
}) {
  const canPrev = info.index > 0;
  const canNext = info.index < info.total - 1;
  return (
    <div className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-soft">
      <button
        type="button"
        disabled={!canPrev}
        onClick={() => canPrev && onSelect(info.siblingLeafIds[info.index - 1])}
        className="flex h-5 w-5 items-center justify-center rounded transition-colors duration-120 ease-out hover:bg-surface-card hover:text-ink disabled:pointer-events-none disabled:opacity-30"
        title="Previous version"
      >
        <ChevronLeft size={12} />
      </button>
      <span className="tabular-nums">
        {info.index + 1}/{info.total}
      </span>
      <button
        type="button"
        disabled={!canNext}
        onClick={() => canNext && onSelect(info.siblingLeafIds[info.index + 1])}
        className="flex h-5 w-5 items-center justify-center rounded transition-colors duration-120 ease-out hover:bg-surface-card hover:text-ink disabled:pointer-events-none disabled:opacity-30"
        title="Next version"
      >
        <ChevronRight size={12} />
      </button>
    </div>
  );
}

function AIAvatar() {
  return (
    <div className="mt-0.5 flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
      <Sparkle size={13} fill="currentColor" />
    </div>
  );
}

// ── Inline message editing — edits happen in place, not in the composer ──────
function EditableUserBubble({
  initialText,
  onSubmit,
  onCancel,
}: {
  initialText: string;
  onSubmit: (text: string) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(initialText);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);

  function submit() {
    const t = text.trim();
    if (t) onSubmit(t);
  }

  return (
    <div className="w-full max-w-[85%] sm:max-w-[80%]">
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          e.currentTarget.style.height = 'auto';
          e.currentTarget.style.height = `${e.currentTarget.scrollHeight}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
          if (e.key === 'Escape') onCancel();
        }}
        rows={1}
        className="max-h-[300px] w-full resize-none rounded-2xl border border-primary/50 bg-surface-card px-4 py-2.5 font-sans text-[15px] leading-relaxed text-ink outline-none transition-colors duration-160 ease-out focus:border-primary"
      />
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" disabled={!text.trim()} onClick={submit}>
          Save &amp; submit
        </Button>
      </div>
    </div>
  );
}

function ActionBtn({
  onClick,
  title,
  icon: Icon,
  danger = false,
}: {
  onClick: () => void;
  title: string;
  icon: React.ComponentType<{ size?: number }>;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        'flex h-7 w-7 items-center justify-center rounded-md text-muted-soft transition-colors duration-120 ease-out',
        danger ? 'hover:bg-danger/10 hover:text-danger' : 'hover:bg-surface-card hover:text-ink',
      )}
    >
      <Icon size={13} />
    </button>
  );
}

function ToolCallRow({ message }: { message: Message }) {
  const [expanded, setExpanded] = useState(false);
  const result = contentText(message);
  const toolName = message.tool_name || 'tool';

  let parsedResult: string = result;
  try {
    parsedResult = JSON.stringify(JSON.parse(result), null, 2);
  } catch {
    /* keep raw */
  }

  return (
    <div className="mb-0.5">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left transition-colors duration-120 ease-out hover:bg-surface-card"
      >
        {expanded ? (
          <ChevronDown size={12} className="shrink-0 text-muted-soft" />
        ) : (
          <ChevronRight size={12} className="shrink-0 text-muted-soft" />
        )}
        <Terminal size={12} className="shrink-0 text-muted-soft" />
        <span className="font-mono text-[13px] font-medium text-body">{toolName}</span>
        {!expanded && (
          <span className="flex-1 truncate font-mono text-xs text-muted-soft">{result}</span>
        )}
      </button>
      {expanded && (
        <div className="ml-8 mr-3 mb-1.5 mt-0.5 border-l-2 border-hairline pl-3">
          <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-surface-card px-2.5 py-2 font-mono text-xs text-body">
            {parsedResult}
          </pre>
        </div>
      )}
    </div>
  );
}

function AIActionsBlock({
  thinkingMsg,
  toolMessages,
  latencyMs,
}: {
  thinkingMsg: Message | null;
  toolMessages: Message[];
  latencyMs: number;
}) {
  const [open, setOpen] = useState(false);
  const secs = latencyMs > 0 ? (latencyMs / 1000).toFixed(1) : null;
  const label = secs ? `Thought for ${secs}s` : `Used ${toolMessages.length} tool${toolMessages.length !== 1 ? 's' : ''}`;

  return (
    <div className="overflow-hidden rounded-lg border border-dashed border-hairline text-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-muted transition-colors duration-120 ease-out hover:bg-surface-soft"
      >
        {open ? <ChevronDown size={12} className="shrink-0" /> : <ChevronRight size={12} className="shrink-0" />}
        <Clock size={12} className="shrink-0" />
        <span>{label}</span>
      </button>
      {open && (
        <div className="border-t border-hairline">
          <div className="py-1">
            {toolMessages.map((tm) => (
              <ToolCallRow key={tm.id} message={tm} />
            ))}
          </div>
          {secs && (
            <div className="border-t border-hairline px-3 py-1.5 text-xs text-muted-soft">Worked for {secs}s</div>
          )}
        </div>
      )}
    </div>
  );
}

export function MessageList({ messages, streaming, streamText, activeLeafId, onAction }: Props) {
  const { activeMessages, siblingByUserMsgId } = useMemo(
    () => computeBranchView(messages, activeLeafId),
    [messages, activeLeafId],
  );
  const groups = groupMessages(activeMessages);

  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-5 pb-6">
      {groups.map((group, idx) => {
        if (group.kind === 'user') {
          const msg = group.message;

          if (editingId === msg.id) {
            return (
              <motion.div key={msg.id} {...rowMotion} className="mx-auto w-full max-w-[760px] px-4 sm:px-6">
                <div className="flex justify-end">
                  <EditableUserBubble
                    initialText={contentText(msg)}
                    onCancel={() => setEditingId(null)}
                    onSubmit={(text) => {
                      setEditingId(null);
                      onAction?.({ type: 'edit-submit', message: msg, text });
                    }}
                  />
                </div>
              </motion.div>
            );
          }

          const imageIds = imageAttachmentIds(msg);

          return (
            <motion.div key={msg.id} {...rowMotion} className="group/row mx-auto w-full max-w-[760px] px-4 sm:px-6">
              <div className="flex justify-end">
                <div className="flex max-w-full flex-col items-end gap-1.5">
                  {imageIds.length > 0 && (
                    <div className="flex flex-wrap justify-end gap-2">
                      {imageIds.map((id) => (
                        <MessageAttachmentImage key={id} attachmentId={id} />
                      ))}
                    </div>
                  )}
                  {contentText(msg) && (
                    <div className="inline-block max-w-full rounded-2xl border border-hairline bg-surface-card px-4 py-2.5 text-[15px] leading-relaxed text-ink">
                      {contentText(msg)}
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    {siblingByUserMsgId.get(msg.id) && (
                      <BranchSwitcher
                        info={siblingByUserMsgId.get(msg.id)!}
                        onSelect={(leafId) => onAction?.({ type: 'switch-branch', leafMessageId: leafId })}
                      />
                    )}
                    <div className="flex gap-0.5 opacity-0 transition-opacity duration-160 ease-out group-hover/row:opacity-100">
                      <ActionBtn
                        onClick={() => navigator.clipboard.writeText(contentText(msg)).then(() => toast.success('Copied'))}
                        title="Copy"
                        icon={Copy}
                      />
                      {onAction && (
                        <ActionBtn onClick={() => setEditingId(msg.id)} title="Edit & resend" icon={PenLine} />
                      )}
                      {onAction && (
                        <ActionBtn onClick={() => onAction({ type: 'delete', message: msg })} title="Delete" icon={Trash2} danger />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          );
        }

        if (group.kind === 'ai-turn') {
          return (
            <motion.div key={`ai-turn-${idx}`} {...rowMotion} className="mx-auto w-full max-w-[760px] px-4 sm:px-6">
              <div className="flex gap-3">
                <AIAvatar />
                <div className="min-w-0 flex-1 pt-0.5">
                  <AIActionsBlock thinkingMsg={group.thinkingMsg} toolMessages={group.toolMessages} latencyMs={group.latencyMs} />
                </div>
              </div>
            </motion.div>
          );
        }

        const msg = group.message;
        return (
          <motion.div key={msg.id} {...rowMotion} className="group/row relative mx-auto w-full max-w-[760px] px-4 sm:px-6">
            <div className="flex gap-3">
              <AIAvatar />
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="prose-chat">{contentText(msg)}</div>
                <div className="mt-1.5 flex gap-0.5 opacity-0 transition-opacity duration-160 ease-out group-hover/row:opacity-100">
                  <ActionBtn
                    onClick={() => navigator.clipboard.writeText(contentText(msg)).then(() => toast.success('Copied'))}
                    title="Copy"
                    icon={Copy}
                  />
                  {onAction && (
                    <ActionBtn onClick={() => onAction({ type: 'branch', message: msg })} title="Regenerate" icon={GitBranch} />
                  )}
                  {onAction && (
                    <ActionBtn onClick={() => onAction({ type: 'delete', message: msg })} title="Delete" icon={Trash2} danger />
                  )}
                </div>
              </div>
              <div className="shrink-0 pt-0.5">
                <MessageUsageChip
                  inputTokens={msg.input_tokens}
                  outputTokens={msg.output_tokens}
                  costUsd={msg.cost_usd}
                  latencyMs={msg.latency_ms}
                  providerSnapshot={msg.provider_snapshot}
                />
              </div>
            </div>
          </motion.div>
        );
      })}

      {streaming && (
        <div className="mx-auto flex w-full max-w-[760px] gap-3 px-4 sm:px-6">
          <AIAvatar />
          <div className="prose-chat min-w-0 flex-1 pt-0.5">
            <TypingAnimation>{streamText}</TypingAnimation>
          </div>
        </div>
      )}
    </div>
  );
}
