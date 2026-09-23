import type { Lead } from '../types'

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  if (days < 30) return `${days} days ago`
  return `${Math.floor(days / 30)} mo ago`
}

const REMOTE_BADGE: Record<string, string> = {
  remote: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  hybrid: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  onsite: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300',
}

export default function LeadCard({ lead, onToggleStar }: { lead: Lead; onToggleStar: (id: number) => void }) {
  const location = [lead.city, lead.country].filter(Boolean).join(', ') || 'Location unknown'

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 transition hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={lead.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="block truncate font-medium text-neutral-900 hover:text-indigo-600 dark:text-neutral-100 dark:hover:text-indigo-400"
          >
            {lead.title}
          </a>
          <p className="truncate text-sm text-neutral-500">
            {lead.company} · {location}
          </p>
        </div>
        <button
          onClick={() => onToggleStar(lead.id)}
          aria-label={lead.starred ? 'Unstar' : 'Star'}
          className={`shrink-0 text-lg ${lead.starred ? 'text-amber-400' : 'text-neutral-300 hover:text-amber-400'}`}
        >
          {lead.starred ? '★' : '☆'}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
        {lead.lead_type === 'job' && lead.remote_type && (
          <span className={`rounded-full px-2 py-0.5 font-medium ${REMOTE_BADGE[lead.remote_type] ?? REMOTE_BADGE.onsite}`}>
            {lead.remote_type}
          </span>
        )}
        {lead.lead_type === 'job' && lead.seniority && (
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
            {lead.seniority}
          </span>
        )}
        {lead.lead_type === 'business' && lead.industry && (
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
            {lead.industry}
          </span>
        )}
        {lead.company_size && (
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
            {lead.company_size} employees
          </span>
        )}
        {lead.funding_stage && (
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
            {lead.funding_stage}
          </span>
        )}
        <span className="ml-auto text-neutral-400">{timeAgo(lead.posted_date)}</span>
      </div>

      {lead.signal && (
        <p className="mt-2 text-sm text-indigo-700 dark:text-indigo-400">{lead.signal}</p>
      )}

      {lead.lead_type === 'business' && lead.contact_path && (
        <p className="mt-1 truncate text-xs text-neutral-500">Contact: {lead.contact_path}</p>
      )}

      <p className="mt-2 text-[11px] uppercase tracking-wide text-neutral-400">{lead.source}</p>
    </div>
  )
}
