'use client';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { PageHamburger } from './page-hamburger';
import { Logo } from './logo';

/** Warm cream top bar with brand mark, page path, and optional right-slot actions. */
export function PageTopBar({ section, right }: { section?: string; right?: ReactNode }) {
  return (
    <div className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-hairline bg-canvas/90 px-4 backdrop-blur-md sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        <PageHamburger />
        <Link href="/app">
          <Logo size={20} className="shrink-0" wordmarkClassName="hidden sm:inline" />
        </Link>
        {section && (
          <>
            <span className="hidden text-base text-muted-soft sm:inline">/</span>
            <span className="truncate text-sm text-body">{section}</span>
          </>
        )}
      </div>
      {right && <div className="flex shrink-0 items-center gap-2">{right}</div>}
    </div>
  );
}
