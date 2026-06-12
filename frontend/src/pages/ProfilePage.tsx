import { useState } from 'react'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { PromoterRecommendationsPanel, type RecommendationTargetControls } from './components/RecommendationPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'

type ProfileWorkspaceTab = 'graph' | 'recommendations'

interface ProfilePageProps {
  recommendationTargetControls?: RecommendationTargetControls
}

export function ProfilePage({ recommendationTargetControls }: ProfilePageProps = {}) {
  const { detailsPanelProps, searchFormProps, setSelected } = useGraphSearchDetails()
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ProfileWorkspaceTab>('graph')

  return (
    <div className="profile-page">
      <section className="profile-grid" aria-label="Profile overview">
        <article className="graph-sidebar-card context-panel">
          <div className="graph-sidebar-search">
            <SearchInputField
              inputId="profile-details-search-query-input"
              {...searchFormProps}
            />
          </div>

          {/* <div className="panel-heading">
            <span className="search-query-label">Node details</span>
          </div> */}
          <DetailsPanel
            {...detailsPanelProps}
          />
        </article>

        <section className="graph-workspace" aria-label="Profile graph workspace">
          <article className="profile-card graph-panel">
            <div className="profile-workspace-tabs" role="tablist" aria-label="Profile graph views">
              <button
                type="button"
                id="profile-workspace-tab-graph"
                className={`profile-workspace-tab${activeWorkspaceTab === 'graph' ? ' active' : ''}`}
                role="tab"
                aria-selected={activeWorkspaceTab === 'graph'}
                aria-controls="profile-workspace-panel-graph"
                onClick={() => setActiveWorkspaceTab('graph')}
              >
                Graph
              </button>
              <button
                type="button"
                id="profile-workspace-tab-recommendations"
                className={`profile-workspace-tab${activeWorkspaceTab === 'recommendations' ? ' active' : ''}`}
                role="tab"
                aria-selected={activeWorkspaceTab === 'recommendations'}
                aria-controls="profile-workspace-panel-recommendations"
                onClick={() => setActiveWorkspaceTab('recommendations')}
              >
                Recommendations
              </button>
            </div>
            <section
              id="profile-workspace-panel-graph"
              className="profile-workspace-content"
              role="tabpanel"
              aria-labelledby="profile-workspace-tab-graph"
              hidden={activeWorkspaceTab !== 'graph'}
            >
              <ScenegraphMapPanel />
            </section>
            <PromoterRecommendationsPanel
              isActive={activeWorkspaceTab === 'recommendations'}
              targetControls={recommendationTargetControls}
              onSelectNode={setSelected}
            />
          </article>
        </section>
      </section>
    </div>
  )
}
