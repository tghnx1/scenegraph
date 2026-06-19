import * as React from 'react'

import { cn } from '@/shared/lib/cn-utils'

function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'h-10 w-full min-w-0 rounded-md border border-[var(--control-border)] bg-[var(--surface-input)] px-3 py-2 text-sm text-[var(--text)] outline-none transition-[border-color,box-shadow] placeholder:text-[var(--text-placeholder)] focus-visible:border-[var(--focus-border)] focus-visible:ring-3 focus-visible:ring-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
