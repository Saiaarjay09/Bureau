import type { LeadType, SortOrder } from '../types'

export interface Filters {
  search: string
  remoteType: string
  sort: SortOrder
  starredOnly: boolean
}

export default function FiltersBar({
  leadType,
  filters,
  onChange,
  onExport,
}: {
  leadType: LeadType
  filters: Filters
  onChange: (filters: Filters) => void
  onExport: (format: 'csv' | 'json') => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        placeholder={leadType === 'job' ? 'Search title, company, signal…' : 'Search company, signal…'}
        className="w-56 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
      />

      {leadType === 'job' && (
        <select
          value={filters.remoteType}
          onChange={(e) => onChange({ ...filters, remoteType: e.target.value })}
          className="rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
        >
          <option value="">Any work mode</option>
          <option value="remote">Remote</option>
          <option value="hybrid">Hybrid</option>
          <option value="onsite">Onsite</option>
        </select>
      )}

      <select
        value={filters.sort}
        onChange={(e) => onChange({ ...filters, sort: e.target.value as SortOrder })}
        className="rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
      >
        <option value="newest">Newest first</option>
        <option value="oldest">Oldest first</option>
        <option value="company">Company A-Z</option>
      </select>

      <label className="flex items-center gap-1.5 text-sm text-neutral-600 dark:text-neutral-400">
        <input
          type="checkbox"
          checked={filters.starredOnly}
          onChange={(e) => onChange({ ...filters, starredOnly: e.target.checked })}
        />
        Starred only
      </label>

      <div className="ml-auto flex gap-2">
        <button
          onClick={() => onExport('csv')}
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          Export CSV
        </button>
        <button
          onClick={() => onExport('json')}
          className="rounded-lg border border-neutral-300 px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          Export JSON
        </button>
      </div>
    </div>
  )
}
