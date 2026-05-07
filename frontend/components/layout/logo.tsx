import { cn } from '@/lib/utils';

const SPECTRUM = ['#FF3B30', '#FF9F0A', '#FFD60A', '#34C759', '#32ADE6', '#0A84FF', '#AF52DE'];

/**
 * The Prism mark — a triangle refracting a spectrum of light. Fixed dark
 * chip regardless of theme, like any app icon (Slack/Discord-style), so it
 * reads consistently whether it sits on the cream canvas or the dark auth
 * background.
 */
function PrismMark({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#14120F" />
      {SPECTRUM.map((color, i) => (
        <line
          key={color}
          x1="16.5"
          y1="16"
          x2="28"
          y2={7.5 + i * 3}
          stroke={color}
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      ))}
      <path
        d="M13.5 6.5L6.5 24.5H20.5L13.5 6.5Z"
        stroke="#FAF9F5"
        strokeWidth="1.6"
        strokeLinejoin="round"
        fill="#14120F"
      />
    </svg>
  );
}

export function Logo({
  size = 22,
  withWordmark = true,
  wordmarkClassName,
  className,
}: {
  size?: number;
  withWordmark?: boolean;
  wordmarkClassName?: string;
  className?: string;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <PrismMark size={size} />
      {withWordmark && (
        <span className={cn('font-serif text-[17px] leading-none tracking-tight text-ink', wordmarkClassName)}>
          Prism
        </span>
      )}
    </span>
  );
}
