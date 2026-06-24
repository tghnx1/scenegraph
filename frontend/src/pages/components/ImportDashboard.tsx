import {useRef, useState, type ChangeEvent} from 'react'
import {Button} from '@/shared/ui/button'
import {runImportFile} from '../../api/imports'

interface DashboardImportButtonProps {
  onImported?: () => void
}

export function DashboardImportButton({onImported}: DashboardImportButtonProps) {
  const [isImporting, setIsImporting] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)

  const handleRunImportClick = () => {
    if (!isImporting) {
      importInputRef.current?.click()
    }
  }

  const handleImportFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setIsImporting(true)
    setImportMessage(null)

    try {
      const result = await runImportFile(file)
      setImportMessage(result.message || `Imported ${result.imported_file}`)
      onImported?.()
    } catch (error) {
      console.error(error)
      setImportMessage(error instanceof Error ? error.message : 'Import failed. Check the backend logs for details.')
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <>
      {importMessage && (
        <span className="text-sm text-[color-mix(in_srgb,var(--text)_72%,transparent)]">
          {importMessage}
        </span>
      )}
      <input
        ref={importInputRef}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={handleImportFileChange}
      />
      <Button type="button" size="sm" onClick={handleRunImportClick} disabled={isImporting}>
        {isImporting ? 'Importing...' : 'Run import'}
      </Button>
    </>
  )
}
