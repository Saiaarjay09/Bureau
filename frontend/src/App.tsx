import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import BusinessDiscovery from './components/BusinessDiscovery'
import FiltersBar, { type Filters } from './components/FiltersBar'
import LeadTypeToggle from './components/LeadTypeToggle'
import LoginPage from './components/LoginPage'
import RegionSelector, { GLOBAL, type RegionValue } from './components/RegionSelector'
import ResultsFeed from './components/ResultsFeed'
import type { Lead, LeadType } from './types'

const PAGE_SIZE = 30

const DEFAULT_FILTERS: Filters = { search: '', remoteType: '', sort: 'newest', starredOnly: false }

export default function App() {
  const [authState, setAuthState] = useState<'checking' | 'out' | 'in'>('checking')
  const [username, setUsername] = useState<string | null>(null)

  const [leadType, setLeadType] = useState<LeadType>('job')
  const [region, setRegion] = useState<RegionValue>(GLOBAL)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [ingesting, setIngesting] = useState(false)
  const [ingestMessage, setIngestMessage] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [firecrawlConfigured, setFirecrawlConfigured] = useState(false)

  useEffect(() => {
    api
      .me()
      .then((res) => {
        setUsername(res.username)
        setAuthState('in')
      })
      .catch(() => setAuthState('out'))
  }, [])

  useEffect(() => {
    if (authState !== 'in') return
    api
      .ingestStatus()
      .then((res) => setFirecrawlConfigured(res.firecrawl_configured))
      .catch(() => {})
  }, [authState])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(filters.search), 300)
    return () => clearTimeout(t)
  }, [filters.search])

  // Reset to page 1 whenever the query itself changes.
  useEffect(() => {
    setPage(1)
  }, [leadType, region, debouncedSearch, filters.remoteType, filters.sort, filters.starredOnly])

  const queryParams = useCallback(
    (targetPage: number) => ({
      lead_type: leadType,
      continent: region.continent || undefined,
      country: region.country || undefined,
      city: region.city || undefined,
      search: debouncedSearch || undefined,
      remote_type: filters.remoteType || undefined,
      starred_only: filters.starredOnly || undefined,
      sort: filters.sort,
      page: targetPage,
      page_size: PAGE_SIZE,
    }),
    [leadType, region, debouncedSearch, filters.remoteType, filters.sort, filters.starredOnly],
  )

  useEffect(() => {
    if (authState !== 'in') return
    setLoading(true)
    setError(null)
    api
      .leads(queryParams(page))
      .then((res) => {
        setTotal(res.total)
        setLeads((prev) => (page === 1 ? res.items : [...prev, ...res.items]))
      })
      .catch(() => setError('Could not load leads. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [authState, page, queryParams, refreshTick])

  async function toggleStar(id: number) {
    const updated = await api.toggleStar(id)
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)))
  }

  function exportLeads(format: 'csv' | 'json') {
    const url = api.exportUrl({ ...queryParams(1), page: undefined, page_size: undefined, format })
    window.open(url, '_blank')
  }

  async function refreshJobSources() {
    setIngesting(true)
    setIngestMessage(null)
    try {
      await api.ingestJobs()
      setIngestMessage('Refreshed job sources.')
      setPage(1)
      setRefreshTick((t) => t + 1)
    } catch {
      setIngestMessage('Refresh failed — check the backend log.')
    } finally {
      setIngesting(false)
    }
  }

  if (authState === 'checking') {
    return <div className="flex min-h-screen items-center justify-center text-neutral-400">Loading…</div>
  }

  if (authState === 'out') {
    return (
      <LoginPage
        onLoggedIn={(name) => {
          setUsername(name)
          setAuthState('in')
        }}
      />
    )
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <header className="border-b border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-4">
          <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">Scout</h1>
          <LeadTypeToggle value={leadType} onChange={setLeadType} />
          <RegionSelector leadType={leadType} value={region} onChange={setRegion} />
          <div className="ml-auto flex items-center gap-3 text-sm text-neutral-500">
            <button
              onClick={refreshJobSources}
              disabled={ingesting}
              className="rounded-lg border border-neutral-300 px-3 py-1.5 hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
            >
              {ingesting ? 'Refreshing…' : 'Refresh job sources'}
            </button>
            <span>{username}</span>
            <button
              onClick={() => api.logout().then(() => setAuthState('out'))}
              className="hover:text-neutral-800 dark:hover:text-neutral-300"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {ingestMessage && <p className="mb-3 text-sm text-neutral-500">{ingestMessage}</p>}
        {leadType === 'business' && (
          <BusinessDiscovery
            firecrawlConfigured={firecrawlConfigured}
            region={region.city || region.country || region.continent || ''}
            onDiscovered={() => {
              setPage(1)
              setRefreshTick((t) => t + 1)
            }}
          />
        )}
        <div className="mb-4">
          <FiltersBar leadType={leadType} filters={filters} onChange={setFilters} onExport={exportLeads} />
        </div>
        <ResultsFeed
          leads={leads}
          total={total}
          loading={loading}
          error={error}
          onToggleStar={toggleStar}
          onLoadMore={() => setPage((p) => p + 1)}
          hasMore={leads.length < total}
        />
      </main>
    </div>
  )
}
