import { useState } from 'react'
import { api, ApiError } from '../api'

export default function JobDiscovery({
  firecrawlConfigured,
  region,
  onDiscovered,
}: {
  firecrawlConfigured: boolean
  region: string
  onDiscovered: () => void
}) {
  const [role, setRole] = useState('')
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  if (!firecrawlConfigured) {
    return null // the job feed already works without Firecrawl; no need to nag here too
  }

  async function run() {
    if (!role.trim()) return
    setRunning(true)
    setMessage(null)
    try {
      const res = await api.ingestJobSearch(role.trim(), region)
      setMessage(`Found ${res.created} new leads (${res.updated} updated).`)
      onDiscovered()
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : 'Discovery failed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 border border-[var(--hairline)] bg-[var(--surface)] p-3">
      <span className="text-sm text-[var(--ink-muted)]">Search the web for</span>
      <input
        value={role}
        onChange={(e) => setRole(e.target.value)}
        placeholder="a role, e.g. IT Director"
        className="w-48 border border-[var(--hairline)] bg-transparent px-3 py-1.5 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)]"
      />
      <span className="text-sm text-[var(--ink-muted)]">{region ? `in ${region}` : 'globally'}</span>
      <button
        onClick={run}
        disabled={running || !role.trim()}
        className="bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 disabled:opacity-50"
      >
        {running ? 'Searching…' : 'Discover'}
      </button>
      {message && <span className="text-sm text-[var(--ink-muted)]">{message}</span>}
      <span className="ml-auto font-mono-kicker text-[9px] text-[var(--ink-faint)]">
        reaches roles/regions the automatic sources miss
      </span>
    </div>
  )
}
