'use client';

import { cn } from '@/lib/utils';

type Tone = 'neutral' | 'red' | 'blue' | 'green' | 'yellow';

const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'bg-surface-card text-body border-hairline',
  red: 'bg-danger/10 text-danger border-danger/25',
  blue: 'bg-teal/10 text-teal border-teal/25',
  green: 'bg-success/10 text-success border-success/25',
  yellow: 'bg-warning/10 text-warning border-warning/25',
};

export function Tag({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5',
        'font-sans text-[11px] font-medium leading-normal',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
