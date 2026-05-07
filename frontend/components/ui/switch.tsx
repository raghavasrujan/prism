'use client';

import * as SwitchPrimitive from '@radix-ui/react-switch';
import * as React from 'react';
import { cn } from '@/lib/utils';

export const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      'peer inline-flex h-[18px] w-8 shrink-0 items-center rounded-full border border-transparent',
      'bg-hairline transition-colors duration-160 ease-out',
      'data-[state=checked]:bg-primary',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        'pointer-events-none block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow-card',
        'transition-transform duration-200 ease-out',
        'data-[state=checked]:translate-x-[15px]',
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = 'Switch';
