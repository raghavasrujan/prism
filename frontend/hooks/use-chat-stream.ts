'use client';

import { useCallback, useRef, useState } from 'react';
import { startStream } from '@/lib/sse';
import type { Message } from '@/lib/types';

export type StreamState = {
  streaming: boolean;
  streamText: string;
  currentRequestId: string | null;
  lastUsage: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    message_id: string | null;
    latency_ms: number | null;
  } | null;
  error: string | null;
};

/**
 * Streams a chat turn via SSE with smooth token-by-token rendering.
 *
 * Tokens are accumulated in a `useRef` buffer and flushed to React state via
 * `requestAnimationFrame` (≤ 60 fps).  This avoids two problems:
 *
 * 1. React 18 automatic batching – multiple `setState` calls inside an async
 *    callback are batched into one render, so without rAF the text only
 *    appears after the full response arrives.
 * 2. Excessive re-renders – calling `setState` per token (hundreds per
 *    second) would saturate the React scheduler.
 */
export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);
  const [lastUsage, setLastUsage] = useState<StreamState['lastUsage']>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Accumulated token text — updated without triggering renders.
  const _buf = useRef('');
  // rAF handle — 0 means no frame is scheduled.
  const _raf = useRef<number>(0);

  /** Push the current buffer to React state on the next animation frame. */
  const _scheduleFlush = useCallback(() => {
    if (_raf.current) return; // frame already pending
    if (typeof requestAnimationFrame === 'undefined') {
      // SSR / non-browser fallback: flush synchronously.
      setStreamText(_buf.current);
      return;
    }
    _raf.current = requestAnimationFrame(() => {
      setStreamText(_buf.current);
      _raf.current = 0;
    });
  }, []);

  /** Cancel any pending rAF and force an immediate flush. */
  const _flushNow = useCallback(() => {
    if (_raf.current) {
      if (typeof cancelAnimationFrame !== 'undefined') cancelAnimationFrame(_raf.current);
      _raf.current = 0;
    }
    setStreamText(_buf.current);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    if (currentRequestId) {
      // Fire-and-forget cancel signal
      fetch(`/api/v1/messages/${currentRequestId}/cancel`, {
        method: 'POST',
        headers: {
          authorization: `Bearer ${sessionStorage.getItem('agent_ui_access') || ''}`,
        },
      }).catch(() => undefined);
    }
  }, [currentRequestId]);

  const send = useCallback(
    async (
      conversationId: string,
      content: string,
      parentMessageId?: string,
      attachmentIds?: string[],
      onEvent?: (ev: { event: string; data: unknown }) => void,
    ) => {
      // Reset state for the new turn.
      setError(null);
      setLastUsage(null);
      setStreaming(true);
      _flushNow();          // cancel any pending frame from previous turn
      _buf.current = '';
      setStreamText('');

      const controller = new AbortController();
      abortRef.current = controller;

      await startStream({
        path: `/conversations/${conversationId}/messages/stream`,
        body: {
          content,
          ...(parentMessageId ? { parent_message_id: parentMessageId } : {}),
          ...(attachmentIds && attachmentIds.length > 0 ? { attachment_ids: attachmentIds } : {}),
        },
        signal: controller.signal,
        onEvent: (ev) => {
          onEvent?.(ev);
          switch (ev.event) {
            case 'stream.start': {
              const rid = (ev.data as { request_id?: string })?.request_id;
              if (rid) setCurrentRequestId(rid);
              break;
            }
            case 'token': {
              // Accumulate in ref → schedule one rAF render rather than one
              // setState per token.  This is the key fix for smooth streaming.
              const delta = (ev.data as { delta?: string })?.delta ?? '';
              _buf.current += delta;
              _scheduleFlush();
              break;
            }
            case 'usage': {
              setLastUsage(ev.data as StreamState['lastUsage']);
              break;
            }
            case 'error': {
              setError((ev.data as { message?: string })?.message || 'error');
              break;
            }
          }
        },
        onError: (err) => {
          setError((err as Error)?.message ?? 'stream error');
        },
      });

      // Stream finished: cancel any pending frame and do a final synchronous
      // flush so the complete text is visible even if the last rAF hasn't
      // fired yet.
      _flushNow();
      setStreaming(false);
      setCurrentRequestId(null);
      abortRef.current = null;
    },
    [_scheduleFlush, _flushNow],
  );

  const clearStreamText = useCallback(() => {
    _flushNow();
    _buf.current = '';
    setStreamText('');
  }, [_flushNow]);


  return {
    streaming,
    streamText,
    currentRequestId,
    lastUsage,
    error,
    send,
    cancel,
    clearStreamText,
  } as const;
}

/** Helper for inserting a synthetic streaming assistant message into a list. */
export function makeStreamingPlaceholder(conversationId: string, text: string): Message {
  return {
    id: '__streaming__',
    conversation_id: conversationId,
    request_id: '__streaming__',
    parent_message_id: null,
    role: 'assistant',
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
}
