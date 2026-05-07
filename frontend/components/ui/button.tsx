'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap select-none',
    'rounded-md font-sans font-medium',
    'transition-[transform,background-color,border-color,color,box-shadow] duration-160 ease-out',
    'active:scale-[0.97]',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
    'disabled:pointer-events-none disabled:opacity-40 disabled:active:scale-100',
  ].join(' '),
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary-active shadow-card',
        secondary:
          'bg-canvas text-ink border border-hairline hover:border-muted-soft/50 hover:bg-surface-soft',
        ghost: 'bg-transparent text-body hover:bg-surface-card hover:text-ink',
        ghostDark: 'bg-transparent text-ondark-soft hover:bg-dark-elevated hover:text-ondark',
        danger: 'bg-transparent text-danger border border-danger/30 hover:bg-danger/8',
        link: 'text-primary underline-offset-4 hover:underline h-auto px-0 py-0 active:scale-100',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4 text-sm',
        lg: 'h-11 px-6 text-[15px]',
        icon: 'h-9 w-9 p-0',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean };

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { buttonVariants };
