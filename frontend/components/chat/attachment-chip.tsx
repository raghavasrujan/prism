'use client';

import { File as FileIcon, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type PendingAttachment = {
  localId: string;
  file: File;
  previewUrl: string | null;
  status: 'uploading' | 'done' | 'error';
  id?: string; // set once uploaded
  error?: string;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export function AttachmentChip({ attachment, onRemove }: { attachment: PendingAttachment; onRemove: () => void }) {
  const isImage = attachment.file.type.startsWith('image/');

  return (
    <div
      className={cn(
        'group/chip relative flex shrink-0 items-center gap-2 overflow-hidden rounded-lg border bg-canvas pr-2 transition-colors duration-160 ease-out',
        attachment.status === 'error' ? 'border-danger/40' : 'border-hairline',
      )}
    >
      {isImage && attachment.previewUrl ? (
        <img src={attachment.previewUrl} alt={attachment.file.name} className="h-11 w-11 shrink-0 object-cover" />
      ) : (
        <div className="flex h-11 w-11 shrink-0 items-center justify-center bg-surface-card text-muted">
          <FileIcon size={16} />
        </div>
      )}

      <div className="min-w-0 py-1.5">
        <div className="max-w-[120px] truncate text-xs text-ink">{attachment.file.name}</div>
        <div className={cn('text-[11px]', attachment.status === 'error' ? 'text-danger' : 'text-muted-soft')}>
          {attachment.status === 'error' ? attachment.error || 'Upload failed' : formatSize(attachment.file.size)}
        </div>
      </div>

      {attachment.status === 'uploading' && (
        <div className="absolute inset-0 flex items-center justify-center bg-canvas/60">
          <Loader2 size={16} className="animate-spin text-muted" />
        </div>
      )}

      <button
        onClick={onRemove}
        aria-label="Remove attachment"
        className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-ink/70 text-white opacity-80 transition-opacity duration-120 ease-out hover:opacity-100"
      >
        <X size={10} />
      </button>
    </div>
  );
}
