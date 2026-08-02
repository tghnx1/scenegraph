import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'

export function GraphPage() {
  const { detailsPanelProps, searchFormProps } = useGraphSearchDetails()

  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-none items-stretch gap-5 overflow-hidden p-4 max-[900px]:h-auto max-[900px]:flex-col max-[900px]:overflow-visible">
      <aside className="relative z-[5] flex min-h-0 self-stretch w-[440px] min-w-[380px] flex-shrink-0 max-[900px]:w-full max-[900px]:min-w-0">
        <article className="flex h-full min-h-0 flex-1 flex-col gap-4 rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
          <div className="search-sidebar-anchor grid gap-2.5 pb-4">
            <SearchInputField
              inputId="graph-search-query-input"
              {...searchFormProps}
            />
          </div>

          <DetailsPanel
            {...detailsPanelProps}
          />
        </article>
      </aside>

      <section className="flex h-full min-h-0 min-w-0 flex-1 self-stretch">
        <article className="flex h-full min-h-0 w-full flex-1 self-stretch overflow-hidden rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
          <div className="h-full min-h-0 w-full flex-1">
            <ScenegraphMapPanel />
          </div>
        </article>
      </section>
    </div>
  )
}
