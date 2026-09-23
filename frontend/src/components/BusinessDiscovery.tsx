import { useState } from 'react'
import { api, ApiError } from '../api'

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
      <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
        Set <code>FIRECRAWL_API_KEY</code> in backend/.env to discover new business leads live. Showing
        whatever's already in the database (mock data, until then).
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
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
      <span className="text-sm text-neutral-500">Discover businesses in</span>
      <input
        value={industry}
        onChange={(e) => setIndustry(e.target.value)}
        placeholder="an industry, e.g. Fintech"
        className="w-48 rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-sm text-neutral-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
      />
      <span className="text-sm text-neutral-500">{region ? `within ${region}` : 'globally'}</span>
      <button
        onClick={run}
        disabled={running || !industry.trim()}
        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {running ? 'Searching…' : 'Discover'}
      </button>
      {message && <span className="text-sm text-neutral-500">{message}</span>}
    </div>
  )
}
