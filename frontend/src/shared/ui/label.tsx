import * as React from 'react'

import { cn } from '@/shared/lib/cn-utils'

function Label({ className, ...props }: React.ComponentProps<'label'>) {
  return (
    <label
      data-slot="label"
      className={cn('grid gap-1.5 text-sm font-medium text-[var(--text-muted)]', className)}
      {...props}
    />
  )
}

export { Label }
