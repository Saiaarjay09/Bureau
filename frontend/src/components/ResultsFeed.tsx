import type { Lead } from '../types'
import LeadCard from './LeadCard'
import Spinner from './Spinner'

export default function ResultsFeed({
  leads,
  total,
  loading,
  error,
  onToggleStar,
  onLoadMore,
  hasMore,
}: {
  leads: Lead[]
  total: number
  loading: boolean
  error: string | null
  onToggleStar: (id: number) => void
  onLoadMore: () => void
  hasMore: boolean
}) {
  if (error) {
    return <p className="py-12 text-center text-sm text-[var(--accent)]">{error}</p>
  }

  if (loading && leads.length === 0) {
    return (
      <div className="flex justify-center py-16 text-[var(--ink-faint)]">
        <Spinner className="h-6 w-6 border-[3px]" />
      </div>
    )
  }

  if (!loading && leads.length === 0) {
    return (
      <div className="py-16 text-center text-[var(--ink-muted)]">
        <p className="font-serif-mast text-xl italic">No leads match these filters yet.</p>
        <p className="mt-1 text-sm">Try widening the region, or refresh sources above.</p>
      </div>
    )
  }

  return (
    <div>
      <p className="font-mono-kicker mb-3 text-[10px] text-[var(--ink-faint)]">
        {total} lead{total === 1 ? '' : 's'}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {leads.map((lead) => (
          <LeadCard key={lead.id} lead={lead} onToggleStar={onToggleStar} />
        ))}
      </div>
      {loading && (
        <p className="flex items-center justify-center gap-2 py-6 text-sm text-[var(--ink-faint)]">
          <Spinner /> Loading…
        </p>
      )}
      {!loading && hasMore && (
        <div className="mt-6 flex justify-center">
          <button
            onClick={onLoadMore}
            className="font-mono-kicker border border-[var(--hairline)] px-4 py-2 text-[10px] text-[var(--ink-muted)] hover:border-[var(--hairline-strong)] hover:text-[var(--ink)]"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  )
}
