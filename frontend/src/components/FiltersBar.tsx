import type { LeadType, SortOrder } from '../types'

export interface Filters {
  search: string
  remoteType: string
  sort: SortOrder
  starredOnly: boolean
}

const fieldClass =
  'border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)]'

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
    <div className="flex flex-wrap items-center gap-2 border-y border-[var(--hairline)] py-3">
      <input
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        placeholder={leadType === 'job' ? 'Search title, company, signal…' : 'Search company, signal…'}
        className={`w-56 ${fieldClass}`}
      />

      {leadType === 'job' && (
        <select
          value={filters.remoteType}
          onChange={(e) => onChange({ ...filters, remoteType: e.target.value })}
          className={fieldClass}
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
        className={fieldClass}
      >
        <option value="newest">Newest first</option>
        <option value="oldest">Oldest first</option>
        <option value="company">Company A-Z</option>
      </select>

      <label className="flex items-center gap-1.5 text-sm text-[var(--ink-muted)]">
        <input
          type="checkbox"
          checked={filters.starredOnly}
          onChange={(e) => onChange({ ...filters, starredOnly: e.target.checked })}
          className="accent-[var(--accent)]"
        />
        Starred only
      </label>

      <div className="ml-auto flex gap-2">
        <button
          onClick={() => onExport('csv')}
          className="font-mono-kicker border border-[var(--hairline)] px-3 py-2 text-[10px] text-[var(--ink-muted)] hover:border-[var(--hairline-strong)] hover:text-[var(--ink)]"
        >
          Export CSV
        </button>
        <button
          onClick={() => onExport('json')}
          className="font-mono-kicker border border-[var(--hairline)] px-3 py-2 text-[10px] text-[var(--ink-muted)] hover:border-[var(--hairline-strong)] hover:text-[var(--ink)]"
        >
          Export JSON
        </button>
      </div>
    </div>
  )
}
