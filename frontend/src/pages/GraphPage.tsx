import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'

export function GraphPage() {
  const { detailsPanelProps, searchFormProps } = useGraphSearchDetails()

  return (
    <div className="mx-auto grid h-full min-h-0 w-full max-w-[1480px] grid-cols-[minmax(380px,440px)_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] items-stretch gap-5 overflow-hidden p-4 max-[900px]:h-auto max-[900px]:grid-cols-1 max-[900px]:overflow-visible">
      <aside className="relative z-[5] grid min-h-0 min-w-0 grid-rows-[1fr]">
        <article className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4 rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
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

      <section className="grid min-h-0 min-w-0">
        <article className="grid h-full min-h-0 overflow-hidden rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
          <ScenegraphMapPanel />
        </article>
      </section>
    </div>
  )
}
