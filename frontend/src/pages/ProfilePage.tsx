import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils.ts'
import { DetailsPanel } from './components/DetailsPanel.tsx'
import { ScenegraphMapPanel } from './components/GraphPanel.tsx'
import { PromoterRecommendationsPanel, type RecommendationTargetControls } from './components/RecommendationPanel.tsx'
import { SearchInputField } from './components/SearchInputField.tsx'
import { useGraphSearchDetails } from './hooks/useGraphSearchDetails.ts'
import { useManualArtistConnections } from './hooks/useManualArtistConnections.ts'
import { BiographyPanel } from './components/BiographyPanel.tsx'
import { getMe, type AuthRole } from '../api/auth'
import {
  getProfileSetupTargetId,
  type ArtistProfileReadiness,
} from './profileReadiness'

type ProfileWorkspaceTab = 'graph' | 'recommendations'

interface ProfilePageProps {
  recommendationTargetControls?: RecommendationTargetControls
  showBiography?: boolean
}

export function ProfilePage({ recommendationTargetControls, showBiography = true }: ProfilePageProps = {}) {
  const { detailsPanelProps, searchFormProps, selectedNode, setSelected } = useGraphSearchDetails()
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ProfileWorkspaceTab>('recommendations')
  const [currentRole, setCurrentRole] = useState<AuthRole | null>(() => {
    const storedRole = localStorage.getItem('role')
    return storedRole === 'artist' || storedRole === 'agent' || storedRole === 'admin'
      ? storedRole
      : null
  })

  const [assignedArtistId, setAssignedArtistId] = useState<number | null>(() => {
    const stored = Number(localStorage.getItem('artist_id'))
    return Number.isInteger(stored) && stored > 0 ? stored : null
  })
  const [assignedArtistName, setAssignedArtistName] = useState<string | null>(() => {
    const stored = localStorage.getItem('artist_name')?.trim() ?? ''
    return stored || null
  })

  const [biographyReadiness, setBiographyReadiness] = useState<Pick<ArtistProfileReadiness, 'isLoading' | 'hasBiography'>>({
    isLoading: true,
    hasBiography: null,
  })

  const refreshCurrentUser = useCallback(async () => {
    try {
      const response = await getMe()
      setCurrentRole(response.role)

      if (response.artist_id) {
        localStorage.setItem('artist_id', String(response.artist_id))
        setAssignedArtistId(response.artist_id)
      } else {
        localStorage.removeItem('artist_id')
        setAssignedArtistId(null)
      }

      if (response.artist_name) {
        localStorage.setItem('artist_name', response.artist_name)
        setAssignedArtistName(response.artist_name)
      } else {
        localStorage.removeItem('artist_name')
        setAssignedArtistName(null)
      }
    } catch {
      // Keep the last known state when the session is unavailable.
    }
  }, [])

  useEffect(() => {
    void refreshCurrentUser()
  }, [])

  useEffect(() => {
    const handleRefresh = () => {
      void refreshCurrentUser()
    }

    window.addEventListener('focus', handleRefresh)
    document.addEventListener('visibilitychange', handleRefresh)
    return () => {
      window.removeEventListener('focus', handleRefresh)
      document.removeEventListener('visibilitychange', handleRefresh)
    }
  }, [])

  const searchParams = new URLSearchParams(window.location.search)
  const selectedType = searchParams.get('selectedType')
  const selectedId = Number(searchParams.get('selectedId'))

  const hasSelectedArtist =
    selectedType === 'artist' &&
    Number.isInteger(selectedId) &&
    selectedId > 0

  const storedArtistId = assignedArtistId
  const hasAssignedArtist = storedArtistId !== null
  const isArtistUser = currentRole === 'artist'
  const selectedNodeArtistId = selectedNode?.type === 'artist' ? selectedNode.entityId : null
  const selectedDetailArtistId = detailsPanelProps.selectedEntityDetail?.type === 'artist'
    ? detailsPanelProps.selectedEntityDetail.id
    : null
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
  const profileArtistId = isArtistUser ? storedArtistId : artistId
  const recommendationTargetName = recommendationTargetControls?.artistName
    ?? (isArtistUser ? assignedArtistName : selectedArtistName)
  const biographyArtistId = isArtistUser
    ? (profileArtistId ?? selectedDetailArtistId ?? selectedNodeArtistId)
    : artistId
  const biographySelectedArtistName = hasAssignedArtist
    ? null
    : selectedArtistName

  const canEditBiography =
    hasAssignedArtist && storedArtistId === profileArtistId
  const manualConnectionsArtistId = isArtistUser
    ? profileArtistId
    : artistId
  const manualConnections = useManualArtistConnections(manualConnectionsArtistId)
  const isSingleRowWorkspace = !showBiography
  const profileReadiness = useMemo<ArtistProfileReadiness>(() => ({
    isLoading: biographyReadiness.isLoading || manualConnections.isLoading,
    hasBiography: biographyReadiness.hasBiography,
    manualArtistCount: manualConnections.connections.length,
    requiredManualArtistCount: 3,
  }), [
    biographyReadiness.hasBiography,
    biographyReadiness.isLoading,
    manualConnections.connections.length,
    manualConnections.isLoading,
  ])

  const handleCompleteProfile = useCallback(() => {
    const targetId = getProfileSetupTargetId(profileReadiness)
    const target = document.getElementById(targetId)
    if (!target) return

    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    if ('focus' in target) {
      window.setTimeout(() => {
        target.focus({ preventScroll: true })
      }, 350)
    }
  }, [profileReadiness])

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
            manualArtistConnections={manualConnectionsArtistId !== null ? {
              sourceArtistId: manualConnectionsArtistId,
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
              artistId={profileArtistId}
              artistName={recommendationTargetName}
              targetControls={recommendationTargetControls}
              autoLoad={isArtistUser && profileArtistId !== null}
              profileReadiness={isArtistUser ? profileReadiness : undefined}
              onCompleteProfile={isArtistUser ? handleCompleteProfile : undefined}
              emptyStateMessage={isArtistUser
                ? 'Complete your artist profile to unlock recommendations.'
                : undefined}
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
              onBiographyStatusChange={setBiographyReadiness}
              manualConnections={{
                connections: manualConnections.connections,
                isLoading: manualConnections.isLoading,
                pendingArtistId: manualConnections.pendingArtistId,
                error: manualConnections.error,
                onAdd: manualConnections.add,
                onRemove: manualConnections.remove,
              }}
            />
          </div>
        )}
      </section>
    </div>
  )
}
