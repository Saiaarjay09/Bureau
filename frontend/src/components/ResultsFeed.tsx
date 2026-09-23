import type { Lead } from '../types'
import LeadCard from './LeadCard'

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
    return <p className="py-12 text-center text-sm text-red-600 dark:text-red-400">{error}</p>
  }

  if (!loading && leads.length === 0) {
    return (
      <div className="py-16 text-center text-neutral-500">
        <p className="text-lg font-medium">No leads match these filters yet.</p>
        <p className="mt-1 text-sm">Try widening the region, or refresh sources from the sidebar.</p>
      </div>
    )
  }

  return (
    <div>
      <p className="mb-3 text-sm text-neutral-500">{total} lead{total === 1 ? '' : 's'}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {leads.map((lead) => (
          <LeadCard key={lead.id} lead={lead} onToggleStar={onToggleStar} />
        ))}
      </div>
      {loading && <p className="py-6 text-center text-sm text-neutral-400">Loading…</p>}
      {!loading && hasMore && (
        <div className="mt-6 flex justify-center">
          <button
            onClick={onLoadMore}
            className="rounded-lg border border-neutral-300 px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  )
}
