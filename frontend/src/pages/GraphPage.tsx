import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'

export function GraphPage() {
  const { detailsPanelProps, searchFormProps } = useGraphSearchDetails()

  return (
    <div className="graph-page-shell">
      <aside className="graph-sidebar">
        <article className="graph-sidebar-card">
          <div className="graph-sidebar-search">
            <SearchInputField
              inputId="graph-search-query-input"
              {...searchFormProps}
            />
            {/* <p className="search-query-hint">Enter a name, then press Enter to update the search.</p> */}
          </div>

          <DetailsPanel
            {...detailsPanelProps}
          />
        </article>
      </aside>

      <section className="graph-main">
        <article className="profile-card graph-panel">
          <ScenegraphMapPanel />
        </article>
      </section>
    </div>
  )
}
