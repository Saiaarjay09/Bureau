import { useState } from 'react'
import { api, ApiError } from '../api'

export default function LoginPage({ onLoggedIn }: { onLoggedIn: (username: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await api.login(username, password)
      onLoggedIn(res.username)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--paper)] px-4 py-12">
      <div className="mb-10 select-none text-center">
        <h1 className="font-serif-mast text-6xl italic text-[var(--ink)]" style={{ letterSpacing: '0.01em' }}>
          Bureau
        </h1>
        <div className="mx-auto my-3 h-[2px] w-16 bg-[var(--accent)]" />
        <p className="font-mono-kicker text-[11px] text-[var(--ink-faint)]">Leads, by region</p>
      </div>

      <form
        onSubmit={submit}
        className="w-full max-w-sm border border-[var(--hairline)] bg-[var(--surface)] p-8"
      >
        <p className="mb-6 text-sm text-[var(--ink-muted)]">Sign in to see today's dispatch.</p>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-mono-kicker text-[10px] text-[var(--ink-faint)]">Username</span>
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full border border-[var(--hairline)] bg-transparent px-3 py-2 text-[var(--ink)] outline-none focus:border-[var(--accent)]"
          />
        </label>
        <label className="mb-5 block text-sm">
          <span className="mb-1 block font-mono-kicker text-[10px] text-[var(--ink-faint)]">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-[var(--hairline)] bg-transparent px-3 py-2 text-[var(--ink)] outline-none focus:border-[var(--accent)]"
          />
        </label>

        {error && <p className="mb-4 text-sm text-[var(--accent)]">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[var(--accent)] py-2 font-medium text-[var(--accent-ink)] transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
