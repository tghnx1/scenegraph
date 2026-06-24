import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import type { SearchEntityType, SearchResult, SearchSort } from '../../types/search'

const SEARCH_RESULT_TABS: { type: SearchEntityType; label: string }[] = [
  { type: 'artist', label: 'Artists' },
  { type: 'venue', label: 'Venues' },
  { type: 'promoter', label: 'Promoters' },
  { type: 'event', label: 'Events' },
]

const SEARCH_SORT_OPTIONS: { value: SearchSort; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name_asc', label: 'Name A-Z' },
  { value: 'name_desc', label: 'Name Z-A' },
]

const labelClass = 'text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]'
const dropdownStatusClass = 'px-3 py-2.5 text-sm text-[var(--text-muted)]'
const tabClass = 'grid min-w-0 cursor-pointer justify-items-center rounded-[9px] border-0 bg-transparent px-1 py-2.5 text-[0.76rem] leading-tight text-[var(--text-muted)] outline-none hover:bg-[var(--control-bg)] hover:text-[var(--text)] focus-visible:bg-[var(--control-bg)] focus-visible:text-[var(--text)]'
const optionClass = 'flex w-full cursor-pointer items-center justify-start gap-3 rounded-[10px] border-0 bg-transparent px-3 py-2.5 text-left font-[inherit] text-[var(--text)] outline-none hover:bg-[var(--control-bg)] focus-visible:bg-[var(--control-bg)]'

interface SearchInputFieldProps {
  inputId: string
  label?: string
  placeholder?: string
  value: string
  onChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onClear: () => void
  showClear: boolean
  results?: SearchResult[]
  isLoading?: boolean
  activeResultType?: SearchEntityType
  onActiveResultTypeChange?: (type: SearchEntityType) => void
  activeSort?: SearchSort
  onActiveSortChange?: (sort: SearchSort) => void
  showResultTabs?: boolean
  showResultsWhenEmpty?: boolean
  canLoadMore?: boolean
  onLoadMore?: () => void
  onSelectResult?: (result: SearchResult) => void
}

function getResultMeta(result: SearchResult) {
  return result.id
}

export function SearchInputField({
  inputId,
  label = 'Search Database',
  placeholder = 'Search artists, venues, promoters, events...',
  value,
  onChange,
  onSubmit,
  onClear,
  showClear,
  results = [],
  isLoading = false,
  activeResultType: controlledActiveResultType,
  onActiveResultTypeChange,
  activeSort = 'relevance',
  onActiveSortChange,
  showResultTabs = true,
  showResultsWhenEmpty = false,
  canLoadMore = false,
  onLoadMore,
  onSelectResult,
}: SearchInputFieldProps) {
  const formRef = useRef<HTMLFormElement | null>(null)
  const dropdownRef = useRef<HTMLDivElement | null>(null)
  const pendingScrollTopRef = useRef<number | null>(null)
  const pendingResultCountRef = useRef<number | null>(null)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [activeResultIndex, setActiveResultIndex] = useState(-1)
  const groupedResults = useMemo(
    () => Object.fromEntries(
      SEARCH_RESULT_TABS.map(({ type }) => [
        type,
        results.filter((result) => result.type === type),
      ])
    ) as Record<SearchEntityType, SearchResult[]>,
    [results]
  )
  const firstTabWithResults = SEARCH_RESULT_TABS.find(({ type }) => groupedResults[type].length > 0)?.type ?? 'artist'
  const [internalActiveResultType, setInternalActiveResultType] = useState<SearchEntityType>(firstTabWithResults)
  const [hasManualTabSelection, setHasManualTabSelection] = useState(false)
  const activeResultType = controlledActiveResultType ?? internalActiveResultType
  const isActiveResultTypeControlled = controlledActiveResultType !== undefined
  const visibleResults = showResultTabs ? groupedResults[activeResultType] : results
  const shouldShowDropdown = Boolean(
    onSelectResult &&
    isDropdownOpen &&
    value.trim().length >= 2 &&
    (isLoading || results.length > 0 || showResultsWhenEmpty)
  )
  const activeResult = activeResultIndex >= 0 ? visibleResults[activeResultIndex] : undefined

  useEffect(() => {
    setActiveResultIndex(-1)
    setHasManualTabSelection(false)
  }, [value])

  useEffect(() => {
    setActiveResultIndex(-1)
  }, [value, results])

  useEffect(() => {
    if (!isActiveResultTypeControlled && !hasManualTabSelection) {
      setInternalActiveResultType(firstTabWithResults)
    }
  }, [firstTabWithResults, hasManualTabSelection, isActiveResultTypeControlled])

  useEffect(() => {
    if (pendingScrollTopRef.current === null) return
    if (isLoading) return
    if (pendingResultCountRef.current !== null && visibleResults.length <= pendingResultCountRef.current) return

    window.requestAnimationFrame(() => {
      if (dropdownRef.current && pendingScrollTopRef.current !== null) {
        dropdownRef.current.scrollTop = pendingScrollTopRef.current
      }

      pendingScrollTopRef.current = null
      pendingResultCountRef.current = null
    })
  }, [isLoading, visibleResults.length])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onSubmit(event)
  }

  const handleClear = () => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onClear()
  }

  const selectResult = (result: SearchResult) => {
    setIsDropdownOpen(false)
    setActiveResultIndex(-1)
    onSelectResult?.(result)
  }

  const selectTab = (type: SearchEntityType) => {
    setHasManualTabSelection(true)
    if (isActiveResultTypeControlled) {
      onActiveResultTypeChange?.(type)
    } else {
      setInternalActiveResultType(type)
    }
    setActiveResultIndex(-1)
  }

  const handleSortChange = (sort: SearchSort) => {
    dropdownRef.current?.scrollTo({ top: 0 })
    pendingScrollTopRef.current = null
    pendingResultCountRef.current = null
    setActiveResultIndex(-1)
    onActiveSortChange?.(sort)
  }

  const handleLoadMore = () => {
    pendingScrollTopRef.current = dropdownRef.current?.scrollTop ?? null
    pendingResultCountRef.current = visibleResults.length
    setActiveResultIndex(-1)
    onLoadMore?.()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsDropdownOpen(false)
      setActiveResultIndex(-1)
      return
    }

    if (!onSelectResult || visibleResults.length === 0) {
      return
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setIsDropdownOpen(true)
      setActiveResultIndex((currentIndex) => (currentIndex + 1) % visibleResults.length)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setIsDropdownOpen(true)
      setActiveResultIndex((currentIndex) => (currentIndex <= 0 ? visibleResults.length - 1 : currentIndex - 1))
      return
    }

    if (event.key === 'Enter') {
      event.preventDefault()
      if (shouldShowDropdown && activeResult) {
        selectResult(activeResult)
      }
    }
  }

  return (
    <form className="relative grid gap-2" ref={formRef} onSubmit={handleSubmit}>
      <label className={cn(labelClass, !label && 'sr-only')} htmlFor={inputId}>
        {label}
      </label>
      <div className="flex items-center gap-2.5 rounded-[14px] border border-[var(--control-border)] bg-[var(--surface-input)] px-3 py-2.5 transition-[border-color,box-shadow] focus-within:border-[var(--focus-border)] focus-within:shadow-[0_0_0_3px_var(--focus-ring)]">
        <input
          id={inputId}
          className="min-w-0 flex-1 border-0 bg-transparent text-sm font-[inherit] text-[var(--text)] outline-none placeholder:text-[var(--text-placeholder)]"
          type="search"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          value={value}
          onChange={(event) => {
            setIsDropdownOpen(true)
            onChange(event.target.value)
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            window.setTimeout(() => {
              if (formRef.current?.contains(document.activeElement)) return
              setIsDropdownOpen(false)
            }, 120)
          }}
          placeholder={placeholder}
          aria-label="Search"
          aria-autocomplete="list"
          aria-expanded={shouldShowDropdown}
          aria-controls={`${inputId}-results-panel-${activeResultType}`}
          aria-activedescendant={activeResult ? `${inputId}-result-${activeResult.type}-${activeResult.id}` : undefined}
        />
        {showClear && (
          <Button type="button" variant="ghost" size="icon" className="size-7 rounded-full bg-[var(--control-bg)] text-[var(--text-muted)] hover:bg-[var(--control-hover)] hover:text-[var(--text)]" onClick={handleClear} aria-label="Clear search and selection">
            <X aria-hidden="true" />
          </Button>
        )}
      </div>

      {shouldShowDropdown && (
        <div
          id={`${inputId}-results`}
          className="absolute left-0 right-0 top-[calc(100%+8px)] z-[100] grid max-h-[280px] gap-1 overflow-y-auto rounded-[14px] border border-[var(--surface-border)] bg-[var(--surface-dropdown)] p-1.5 shadow-[var(--surface-shadow)] min-[900px]:[.search-sidebar-anchor_&]:left-[calc(100%+20px)] min-[900px]:[.search-sidebar-anchor_&]:right-auto min-[900px]:[.search-sidebar-anchor_&]:top-[25px] min-[900px]:[.search-sidebar-anchor_&]:max-h-[min(580px,calc(100dvh-170px))] min-[900px]:[.search-sidebar-anchor_&]:w-[clamp(340px,34vw,500px)] min-[900px]:[.search-sidebar-anchor_&]:bg-[var(--surface-panel)] min-[900px]:[.search-sidebar-anchor_&]:backdrop-blur-[10px]"
          ref={dropdownRef}
        >
          {isLoading && <div className={dropdownStatusClass}>Searching...</div>}
          {!isLoading && (
            <>
              {showResultTabs && (
                <div className="grid gap-1.5">
                  <div className="grid grid-cols-4 gap-1 rounded-xl bg-[var(--surface-input)] p-1" role="tablist" aria-label="Search result types">
                    {SEARCH_RESULT_TABS.map(({ type, label }) => {
                      const isActive = activeResultType === type

                      return (
                        <button
                          key={type}
                          id={`${inputId}-tab-${type}`}
                          type="button"
                          className={cn(tabClass, isActive && 'bg-[var(--control-bg)] text-[var(--text)]')}
                          role="tab"
                          aria-selected={isActive}
                          aria-controls={`${inputId}-results-panel-${type}`}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectTab(type)}
                        >
                          <span className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap">{label}</span>
                        </button>
                      )
                    })}
                  </div>

                  <label className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2 rounded-[10px] bg-[var(--surface-input)] px-1.5 py-1">
                    <span className="text-[0.74rem] font-bold uppercase text-[var(--text-muted)]">Sort</span>
                    <select
                      className="min-w-0 cursor-pointer rounded-lg border border-[var(--control-border)] bg-[var(--surface-panel)] px-2 py-1.5 text-[0.82rem] font-[inherit] text-[var(--text)]"
                      value={activeSort}
                      onChange={(event) => handleSortChange(event.target.value as SearchSort)}
                    >
                      {SEARCH_SORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              <div
                id={`${inputId}-results-panel-${activeResultType}`}
                className="grid gap-1"
                role={showResultTabs ? 'tabpanel' : undefined}
                aria-labelledby={showResultTabs ? `${inputId}-tab-${activeResultType}` : undefined}
              >
                {visibleResults.length > 0 ? (
                  <div className="grid gap-1" role="listbox" aria-label={showResultTabs ? `${activeResultType} search results` : 'Search results'}>
                    {visibleResults.map((result, index) => (
                      <button
                        key={`${result.type}-${result.id}`}
                        id={`${inputId}-result-${result.type}-${result.id}`}
                        type="button"
                        className={cn(optionClass, index === activeResultIndex && 'bg-[var(--control-bg)]')}
                        role="option"
                        aria-selected={index === activeResultIndex}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          selectResult(result)
                        }}
                      >
                        <span className="grid size-6 flex-[0_0_24px] place-items-center rounded-full bg-[var(--control-bg)] text-[0.76rem] font-bold text-[var(--text-muted)]">{index + 1}</span>
                        <span className="grid min-w-0 flex-auto justify-items-start gap-0.5 text-left">
                          <strong className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap">{result.name}</strong>
                          {getResultMeta(result) && <small className="max-w-full overflow-hidden text-ellipsis whitespace-nowrap text-[0.82rem] text-[var(--text-muted)]">{getResultMeta(result)}</small>}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className={dropdownStatusClass}>No {activeResultType} matches</div>
                )}
              </div>

              {canLoadMore && (
                <button
                  type="button"
                  className="w-full cursor-pointer rounded-[10px] border border-[var(--control-border)] bg-[var(--control-bg)] px-3 py-2.5 text-center text-[0.88rem] font-[inherit] text-[var(--text)] outline-none hover:border-[var(--focus-border)] hover:bg-[var(--control-hover)] focus-visible:border-[var(--focus-border)] focus-visible:bg-[var(--control-hover)]"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={handleLoadMore}
                >
                  Load more results
                </button>
              )}
            </>
          )}
        </div>
      )}
    </form>
  )
}
