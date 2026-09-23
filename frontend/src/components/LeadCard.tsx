import type { Lead } from '../types'

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  if (days < 30) return `${days} days ago`
  return `${Math.floor(days / 30)} mo ago`
}

export default function LeadCard({ lead, onToggleStar }: { lead: Lead; onToggleStar: (id: number) => void }) {
  const location = [lead.city, lead.country].filter(Boolean).join(', ') || 'Location unknown'

  const tags = [
    lead.lead_type === 'job' ? lead.remote_type : null,
    lead.lead_type === 'job' ? lead.seniority : lead.industry,
    lead.company_size && `${lead.company_size} employees`,
    lead.funding_stage,
  ].filter(Boolean) as string[]

  return (
    <div className="flex flex-col border border-[var(--hairline)] bg-[var(--surface)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={lead.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="block truncate text-[15px] font-medium text-[var(--ink)] hover:text-[var(--accent)]"
          >
            {lead.title}
          </a>
          <p className="truncate text-sm text-[var(--ink-muted)]">
            {lead.company} · {location}
          </p>
        </div>
        <button
          onClick={() => onToggleStar(lead.id)}
          aria-label={lead.starred ? 'Unstar' : 'Star'}
          className={`shrink-0 text-lg leading-none ${lead.starred ? 'text-[var(--accent)]' : 'text-[var(--hairline-strong)] hover:text-[var(--accent)]'}`}
        >
          {lead.starred ? '★' : '☆'}
        </button>
      </div>

      {tags.length > 0 && (
        <p className="font-mono-kicker mt-3 text-[10px] text-[var(--ink-faint)]">
          {tags.join('  ·  ')}
          <span className="float-right normal-case tracking-normal">{timeAgo(lead.posted_date)}</span>
        </p>
      )}

      {lead.signal && (
        <p className="mt-3 border-l-2 border-[var(--accent)] pl-3 font-serif-mast text-[15px] italic leading-snug text-[var(--accent)]">
          {lead.signal}
        </p>
      )}

      {lead.lead_type === 'business' && lead.contact_path && (
        <p className="mt-2 truncate text-xs text-[var(--ink-faint)]">Contact: {lead.contact_path}</p>
      )}

      <p className="font-mono-kicker mt-3 text-[9px] text-[var(--ink-faint)]">{lead.source}</p>
    </div>
  )
}
