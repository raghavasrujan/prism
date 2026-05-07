'use client';

import { ArrowDown, ArrowUp, Clock, DollarSign } from 'lucide-react';
import { formatCost, formatDuration, formatTokens } from '@/lib/utils';

type Props = {
  inputTokens: number | null | undefined;
  outputTokens: number | null | undefined;
  costUsd: number | null | undefined;
  latencyMs: number | null | undefined;
  providerSnapshot: string | null | undefined;
};

export function MessageUsageChip({ inputTokens, outputTokens, costUsd, latencyMs }: Props) {
  const hasAny = inputTokens != null || outputTokens != null || costUsd != null || latencyMs != null;
  if (!hasAny) return null;

  return (
    <div
      tabIndex={0}
      aria-label="Token usage"
      className={[
        'absolute right-3 top-0 hidden max-w-[calc(100vw-32px)] items-center gap-1.5 whitespace-nowrap',
        'rounded-full border border-hairline bg-canvas/90 px-2.5 py-1 font-mono text-[11px] text-muted-soft backdrop-blur-md',
        'opacity-0 translate-x-1 transition-[opacity,transform] duration-160 ease-out pointer-events-none',
        'group-hover/row:opacity-100 group-hover/row:translate-x-0 group-hover/row:pointer-events-auto',
        'focus-visible:opacity-100 sm:flex',
      ].join(' ')}
    >
      {inputTokens != null && (
        <>
          <ArrowUp size={10} />
          {formatTokens(inputTokens)}
        </>
      )}
      {outputTokens != null && (
        <>
          <span className="opacity-40">·</span>
          <ArrowDown size={10} />
          {formatTokens(outputTokens)}
        </>
      )}
      {costUsd != null && (
        <>
          <span className="opacity-40">·</span>
          <DollarSign size={10} />
          {formatCost(costUsd).replace('$', '')}
        </>
      )}
      {latencyMs != null && latencyMs > 1000 && (
        <>
          <span className="opacity-40">·</span>
          <Clock size={10} />
          {formatDuration(latencyMs)}
        </>
      )}
    </div>
  );
}
