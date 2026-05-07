import type { Config } from 'tailwindcss';

/** Reads a `R G B` CSS custom property and makes it opacity-modifier aware (bg-primary/10, etc). */
function withOpacity(variable: string) {
  return `rgb(var(${variable}) / <alpha-value>)`;
}

const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        canvas: withOpacity('--canvas'),
        surface: {
          soft: withOpacity('--surface-soft'),
          card: withOpacity('--surface-card'),
          strong: withOpacity('--surface-cream-strong'),
        },
        hairline: {
          DEFAULT: withOpacity('--hairline'),
          soft: withOpacity('--hairline-soft'),
        },
        ink: withOpacity('--ink'),
        body: {
          DEFAULT: withOpacity('--body'),
          strong: withOpacity('--body-strong'),
        },
        muted: {
          DEFAULT: withOpacity('--muted'),
          soft: withOpacity('--muted-soft'),
        },
        primary: {
          DEFAULT: withOpacity('--primary'),
          active: withOpacity('--primary-active'),
          disabled: withOpacity('--primary-disabled'),
          foreground: withOpacity('--on-primary'),
        },
        dark: {
          DEFAULT: withOpacity('--surface-dark'),
          elevated: withOpacity('--surface-dark-elevated'),
          soft: withOpacity('--surface-dark-soft'),
        },
        ondark: {
          DEFAULT: withOpacity('--on-dark'),
          soft: withOpacity('--on-dark-soft'),
        },
        teal: withOpacity('--accent-teal'),
        amber: withOpacity('--accent-amber'),
        success: withOpacity('--success'),
        warning: withOpacity('--warning'),
        danger: withOpacity('--error'),
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'Cormorant Garamond', 'EB Garamond', 'Georgia', 'serif'],
        sans: ['var(--font-sans)', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'ui-monospace', 'SF Mono', 'Consolas', 'monospace'],
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        DEFAULT: '8px',
        md: '8px',
        lg: '12px',
        xl: '16px',
        '2xl': '20px',
        '3xl': '24px',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(20 20 19 / 0.04), 0 1px 1px 0 rgb(20 20 19 / 0.03)',
        popover: '0 12px 32px -8px rgb(20 20 19 / 0.16), 0 4px 12px -4px rgb(20 20 19 / 0.08)',
        'popover-dark': '0 16px 40px -8px rgb(0 0 0 / 0.45), 0 4px 14px -4px rgb(0 0 0 / 0.3)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.23, 1, 0.32, 1)',
        'in-out': 'cubic-bezier(0.77, 0, 0.175, 1)',
        drawer: 'cubic-bezier(0.32, 0.72, 0, 1)',
      },
      transitionDuration: {
        120: '120ms',
        160: '160ms',
        250: '250ms',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'caret-blink': {
          '0%, 100%': { opacity: '0.15' },
          '50%': { opacity: '0.9' },
        },
        shimmer: {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 420ms cubic-bezier(0.23, 1, 0.32, 1) both',
        'fade-in': 'fade-in 280ms ease both',
        'scale-in': 'scale-in 160ms cubic-bezier(0.23, 1, 0.32, 1) both',
        'caret-blink': 'caret-blink 1000ms ease-in-out infinite',
        shimmer: 'shimmer 2200ms linear infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
export default config;
