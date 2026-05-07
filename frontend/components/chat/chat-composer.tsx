'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Mic, Square } from 'lucide-react';
import { toast } from 'sonner';
import { ApiError, uploadFile, deleteAttachment } from '@/lib/api';
import { ComposerAttachMenu } from './composer-attach-menu';
import { ComposerModelSelect } from './composer-model-select';
import { AttachmentChip, type PendingAttachment } from './attachment-chip';
import type { CustomTool, McpServer, ProviderModel } from '@/lib/types';

type Props = {
  onSend: (text: string, attachmentIds: string[]) => void;
  onCancel: () => void;
  streaming: boolean;
  disabled?: boolean;
  /** Set (and bump a new value into) to programmatically fill the input — e.g. suggestion chips */
  prefill?: string;
  /** Tools enabled for this conversation */
  activeTools?: CustomTool[];
  /** All available tools (for the attach menu) */
  availableTools?: CustomTool[];
  onToggleTool?: (toolId: string) => void;
  /** MCP servers enabled for this conversation */
  activeMcp?: McpServer[];
  /** All available MCP servers (for the attach menu) */
  availableMcp?: McpServer[];
  onToggleMcp?: (id: string) => void;
  /** Model picker docked at the bottom of the composer */
  models?: ProviderModel[];
  modelId?: string;
  onModelChange?: (id: string) => void;
};

let localIdCounter = 0;

export function ChatComposer({
  onSend,
  onCancel,
  streaming,
  disabled,
  prefill,
  activeTools = [],
  availableTools = [],
  onToggleTool,
  activeMcp = [],
  availableMcp = [],
  onToggleMcp,
  models = [],
  modelId,
  onModelChange,
}: Props) {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const removedWhileUploading = useRef<Set<string>>(new Set());

  const currentModel = models.find((m) => m.id === modelId);

  useEffect(() => {
    if (prefill === undefined) return;
    setText(prefill);
    setTimeout(() => {
      if (ref.current) {
        ref.current.style.height = 'auto';
        ref.current.style.height = `${Math.min(ref.current.scrollHeight, 200)}px`;
        ref.current.focus();
      }
    }, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  // Revoke local preview URLs on unmount to avoid leaking memory.
  useEffect(() => {
    return () => {
      attachments.forEach((a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      const isImage = file.type.startsWith('image/');
      if (isImage && currentModel && !currentModel.supports_vision) {
        toast.warning(`${currentModel.name} doesn't support image input — it'll only see the filename.`);
      }
      const localId = `pending-${++localIdCounter}`;
      const pending: PendingAttachment = {
        localId,
        file,
        previewUrl: isImage ? URL.createObjectURL(file) : null,
        status: 'uploading',
      };
      setAttachments((prev) => [...prev, pending]);

      try {
        const uploaded = await uploadFile(file);
        if (removedWhileUploading.current.has(localId)) {
          removedWhileUploading.current.delete(localId);
          deleteAttachment(uploaded.id).catch(() => undefined);
          continue;
        }
        setAttachments((prev) =>
          prev.map((a) => (a.localId === localId ? { ...a, status: 'done', id: uploaded.id } : a)),
        );
      } catch (err) {
        removedWhileUploading.current.delete(localId);
        const message = err instanceof ApiError ? err.message : 'Upload failed';
        setAttachments((prev) => prev.map((a) => (a.localId === localId ? { ...a, status: 'error', error: message } : a)));
      }
    }
  }

  function removeAttachment(localId: string) {
    setAttachments((prev) => {
      const target = prev.find((a) => a.localId === localId);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      if (target?.status === 'uploading') removedWhileUploading.current.add(localId);
      if (target?.status === 'done' && target.id) deleteAttachment(target.id).catch(() => undefined);
      return prev.filter((a) => a.localId !== localId);
    });
  }

  const uploading = attachments.some((a) => a.status === 'uploading');

  function submit() {
    const t = text.trim();
    const readyIds = attachments.filter((a) => a.status === 'done' && a.id).map((a) => a.id as string);
    if ((!t && readyIds.length === 0) || streaming || disabled || uploading) return;
    onSend(t, readyIds);
    setText('');
    attachments.forEach((a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl));
    setAttachments([]);
    if (ref.current) ref.current.style.height = 'auto';
  }

  return (
    <div className="w-full rounded-2xl border border-hairline bg-surface-soft shadow-card transition-colors duration-160 ease-out focus-within:border-primary/40">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          handleFilesSelected(e.target.files);
          e.target.value = '';
        }}
      />

      {attachments.length > 0 && (
        <div className="flex gap-2 overflow-x-auto px-4 pt-3.5">
          {attachments.map((a) => (
            <AttachmentChip key={a.localId} attachment={a} onRemove={() => removeAttachment(a.localId)} />
          ))}
        </div>
      )}

      <div className="px-4 pt-3.5">
        <textarea
          ref={ref}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            e.currentTarget.style.height = 'auto';
            e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 200)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={streaming ? 'AI is responding…' : 'Ask anything'}
          disabled={disabled || streaming}
          rows={1}
          className="max-h-[200px] min-h-[24px] w-full resize-none bg-transparent font-sans text-[15px] leading-normal text-ink outline-none placeholder:text-muted-soft"
        />
      </div>

      <div className="flex items-center gap-1 px-2.5 pb-2.5 pt-2.5">
        <ComposerAttachMenu
          onAddFiles={() => fileInputRef.current?.click()}
          tools={availableTools}
          enabledToolIds={new Set(activeTools.map((t) => t.id))}
          onToggleTool={onToggleTool ?? (() => {})}
          mcpServers={availableMcp}
          enabledMcpIds={new Set(activeMcp.map((s) => s.id))}
          onToggleMcp={onToggleMcp ?? (() => {})}
        />

        <div className="flex-1" />

        <ComposerModelSelect models={models} value={modelId ?? ''} onChange={(id) => onModelChange?.(id)} />

        <button
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted transition-[background-color,color,transform] duration-160 ease-out hover:bg-surface-card hover:text-ink active:scale-[0.94]"
          aria-label="Voice input"
        >
          <Mic size={14} />
        </button>

        <AnimatePresence mode="wait" initial={false}>
          {streaming ? (
            <motion.button
              key="stop"
              onClick={onCancel}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ duration: 0.15, ease: [0.23, 1, 0.32, 1] }}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-hairline bg-surface-card text-body transition-colors duration-160 hover:text-ink"
              aria-label="Stop generating"
            >
              <Square size={11} fill="currentColor" />
            </motion.button>
          ) : (
            <motion.button
              key="send"
              onClick={submit}
              disabled={(!text.trim() && attachments.length === 0) || disabled || uploading}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              transition={{ duration: 0.15, ease: [0.23, 1, 0.32, 1] }}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground transition-[opacity,transform] duration-160 ease-out hover:bg-primary-active active:scale-[0.94] disabled:opacity-30"
              aria-label="Send message"
            >
              <ArrowUp size={15} />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
