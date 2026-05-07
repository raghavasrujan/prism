'use client';

import * as Popover from '@radix-ui/react-popover';
import { ArrowDown, ArrowUp, Hash } from 'lucide-react';
import { cn, formatCost, formatTokens } from '@/lib/utils';
import type { ConversationUsage } from '@/lib/types';

type Props = {
  usage: ConversationUsage | null | undefined;
  streaming?: boolean;
};

export function ConversationUsageBadge({ usage, streaming }: Props) {
  if (!usage) return null;

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={cn(
            'inline-flex h-8 items-center gap-2 rounded-full border px-3 font-mono text-xs text-muted-soft',
            'transition-colors duration-160 ease-out',
            streaming ? 'border-teal/30 bg-teal/8' : 'border-hairline bg-surface-soft hover:bg-surface-card',
          )}
        >
          <span className="flex items-center gap-1">
            <ArrowUp size={10} />
            {formatTokens(usage.input_tokens)}
          </span>
          <span className="opacity-40">·</span>
          <span className="flex items-center gap-1">
            <ArrowDown size={10} />
            {formatTokens(usage.output_tokens)}
          </span>
          <span className="opacity-40">·</span>
          <span className="flex items-center gap-1">
            <Hash size={9} />
            {usage.message_count}
          </span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          style={{ transformOrigin: 'var(--radix-popover-content-transform-origin)' }}
          className="z-50 w-64 rounded-lg border border-hairline bg-canvas p-4 text-sm text-body shadow-popover data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95 duration-160 ease-out"
        >
          <div className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-soft">
            Usage · this conversation
          </div>
          <div className="mb-3 grid grid-cols-3 gap-3">
            {[
              { label: 'Input', value: formatTokens(usage.input_tokens) },
              { label: 'Output', value: formatTokens(usage.output_tokens) },
              { label: 'Cost', value: formatCost(usage.cost_usd) },
            ].map(({ label, value }) => (
              <div key={label}>
                <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-soft">{label}</div>
                <div className="font-mono text-[13px] text-ink">{value}</div>
              </div>
            ))}
          </div>
          {usage.by_model.length > 0 && (
            <>
              <div className="my-2 h-px bg-hairline" />
              <div className="mb-2 text-[11px] uppercase tracking-wider text-muted-soft">By model</div>
              {usage.by_model.map((row, i) => (
                <div key={row.model_snapshot ?? i} className="mb-1 flex justify-between gap-3 text-xs">
                  <span className="max-w-[140px] truncate font-mono text-body">
                    {row.model_snapshot || 'unknown'}
                  </span>
                  <span className="shrink-0 text-muted-soft">
                    {formatTokens(row.input_tokens)} / {formatTokens(row.output_tokens)}
                  </span>
                </div>
              ))}
            </>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
