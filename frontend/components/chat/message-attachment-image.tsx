'use client';

import { useEffect, useState } from 'react';
import { fetchAttachmentBlobUrl } from '@/lib/api';

/** Renders a stored `attachment://{id}` image reference — fetched with auth and shown as a blob URL. */
export function MessageAttachmentImage({ attachmentId }: { attachmentId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let blobUrl: string | null = null;
    let cancelled = false;
    fetchAttachmentBlobUrl(attachmentId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        blobUrl = url;
        setSrc(url);
      })
      .catch(() => setError(true));
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [attachmentId]);

  if (error) return null;
  if (!src) return <div className="h-40 w-40 animate-pulse rounded-lg bg-surface-card" />;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="Attached image" className="max-h-64 max-w-full rounded-lg border border-hairline object-cover" />
  );
}
