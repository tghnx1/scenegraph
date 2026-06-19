import {useState} from 'react'
import {Button} from './button'

type ExportMenuProps = {
  enabled: boolean
  label: string
  onJson: () => void
  onCsv: () => void
  onPdf: () => void
}

export function ExportMenu({enabled, label, onJson, onCsv, onPdf}: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const action = (handler: () => void) => () => {
    setIsOpen(false)
    handler()
  }

  return (
    <div className="relative inline-flex">
      <Button type="button" size="sm" aria-haspopup="menu" aria-expanded={isOpen} disabled={!enabled} onClick={() => setIsOpen((open) => !open)}>
        Export
      </Button>
      {isOpen && enabled && (
        <div className="absolute right-0 top-[calc(100%+8px)] z-30 grid min-w-32 gap-1 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-dropdown)] p-1.5 shadow-[var(--surface-shadow)]" role="menu" aria-label={label}>
          <Button type="button" variant="ghost" size="sm" role="menuitem" onClick={action(onJson)}>JSON</Button>
          <Button type="button" variant="ghost" size="sm" role="menuitem" onClick={action(onCsv)}>CSV</Button>
          <Button type="button" variant="ghost" size="sm" role="menuitem" onClick={action(onPdf)}>PDF</Button>
        </div>
      )}
    </div>
  )
}
