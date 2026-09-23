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
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 dark:bg-neutral-950">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-neutral-200 bg-white p-8 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      >
        <h1 className="mb-1 text-2xl font-semibold text-neutral-900 dark:text-neutral-100">Scout</h1>
        <p className="mb-6 text-sm text-neutral-500">Sign in to see your leads.</p>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block text-neutral-600 dark:text-neutral-400">Username</span>
          <input
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-neutral-900 outline-none focus:border-indigo-500 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
          />
        </label>
        <label className="mb-4 block text-sm">
          <span className="mb-1 block text-neutral-600 dark:text-neutral-400">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-neutral-900 outline-none focus:border-indigo-500 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
          />
        </label>

        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-indigo-600 py-2 font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
