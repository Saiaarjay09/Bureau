import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { LeadDetail } from '../types'
import Spinner from './Spinner'

const COUNCIL_POLL_MS = 10_000

export default function LeadDetailPanel({
  leadId,
  onClose,
  onLeadChanged,
}: {
  leadId: number
  onClose: () => void
  onLeadChanged: () => void
}) {
  const [lead, setLead] = useState<LeadDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [councilError, setCouncilError] = useState<string | null>(null)

  // No state reset needed on leadId change: App.tsx keys this component on
  // the lead id, so opening a different lead remounts it with fresh state
  // rather than briefly showing the previous lead's description.
  useEffect(() => {
    let cancelled = false
    api
      .lead(leadId)
      .then((res) => !cancelled && setLead(res))
      .catch(() => !cancelled && setError('Could not load this lead.'))
    return () => {
      cancelled = true
    }
  }, [leadId])

  // A council run takes minutes and finishes server-side, so the panel polls
  // rather than holding a request open for the duration.
  useEffect(() => {
    if (lead?.council_status !== 'running') return
    const timer = setInterval(() => {
      api
        .lead(leadId)
        .then((res) => {
          setLead(res)
          if (res.council_status !== 'running') onLeadChanged()
        })
        .catch(() => {})
    }, COUNCIL_POLL_MS)
    return () => clearInterval(timer)
  }, [lead?.council_status, leadId, onLeadChanged])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function runCouncil() {
    setStarting(true)
    setCouncilError(null)
    try {
      await api.startCouncil(leadId)
      const res = await api.lead(leadId)
      setLead(res)
    } catch (err) {
      setCouncilError(err instanceof ApiError ? err.message : 'Could not start the council.')
    } finally {
      setStarting(false)
    }
  }

  const location = lead ? [lead.city, lead.country].filter(Boolean).join(', ') || 'Location unknown' : ''

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-[var(--hairline)] bg-[var(--surface)] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <span className="font-mono-kicker text-[10px] text-[var(--ink-faint)]">
            {lead?.source ?? 'loading'}
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="font-mono-kicker text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent)]"
          >
            Close ✕
          </button>
        </div>

        {error && <p className="text-sm text-[var(--accent)]">{error}</p>}
        {!lead && !error && (
          <div className="flex justify-center py-16 text-[var(--ink-faint)]">
            <Spinner className="h-6 w-6 border-[3px]" />
          </div>
        )}

        {lead && (
          <>
            <h2 className="font-serif-mast text-2xl italic text-[var(--ink)]">{lead.title}</h2>
            <p className="mt-1 text-sm text-[var(--ink-muted)]">
              {lead.company} · {location}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-3 border-y border-[var(--hairline)] py-3">
              {lead.fit_score !== null && (
                <span className="font-mono-kicker text-[10px] text-[var(--ink-muted)]">
                  screen {lead.fit_score}/100
                </span>
              )}
              {lead.council_score !== null && (
                <span className="font-mono-kicker text-[10px] text-[var(--accent)]">
                  council {lead.council_score}/100
                </span>
              )}
              {lead.url && (
                <a
                  href={lead.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono-kicker ml-auto text-[10px] text-[var(--ink-muted)] hover:text-[var(--accent)]"
                >
                  Open original ↗
                </a>
              )}
            </div>

            {lead.fit_reason && (
              <p className="mt-3 text-sm text-[var(--ink-muted)]">
                <span className="font-mono-kicker text-[10px] text-[var(--ink-faint)]">screen note</span>{' '}
                {lead.fit_reason}
              </p>
            )}

            <CouncilSection
              lead={lead}
              starting={starting}
              error={councilError}
              onRun={runCouncil}
            />

            <h3 className="font-mono-kicker mt-6 text-[10px] text-[var(--ink-faint)]">Description</h3>
            {lead.description ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">
                {lead.description}
              </p>
            ) : (
              <p className="mt-2 text-sm text-[var(--ink-muted)]">
                No description was captured when this lead was ingested — the source only listed a
                title. Convening the council will try to fetch the posting first
                {lead.url ? '' : ', though this lead has no URL to fetch from'}; failing that, it
                assesses the title against a generic rubric for that role.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function CouncilSection({
  lead,
  starting,
  error,
  onRun,
}: {
  lead: LeadDetail
  starting: boolean
  error: string | null
  onRun: () => void
}) {
  const verdict = lead.council

  if (lead.council_status === 'running') {
    return (
      <div className="mt-4 flex items-center gap-2 border border-[var(--hairline)] bg-[var(--accent-soft)] p-3 text-sm text-[var(--ink-muted)]">
        <Spinner />
        The council is sitting — seven assessors, typically 5–7 minutes. You can close this; the
        verdict is saved when it finishes.
      </div>
    )
  }

  if (lead.council_status === 'done' && verdict) {
    return (
      <div className="mt-4 border border-[var(--hairline)] p-4">
        <div className="flex flex-wrap items-baseline gap-4">
          <span className="font-serif-mast text-3xl italic text-[var(--accent)]">
            {verdict.score ?? lead.council_score}
          </span>
          <span className="font-mono-kicker text-[10px] text-[var(--ink-faint)]">
            out of 100 · {verdict.match_pct ?? lead.council_match_pct}% of requirements ·{' '}
            {verdict.verdict} · {verdict.confidence} confidence
          </span>
        </div>
        {verdict.summary && (
          <p className="mt-3 text-sm leading-relaxed text-[var(--ink)]">{verdict.summary}</p>
        )}
        {verdict.blocking_gaps && verdict.blocking_gaps.length > 0 && (
          <>
            <h4 className="font-mono-kicker mt-4 text-[10px] text-[var(--ink-faint)]">Blocking gaps</h4>
            <ul className="mt-1 list-disc pl-5 text-sm text-[var(--ink-muted)]">
              {verdict.blocking_gaps.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </>
        )}
        <button
          onClick={onRun}
          disabled={starting}
          className="font-mono-kicker mt-4 border border-[var(--hairline)] px-3 py-1.5 text-[10px] text-[var(--ink-muted)] hover:border-[var(--hairline-strong)] hover:text-[var(--ink)] disabled:opacity-50"
        >
          Run again
        </button>
      </div>
    )
  }

  return (
    <div className="mt-4">
      {lead.council_status === 'failed' && (
        <p className="mb-2 text-sm text-[var(--accent)]">
          The last council run failed{verdict?.error ? `: ${verdict.error}` : '.'}
        </p>
      )}
      <button
        onClick={onRun}
        disabled={starting}
        className="flex items-center gap-2 bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 disabled:opacity-50"
      >
        {starting && <Spinner />}
        Convene the council on this job
      </button>
      {error && <p className="mt-2 text-sm text-[var(--accent)]">{error}</p>}
      <p className="mt-2 text-xs text-[var(--ink-faint)]">
        Runs Sabha's full seven-member panel against your CV locally — 5–7 minutes. The screen
        score above is a one-pass triage signal, not this.
        {!lead.description && ' With no description stored, it fetches the posting first.'}
      </p>
    </div>
  )
}
