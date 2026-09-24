import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { MatchStatus } from '../types'
import Spinner from './Spinner'

export default function CvPanel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [status, setStatus] = useState<MatchStatus | null>(null)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.matchStatus().then(setStatus).catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function save() {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const res = await api.putCv(text)
      setMessage(`Saved (${res.chars.toLocaleString()} characters). Re-screening ${res.rescoring.toLocaleString()} leads in the background.`)
      setText('')
      setStatus(await api.matchStatus())
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the CV.')
    } finally {
      setSaving(false)
    }
  }

  async function upload(file: File) {
    setUploading(true)
    setError(null)
    setMessage(null)
    try {
      const res = await api.uploadCv(file)
      setMessage(
        `Read ${res.chars.toLocaleString()} characters from ${res.filename} (${res.parsed_from}). ` +
          `Re-screening ${res.rescoring.toLocaleString()} leads in the background.`,
      )
      setStatus(await api.matchStatus())
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not read that file.')
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  async function remove() {
    await api.deleteCv().catch(() => {})
    setStatus(await api.matchStatus().catch(() => null))
    setMessage('CV removed and all screen scores cleared.')
    onSaved()
  }

  const screening = status?.screening

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose} role="presentation">
      <div
        className="h-full w-full max-w-xl overflow-y-auto border-l border-[var(--hairline)] bg-[var(--surface)] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <h2 className="font-serif-mast text-2xl italic text-[var(--ink)]">Your CV</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="font-mono-kicker text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent)]"
          >
            Close ✕
          </button>
        </div>

        <p className="text-sm leading-relaxed text-[var(--ink-muted)]">
          Every lead gets screened against this by a local model, so the feed can be sorted by fit.
          It's stored in <code className="font-mono-kicker text-[10px] normal-case tracking-normal">backend/data/cv.txt</code>{' '}
          on this Mac only — gitignored, never uploaded. Nothing is sent to any external service:
          both the screen and the council run on local models.
        </p>

        <dl className="mt-4 border-y border-[var(--hairline)] py-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-[var(--ink-muted)]">Stored CV</dt>
            <dd className="text-[var(--ink)]">
              {status?.cv.present ? `${status.cv.chars.toLocaleString()} characters` : 'none yet'}
            </dd>
          </div>
          <div className="mt-1 flex justify-between">
            <dt className="text-[var(--ink-muted)]">Sabha (council service)</dt>
            <dd className={status?.sabha.available ? 'text-[var(--positive)]' : 'text-[var(--accent)]'}>
              {status?.sabha.available ? `up · ${status.sabha.council_size} assessors` : 'not reachable'}
            </dd>
          </div>
          {screening && (
            <div className="mt-1 flex justify-between">
              <dt className="text-[var(--ink-muted)]">Screening queue</dt>
              <dd className="flex items-center gap-2 text-[var(--ink)]">
                {screening.running && <Spinner />}
                {screening.remaining.toLocaleString()} left
                {screening.paused_for_council && ' · paused for a council run'}
              </dd>
            </div>
          )}
        </dl>

        <div className="mt-5">
          <span className="font-mono-kicker mb-2 block text-[10px] text-[var(--ink-faint)]">
            Upload a file
          </span>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) upload(file)
            }}
            className="hidden"
          />
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
              className="flex items-center gap-2 border border-[var(--hairline)] px-3 py-1.5 text-sm text-[var(--ink)] hover:border-[var(--hairline-strong)] disabled:opacity-50"
            >
              {uploading && <Spinner />}
              {uploading ? 'Reading…' : 'Browse files…'}
            </button>
            <span className="text-xs text-[var(--ink-faint)]">PDF, Word (.docx) or plain text</span>
          </div>
          <p className="mt-2 text-xs text-[var(--ink-faint)]">
            The file is read in memory and discarded — only the extracted text is stored. A
            scanned or image-only PDF has no text to extract, and will say so rather than
            saving an empty CV.
          </p>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <span className="h-px flex-1 bg-[var(--hairline)]" />
          <span className="font-mono-kicker text-[10px] text-[var(--ink-faint)]">or paste it</span>
          <span className="h-px flex-1 bg-[var(--hairline)]" />
        </div>

        <label className="mt-4 block text-sm">
          <span className="font-mono-kicker mb-1 block text-[10px] text-[var(--ink-faint)]">
            {status?.cv.present ? 'Replace CV — paste the full text' : 'Paste your CV text'}
          </span>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={14}
            placeholder="Paste the plain text of your CV here…"
            className="w-full border border-[var(--hairline)] bg-transparent px-3 py-2 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)]"
          />
        </label>

        {error && <p className="mt-2 text-sm text-[var(--accent)]">{error}</p>}
        {message && <p className="mt-2 text-sm text-[var(--positive)]">{message}</p>}

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving || text.trim().length < 200}
            className="flex items-center gap-2 bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-[var(--accent-ink)] hover:opacity-90 disabled:opacity-50"
          >
            {saving && <Spinner />}
            Save CV
          </button>
          {status?.cv.present && (
            <button
              onClick={remove}
              className="font-mono-kicker text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent)]"
            >
              Remove stored CV
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-[var(--ink-faint)]">
          Changing the CV clears every existing screen score — a score against an old CV is worse
          than no score.
        </p>
      </div>
    </div>
  )
}
