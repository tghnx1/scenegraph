import { api } from './client'

export interface ImportResponse {
  success: boolean
  message: string
  imported_file: string
  event_id: number | null
  event_title: string | null
  imported_count: number
}

export const runImportFile = async (file: File): Promise<ImportResponse> => {
  const text = await file.text()
  let payload: unknown

  try {
    payload = JSON.parse(text)
  } catch (error) {
    throw new Error('Import file must contain valid JSON')
  }

  return api.post<ImportResponse>('/admin/import', {
    filename: file.name,
    payload,
  })
}
