import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { LeadType, Regions } from '../types'

export interface RegionValue {
  continent: string
  country: string
  city: string
}

export const GLOBAL: RegionValue = { continent: '', country: '', city: '' }

const selectClass =
  'border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)] disabled:opacity-40'

export default function RegionSelector({
  leadType,
  value,
  onChange,
}: {
  leadType: LeadType
  value: RegionValue
  onChange: (value: RegionValue) => void
}) {
  const [regions, setRegions] = useState<Regions | null>(null)
  const [cityQuery, setCityQuery] = useState(value.city)
  const [citySuggestions, setCitySuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.regions().then(setRegions).catch(() => {})
  }, [])

  useEffect(() => {
    setCityQuery(value.city)
  }, [value.city])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      api
        .cities({ lead_type: leadType, continent: value.continent, country: value.country, q: cityQuery })
        .then((res) => setCitySuggestions(res.cities))
        .catch(() => setCitySuggestions([]))
    }, 200)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leadType, value.continent, value.country, cityQuery])

  const countries = value.continent ? regions?.continents[value.continent] ?? [] : []

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={value.continent}
        onChange={(e) => onChange({ continent: e.target.value, country: '', city: '' })}
        className={selectClass}
      >
        <option value="">Global</option>
        {regions &&
          Object.keys(regions.continents).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
      </select>

      <select
        value={value.country}
        disabled={!value.continent}
        onChange={(e) => onChange({ ...value, country: e.target.value, city: '' })}
        className={selectClass}
      >
        <option value="">All countries</option>
        {countries.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <div className="relative">
        <input
          value={cityQuery}
          placeholder="City…"
          onChange={(e) => {
            setCityQuery(e.target.value)
            setShowSuggestions(true)
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          className="w-40 border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink)] outline-none focus:border-[var(--accent)]"
        />
        {value.city && (
          <button
            aria-label="Clear city"
            onClick={() => {
              setCityQuery('')
              onChange({ ...value, city: '' })
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--ink-faint)] hover:text-[var(--ink)]"
          >
            ×
          </button>
        )}
        {showSuggestions && citySuggestions.length > 0 && (
          <ul className="absolute z-10 mt-1 max-h-56 w-48 overflow-auto border border-[var(--hairline)] bg-[var(--surface)] py-1 text-sm shadow-lg">
            {citySuggestions.map((city) => (
              <li key={city}>
                <button
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    setCityQuery(city)
                    setShowSuggestions(false)
                    onChange({ ...value, city })
                  }}
                  className="block w-full px-3 py-1.5 text-left hover:bg-[var(--accent-soft)]"
                >
                  {city}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(value.continent || value.country || value.city) && (
        <button
          onClick={() => {
            setCityQuery('')
            onChange(GLOBAL)
          }}
          className="font-mono-kicker text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent)]"
        >
          Reset to Global
        </button>
      )}
    </div>
  )
}
