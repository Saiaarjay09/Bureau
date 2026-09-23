import { useState } from 'react'
import { api, ApiError } from '../api'
import Spinner from './Spinner'

export default function BusinessDiscovery({
  firecrawlConfigured,
  region,
  onDiscovered,
}: {
  firecrawlConfigured: boolean
  region: string
  onDiscovered: () => void
}) {
  const [industry, setIndustry] = useState('')
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  if (!firecrawlConfigured) {
    return (
      <p className="mb-4 border border-[var(--hairline)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[var(--ink-muted)]">
        Set <code className="font-mono-kicker text-[10px] normal-case tracking-normal">FIRECRAWL_API_KEY</code> in
        backend/.env to discover new business leads live. Showing whatever's already in the database (mock data,
        until then).
      </p>
    )
  }

  async function run() {
    if (!industry.trim()) return
    setRunning(true)
    setMessage(null)
    try {
      const res = await api.ingestBusiness(industry.trim(), region)
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
      <span className="text-sm text-[var(--ink-muted)]">Discover businesses in</span>
      <input
        value={industry}
        onChange={(e) => setIndustry(e.target.value)}
        placeholder="an industry, e.g. Fintech"
        className="w-48 border border-[var(--hairline)] bg-transparent px-3 py-1.5 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)]"
      />
      <span className="text-sm text-[var(--ink-muted)]">{region ? `within ${region}` : 'globally'}</span>
      <button
        onClick={run}
        disabled={running || !industry.trim()}
        className="flex items-center gap-2 bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 disabled:opacity-50"
      >
        {running && <Spinner />}
        {running ? 'Searching…' : 'Discover'}
      </button>
      {message && <span className="text-sm text-[var(--ink-muted)]">{message}</span>}
    </div>
  )
}
