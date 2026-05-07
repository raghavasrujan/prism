'use client';

import { motion } from 'framer-motion';
import DotField from './dot-field';

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/**
 * Full-bleed dark-navy backdrop for the auth pages — an interactive coral dot
 * field the form card floats over. Fixed so it never scrolls with the form.
 */
export function AuthBackground({ tagline, children }: { tagline?: string; children: React.ReactNode }) {
  return (
    <div className="relative min-h-dvh w-full bg-dark">
      <div className="fixed inset-0">
        <DotField
          dotRadius={1.5}
          dotSpacing={16}
          bulgeStrength={60}
          glowRadius={220}
          cursorRadius={420}
          gradientFrom="rgba(204, 120, 92, 0.4)"
          gradientTo="rgba(250, 249, 245, 0.12)"
          glowColor="#CC785C"
        />
      </div>

      <div className="relative z-10 flex min-h-dvh flex-col items-center justify-center gap-7 px-4 py-10 sm:gap-8 sm:px-6">
        {tagline && (
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
            className="text-center font-serif text-lg italic tracking-tight text-ondark-soft sm:text-xl"
          >
            {tagline}
          </motion.p>
        )}
        {children}
      </div>
    </div>
  );
}
