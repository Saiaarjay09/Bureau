import type { LeadType } from '../types'

export default function LeadTypeToggle({
  value,
  onChange,
}: {
  value: LeadType
  onChange: (value: LeadType) => void
}) {
  return (
    <div className="flex gap-5 border-b border-[var(--hairline)]">
      {(['job', 'business'] as LeadType[]).map((type) => (
        <button
          key={type}
          onClick={() => onChange(type)}
          className={`font-mono-kicker -mb-px border-b-2 px-1 pb-2 pt-1 text-[11px] transition ${
            value === type
              ? 'border-[var(--accent)] text-[var(--ink)]'
              : 'border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-muted)]'
          }`}
        >
          {type === 'job' ? 'Jobs' : 'Business Opportunities'}
        </button>
      ))}
    </div>
  )
}
