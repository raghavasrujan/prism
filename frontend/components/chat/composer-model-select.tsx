'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProviderModel } from '@/lib/types';

type Props = {
  models: ProviderModel[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
};

/** The model picker docked at the bottom of the composer, Claude-style. */
export function ComposerModelSelect({ models, value, onChange, className }: Props) {
  if (models.length === 0) return null;
  const current = models.find((m) => m.id === value);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[13px] text-body transition-colors duration-160 ease-out',
            'hover:bg-surface-card hover:text-ink',
            className,
          )}
        >
          <span className="max-w-[140px] truncate sm:max-w-[220px]">{current?.name ?? 'Select model'}</span>
          <ChevronDown size={13} className="shrink-0 text-muted-soft" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="top"
          align="end"
          sideOffset={8}
          style={{ transformOrigin: 'var(--radix-dropdown-menu-content-transform-origin)' }}
          className={cn(
            'z-50 w-64 max-h-72 overflow-y-auto rounded-lg border border-hairline bg-canvas p-1 shadow-popover',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0',
            'data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95',
            'duration-160 ease-out',
          )}
        >
          <DropdownMenu.RadioGroup value={value} onValueChange={onChange}>
            {models.map((m) => (
              <DropdownMenu.RadioItem
                key={m.id}
                value={m.id}
                className="relative flex cursor-pointer select-none items-center gap-2.5 rounded-md py-2 pl-8 pr-3 text-sm text-ink outline-none transition-colors duration-120 ease-out data-[highlighted]:bg-surface-card"
              >
                <span className="absolute left-2.5 flex h-3.5 w-3.5 items-center justify-center text-primary">
                  <DropdownMenu.ItemIndicator>
                    <Check size={13} />
                  </DropdownMenu.ItemIndicator>
                </span>
                <span className="truncate">{m.name}</span>
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
