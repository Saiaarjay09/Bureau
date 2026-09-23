import type { LeadType } from '../types'

export default function LeadTypeToggle({
  value,
  onChange,
}: {
  value: LeadType
  onChange: (value: LeadType) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-300 bg-neutral-100 p-1 dark:border-neutral-700 dark:bg-neutral-800">
      {(['job', 'business'] as LeadType[]).map((type) => (
        <button
          key={type}
          onClick={() => onChange(type)}
          className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
            value === type
              ? 'bg-white text-neutral-900 shadow-sm dark:bg-neutral-950 dark:text-neutral-100'
              : 'text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300'
          }`}
        >
          {type === 'job' ? 'Jobs' : 'Business Opportunities'}
        </button>
      ))}
    </div>
  )
}
