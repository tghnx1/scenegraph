import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/shared/lib/cn-utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border text-sm font-semibold transition-all disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-[var(--focus-ring)] [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'border-[var(--control-border)] bg-[var(--control-bg)] text-[var(--text)] hover:bg-[var(--control-hover)]',
        secondary: 'border-transparent bg-[var(--surface-panel-soft)] text-[var(--text)] hover:bg-[var(--control-bg)]',
        ghost: 'border-transparent bg-transparent text-[var(--text-muted)] hover:bg-[var(--control-bg)] hover:text-[var(--text)]',
        destructive: 'border-[color-mix(in_srgb,var(--event)_50%,transparent)] bg-[color-mix(in_srgb,var(--event)_15%,transparent)] text-[var(--text)] hover:bg-[color-mix(in_srgb,var(--event)_24%,transparent)]',
        outline: 'border-[var(--control-border)] bg-transparent text-[var(--text)] hover:bg-[var(--control-bg)]',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-5',
        icon: 'size-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
