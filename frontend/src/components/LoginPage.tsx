import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

type Mode = 'checking' | 'signup' | 'recovery-display' | 'login' | 'recover'

const Masthead = () => (
  <div className="mb-10 select-none text-center">
    <h1 className="font-serif-mast text-6xl italic text-[var(--ink)]" style={{ letterSpacing: '0.01em' }}>
      Bureau
    </h1>
    <div className="mx-auto my-3 h-[2px] w-16 bg-[var(--accent)]" />
    <p className="font-mono-kicker text-[11px] text-[var(--ink-faint)]">Leads, by region</p>
  </div>
)

const inputClass =
  'w-full border border-[var(--hairline)] bg-transparent px-3 py-2 text-[var(--ink)] outline-none focus:border-[var(--accent)]'
const labelClass = 'mb-1 block font-mono-kicker text-[10px] text-[var(--ink-faint)]'
const primaryButtonClass =
  'w-full bg-[var(--accent)] py-2 font-medium text-[var(--accent-ink)] transition hover:opacity-90 disabled:opacity-50'

export default function LoginPage({ onLoggedIn }: { onLoggedIn: (username: string) => void }) {
  const [mode, setMode] = useState<Mode>('checking')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [recoveryPhrase, setRecoveryPhrase] = useState('')
  const [recoveryAcked, setRecoveryAcked] = useState(false)
  const [recoverPhraseInput, setRecoverPhraseInput] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api
      .authStatus()
      .then((res) => setMode(res.credentials_configured ? 'login' : 'signup'))
      .catch(() => setMode('login'))
  }, [])

  async function submitSignup(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await api.signup(username, password)
      setUsername(res.username)
      setRecoveryPhrase(res.recovery_phrase)
      setMode('recovery-display')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create account')
    } finally {
      setLoading(false)
    }
  }

  async function submitLogin(e: React.FormEvent) {
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

  async function submitRecover(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.recover(recoverPhraseInput, newPassword)
      setInfo('Password updated — sign in with your new password below.')
      setPassword('')
      setRecoverPhraseInput('')
      setNewPassword('')
      setMode('login')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Recovery failed')
    } finally {
      setLoading(false)
    }
  }

  if (mode === 'checking') {
    return <div className="flex min-h-screen items-center justify-center bg-[var(--paper)]" />
  }

  if (mode === 'recovery-display') {
    const words = recoveryPhrase.split(' ')
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--paper)] px-4 py-12">
        <Masthead />
        <div className="w-full max-w-md border border-[var(--hairline)] bg-[var(--surface)] p-8">
          <p className="font-mono-kicker mb-1 text-[10px] text-[var(--accent)]">Save this now — shown once</p>
          <p className="mb-5 text-sm text-[var(--ink-muted)]">
            This 12-word recovery phrase is the only way back into your account if you forget your password.
            Write it down somewhere safe. It will never be shown again.
          </p>
          <div className="mb-5 grid grid-cols-3 gap-2 border border-[var(--hairline)] bg-[var(--accent-soft)] p-4">
            {words.map((word, i) => (
              <div key={i} className="font-mono-kicker text-xs normal-case tracking-normal text-[var(--ink)]">
                <span className="text-[var(--ink-faint)]">{i + 1}.</span> {word}
              </div>
            ))}
          </div>
          <label className="mb-5 flex items-center gap-2 text-sm text-[var(--ink-muted)]">
            <input
              type="checkbox"
              checked={recoveryAcked}
              onChange={(e) => setRecoveryAcked(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            I've saved this phrase somewhere safe
          </label>
          <button
            onClick={() => onLoggedIn(username)}
            disabled={!recoveryAcked}
            className={primaryButtonClass}
          >
            Continue
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--paper)] px-4 py-12">
      <Masthead />

      {mode === 'signup' && (
        <form onSubmit={submitSignup} className="w-full max-w-sm border border-[var(--hairline)] bg-[var(--surface)] p-8">
          <p className="mb-6 text-sm text-[var(--ink-muted)]">Create your account to start today's dispatch.</p>
          <label className="mb-3 block text-sm">
            <span className={labelClass}>Username</span>
            <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} className={inputClass} />
          </label>
          <label className="mb-5 block text-sm">
            <span className={labelClass}>Password (8+ characters)</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </label>
          {error && <p className="mb-4 text-sm text-[var(--accent)]">{error}</p>}
          <button type="submit" disabled={loading} className={primaryButtonClass}>
            {loading ? 'Creating…' : 'Create account'}
          </button>
        </form>
      )}

      {mode === 'login' && (
        <form onSubmit={submitLogin} className="w-full max-w-sm border border-[var(--hairline)] bg-[var(--surface)] p-8">
          <p className="mb-6 text-sm text-[var(--ink-muted)]">Sign in to see today's dispatch.</p>
          {info && <p className="mb-4 text-sm text-[var(--positive)]">{info}</p>}
          <label className="mb-3 block text-sm">
            <span className={labelClass}>Username</span>
            <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} className={inputClass} />
          </label>
          <label className="mb-5 block text-sm">
            <span className={labelClass}>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </label>
          {error && <p className="mb-4 text-sm text-[var(--accent)]">{error}</p>}
          <button type="submit" disabled={loading} className={primaryButtonClass}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
          <button
            type="button"
            onClick={() => {
              setError(null)
              setInfo(null)
              setMode('recover')
            }}
            className="mt-4 w-full text-center text-xs text-[var(--ink-faint)] hover:text-[var(--accent)]"
          >
            Forgot password?
          </button>
        </form>
      )}

      {mode === 'recover' && (
        <form onSubmit={submitRecover} className="w-full max-w-sm border border-[var(--hairline)] bg-[var(--surface)] p-8">
          <p className="mb-6 text-sm text-[var(--ink-muted)]">
            Enter your 12-word recovery phrase to set a new password.
          </p>
          <label className="mb-3 block text-sm">
            <span className={labelClass}>Recovery phrase</span>
            <textarea
              autoFocus
              value={recoverPhraseInput}
              onChange={(e) => setRecoverPhraseInput(e.target.value)}
              rows={2}
              className={inputClass}
            />
          </label>
          <label className="mb-5 block text-sm">
            <span className={labelClass}>New password (8+ characters)</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClass}
            />
          </label>
          {error && <p className="mb-4 text-sm text-[var(--accent)]">{error}</p>}
          <button type="submit" disabled={loading} className={primaryButtonClass}>
            {loading ? 'Resetting…' : 'Reset password'}
          </button>
          <button
            type="button"
            onClick={() => {
              setError(null)
              setMode('login')
            }}
            className="mt-4 w-full text-center text-xs text-[var(--ink-faint)] hover:text-[var(--accent)]"
          >
            Back to sign in
          </button>
        </form>
      )}
    </div>
  )
}
