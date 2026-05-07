'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

type TypingAnimationProps = {
  /** The target text to animate towards. Grows as more tokens stream in. */
  children: string;
  /** Milliseconds between animation ticks. Lower = faster typing. */
  duration?: number;
  /** When true (default), a blinking caret is rendered while typing. */
  showCursor?: boolean;
  /** Optional class name for the wrapper element. */
  className?: string;
};

/**
 * Reveals `children` character-by-character with a smooth typewriter effect.
 *
 * Designed to sit on top of a growing buffer (e.g. SSE tokens): each interval
 * tick reveals a few characters, and the step size scales with the backlog so
 * we catch up when many tokens arrive at once without losing the "typing" feel.
 */
export function TypingAnimation({
  children: text,
  duration = 18,
  showCursor = true,
  className,
}: TypingAnimationProps) {
  const textRef = useRef(text);
  textRef.current = text;
  const [count, setCount] = useState(0);

  // Reset when the target shrinks (e.g. a new stream starts).
  useEffect(() => {
    setCount((c) => (c > text.length ? 0 : c));
  }, [text]);

  useEffect(() => {
    const interval = setInterval(() => {
      setCount((c) => {
        const target = textRef.current.length;
        if (c >= target) return c;
        // Reveal 1-4 chars per tick; speed up when we're far behind.
        const backlog = target - c;
        const step = Math.min(Math.max(1, Math.ceil(backlog / 40)), 4);
        return Math.min(c + step, target);
      });
    }, duration);
    return () => clearInterval(interval);
  }, [duration]);

  const done = count >= text.length;
  return (
    <span className={cn(className)}>
      {text.slice(0, count)}
      {showCursor && !done && (
        <span className="ml-0.5 inline-block h-4 w-0.5 -mb-0.5 animate-caret-blink bg-body align-text-bottom" />
      )}
    </span>
  );
}
