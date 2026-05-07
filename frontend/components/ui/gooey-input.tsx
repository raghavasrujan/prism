'use client';

import {
  useState,
  useRef,
  useEffect,
  useId,
  useMemo,
  useCallback,
  type ChangeEvent,
} from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

// ── Gooey SVG filter ──────────────────────────────────────────────────────────

function GooeyFilter({ filterId, blur }: { filterId: string; blur: number }) {
  return (
    <svg className="absolute hidden h-0 w-0" aria-hidden>
      <defs>
        <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceGraphic" stdDeviation={blur} result="blur" />
          <feColorMatrix
            in="blur"
            type="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -10"
            result="goo"
          />
          <feComposite in="SourceGraphic" in2="goo" operator="atop" />
        </filter>
      </defs>
    </svg>
  );
}

// ── Animated search icon (shared layout animation between pill & bubble) ──────

function SearchIcon({ layoutId }: { layoutId: string }) {
  return (
    <motion.svg
      layoutId={layoutId}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      className="size-4 shrink-0"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </motion.svg>
  );
}

// ── Motion config ─────────────────────────────────────────────────────────────

const transition = {
  duration: 0.35,
  type: 'spring' as const,
  bounce: 0,
};

const iconBubbleVariants = {
  collapsed: { scale: 0, opacity: 0 },
  expanded: { scale: 1, opacity: 1 },
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface GooeyInputClassNames {
  root?: string;
  filterWrap?: string;
  buttonRow?: string;
  trigger?: string;
  input?: string;
  bubble?: string;
  bubbleSurface?: string;
  collapsedLabel?: string;
}

export interface GooeyInputProps {
  placeholder?: string;
  /** Text shown alongside the icon when the pill is collapsed. Defaults to `placeholder`. */
  collapsedLabel?: string;
  className?: string;
  classNames?: GooeyInputClassNames;
  /** Width (px) of the pill when collapsed. */
  collapsedWidth?: number;
  /** Width (px) of the pill when expanded (the input grows into this). */
  expandedWidth?: number;
  /** Left offset (px) applied to the pill when expanded, leaving room for the icon bubble. */
  expandedOffset?: number;
  /** Blur radius used by the gooey SVG filter. */
  gooeyBlur?: number;
  /**
   * Tailwind classes for the pill + bubble surface.
   * Defaults to the dark ink pill (bg-ink text-canvas).
   * Pass sidebar-appropriate classes to blend with lighter backgrounds.
   */
  surfaceClass?: string;
  /** Controlled value. */
  value?: string;
  /** Initial value when uncontrolled. */
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  onOpenChange?: (open: boolean) => void;
  disabled?: boolean;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function GooeyInput({
  placeholder = 'Search…',
  collapsedLabel,
  className,
  classNames,
  collapsedWidth = 115,
  expandedWidth = 200,
  expandedOffset = 40,
  gooeyBlur = 5,
  surfaceClass = 'bg-ink text-canvas shadow-sm ring-1 ring-hairline/40',
  value: valueProp,
  defaultValue = '',
  onValueChange,
  onOpenChange,
  disabled = false,
}: GooeyInputProps) {
  const reactId = useId();
  const safeId = reactId.replace(/:/g, '');
  const filterId = `gooey-filter-${safeId}`;
  const iconLayoutId = `gooey-input-icon-${safeId}`;

  const inputRef = useRef<HTMLInputElement>(null);
  const prevExpandedRef = useRef(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);

  const isControlled = valueProp !== undefined;
  const searchText = isControlled ? valueProp : uncontrolledValue;

  const setSearchText = useCallback(
    (next: string) => {
      if (!isControlled) setUncontrolledValue(next);
      onValueChange?.(next);
    },
    [isControlled, onValueChange],
  );

  const setExpanded = useCallback(
    (next: boolean) => {
      setIsExpanded(next);
      onOpenChange?.(next);
    },
    [onOpenChange],
  );

  useEffect(() => {
    if (isExpanded) {
      inputRef.current?.focus();
    } else if (prevExpandedRef.current) {
      setSearchText('');
    }
    prevExpandedRef.current = isExpanded;
  }, [isExpanded, setSearchText]);

  const buttonVariants = useMemo(
    () => ({
      collapsed: { width: collapsedWidth, marginLeft: 0 },
      expanded: { width: expandedWidth, marginLeft: expandedOffset },
    }),
    [collapsedWidth, expandedWidth, expandedOffset],
  );

  const handleExpand = useCallback(() => {
    if (!disabled) setExpanded(true);
  }, [disabled, setExpanded]);

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => setSearchText(e.target.value),
    [setSearchText],
  );

  const handleBlur = useCallback(() => {
    if (!searchText) setExpanded(false);
  }, [searchText, setExpanded]);

  // ── Project colour tokens (overridable via surfaceClass prop) ───────────
  const resolvedSurface = surfaceClass;

  return (
    <div className={cn('relative flex items-center justify-center', className, classNames?.root)}>
      <GooeyFilter filterId={filterId} blur={gooeyBlur} />

      <div
        className={cn(
          'relative flex h-10 items-center justify-start',
          classNames?.filterWrap,
        )}
        style={{ filter: `url(#${filterId})` }}
      >
        {/* Expanding pill ─────────────────────────────────────────────────── */}
        <motion.div
          className={cn('flex h-10 items-center justify-center', classNames?.buttonRow)}
          variants={buttonVariants}
          initial="collapsed"
          animate={isExpanded ? 'expanded' : 'collapsed'}
          transition={transition}
        >
          <button
            type="button"
            disabled={disabled}
            onClick={handleExpand}
            className={cn(
              'flex h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-full px-4',
              'text-sm font-medium outline-none',
              'transition-[color,box-shadow] focus-visible:outline-none',
              'disabled:pointer-events-none disabled:opacity-50',
              resolvedSurface,
              classNames?.trigger,
            )}
          >
            {!isExpanded && <SearchIcon layoutId={iconLayoutId} />}
            {!isExpanded && (
              <span
                className={cn(
                  'truncate text-sm font-medium',
                  classNames?.collapsedLabel,
                )}
              >
                {collapsedLabel ?? placeholder}
              </span>
            )}

            <motion.input
              ref={inputRef}
              type="search"
              enterKeyHint="search"
              autoComplete="off"
              value={searchText}
              onChange={handleChange}
              onBlur={handleBlur}
              disabled={disabled || !isExpanded}
              placeholder={placeholder}
              className={cn(
                'h-full min-w-0 bg-transparent text-sm outline-none focus-visible:outline-none',
                isExpanded ? 'flex-1 opacity-100' : 'pointer-events-none w-0 flex-none opacity-0',
                classNames?.input,
              )}
            />
          </button>
        </motion.div>

        {/* Detached icon bubble (appears at left when expanded) ───────────── */}
        <motion.div
          className={cn(
            'absolute left-0 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center',
            classNames?.bubble,
          )}
          variants={iconBubbleVariants}
          initial="collapsed"
          animate={isExpanded ? 'expanded' : 'collapsed'}
          transition={transition}
        >
          <div
            className={cn(
              'flex size-10 items-center justify-center rounded-full',
              resolvedSurface,
              classNames?.bubbleSurface,
            )}
          >
            <SearchIcon layoutId={iconLayoutId} />
          </div>
        </motion.div>
      </div>
    </div>
  );
}
