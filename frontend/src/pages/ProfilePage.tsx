import { useEffect, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils.ts'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { PromoterRecommendationsPanel, type RecommendationTargetControls } from './components/RecommendationPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'
import { useManualArtistConnections } from './hooks/useManualArtistConnections.ts'
import { BiographyPanel } from './components/BiographyPanel.tsx'
import { getMe } from '../api/auth'
import type { MeResponse } from '../api/auth'

type ProfileWorkspaceTab = 'graph' | 'recommendations'

interface ProfilePageProps {
  recommendationTargetControls?: RecommendationTargetControls
  showBiography?: boolean
}

export function ProfilePage({ recommendationTargetControls, showBiography = true }: ProfilePageProps = {}) {
  const { detailsPanelProps, searchFormProps, selectedNode, setSelected } = useGraphSearchDetails()
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ProfileWorkspaceTab>('graph')

  const [assignedArtistId, setAssignedArtistId] = useState<number | null>(() => {
    const stored = Number(localStorage.getItem('artist_id'))
    return Number.isInteger(stored) && stored > 0 ? stored : null
  }) 
  const [pendingArtistClaim, setPendingArtistClaim] = useState<NonNullable<MeResponse['pending_artist_claim']> | null>(null)

  useEffect(() => {
    getMe()
    .then((response) => {
      if (response.artist_id) {
        localStorage.setItem('artist_id', String(response.artist_id))
        setAssignedArtistId(response.artist_id)
        setPendingArtistClaim(null)
      } else {
        localStorage.removeItem('artist_id')
        setAssignedArtistId(null)
        setPendingArtistClaim(response.pending_artist_claim ?? null)
      }
    })
    .catch(() => {
    })
  }, [])
  
  const searchParams = new URLSearchParams(window.location.search)
  const selectedType = searchParams.get('selectedType')
  const selectedId = Number(searchParams.get('selectedId'))

  const hasSelectedArtist =
    selectedType === 'artist' &&
    Number.isInteger(selectedId) &&
    selectedId > 0

  const storedArtistId = assignedArtistId

  const hasAssignedArtist =storedArtistId !== null
  const selectedNodeArtistId = selectedNode?.type === 'artist' ? selectedNode.entityId : null
  const selectedDetailArtistName = detailsPanelProps.selectedEntityDetail?.type === 'artist'
    ? detailsPanelProps.selectedEntityDetail.name
    : null
  const selectedArtistName = selectedNode?.type === 'artist'
    ? selectedNode.name
    : selectedDetailArtistName

  const artistId = hasSelectedArtist
    ? selectedId
    : selectedNodeArtistId
      ? selectedNodeArtistId
    : hasAssignedArtist
      ? storedArtistId
      : null

  const biographyArtistId = hasAssignedArtist ? storedArtistId : pendingArtistClaim?.artist_id ?? artistId
  const biographySelectedArtistName = hasAssignedArtist ? null : pendingArtistClaim?.artist_name ?? selectedArtistName
  const canEditBiography = 
    hasAssignedArtist && storedArtistId === biographyArtistId

  const manualConnectionSourceArtistId = showBiography && hasAssignedArtist ? storedArtistId : null
  const manualConnections = useManualArtistConnections(manualConnectionSourceArtistId)
  const isSingleRowWorkspace = !showBiography

  return (
    <div className={cn(
      'mx-auto w-full max-w-[1480px] p-4',
      isSingleRowWorkspace
        ? 'min-h-full min-[901px]:h-full min-[901px]:min-h-0 min-[901px]:overflow-hidden'
        : 'min-h-full',
    )}>
      <section
        className={cn(
          'grid grid-cols-[minmax(380px,440px)_minmax(0,1fr)] gap-5 max-[900px]:grid-cols-1 max-[900px]:grid-rows-none',
          isSingleRowWorkspace
            ? 'min-[901px]:h-full min-[901px]:min-h-0 min-[901px]:grid-rows-[minmax(0,1fr)]'
            : 'grid-rows-[minmax(560px,calc(100dvh-128px))_auto]',
        )}
        aria-label="Profile overview"
      >
        <article className="relative z-20 grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4 rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
          <div className="search-sidebar-anchor grid gap-2.5 pb-4">
            <SearchInputField
              inputId="profile-details-search-query-input"
              {...searchFormProps}
            />
          </div>

          <DetailsPanel
            {...detailsPanelProps}
            manualArtistConnections={manualConnectionSourceArtistId !== null ? {
              sourceArtistId: manualConnectionSourceArtistId,
              connectedArtistIds: manualConnections.connectedArtistIds,
              isLoading: manualConnections.isLoading,
              pendingArtistId: manualConnections.pendingArtistId,
              error: manualConnections.error,
              onToggle: manualConnections.toggle,
            } : undefined}
          />
        </article>

        <section className="relative z-0 grid min-h-0 min-w-0" aria-label="Profile graph workspace">
          <article className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 overflow-hidden rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
            <div className="inline-flex w-fit gap-1 rounded-xl bg-[var(--surface-input)] p-1" role="tablist" aria-label="Profile graph views">
              <Button
                type="button"
                id="profile-workspace-tab-graph"
                variant={activeWorkspaceTab === 'graph' ? 'default' : 'ghost'}
                size="sm"
                className={cn('rounded-lg', activeWorkspaceTab === 'graph' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
                role="tab"
                aria-selected={activeWorkspaceTab === 'graph'}
                aria-controls="profile-workspace-panel-graph"
                onClick={() => setActiveWorkspaceTab('graph')}
              >
                Graph
              </Button>
              <Button
                type="button"
                id="profile-workspace-tab-recommendations"
                variant={activeWorkspaceTab === 'recommendations' ? 'default' : 'ghost'}
                size="sm"
                className={cn('rounded-lg', activeWorkspaceTab === 'recommendations' && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
                role="tab"
                aria-selected={activeWorkspaceTab === 'recommendations'}
                aria-controls="profile-workspace-panel-recommendations"
                onClick={() => setActiveWorkspaceTab('recommendations')}
              >
                Recommendations
              </Button>
            </div>
            <section
              id="profile-workspace-panel-graph"
              className="min-h-0 min-w-0"
              role="tabpanel"
              aria-labelledby="profile-workspace-tab-graph"
              hidden={activeWorkspaceTab !== 'graph'}
            >
              <ScenegraphMapPanel />
            </section>
            <PromoterRecommendationsPanel
              isActive={activeWorkspaceTab === 'recommendations'}
              artistId={artistId}
              targetControls={recommendationTargetControls}
              onSelectNode={setSelected}
            />
          </article>
        </section>
        {showBiography && (
          <div className="col-span-2 max-[900px]:col-span-1">
            <BiographyPanel
              artistId={biographyArtistId}
              selectedArtistName={biographySelectedArtistName}
              canEditBiography={canEditBiography}
              hasApprovedArtistProfile={hasAssignedArtist}
              pendingArtistClaim={pendingArtistClaim}
              onClaimSubmitted={(claim) => setPendingArtistClaim(claim)}
              manualConnections={{
                connections: manualConnections.connections,
                isLoading: manualConnections.isLoading,
                pendingArtistId: manualConnections.pendingArtistId,
                error: manualConnections.error,
                onRemove: manualConnections.remove,
              }}
            />
          </div>
        )}
      </section>
    </div>
  )
}
