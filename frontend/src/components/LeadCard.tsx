import type { Lead } from '../types'

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  if (days < 30) return `${days} days ago`
  return `${Math.floor(days / 30)} mo ago`
}

export default function LeadCard({
  lead,
  onToggleStar,
  onOpen,
}: {
  lead: Lead
  onToggleStar: (id: number) => void
  onOpen: (id: number) => void
}) {
  const location = [lead.city, lead.country].filter(Boolean).join(', ') || 'Location unknown'

  const tags = [
    lead.lead_type === 'job' ? lead.remote_type : null,
    lead.lead_type === 'job' ? lead.seniority : lead.industry,
    lead.company_size && `${lead.company_size} employees`,
    lead.funding_stage,
  ].filter(Boolean) as string[]

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(lead.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen(lead.id)
        }
      }}
      className="flex cursor-pointer flex-col border border-[var(--hairline)] bg-[var(--surface)] p-4 text-left transition hover:border-[var(--hairline-strong)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="block truncate text-[15px] font-medium text-[var(--ink)]">{lead.title}</span>
          <p className="truncate text-sm text-[var(--ink-muted)]">
            {lead.company} · {location}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {/* Either number may exist without the other: a lead can be
              screened but never sent to the council, or sent to the council
              directly without ever having been screened. The council verdict
              is the stronger signal, so it wins when both are present. */}
          {lead.council_score !== null ? (
            <span className="font-mono-kicker text-[10px] text-[var(--accent)]">
              council {lead.council_score}
            </span>
          ) : (
            lead.fit_score !== null && (
              <span
                title={lead.fit_reason ?? undefined}
                className="font-mono-kicker text-[10px] text-[var(--ink-muted)]"
              >
                {lead.fit_score}
              </span>
            )
          )}
          <button
            // Stops the card's own onClick from firing — starring shouldn't
            // also open the panel.
            onClick={(e) => {
              e.stopPropagation()
              onToggleStar(lead.id)
            }}
            aria-label={lead.starred ? 'Unstar' : 'Star'}
            className={`text-lg leading-none ${lead.starred ? 'text-[var(--accent)]' : 'text-[var(--hairline-strong)] hover:text-[var(--accent)]'}`}
          >
            {lead.starred ? '★' : '☆'}
          </button>
        </div>
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
